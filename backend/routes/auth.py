"""
backend/routes/auth.py
=======================
POST /signup, POST /login, GET /me
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.dependencies import require_auth
from backend.middleware.rate_limit import login_rate_limit, signup_rate_limit
from backend.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from backend.services.auth_service import create_access_token

router = APIRouter()


# Bind the rate limit to the validated request body's email address.
# FastAPI injects the real Request and the already-validated body into these
# dependency functions, so the throttling key uses client IP + normalized email.
def _require_login_rate_limit(request: Request, body: UserLogin) -> None:
    login_rate_limit(request, body.email)


def _require_signup_rate_limit(request: Request, body: UserCreate) -> None:
    signup_rate_limit(request, body.email)


def _get_user_manager():
    from database.mongo_client import MongoDBManager
    from database.users import UserManager
    from config import get_bcrypt_rounds
    manager = MongoDBManager()
    um = UserManager(manager, bcrypt_rounds=get_bcrypt_rounds())
    return manager, um


@router.post("/signup", response_model=TokenResponse)
def signup(body: UserCreate, _: None = Depends(_require_signup_rate_limit)):
    manager, um = _get_user_manager()
    try:
        result = um.create_user(body.name, body.email, body.password)
        if result == "email_exists":
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        # Authenticate after signup
        user = um.authenticate_user(body.email, body.password)
        if not user:
            raise HTTPException(status_code=500, detail="Signup succeeded but login failed.")
        token = create_access_token(user["user_id"])
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                user_id=user["user_id"],
                name=user["name"],
                email=user["email"],
                preferences=user.get("preferences") or {},
            ),
        )
    finally:
        manager.close()


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, _: None = Depends(_require_login_rate_limit)):
    manager, um = _get_user_manager()
    try:
        user = um.authenticate_user(body.email, body.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = create_access_token(user["user_id"])
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                user_id=user["user_id"],
                name=user["name"],
                email=user["email"],
                preferences=user.get("preferences") or {},
            ),
        )
    finally:
        manager.close()


@router.get("/me", response_model=UserResponse)
def get_me(user_id: str = Depends(require_auth)):
    from database.mongo_client import MongoDBManager
    from database.users import UserManager
    manager = MongoDBManager()
    try:
        um = UserManager(manager)
        user = um.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return UserResponse(
            user_id=user["user_id"],
            name=user["name"],
            email=user["email"],
            preferences=user.get("preferences") or {},
            created_at=user.get("created_at"),
        )
    finally:
        manager.close()
