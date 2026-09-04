"""
api/watch_providers.py
======================
Streaming-availability look-ups built on top of the existing TMDb client.

The main entry point is `get_watch_providers_for_series()` which:
    1. Accepts a series ID, optional IMDB ID, and optional series metadata.
    2. If an IMDB ID is available, uses TMDb's /find endpoint to resolve a
       TMDb series ID (with title validation).
    3. Falls back to a title+year search via TMDb's /search/tv when IMDB
       resolution is not possible.
    4. Fetches watch-provider data from TMDb for the configured region.
    5. Returns a structured dict ready for the caller to consume.

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

# Default ISO 3166-1 region for availability lookups (free/ads are verified
# against this region's provider set).
DEFAULT_WATCH_REGION = "IN"

# Maximum number of free/ad-supported providers surfaced to the user so the
# free tier doesn't drown the UI (verified free/ads only).
MAX_FREE_PROVIDERS = 3

# Per-category display caps for paid options.
MAX_PAID_PROVIDERS = {"flatrate": 3, "rent": 2, "buy": 2}


def _slugify(name: str) -> str:
    """
    Convert a series name into a URL-friendly slug suitable for JustWatch
    deep-links.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = ascii_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison."""
    t = (title or "").strip().lower()
    t = re.sub(r"[^a-z0-9]", "", t)
    return t


def _extract_year(premiered: Optional[str]) -> Optional[int]:
    """Extract a 4-digit year from a premiered date string."""
    if isinstance(premiered, str) and len(premiered) >= 4 and premiered[:4].isdigit():
        return int(premiered[:4])
    return None


def _find_tmdb_id_from_imdb(
    client: TMDbClient, imdb_id: str, series_name: Optional[str] = None
) -> Optional[int]:
    """
    Resolve a TMDb series ID from an IMDB ID via TMDb's /find endpoint.

    If a series_name is provided, validates the match by comparing the
    result's title against the expected name (normalized, case-insensitive).

    Returns:
        The TMDb ID if found and validated, or None on failure.
    """
    try:
        payload = client._get(
            f"/find/{imdb_id}",
            params={"external_source": "imdb_id"},
        )
        tv_results = payload.get("tv_results", [])
        if tv_results and isinstance(tv_results, list):
            for result in tv_results:
                tmdb_id = result.get("id")
                if tmdb_id is None:
                    continue
                # If no series name to validate against, take the first match
                if not series_name:
                    logger.debug("Resolved IMDB %s -> TMDb %s", imdb_id, tmdb_id)
                    return int(tmdb_id)
                # Validate title match
                result_name = result.get("name") or result.get("original_name") or ""
                if _normalize_title(result_name) == _normalize_title(series_name):
                    logger.debug("Resolved IMDB %s -> TMDb %s (validated: %s)", imdb_id, tmdb_id, result_name)
                    return int(tmdb_id)
                # Partial match — name contains the search or vice versa
                if (_normalize_title(series_name) in _normalize_title(result_name)
                        or _normalize_title(result_name) in _normalize_title(series_name)):
                    logger.debug("Resolved IMDB %s -> TMDb %s (partial: %s)", imdb_id, tmdb_id, result_name)
                    return int(tmdb_id)
            # If nothing validated, fall back to first result
            tmdb_id = tv_results[0].get("id")
            if tmdb_id is not None:
                logger.debug("Resolved IMDB %s -> TMDb %s (unvalidated first result)", imdb_id, tmdb_id)
                return int(tmdb_id)
        logger.debug("No TMDb match found for IMDB ID %s", imdb_id)
        return None
    except (TMDbAPIError, (TypeError, ValueError)) as exc:
        logger.warning("Failed to resolve TMDb ID from IMDB %s: %s", imdb_id, exc)
        return None


def _find_tmdb_id_from_title(
    client: TMDbClient, series_name: str, premiered: Optional[str] = None
) -> Optional[int]:
    """
    Resolve a TMDb series ID by searching TMDb's /search/tv endpoint
    with the series name and optional premiere year.

    Matching strategy:
        1. Normalized exact title match (prioritized).
        2. Normalized contains/partial match.
        3. First result as fallback.

    Args:
        client: An initialised TMDbClient.
        series_name: The series name to search for.
        premiered: Optional premiered date string (e.g. "2017-04-15").

    Returns:
        The best-matching TMDb series ID, or None.
    """
    try:
        search_year = _extract_year(premiered)
        params: Dict[str, Any] = {"query": series_name}
        if search_year:
            params["first_air_date_year"] = search_year

        payload = client._get("/search/tv", params=params)
        results = payload.get("results", [])
        if not results or not isinstance(results, list):
            logger.debug("No TMDb search results for title '%s'", series_name)
            return None

        target = _normalize_title(series_name)
        best_match = None
        best_year_match = None

        for result in results:
            result_name = result.get("name") or result.get("original_name") or ""
            result_normalized = _normalize_title(result_name)
            result_id = result.get("id")
            if result_id is None:
                continue

            # Exact normalized match
            if result_normalized == target:
                # Prefer year match if we have a year
                if search_year:
                    air_date = result.get("first_air_date") or ""
                    if air_date[:4].isdigit() and abs(int(air_date[:4]) - search_year) <= 1:
                        logger.debug(
                            "Title+year match: '%s' -> TMDb %s",
                            series_name, result_id,
                        )
                        return int(result_id)
                    if best_match is None:
                        best_match = result_id
                else:
                    logger.debug("Exact title match: '%s' -> TMDb %s", series_name, result_id)
                    return int(result_id)

            # Partial match
            if best_year_match is None and (
                target in result_normalized or result_normalized in target
            ):
                best_year_match = result_id

        if best_match is not None:
            logger.debug("Best exact title match (no year): '%s' -> TMDb %s", series_name, best_match)
            return int(best_match)

        if best_year_match is not None:
            logger.debug("Best partial match: '%s' -> TMDb %s", series_name, best_year_match)
            return int(best_year_match)

        # Last resort: first result
        first_id = results[0].get("id")
        if first_id is not None:
            logger.debug("Fallback first result for '%s' -> TMDb %s", series_name, first_id)
            return int(first_id)

        return None

    except (TMDbAPIError, (TypeError, ValueError)) as exc:
        logger.warning("Failed to search TMDb for '%s': %s", series_name, exc)
        return None


def get_watch_providers_for_series(
    series_id: int,
    imdb_id: Optional[str] = None,
    region: Optional[str] = None,
    series_name: Optional[str] = None,
    premiered: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch streaming-provider availability for a series.

    Resolution order:
        1. If an ``imdb_id`` is supplied, look up the TMDb ID via TMDb's
           /find endpoint (with title validation if series_name is given).
        2. If IMDB resolution fails, search TMDb by title+year.
        3. Use the resolved TMDb ID to fetch watch providers.

    Args:
        series_id: series identifier.
        imdb_id: IMDB identifier string.  May be None.
        region: ISO 3166-1 country code.  Defaults to "IN".
        series_name: Optional series name for title-based fallback.
        premiered: Optional premiered date for year matching.

    Returns:
        A dict of the form::

            {
                "region": "IN",
                "providers": {
                    "flatrate": [...],
                    "ads": [...],
                    "free": [...],
                    "rent": [...],
                    "buy": [...],
                },
                "link": "https://www.themoviedb.org/tv/..."
            }

        Returns an empty dict when no data can be obtained.
    """
    # ---- Build client ----
    try:
        client = TMDbClient()
    except (ConfigError, Exception) as exc:
        logger.warning(
            "Cannot initialise TMDb client for watch-provider lookup: %s", exc
        )
        return {}

    # ---- Resolve TMDb ID ----
    tmdb_id = None

    if imdb_id:
        tmdb_id = _find_tmdb_id_from_imdb(client, imdb_id, series_name)

    if tmdb_id is None and series_name:
        tmdb_id = _find_tmdb_id_from_title(client, series_name, premiered)

    if tmdb_id is None:
        logger.debug(
            "Could not resolve TMDb ID for series %s (IMDB: %s, name: %s)",
            series_id, imdb_id, series_name,
        )
        return {}

    # ---- Cache check ----
    # The TTL-backed cache lives in backend.services.watch_provider_cache
    # (CACHE_TTL_SECONDS = 600) and is the single source of caching for
    # availability lookups. This function itself is deliberately uncached so
    # there is only one, TTL-bounded cache instead of a second unbounded one.

    # ---- Fetch providers ----
    try:
        providers_raw: Dict[str, list] = client.fetch_tv_watch_providers(
            tmdb_id, region=region
        )
    except (TMDbAPIError, Exception) as exc:
        logger.warning(
            "Failed to fetch watch providers for TMDb %s (series %s): %s",
            tmdb_id, series_id, exc,
        )
        return {}

    # ---- Build link ----
    link = ""
    try:
        details = client.fetch_tv_details(tmdb_id)
        link = details.get("homepage") or f"https://www.themoviedb.org/tv/{tmdb_id}"
    except (TMDbAPIError, Exception):
        link = f"https://www.themoviedb.org/tv/{tmdb_id}"

    # Normalise to the full shape expected by callers.
    providers = {
        "flatrate": providers_raw.get("flatrate", []),
        "ads": providers_raw.get("ads", []),
        "free": providers_raw.get("free", []),
        "rent": providers_raw.get("rent", []),
        "buy": providers_raw.get("buy", []),
    }

    effective_region = region or DEFAULT_WATCH_REGION

    result: Dict[str, Any] = {
        "region": effective_region,
        "providers": providers,
        # TMDB availability page for this series in the requested region.
        "link": link,
        # Canonical TMDB "where to watch" page. Both derived from the resolved
        # TMDb id (real URLs, never hand-assembled or fabricated data).
        "watch_now_url": f"https://www.themoviedb.org/tv/{tmdb_id}/watch?locale={effective_region}",
        "tmdb_id": tmdb_id,
    }
    return result


def get_provider_page_url(series_name: str, region: Optional[str] = None) -> Optional[str]:
    """
    Build a JustWatch search URL as a fallback for manual browsing.

    Uses the target region path (default India) so the availability page
    reflects the region we resolve providers against.
    """
    name = (series_name or "").strip()
    if not name:
        return None
    slug = _slugify(name)
    region_code = (region or DEFAULT_WATCH_REGION).lower()
    return f"https://www.justwatch.com/{region_code}/tv-show/{slug}"
