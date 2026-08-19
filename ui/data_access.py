"""
ui/data_access.py
====================
Read-only data-access layer for the Phase 4 Streamlit app.

This module is the ONLY place the UI talks to the backend. It wraps:
    - database.mongo_client.MongoDBManager  (existing Phase 2 backend)
    - recommender.recommend.get_recommendations  (existing Phase 3 model)

No new writes, no new indexes, no changes to the recommendation
algorithm — this purely reads through the existing modules and shapes
the results for display, while turning every failure mode into a
`(data, error_message)` tuple instead of letting Streamlit crash.

Caching:
    - `load_all_series()` is cached (st.cache_data) for a few minutes so
      switching between Home / Discover / Details doesn't re-hit
      MongoDB on every rerun (Streamlit reruns the whole script on every
      widget interaction).
    - A manual "Refresh data" action (exposed in streamlit_app.py) clears
      the cache on demand.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# ---------------------------------------------------------------------------
# Backend imports. Deliberately imported inside functions where a missing/
# misconfigured backend (e.g. no .env yet) should be reported as a friendly
# in-app message rather than crashing the whole Streamlit process at import
# time.
# ---------------------------------------------------------------------------


def _connect() -> Tuple[Optional["MongoDBManager"], Optional[str]]:  # noqa: F821
    """Open a MongoDBManager, translating connection/config failures into a message."""
    try:
        from config import ConfigError
        from database.mongo_client import MongoDatabaseError, MongoDBManager
    except Exception as exc:  # pragma: no cover - import-level failure
        return None, f"Backend could not be loaded: {exc}"

    try:
        manager = MongoDBManager()
    except ConfigError as exc:
        return None, (
            "MongoDB is not configured. Copy `.env.example` to `.env` and set "
            f"MONGODB_URI / MONGODB_DATABASE. ({exc})"
        )
    except MongoDatabaseError as exc:
        return None, f"Could not connect to MongoDB: {exc}"
    return manager, None


def _sanitize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Make a Mongo document safely cacheable/displayable (stringify ObjectId)."""
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


@st.cache_data(ttl=300, show_spinner="Loading series from MongoDB...")
def load_all_series() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetch every series document from MongoDB (existing Phase 2 backend).

    Returns:
        (series_list, error_message). On any failure, series_list is []
        and error_message describes what went wrong. An empty-but-healthy
        database returns ([], None).
    """
    manager, err = _connect()
    if err:
        return [], err

    try:
        from database.mongo_client import MongoDatabaseError

        docs = manager.get_all_series()
    except Exception as exc:  # MongoDatabaseError or anything unexpected
        return [], f"Failed to read series from MongoDB: {exc}"
    finally:
        manager.close()

    return [_sanitize(d) for d in docs], None


def get_series_map() -> Dict[int, Dict[str, Any]]:
    """Return {tvmaze_id: document} for every series (empty dict on error)."""
    docs, _ = load_all_series()
    return {d["tvmaze_id"]: d for d in docs if d.get("tvmaze_id") is not None}


def get_series_by_id(series_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Look up one series by tvmaze_id from the already-loaded catalog.

    Returns:
        (document, None) if found, or (None, error_message) if the
        database is unreachable/empty or the id doesn't exist.
    """
    docs, err = load_all_series()
    if err:
        return None, err
    if not docs:
        return None, "The series database is empty. Run the Phase 2 sync first."

    for doc in docs:
        if doc.get("tvmaze_id") == series_id:
            return doc, None
    return None, f"No series found with id {series_id}. It may have been removed."


def search_and_add_series(query: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    On-demand fallback for when a title search finds nothing in the
    already-loaded MongoDB catalog:
      - MongoDB is checked first by the caller (via `filter_series` on
        `load_all_series()`) — this function is only reached when that
        comes back empty.
      - Search TVmaze for `query`; if a match is found, fetch its cast
        and upsert it into MongoDB using the existing Phase 2
        upsert-by-tvmaze_id logic (never a duplicate).
      - Clear the cached catalog so the new series appears immediately
        on the next read.

    Returns:
        (new_document, None) if a matching show was found and stored,
        or (None, message) if TVmaze had no match, or a backend/config
        error occurred.
    """
    query = (query or "").strip()
    if not query:
        return None, "Enter a title to search for."

    manager, err = _connect()
    if err:
        return None, err

    try:
        from database.update_mongo import find_or_fetch_show

        doc = find_or_fetch_show(query, manager)
    except Exception as exc:  # TVmazeAPIError, MongoDatabaseError, or unexpected
        return None, f"TVmaze search failed: {exc}"
    finally:
        manager.close()

    if doc is None:
        return None, f'No TVmaze series found matching "{query}".'

    load_all_series.clear()  # next load_all_series() call picks up the new series
    return _sanitize(doc), None


def search_tvmaze(query: str, limit: int = 8) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Live TVmaze title search (read-only — nothing is written to MongoDB
    here). Used when the local catalog has no match for `query`.

    Unlike `TVmazeClient.search_shows()`'s raw relevance ordering, this
    re-ranks the results so an exact (case-insensitive) title match is
    always first, then "starts with" matches, then everything else in
    TVmaze's own order — so searching "Money Heist" surfaces the real
    "Money Heist" ahead of spin-offs like "Money Heist: Korea".

    Returns:
        (candidates, None) where each candidate is a small display-ready
        dict ({tvmaze_id, name, premiered, image_medium, language}) plus
        a "show" key holding the raw TVmaze show dict (needed to add it
        later via `add_series_from_tvmaze`), or ([], error_message).
    """
    query = (query or "").strip()
    if not query:
        return [], "Enter a title to search for."

    try:
        from api.tvmaze import TVmazeAPIError, TVmazeClient
    except Exception as exc:  # pragma: no cover
        return [], f"Backend could not be loaded: {exc}"

    try:
        with TVmazeClient() as client:
            results = client.search_shows(query)
    except TVmazeAPIError as exc:
        return [], f"TVmaze search failed: {exc}"

    shows = [r.get("show") for r in (results or []) if isinstance(r, dict) and r.get("show")]
    if not shows:
        return [], f'No TVmaze series found matching "{query}".'

    q_norm = query.strip().lower()

    def _rank(show: Dict[str, Any]) -> tuple:
        name_norm = (show.get("name") or "").strip().lower()
        if name_norm == q_norm:
            return (0,)
        if name_norm.startswith(q_norm):
            return (1,)
        return (2,)

    shows.sort(key=_rank)

    candidates = []
    for show in shows[:limit]:
        image = show.get("image")
        image_medium = image.get("medium") if isinstance(image, dict) else None
        candidates.append(
            {
                "tvmaze_id": show.get("id"),
                "name": show.get("name"),
                "premiered": show.get("premiered"),
                "language": show.get("language"),
                "image_medium": image_medium,
                "show": show,
            }
        )
    return candidates, None


def add_series_from_tvmaze(show: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Store one specific TVmaze show the user picked (e.g. from
    `search_tvmaze()`'s results) into MongoDB, reusing the exact same
    mapping/upsert path (`database.update_mongo.fetch_and_upsert_show`)
    as the bulk sync and the old auto-pick flow — never a different
    document shape, never a duplicate.

    Returns:
        (new_document, None) on success, or (None, error_message).
    """
    if not isinstance(show, dict) or show.get("id") is None:
        return None, "That series is missing a TVmaze id and can't be added."

    manager, err = _connect()
    if err:
        return None, err

    try:
        from api.tvmaze import TVmazeAPIError, TVmazeClient
        from database.update_mongo import fetch_and_upsert_show

        with TVmazeClient() as client:
            doc = fetch_and_upsert_show(show, client, manager)
    except TVmazeAPIError as exc:
        return None, f"TVmaze lookup failed: {exc}"
    except Exception as exc:  # pragma: no cover
        return None, f"Could not add series: {exc}"
    finally:
        manager.close()

    if doc is None:
        return None, "That series could not be added (missing TVmaze id)."

    load_all_series.clear()
    return _sanitize(doc), None


# ---------------------------------------------------------------------------
# Search / filter / discovery helpers (pure Python, operate on the cached
# catalog — no new Mongo queries or indexes introduced).
# ---------------------------------------------------------------------------

def _year_of(doc: Dict[str, Any]) -> Optional[int]:
    premiered = doc.get("premiered")
    if isinstance(premiered, str) and len(premiered) >= 4 and premiered[:4].isdigit():
        return int(premiered[:4])
    return None


def get_filter_options(docs: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    """Distinct, sorted filter values actually present in the catalog."""
    genres, languages, statuses, years = set(), set(), set(), set()
    for doc in docs:
        for g in doc.get("genres") or []:
            if isinstance(g, str) and g.strip():
                genres.add(g.strip())
        if isinstance(doc.get("language"), str) and doc["language"].strip():
            languages.add(doc["language"].strip())
        if isinstance(doc.get("status"), str) and doc["status"].strip():
            statuses.add(doc["status"].strip())
        year = _year_of(doc)
        if year:
            years.add(year)

    return {
        "genres": sorted(genres),
        "languages": sorted(languages),
        "statuses": sorted(statuses),
        "years": sorted(years, reverse=True),
    }


def filter_series(
    docs: List[Dict[str, Any]],
    query: str = "",
    genres: Optional[List[str]] = None,
    min_rating: float = 0.0,
    language: Optional[str] = None,
    year: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter the in-memory catalog by title substring + the existing schema fields.

    Results are ranked so an exact (or "starts with") title match always
    surfaces first — e.g. searching "Money Heist" puts the real "Money
    Heist" ahead of "Money Heist: Korea" instead of leaving the order to
    whatever MongoDB happened to return.
    """
    query = (query or "").strip().lower()
    results = []
    for doc in docs:
        name_norm = (doc.get("name") or "").lower()
        if query and query not in name_norm:
            continue
        if genres:
            doc_genres = set(doc.get("genres") or [])
            if not doc_genres.intersection(genres):
                continue
        rating = doc.get("rating")
        if min_rating > 0 and (rating is None or rating < min_rating):
            continue
        if language and doc.get("language") != language:
            continue
        if year and _year_of(doc) != year:
            continue
        if status and doc.get("status") != status:
            continue
        results.append(doc)

    if query:
        def _rank(doc: Dict[str, Any]) -> tuple:
            name_norm = (doc.get("name") or "").lower()
            if name_norm == query:
                tier = 0
            elif name_norm.startswith(query):
                tier = 1
            else:
                tier = 2
            return (tier, len(name_norm))

        results.sort(key=_rank)

    return results


def get_featured_series(docs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Top-rated series with a real rating value — used for Home's 'Featured'."""
    rated = [d for d in docs if isinstance(d.get("rating"), (int, float))]
    return sorted(rated, key=lambda d: d["rating"], reverse=True)[:limit]


def get_popular_series(docs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Highest TVmaze 'weight' (their own popularity signal) — used for Home's 'Popular'."""
    weighted = [d for d in docs if isinstance(d.get("weight"), (int, float))]
    return sorted(weighted, key=lambda d: d["weight"], reverse=True)[:limit]


def get_hidden_gems(docs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Highly-rated series with lower TVmaze weight — underrated finds."""
    gems = [
        d for d in docs
        if isinstance(d.get("rating"), (int, float))
        and d["rating"] >= 7.5
        and (not isinstance(d.get("weight"), (int, float)) or d["weight"] < 500)
    ]
    return sorted(gems, key=lambda d: d["rating"], reverse=True)[:limit]


def get_trending_series(docs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Currently-running series, most recently premiered first — used for Home's 'Trending Now'."""
    running = [
        d for d in docs
        if d.get("status") == "Running" and _year_of(d) is not None
    ]
    return sorted(running, key=lambda d: d.get("premiered") or "", reverse=True)[:limit]


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def add_to_watchlist(tvmaze_id: int) -> Tuple[bool, Optional[str]]:
    """Add a series to the watchlist. Returns (success, error_message)."""
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        result = wl.add_to_watchlist(tvmaze_id)
        return True, None if result == "added" else None
    except Exception as exc:
        return False, f"Could not add to watchlist: {exc}"
    finally:
        manager.close()


def remove_from_watchlist(tvmaze_id: int) -> Tuple[bool, Optional[str]]:
    """Remove a series from the watchlist. Returns (success, error_message)."""
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        wl.remove_from_watchlist(tvmaze_id)
        return True, None
    except Exception as exc:
        return False, f"Could not remove from watchlist: {exc}"
    finally:
        manager.close()


def is_in_watchlist(tvmaze_id: int) -> bool:
    """Check if a series is in the watchlist."""
    manager, err = _connect()
    if err:
        return False
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        return wl.is_in_watchlist(tvmaze_id)
    except Exception:
        return False
    finally:
        manager.close()


def get_watchlist_series() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Load all watchlist items enriched with their series data. Returns (series_list, error_message)."""
    manager, err = _connect()
    if err:
        return [], err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        watchlist_docs = wl.get_watchlist()
        
        # Enrich with series data from the cached catalog
        docs, _ = load_all_series()
        series_map = {d["tvmaze_id"]: d for d in docs if d.get("tvmaze_id") is not None}
        
        result = []
        for wl_doc in watchlist_docs:
            sid = wl_doc.get("tvmaze_id")
            if sid in series_map:
                entry = dict(series_map[sid])
                entry["added_at"] = wl_doc.get("added_at")
                result.append(entry)
        return result, None
    except Exception as exc:
        return [], f"Could not load watchlist: {exc}"
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# Recommendations (existing Phase 3 engine — untouched).
# ---------------------------------------------------------------------------

def fetch_recommendations(
    series_id: int, top_n: int = 10
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Call the existing recommender.recommend.get_recommendations() as-is.

    Returns:
        (recommendations, None) on success (recommendations may be an
        empty list if the model genuinely has nothing else to suggest),
        or ([], error_message) if the model isn't built yet or the
        series isn't in the model.
    """
    try:
        from recommender.exceptions import ModelNotBuiltError, RecommenderError, SeriesNotFoundError
        from recommender.recommend import get_recommendations
    except Exception as exc:  # pragma: no cover
        return [], f"Recommendation engine could not be loaded: {exc}"

    try:
        return get_recommendations(series_id, top_n=top_n), None
    except ModelNotBuiltError as exc:
        return [], (
            "The recommendation model hasn't been built yet. Run "
            f"`python -m recommender.build_model` first. ({exc})"
        )
    except SeriesNotFoundError as exc:
        return [], (
            "This series isn't in the recommendation model yet (it may have "
            f"been added since the model was last built). ({exc})"
        )
    except RecommenderError as exc:
        return [], f"Could not generate recommendations: {exc}"
