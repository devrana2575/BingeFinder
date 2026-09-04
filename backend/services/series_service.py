"""
backend/services/series_service.py
====================================
Wraps MongoDBManager for series queries.
"""

from typing import Any, Dict, List, Optional, Tuple

from database.mongo_client import MongoDBManager


def _connect() -> Tuple[MongoDBManager, None] | Tuple[None, str]:
    try:
        manager = MongoDBManager()
        return manager, None
    except Exception as exc:
        return None, str(exc)


def get_all_series() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    manager, err = _connect()
    if err:
        return [], err
    try:
        docs = manager.get_all_series()
        result = []
        for d in docs:
            doc = dict(d)
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            result.append(doc)
        return result, None
    finally:
        manager.close()


def get_series_by_id(series_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    manager, err = _connect()
    if err:
        return None, err
    try:
        doc = manager.get_series_by_id(series_id)
        if doc:
            doc = dict(doc)
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            return doc, None
        return None, f"No series found with id {series_id}."
    finally:
        manager.close()


def get_series_count() -> int:
    manager, err = _connect()
    if err:
        return 0
    try:
        return manager.get_series_count()
    finally:
        manager.close()


def search_series(
    docs: List[Dict[str, Any]],
    query: str = "",
    genres: Optional[List[str]] = None,
    min_rating: float = 0.0,
    language: Optional[str] = None,
    year: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter in-memory catalog.

    Supports filters (query, genres, min_rating, language, year, status) and,
    when a query is present, the returned results are ranked by title match
    priority: exact match first, then prefix match, then contains, ordering
    shorter titles earlier within the same tier.
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
        if year:
            premiered = doc.get("premiered") or ""
            if len(premiered) >= 4 and premiered[:4].isdigit():
                if int(premiered[:4]) != year:
                    continue
            else:
                continue
        if status and doc.get("status") != status:
            continue
        results.append(doc)

    if query:
        def _rank(doc):
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


def get_filter_options(docs: List[Dict[str, Any]]) -> Dict[str, List]:
    genres, languages, statuses, years = set(), set(), set(), set()
    for doc in docs:
        for g in doc.get("genres") or []:
            if isinstance(g, str) and g.strip():
                genres.add(g.strip())
        if isinstance(doc.get("language"), str) and doc["language"].strip():
            languages.add(doc["language"].strip())
        if isinstance(doc.get("status"), str) and doc["status"].strip():
            statuses.add(doc["status"].strip())
        premiered = doc.get("premiered") or ""
        if len(premiered) >= 4 and premiered[:4].isdigit():
            yr = int(premiered[:4])
            if 1950 <= yr <= 2030:
                years.add(yr)
    return {
        "genres": sorted(genres),
        "languages": sorted(languages),
        "statuses": sorted(statuses),
        "years": sorted(years, reverse=True),
    }
