"""
backend/middleware/rate_limit.py
================================
Lightweight in-memory rate limiter for the auth endpoints.

Protects /login and /signup against brute-force and credential-stuffing by
throttling repeated attempts per client IP and per target email. The limiter
is process-local (in-memory) — intentionally simple and dependency-free. For a
multi-instance / distributed deployment, swap this for a shared store (e.g.
Redis) behind the same interface.
"""

import threading
import time
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary identifier string."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # key -> list of event timestamps (oldest first). Bounded: pruned on
        # every check, and keys only exist while an attempt is recorded.
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record an attempt and raise 429 if the sliding-window limit is exceeded."""
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            self._prune(events, now)
            if len(events) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please try again later.",
                )
            events.append(now)

    def _prune(self, events: list[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.pop(0)


_LOGIN_LIMITER = InMemoryRateLimiter(max_attempts=10, window_seconds=900)
_SIGNUP_LIMITER = InMemoryRateLimiter(max_attempts=10, window_seconds=3600)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _auth_rate_limit(
    request: Request,
    limiter: InMemoryRateLimiter,
    email: Optional[str],
) -> None:
    limiter.check(f"{_client_ip(request)}:{email or ''}")


def login_rate_limit(request: Request, email: Optional[str] = None) -> None:
    """FastAPI dependency: throttle /api/auth/login per IP + email."""
    _auth_rate_limit(request, _LOGIN_LIMITER, email)


def signup_rate_limit(request: Request, email: Optional[str] = None) -> None:
    """FastAPI dependency: throttle /api/auth/signup per IP + email."""
    _auth_rate_limit(request, _SIGNUP_LIMITER, email)
