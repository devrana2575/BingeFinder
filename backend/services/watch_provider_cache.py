"""
backend/services/watch_provider_cache.py
==========================================
Cached wrapper around the Where-To-Watch provider lookup.

Provides a simple in-memory TTL cache so repeated lookups of the same
series don't hammer the TMDb API. This works independently of any UI
framework.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

_cache: Dict[Any, Any] = {}
_timestamps: Dict[Any, float] = {}
_lock = threading.Lock()

CACHE_TTL_SECONDS = 600  # 10 minutes


def _cached_watch_providers(
    series_id: int,
    imdb_id: Optional[str],
    series_name: str,
    premiered: Optional[str],
    region: Optional[str] = None,
) -> dict:
    """Cached wrapper around get_watch_providers_for_series."""
    from backend.services.tmdb_reachability import tmdb_available
    if not tmdb_available():
        return {}

    from regions import normalize_region
    effective_region = normalize_region(region)

    key = (series_id, imdb_id, series_name, premiered, effective_region)
    now = time.time()

    with _lock:
        cached = _cache.get(key)
        ts = _timestamps.get(key)
        if cached is not None and ts is not None and (now - ts) < CACHE_TTL_SECONDS:
            return cached

    try:
        from api.watch_providers import get_watch_providers_for_series
        result = get_watch_providers_for_series(
            series_id, imdb_id=imdb_id, series_name=series_name, premiered=premiered,
            region=effective_region,
        ) or {}
    except Exception:
        result = {}

    with _lock:
        _cache[key] = result
        _timestamps[key] = now

    return result
