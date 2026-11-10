"""
backend/middleware/security_headers.py
======================================
Production-grade HTTP security headers applied to every response.

Development stays permissive enough for Vite HMR. Production adds HTTPS
transport security, a Content-Security-Policy for the built SPA, and
immutable caching for fingerprinted assets. No inline scripts are emitted by
the Vite production build; inline styles are still required by React's
`style={{...}}` props, so `style-src` allows 'unsafe-inline'.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import is_production

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}

# The built SPA loads its own JS/CSS, Google Fonts, and TMDb poster art.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://image.tmdb.org; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers and production cache policy to responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        for header, value in _BASE_HEADERS.items():
            response.headers.setdefault(header, value)

        if is_production():
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            response.headers.setdefault("Content-Security-Policy", _CSP)

        # Vite fingerprints everything under /assets/, so it is safe to cache
        # those files forever. HTML must always be revalidated.
        if request.url.path.startswith("/assets/"):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")

        return response
