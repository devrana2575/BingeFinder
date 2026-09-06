"""
backend/main.py
===============
FastAPI application entry point.

Wires up CORS, routers, and startup/shutdown lifecycle.
Reuses existing Python modules directly — no duplicated business logic.
"""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.middleware.cors import get_allowed_origins
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.routes import auth, series, recommendations, discovery, watch_providers, users, events, regions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm the recommendation model. Shutdown: nothing special."""
    from utils.logger import get_logger
    logger = get_logger("backend.main")
    logger.info("BingeFinder API starting up...")

    # Pre-load the recommendation model into memory
    try:
        from recommender.recommend import load_model
        load_model()
        logger.info("Recommendation model loaded.")
    except Exception as exc:
        logger.warning("Recommendation model not available: %s", exc)

    yield

    logger.info("BingeFinder API shutting down.")


app = FastAPI(
    title="BingeFinder API",
    description="TV/web-series discovery and recommendation API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers (Helmet-style) applied to every response.
app.add_middleware(SecurityHeadersMiddleware)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(series.router, prefix="/api/series", tags=["series"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(discovery.router, prefix="/api/discover", tags=["discovery"])
app.include_router(watch_providers.router, prefix="/api/series", tags=["watch-providers"])
app.include_router(watch_providers.provider_list_router, prefix="/api/watch-providers", tags=["watch-providers"])
app.include_router(users.router, prefix="/api/user", tags=["user"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(regions.router, prefix="/api", tags=["regions"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so unexpected errors never leak internals to the client.

    The error is logged server-side with the path for diagnosis; the client
    receives a clean, generic JSON message with 500.
    """
    from utils.logger import get_logger
    logger = get_logger("backend.main")
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "bingefinder-api"}
