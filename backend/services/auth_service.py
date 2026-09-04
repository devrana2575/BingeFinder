"""
backend/services/auth_service.py
=================================
JWT token creation/validation. Wraps existing UserManager.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from config import get_jwt_secret

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Return user_id or None if token is invalid/expired."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
