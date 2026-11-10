"""
backend/main.py
===============
FastAPI application entry point.

Wires up middleware, routers, lifecycle warm-up, health/readiness probes and
(optionally) serves the production frontend build as a single-origin app.
Reuses existing Python modules directly — no duplicated business logic.
"""

import os
import sys
import threading
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import APP_ENV, get_allowed_hosts, get_mongodb_uri, is_production
from backend.middleware.cors import get_allowed_origins
from backend.middleware.observability import RequestContextMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.routes import (
    auth,
    discovery,
    events,
    recommendations,
    regions,
    series,
    users,
    watch_providers,
)
from utils.logger import get_logger

logger = get_logger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm caches/models in the background. Shutdown: log and exit."""
    # Fail fast instead of surfacing a 500 on the first login attempt.
    if is_production():
        from config import get_jwt_secret

        get_jwt_secret()

    logger.info("BingeFinder API starting up (env=%s)...", APP_ENV)

    # Pre-load the recommendation model in the background so the API starts
    # accepting requests immediately; deserializing the artifact can take
    # tens of seconds and used to block the whole server startup.
    def _warm_model() -> None:
        try:
            from recommender.recommend import load_model
            load_model()
            logger.info("Recommendation model loaded.")
        except Exception as exc:
            logger.warning("Recommendation model not available: %s", exc)

    threading.Thread(target=_warm_model, name="model-warmup", daemon=True).start()

    # Warm the shared catalog snapshot too: the first discovery/search request
    # would otherwise pay the one-off full-collection read (a couple of
    # seconds at ~190k documents).
    def _warm_catalog() -> None:
        try:
            from backend.services import series_service
            series_service.get_catalog_snapshot()
            logger.info("Catalog snapshot warmed.")
        except Exception as exc:
            logger.warning("Catalog snapshot warm-up failed: %s", exc)

    threading.Thread(target=_warm_catalog, name="catalog-warmup", daemon=True).start()

    # Warm the TMDb reachability breaker so TMDb-dependent routes never
    # stall the first request on a connect timeout when the API is down.
    try:
        from backend.services.tmdb_reachability import tmdb_available
        tmdb_available()
    except Exception:
        pass

    yield

    logger.info("BingeFinder API shutting down.")


_docs_enabled = not is_production()

app = FastAPI(
    title="BingeFinder API",
    description="Web-series discovery and recommendation API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Compression first (innermost middleware).
app.add_middleware(GZipMiddleware, minimum_size=500)

# Host-header validation in production (trusts every host in development).
_allowed_hosts = get_allowed_hosts()
if _allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

# CORS. In production the SPA is served from the same origin, so the default
# allow-list is empty; set CORS_ORIGINS only for a split frontend/API deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

# Security headers (Helmet-style) and asset cache policy.
app.add_middleware(SecurityHeadersMiddleware)

# Request correlation + access logs (outermost so every response gets an ID).
app.add_middleware(RequestContextMiddleware)

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
    """Catch-all so unexpected errors never leak internals to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


@app.get("/api/health")
def health_check():
    """Liveness probe: process is up and serving requests."""
    return {"status": "ok", "service": "bingefinder-api", "environment": APP_ENV}


@app.get("/api/ready")
def readiness_check():
    """Readiness probe: process can reach its dependencies (MongoDB)."""
    from pymongo import MongoClient

    client = None
    try:
        client = MongoClient(get_mongodb_uri(), serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        # Any dependency/configuration failure means this instance cannot
        # serve catalog traffic; report 503 instead of a 500 crash.
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )
    finally:
        if client is not None:
            client.close()


# ---------------------------------------------------------------------------
# Production static frontend (single-origin deployment)
# ---------------------------------------------------------------------------
# During development Vite serves the SPA on :5174 and proxies /api here, so
# this block is inert unless a build exists (or STATIC_DIR points at one).
# In production the frontend is built into frontend/dist and served here.
_STATIC_DIR = Path(
    os.getenv("STATIC_DIR", str(Path(__file__).resolve().parent.parent / "frontend" / "dist"))
).resolve()


def _mount_frontend() -> None:
    index_file = _STATIC_DIR / "index.html"
    if not index_file.is_file():
        logger.info("No frontend build found at %s; running API-only.", _STATIC_DIR)
        return

    assets_dir = _STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve built static files, falling back to index.html for SPA routes."""
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        candidate = (_STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(_STATIC_DIR)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")

        if candidate.is_file():
            headers = {"Cache-Control": "public, max-age=3600"}
            return FileResponse(candidate, headers=headers)

        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    logger.info("Serving frontend build from %s", _STATIC_DIR)


_mount_frontend()
