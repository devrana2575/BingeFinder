"""
api/tvmaze.py
==============
Thin, well-tested client around the TVmaze REST API
(https://www.tvmaze.com/api), scoped to the show catalog endpoints
BingeFinder needs.

Design notes:
    - A single `requests.Session` is reused (with a mounted retry adapter)
      for connection pooling and automatic retries on transient failures,
      mirroring api/tmdb.py's approach.
    - TVmaze requires no API key.
    - All public methods return raw TVmaze JSON structures (dicts/lists).
      Parsing/mapping into our MongoDB document schema is left to the
      caller (database/update_mongo.py) to keep this module focused
      purely on API access.
    - This client replaces api/tmdb.py as the active data source (TMDb is
      currently unreachable from this network). api/tmdb.py is left in
      place, unused, until the MongoDB migration is fully verified.
"""

import html
import re
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import BACKOFF_FACTOR, MAX_RETRIES, REQUEST_TIMEOUT_SECONDS, TVMAZE_BASE_URL
from utils.logger import get_logger

logger = get_logger(__name__)


class TVmazeAPIError(Exception):
    """Raised when the TVmaze API returns an error or an unexpected response."""


class TVmazeClient:
    """
    Client for interacting with TVmaze's show catalog endpoints.

    Usage:
        client = TVmazeClient()
        page_of_shows = client.fetch_shows_page(page=0)
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        """
        Initialize the TVmaze client.

        Args:
            base_url: Optional explicit API base URL. Defaults to
                `TVMAZE_BASE_URL` from config (https://api.tvmaze.com).
        """
        self._base_url: str = base_url or TVMAZE_BASE_URL
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
        # TVmaze asks API consumers to identify their client (see the
        # "Rate limiting" section of https://www.tvmaze.com/api).
        session.headers.update({"User-Agent": "BingeFinder/1.0 (+https://github.com/)"})
        return session

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        treat_404_as_none: bool = False,
    ) -> Optional[Any]:
        """
        Perform a GET request against a TVmaze endpoint.

        Args:
            endpoint: API path, e.g. "/shows/1".
            params: Additional query parameters.
            treat_404_as_none: If True, a 404 response returns None instead
                of raising. Used for the paginated show index, where a 404
                signals "no more pages" rather than a real error.

        Returns:
            Parsed JSON response body (dict or list), or None if
            `treat_404_as_none` is True and TVmaze returned 404.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns an unexpected non-2xx status code / malformed JSON.
        """
        url = f"{self._base_url}{endpoint}"
        try:
            response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if treat_404_as_none and response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            logger.error("TVmaze API returned an HTTP error for %s: %s", endpoint, exc)
            raise TVmazeAPIError(f"HTTP error while calling TVmaze endpoint '{endpoint}': {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Network error while calling TVmaze endpoint %s: %s", endpoint, exc)
            raise TVmazeAPIError(f"Network error while calling TVmaze endpoint '{endpoint}': {exc}") from exc
        except ValueError as exc:  # JSON decoding error
            logger.error("Malformed JSON response from TVmaze endpoint %s: %s", endpoint, exc)
            raise TVmazeAPIError(f"Malformed JSON from TVmaze endpoint '{endpoint}': {exc}") from exc

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    def fetch_shows_page(self, page: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch one page of TVmaze's full show index/catalog. Each entry
        already contains nearly every field our schema needs (name,
        genres, status, rating, network, image, externals, summary,
        etc.) — only cast requires a separate per-show call.

        Args:
            page: Zero-based page number. TVmaze pages by show ID range
                (page 0 = IDs 0-250, page 1 = IDs 250-500, etc.), so a
                page can return fewer than 250 shows without meaning the
                catalog has ended.

        Returns:
            List of raw TVmaze show dictionaries. Returns an empty list
            once `page` is past the last available page (TVmaze responds
            with HTTP 404 in that case, per its own pagination docs — this
            is treated as "no more data" rather than an error).

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns an unexpected non-2xx status code / malformed JSON.
        """
        payload = self._get("/shows", params={"page": page}, treat_404_as_none=True)
        if payload is None:
            return []
        if not isinstance(payload, list):
            logger.warning("Unexpected shape from /shows page %d; defaulting to empty list.", page)
            return []
        return payload

    def search_shows(self, query: str) -> List[Dict[str, Any]]:
        """
        Full-text search TVmaze's show catalog by title
        (`/search/shows?q=...`). Used for on-demand lookups of a show
        that isn't (yet) in our MongoDB catalog — e.g. when a user
        searches for a title our periodic `/shows` catalog sync hasn't
        reached.

        Args:
            query: Free-text title to search for, e.g. "Money Heist".

        Returns:
            List of raw TVmaze search-result dicts, each shaped like
            {"score": float, "show": {...}}, already ordered by TVmaze
            from best to worst match. Empty list if nothing matches.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns a non-2xx status code / malformed JSON.
        """
        if not query or not query.strip():
            return []
        payload = self._get("/search/shows", params={"q": query.strip()})
        if not isinstance(payload, list):
            logger.warning("Unexpected shape from /search/shows; defaulting to empty list.")
            return []
        return payload

    def fetch_show(self, show_id: int) -> Dict[str, Any]:
        """
        Fetch full details for a single show by TVmaze ID.

        Useful for targeted refreshes (e.g. re-syncing only the shows
        reported as changed by `fetch_show_updates`) without re-fetching
        the whole catalog.

        Args:
            show_id: TVmaze show ID.

        Returns:
            The raw TVmaze show dictionary.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns a non-2xx status code / malformed JSON.
        """
        return self._get(f"/shows/{show_id}")

    def fetch_show_cast(self, show_id: int, top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch the main cast for a single show.

        Args:
            show_id: TVmaze show ID.
            top_n: If given, only the first `top_n` entries are returned.
                TVmaze already orders cast by importance (total character
                appearances), so this is effectively "top N billed".

        Returns:
            List of raw TVmaze cast dictionaries, each with "person" and
            "character" sub-objects.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns a non-2xx status code / malformed JSON.
        """
        payload = self._get(f"/shows/{show_id}/cast")
        if not isinstance(payload, list):
            logger.warning("Unexpected shape from /shows/%s/cast; defaulting to empty list.", show_id)
            return []
        return payload[:top_n] if top_n is not None else payload

    def fetch_show_images(self, show_id: int) -> List[Dict[str, Any]]:
        """
        Fetch the full image gallery for a single show (posters, banners,
        backgrounds, etc.) — beyond the medium/original pair already
        embedded in the show object itself. Not called automatically by
        the ingestion pipeline (the embedded image is normally enough);
        available for later, more selective use.

        Args:
            show_id: TVmaze show ID.

        Returns:
            List of raw TVmaze image dictionaries.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns a non-2xx status code / malformed JSON.
        """
        payload = self._get(f"/shows/{show_id}/images")
        if not isinstance(payload, list):
            logger.warning("Unexpected shape from /shows/%s/images; defaulting to empty list.", show_id)
            return []
        return payload

    def fetch_show_updates(self, since: Optional[str] = None) -> Dict[str, int]:
        """
        Fetch TVmaze's show-update ledger: a mapping of show ID -> Unix
        timestamp of that show's last update. Intended for incremental
        syncs — compare against each stored document's "updated" field to
        find shows that actually need re-fetching, instead of re-pulling
        the entire catalog.

        Args:
            since: Optional TVmaze time-window filter: "day", "week", or
                "month". If omitted, TVmaze returns the full update ledger.

        Returns:
            Dict mapping show ID (as a string key, per TVmaze's response)
            to a Unix timestamp.

        Raises:
            TVmazeAPIError: If the request fails after retries, or TVmaze
                returns a non-2xx status code / malformed JSON.
        """
        params = {"since": since} if since else None
        payload = self._get("/updates/shows", params=params)
        if not isinstance(payload, dict):
            logger.warning("Unexpected shape from /updates/shows; defaulting to empty dict.")
            return {}
        return payload

    def close(self) -> None:
        """Close the underlying HTTP session and release resources."""
        self._session.close()

    def __enter__(self) -> "TVmazeClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ======================================================================
# Summary cleaning helper
# ----------------------------------------------------------------------
# TVmaze show summaries are simple HTML fragments (<p>, <b>, etc). We
# store plain text only, so nothing downstream needs to sanitize HTML
# before displaying or processing it.
# ======================================================================

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_summary(raw_summary: Optional[str]) -> Optional[str]:
    """
    Strip HTML tags from a TVmaze summary field, unescape HTML entities,
    and normalize whitespace.

    Args:
        raw_summary: Raw summary string as returned by TVmaze, possibly
            containing HTML tags (e.g. "<p>A show about...</p>"), or None.

    Returns:
        Plain-text summary, or None if `raw_summary` is falsy or empty
        after cleaning.
    """
    if not raw_summary:
        return None
    without_tags = _HTML_TAG_RE.sub(" ", raw_summary)
    unescaped = html.unescape(without_tags)
    normalized = _WHITESPACE_RE.sub(" ", unescaped).strip()
    return normalized or None
