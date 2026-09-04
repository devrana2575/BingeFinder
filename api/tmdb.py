"""
api/tmdb.py
===========
Thin, well-tested client around the TMDb (The Movie Database) REST API,
scoped to TV/web-series endpoints.

Design notes:
    - A single `requests.Session` is reused (with a mounted retry adapter)
      for connection pooling and automatic retries on transient failures.
    - All public methods return a `List[Dict[str, Any]]` of raw TMDb
      "result" objects. Parsing/mapping into our DB schema is intentionally
      left to the caller to keep this module focused purely on API access.
    - No recommendation logic lives here (out of scope for Phase 1).
"""

from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    BACKOFF_FACTOR,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    TMDB_BASE_URL,
    get_tmdb_api_key,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# BingeFinder's primary market: when a watch-provider lookup doesn't
# specify a region, results are scoped to India.
DEFAULT_WATCH_REGION = "IN"


class TMDbAPIError(Exception):
    """Raised when the TMDb API returns an error or an unexpected response."""


class TMDbClient:
    """
    Client for interacting with TMDb's TV series endpoints.

    Usage:
        client = TMDbClient()
        trending = client.fetch_trending_tv()
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialize the TMDb client.

        Args:
            api_key: Optional explicit API key. If not provided, the key is
                read from the TMDB_API_KEY environment variable via config.

        Raises:
            ConfigError: If no API key is available anywhere.
        """
        self._api_key: str = api_key or get_tmdb_api_key()
        self._base_url: str = TMDB_BASE_URL
        self._session: requests.Session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        """
        Build a `requests.Session` configured with automatic retries for
        transient errors (connection issues, 429, and 5xx responses).

        Returns:
            A configured `requests.Session` instance.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a GET request against a TMDb endpoint.

        Args:
            endpoint: API path, e.g. "/tv/popular".
            params: Additional query parameters (api_key is added automatically).

        Returns:
            Parsed JSON response body as a dictionary.

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        url = f"{self._base_url}{endpoint}"
        query_params = {"api_key": self._api_key, "language": "en-US"}
        if params:
            query_params.update(params)

        try:
            response = self._session.get(
                url, params=query_params, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            logger.error("TMDb API returned an HTTP error for %s: %s", endpoint, exc)
            raise TMDbAPIError(f"HTTP error while calling TMDb endpoint '{endpoint}': {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Network error while calling TMDb endpoint %s: %s", endpoint, exc)
            raise TMDbAPIError(f"Network error while calling TMDb endpoint '{endpoint}': {exc}") from exc
        except ValueError as exc:  # JSON decoding error
            logger.error("Malformed JSON response from TMDb endpoint %s: %s", endpoint, exc)
            raise TMDbAPIError(f"Malformed JSON from TMDb endpoint '{endpoint}': {exc}") from exc

    def _fetch_results(
        self, endpoint: str, page: int = 1, extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Shared helper to fetch a paginated "results" list from a TMDb
        list-style endpoint (used by every fetch_* method below).

        Args:
            endpoint: API path, e.g. "/tv/top_rated".
            page: Page number to fetch (TMDb paginates all list endpoints).
            extra_params: Additional query parameters specific to the endpoint.

        Returns:
            A list of raw TMDb TV series result dictionaries. Returns an
            empty list if the endpoint reports no results.
        """
        params = {"page": page}
        if extra_params:
            params.update(extra_params)

        payload = self._get(endpoint, params=params)
        results = payload.get("results", [])
        if not isinstance(results, list):
            logger.warning("Unexpected 'results' shape from %s; defaulting to empty list.", endpoint)
            return []
        return results

    # ------------------------------------------------------------------
    # Public fetch methods — one per TMDb TV list endpoint.
    # ------------------------------------------------------------------
    def fetch_trending_tv(self, time_window: str = "week", page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch trending TV/web series.

        Args:
            time_window: "day" or "week" (TMDb trending window).
            page: Page number to fetch.

        Returns:
            List of raw TMDb TV series dictionaries.
        """
        return self._fetch_results(f"/trending/tv/{time_window}", page=page)

    def fetch_popular_tv(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch currently popular TV/web series.

        Args:
            page: Page number to fetch.

        Returns:
            List of raw TMDb TV series dictionaries.
        """
        return self._fetch_results("/tv/popular", page=page)

    def fetch_top_rated_tv(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch top-rated TV/web series of all time (per TMDb ranking).

        Args:
            page: Page number to fetch.

        Returns:
            List of raw TMDb TV series dictionaries.
        """
        return self._fetch_results("/tv/top_rated", page=page)

    def fetch_on_the_air_tv(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch TV/web series currently on the air (airing over the next
        few weeks).

        Args:
            page: Page number to fetch.

        Returns:
            List of raw TMDb TV series dictionaries.
        """
        return self._fetch_results("/tv/on_the_air", page=page)

    def fetch_airing_today_tv(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch TV/web series airing today.

        Args:
            page: Page number to fetch.

        Returns:
            List of raw TMDb TV series dictionaries.
        """
        return self._fetch_results("/tv/airing_today", page=page)

    # ------------------------------------------------------------------
    # Detail endpoints — one series/lookup at a time, used to enrich the
    # slim rows above with the fields the recommendation system needs.
    # ------------------------------------------------------------------
    def fetch_tv_details(self, series_id: int) -> Dict[str, Any]:
        """
        Fetch full details for a single TV/web series.

        Populates the fields not present on the list endpoints, including
        original_name, tagline, status, last_air_date, number_of_seasons,
        number_of_episodes, origin_country, and homepage.

        Args:
            series_id: TMDb series ID.

        Returns:
            The raw TMDb TV series details dictionary.

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        return self._get(f"/tv/{series_id}")

    def fetch_tv_genres(self) -> List[Dict[str, Any]]:
        """
        Fetch TMDb's official list of TV genres (id + name pairs). This is
        a global lookup list, not scoped to a single series.

        Returns:
            List of raw TMDb genre dictionaries, each with "id" and "name".

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        payload = self._get("/genre/tv/list")
        genres = payload.get("genres", [])
        if not isinstance(genres, list):
            logger.warning("Unexpected 'genres' shape from /genre/tv/list; defaulting to empty list.")
            return []
        return genres

    def fetch_tv_credits(self, series_id: int, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch the top-billed cast for a single TV/web series, sorted by
        TMDb's billing order (lower "order" = more prominent).

        Args:
            series_id: TMDb series ID.
            top_n: Maximum number of cast members to return.

        Returns:
            List of up to `top_n` raw TMDb cast-credit dictionaries.

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        payload = self._get(f"/tv/{series_id}/credits")
        cast = payload.get("cast", [])
        if not isinstance(cast, list):
            logger.warning(
                "Unexpected 'cast' shape from /tv/%s/credits; defaulting to empty list.", series_id
            )
            return []
        sorted_cast = sorted(cast, key=lambda member: member.get("order", float("inf")))
        return sorted_cast[:top_n]

    def fetch_tv_keywords(self, series_id: int) -> List[Dict[str, Any]]:
        """
        Fetch the keywords/tags associated with a single TV/web series.

        Args:
            series_id: TMDb series ID.

        Returns:
            List of raw TMDb keyword dictionaries, each with "id" and "name".

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        payload = self._get(f"/tv/{series_id}/keywords")
        results = payload.get("results", [])
        if not isinstance(results, list):
            logger.warning(
                "Unexpected 'results' shape from /tv/%s/keywords; defaulting to empty list.", series_id
            )
            return []
        return results

    def fetch_tv_watch_providers(
        self, series_id: int, region: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch watch-provider availability for a single TV/web series,
        scoped to one region. Defaults to India ("IN"), BingeFinder's
        primary market, since TMDb returns providers for every country at
        once and most series only need to be checked against one.

        Args:
            series_id: TMDb series ID.
            region: ISO 3166-1 country code to scope results to. Defaults
                to `DEFAULT_WATCH_REGION` ("IN") if not provided.

        Returns:
            The offer-type breakdown for that region, e.g.
            {"flatrate": [...], "rent": [...], "buy": [...]}. Returns an
            empty dict if the series has no listed providers in that
            region.

        Raises:
            TMDbAPIError: If the request fails after retries, or TMDb
                returns a non-2xx status code / malformed JSON.
        """
        region = region or DEFAULT_WATCH_REGION
        payload = self._get(f"/tv/{series_id}/watch/providers")
        results = payload.get("results", {})
        if not isinstance(results, dict):
            logger.warning(
                "Unexpected 'results' shape from /tv/%s/watch/providers; defaulting to empty dict.",
                series_id,
            )
            return {}
        return results.get(region, {})

    def close(self) -> None:
        """Close the underlying HTTP session and release resources."""
        self._session.close()

    def __enter__(self) -> "TMDbClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ======================================================================
# Image URL helpers
# ----------------------------------------------------------------------
# The database stores only the relative TMDb image path (e.g.
# "/abc123.jpg") returned in API responses — never a full URL and never
# a downloaded file. These helpers build a displayable URL from a stored
# path on demand, e.g. for a future UI layer. Each asset type has a
# TMDb-recommended default size, overridable per call.
# ======================================================================

TMDB_IMAGE_CDN_BASE_URL = "https://image.tmdb.org/t/p"

DEFAULT_POSTER_SIZE = "w500"
DEFAULT_BACKDROP_SIZE = "w780"
DEFAULT_PROFILE_SIZE = "w185"
DEFAULT_LOGO_SIZE = "w92"


def build_image_url(image_path: Optional[str], size: str) -> Optional[str]:
    """
    Build a full TMDb image URL from a stored relative path.

    Args:
        image_path: Relative image path as stored in the database (e.g.
            "/abc123.jpg"), or None/empty if no image is available.
        size: TMDb image size segment, e.g. "w500", "original".

    Returns:
        The full image URL, or None if `image_path` is falsy.
    """
    if not image_path:
        return None
    return f"{TMDB_IMAGE_CDN_BASE_URL}/{size}{image_path}"


def build_poster_url(poster_path: Optional[str], size: str = DEFAULT_POSTER_SIZE) -> Optional[str]:
    """Build a full TMDb URL for a series poster image."""
    return build_image_url(poster_path, size)


def build_backdrop_url(backdrop_path: Optional[str], size: str = DEFAULT_BACKDROP_SIZE) -> Optional[str]:
    """Build a full TMDb URL for a series backdrop image."""
    return build_image_url(backdrop_path, size)


def build_profile_url(profile_path: Optional[str], size: str = DEFAULT_PROFILE_SIZE) -> Optional[str]:
    """Build a full TMDb URL for a cast member's profile (headshot) image."""
    return build_image_url(profile_path, size)


def build_logo_url(logo_path: Optional[str], size: str = DEFAULT_LOGO_SIZE) -> Optional[str]:
    """Build a full TMDb URL for a watch provider's logo image."""
    return build_image_url(logo_path, size)
