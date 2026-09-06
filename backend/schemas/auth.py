"""
backend/schemas/auth.py
========================
Pydantic schemas for auth endpoints.
"""

import re

from pydantic import BaseModel, Field, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 80

# Lightweight email format check (no external dependency).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    """Trim and lowercase an email address. Lenient: never rejects."""
    return value.strip().lower()


class UserCreate(BaseModel):
    # Signup enforces password strength and email format.
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    email: str
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = _normalize_email(value)
        if not _EMAIL_RE.match(value):
            raise ValueError("A valid email address is required.")
        return value

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty.")
        return value


class UserLogin(BaseModel):
    # Login must NEVER reject credentials at the schema layer. Unauthorized
    # attempts are signalled with 401 by the auth service, not 422 by
    # validation. The email is normalized (trim/lowercase) but not format-
    # checked, and there is no minimum password length here.
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email_field(cls, value: str) -> str:
        return _normalize_email(value)


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    preferences: dict = {}
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
