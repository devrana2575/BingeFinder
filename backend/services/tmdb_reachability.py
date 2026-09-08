"""
backend/services/tmdb_reachability.py
=====================================
Shared fail-fast reachability probe for the TMDb API.

Routes that depend on live TMDb lookups (watch providers, Free Tonight,
personalized provider counts) can hang for tens of seconds when the API is
unreachable, because every lookup retries on a connect timeout. This module
provides a single probe + circuit breaker: after one failed probe, all
TMDb-dependent work short-circuits for a short blackout window, so the UI
never stalls behind an unreachable API. No credentials are sent.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_blackout_until = 0.0

BREAKER_TTL_SECONDS = 120
PROBE_TIMEOUT_SECONDS = 1.5
PROBE_URL = "https://api.themoviedb.org/3/movie/popular"


def _probe() -> bool:
    import requests
    try:
        # An unauthenticated 401/200 proves the API is reachable; a
        # timeout/network error means it is not.
        requests.get(
            PROBE_URL,
            params={"language": "en-US"},
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        return True
    except Exception:
        return False


def tmdb_available() -> bool:
    """
    Return True if the TMDb API is reachable, False if it is currently
    blacked out (or the probe fails). Results are cached in a short
    blackout window so a down API is probed at most once per window.
    """
    global _blackout_until
    now = time.time()
    with _lock:
        if now < _blackout_until:
            return False
    ok = _probe()
    with _lock:
        if ok:
            _blackout_until = 0.0
        else:
            _blackout_until = now + BREAKER_TTL_SECONDS
    return ok


def tmdb_unavailable() -> None:
    """Force a blackout so subsequent lookups fail fast."""
    global _blackout_until
    with _lock:
        _blackout_until = time.time() + BREAKER_TTL_SECONDS