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


class _AuthBase(BaseModel):
    email: str
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("A valid email address is required.")
        return value


class UserCreate(_AuthBase):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty.")
        return value


class UserLogin(_AuthBase):
    pass


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
