"""
backend/services/series_service.py
====================================
Wraps MongoDBManager for series queries.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from database.mongo_client import MongoDBManager


def _norm(value: str) -> str:
    """Normalize a title for matching (lowercase, alphanumeric words only)."""
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _tokens(value: str) -> List[str]:
    """Split a normalized title into tokens."""
    return _norm(value).split()


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


def derive_anime_content_types() -> Tuple[int, Optional[str]]:
    """
    Backfill `content_type="anime"` onto catalog documents that carry an
    "Anime" genre (the TVMaze classification) but were ingested before
    content types existed. Idempotent — only documents whose stored type is
    still the TV default are updated. Returns the matched count.
    """
    manager, err = _connect()
    if err:
        return 0, err
    try:
        matched = manager.series.update_many(
            {"genres": "Anime", "content_type": "tv_series"},
            {"$set": {"content_type": "anime"}},
        )
        return matched.matched_count, None
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
    content_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter in-memory catalog.

    Supports filters (query, genres, min_rating, language, year, status,
    content_type) and, when a query is present, ranks by title-match tier:

        0. Normalized exact name/original-title match
        1. Prefix match (title starts with the query)
        2. Every query token prefix-matches a title token
        3. Contains match
        4. Fuzzy substring match (kept only when nothing stronger matches)

    Tier 0/1/2 are decided on EITHER the display name or the original
    (often non-English) title, e.g. searching "money heist" must also
    surface "La Casa de Papel". Within a tier, shorter titles rank first
    so "Money Heist" outranks its longer spin-off.
    """
    query = (query or "").strip().lower()
    q_norm = _norm(query)
    q_tokens = _tokens(query)
    results = []
    for doc in docs:
        name_norm = _norm(doc.get("name"))
        orig_norm = _norm(doc.get("original_name"))
        combined = f"{name_norm} {orig_norm}".strip()

        if query:
            exact_combined = bool(q_norm) and (name_norm == q_norm or orig_norm == q_norm)
            contains = bool(q_norm and (q_norm in combined))
            token_covered = False
            if q_tokens and combined:
                combined_tokens = combined.split()
                token_covered = all(
                    any(tok.startswith(qt) or qt.startswith(tok) for tok in combined_tokens)
                    for qt in q_tokens
                )
            fuzzy = (
                q_norm and name_norm and
                (SequenceMatcher(None, q_norm, name_norm, autojunk=False).ratio() >= 0.6
                 or SequenceMatcher(None, q_norm, orig_norm, autojunk=False).ratio() >= 0.6)
            )
            if not (exact_combined or contains or token_covered or fuzzy):
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
        if content_type and doc.get("content_type", "tv_series") != content_type:
            continue
        results.append(doc)

    if query:
        def _token_coverage(field_norm: str) -> float:
            if not q_tokens or not field_norm:
                return 0.0
            field_tokens = field_norm.split()
            if not field_tokens:
                return 0.0
            covered = sum(
                1 for qt in q_tokens
                if any(tok.startswith(qt) or qt.startswith(tok) for tok in field_tokens)
            )
            return covered / len(q_tokens)

        def _tier(name_norm: str, orig_norm: str) -> int:
            if name_norm == q_norm or orig_norm == q_norm:
                return 0
            if name_norm.startswith(q_norm) or orig_norm.startswith(q_norm):
                return 1
            if _token_coverage(name_norm) >= 0.99 or _token_coverage(orig_norm) >= 0.99:
                return 2
            if q_norm in f"{name_norm} {orig_norm}":
                return 3
            return 4

        def _rank(doc):
            name_norm = _norm(doc.get("name"))
            orig_norm = _norm(doc.get("original_name"))
            tier = _tier(name_norm, orig_norm)
            coverage = max(_token_coverage(name_norm), _token_coverage(orig_norm))
            length = len(name_norm) if name_norm else len(orig_norm)
            return (tier, -coverage, length)
        results.sort(key=_rank)

    return results


def get_filter_options(docs: List[Dict[str, Any]]) -> Dict[str, List]:
    genres, languages, statuses, years, content_types = set(), set(), set(), set(), set()
    for doc in docs:
        for g in doc.get("genres") or []:
            if isinstance(g, str) and g.strip():
                genres.add(g.strip())
        if isinstance(doc.get("language"), str) and doc["language"].strip():
            languages.add(doc["language"].strip())
        if isinstance(doc.get("status"), str) and doc["status"].strip():
            statuses.add(doc["status"].strip())
        content_types.add(doc.get("content_type") or "tv_series")
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
        "content_types": sorted(ct for ct in content_types if ct in ("movie", "tv_series", "anime")),
    }
