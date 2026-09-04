"""
backend/middleware/cors.py
==========================
CORS configuration for the React dev server.
"""

import os


def get_allowed_origins() -> list[str]:
    """Return allowed CORS origins from env or defaults."""
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]
