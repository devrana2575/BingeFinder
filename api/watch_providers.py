"""
api/watch_providers.py
======================
Streaming-availability look-ups built on top of the existing TMDb client.

The main entry point is `get_watch_providers_for_series()` which:
    1. Accepts a TVmaze ID and optional IMDB ID.
    2. If an IMDB ID is available, uses TMDb's /find endpoint to resolve a
       TMDb series ID.
    3. Fetches watch-provider data from TMDb for the configured region.
    4. Returns a structured dict ready for the caller to consume.

A helper `get_provider_page_url()` produces a JustWatch deep-link as a
fallback when no structured data is available.
"""

import re
import unicodedata
from typing import Any, Dict, Optional

from api.tmdb import TMDbAPIError, TMDbClient
from config import ConfigError, get_tmdb_api_key
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache — keyed by TMDb series ID so the same series is only
# fetched once per process lifetime.  Trade-off: tiny memory footprint vs.
# guaranteeing we never hit TMDb twice for the same data.
# ---------------------------------------------------------------------------
_provider_cache: Dict[int, Dict[str, Any]] = {}


def _slugify(name: str) -> str:
    """
    Convert a series name into a URL-friendly slug suitable for JustWatch
    deep-links.

    Steps:
        1. Normalize unicode to ASCII.
        2. Lowercase.
        3. Replace non-alphanumeric characters (except hyphens) with hyphens.
        4. Collapse consecutive hyphens and strip leading/trailing hyphens.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = ascii_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _find_tmdb_id_from_imdb(
    client: TMDbClient, imdb_id: str
) -> Optional[int]:
    """
    Resolve a TMDb series ID from an IMDB ID via TMDb's /find endpoint.

    Returns:
        The TMDb ID if found, or None on failure.
    """
    try:
        payload = client._get(  # noqa: SLF001 — intentional internal use
            f"/find/{imdb_id}",
            params={"external_source": "imdb_id"},
        )
        tv_results = payload.get("tv_results", [])
        if tv_results and isinstance(tv_results, list):
            tmdb_id = tv_results[0].get("id")
            if tmdb_id is not None:
                logger.debug("Resolved IMDB %s -> TMDb %s", imdb_id, tmdb_id)
                return int(tmdb_id)
        logger.debug("No TMDb match found for IMDB ID %s", imdb_id)
        return None
    except (TMDbAPIError, (TypeError, ValueError)) as exc:
        logger.warning("Failed to resolve TMDb ID from IMDB %s: %s", imdb_id, exc)
        return None


def get_watch_providers_for_series(
    tvmaze_id: int,
    imdb_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch streaming-provider availability for a series.

    Resolution order:
        1. If an ``imdb_id`` is supplied, look up the TMDb ID via TMDb's
           /find endpoint.
        2. Use the resolved TMDb ID to fetch watch providers.

    Args:
        tvmaze_id: TVmaze series identifier (used only as a cache key /
            logging context when the TMDb lookup fails).
        imdb_id: IMDB identifier string (e.g. "tt1234567").  May be None
            if the caller doesn't have one.
        region: ISO 3166-1 country code to scope providers to.  Defaults
            to "IN" (handled by the underlying TMDbClient).

    Returns:
        A dict of the form::

            {
                "region": "IN",
                "providers": {
                    "flatrate": [...],
                    "rent": [...],
                    "buy": [...],
                    "free": [...],
                },
                "link": "https://www.themoviedb.org/tv/..."
            }

        Returns an empty dict when no data can be obtained (missing API
        key, lookup failure, or no providers in the region).
    """
    if not imdb_id:
        logger.debug(
            "No IMDB ID for TVmaze %s — cannot resolve TMDb ID.", tvmaze_id
        )
        return {}

    # ---- Build client (may raise ConfigError) ----
    try:
        client = TMDbClient()
    except (ConfigError, Exception) as exc:
        logger.warning(
            "Cannot initialise TMDb client for watch-provider lookup: %s", exc
        )
        return {}

    # ---- Resolve TMDb ID ----
    tmdb_id = _find_tmdb_id_from_imdb(client, imdb_id)
    if tmdb_id is None:
        return {}

    # ---- Cache check ----
    if tmdb_id in _provider_cache:
        logger.debug("Returning cached watch providers for TMDb %s.", tmdb_id)
        return _provider_cache[tmdb_id]

    # ---- Fetch providers ----
    try:
        providers_raw: Dict[str, list] = client.fetch_tv_watch_providers(
            tmdb_id, region=region
        )
    except (TMDbAPIError, Exception) as exc:
        logger.warning(
            "Failed to fetch watch providers for TMDb %s (TVmaze %s): %s",
            tmdb_id,
            tvmaze_id,
            exc,
        )
        return {}

    # ---- Build link via series details (best-effort) ----
    link = ""
    try:
        details = client.fetch_tv_details(tmdb_id)
        link = details.get("homepage") or f"https://www.themoviedb.org/tv/{tmdb_id}"
    except (TMDbAPIError, Exception) as exc:
        logger.debug(
            "Could not fetch series details for TMDb %s, using generic link: %s",
            tmdb_id,
            exc,
        )
        link = f"https://www.themoviedb.org/tv/{tmdb_id}"

    # Normalise to the full shape expected by callers.
    providers = {
        "flatrate": providers_raw.get("flatrate", []),
        "rent": providers_raw.get("rent", []),
        "buy": providers_raw.get("buy", []),
        "free": providers_raw.get("free", []),
    }

    effective_region = region or "IN"

    result: Dict[str, Any] = {
        "region": effective_region,
        "providers": providers,
        "link": link,
    }

    _provider_cache[tmdb_id] = result
    return result


def get_provider_page_url(series_name: str) -> Optional[str]:
    """
    Build a JustWatch search URL as a fallback for manual browsing.

    Args:
        series_name: The human-readable series name to slugify.

    Returns:
        A fully-qualified JustWatch URL, or None if *series_name* is
        empty after stripping.
    """
    name = (series_name or "").strip()
    if not name:
        return None
    slug = _slugify(name)
    return f"https://www.justwatch.com/us/tv-show/{slug}"
