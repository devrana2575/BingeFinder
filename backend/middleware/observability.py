"""
backend/middleware/observability.py
===================================
Request correlation + structured access logging.

Every response carries an ``X-Request-ID`` header (reusing an upstream proxy's
value when present) and an ``X-Response-Time`` header. API requests are logged
with method, path, status, and latency, which is enough to debug production
issues without shipping a full APM stack.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logger import get_logger

logger = get_logger("backend.request")

# Health probes are frequent and noisy; do not log them at INFO level.
_QUIET_PATHS = ("/api/health", "/api/ready")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and emit one access-log line per API request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

        path = request.url.path
        if path.startswith("/api") and path not in _QUIET_PATHS:
            logger.info(
                "%s %s %s %.1fms request_id=%s",
                request.method,
                path,
                response.status_code,
                elapsed_ms,
                request_id,
            )

        return response
