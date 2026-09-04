"""
backend/dependencies.py
========================
Shared FastAPI dependencies: auth, database, etc.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException

from backend.services.auth_service import decode_token


def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract user_id from the Authorization header.
    Returns None for guest users (no token or invalid token).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    user_id = decode_token(token)
    if user_id is None:
        return None
    return user_id


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Like get_current_user but raises 401 if not authenticated."""
    user_id = get_current_user(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
