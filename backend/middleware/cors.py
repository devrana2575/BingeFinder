"""
backend/middleware/cors.py
==========================
CORS configuration for the React frontend.

In development the Vite dev server runs on a different origin, so the common
localhost ports are allowed by default. In production the API and the built
SPA are served from the same origin, so no cross-origin access is needed; set
CORS_ORIGINS explicitly only when the frontend is hosted on a separate domain.
"""

import os


def get_allowed_origins() -> list[str]:
    """Return allowed CORS origins from the environment or safe defaults."""
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    from config import is_production

    if is_production():
        # Same-origin deployment: browsers never need a CORS grant.
        return []

    return [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]
