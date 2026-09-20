"""
backend/routes/series.py
=========================
GET /series, GET /series/{id}, GET /series/search?q=
"""

from typing import List, Optional

from fastapi import APIRouter, Query

from backend.schemas.series import (CatalogCount, SeriesDetail, SeriesSearchResult,
                                    SeriesSuggestion, SeriesSummary)
from backend.services import series_service
from api.tmdb import build_poster_url

router = APIRouter()


def _doc_to_summary(doc: dict) -> SeriesSummary:
    return SeriesSummary(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        content_type=doc.get("content_type") or "tv_series",
        rating=doc.get("rating"),
        genres=doc.get("genres") or [],
        image=build_poster_url(doc.get("image_medium") or doc.get("image_original")),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        status=doc.get("status"),
    )


def _doc_to_detail(doc: dict) -> SeriesDetail:
    def _channel_name(obj):
        if isinstance(obj, dict):
            return obj.get("name")
        return None

    cast = doc.get("cast") or []
    cast_names = [
        c.get("person_name") for c in cast
        if isinstance(c, dict) and c.get("person_name")
    ]

    return SeriesDetail(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        content_type=doc.get("content_type") or "tv_series",
        summary=doc.get("summary"),
        genres=doc.get("genres") or [],
        rating=doc.get("rating"),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        ended=doc.get("ended"),
        status=doc.get("status"),
        runtime=doc.get("runtime"),
        average_runtime=doc.get("average_runtime"),
        image=build_poster_url(doc.get("image_original") or doc.get("image_medium")),
        network=_channel_name(doc.get("network")) or _channel_name(doc.get("web_channel")),
        cast=cast_names[:10],
    )


@router.get("/count", response_model=CatalogCount)
def catalog_count():
    return CatalogCount(total=series_service.get_series_count())


@router.get("/filters")
def filter_options():
    docs, err = series_service.get_catalog_snapshot()
    if err:
        return {"genres": [], "languages": [], "years": [], "ratings": []}
    return series_service.get_filter_options(docs)


@router.get("/search", response_model=SeriesSearchResult)
def search(
    q: str = Query("", description="Search query"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    language: Optional[str] = Query(None, description="Filter by language"),
    year: Optional[int] = Query(None, description="Filter by premiere year"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_rating: float = Query(0.0, description="Minimum rating"),
    content_type: Optional[str] = Query(None, description="Filter by content type (tv_series|movie|anime)"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return in this page"),
    offset: int = Query(0, ge=0, description="Skip this many results (for pagination)"),
):
    docs, err = series_service.get_all_series()
    if err:
        return SeriesSearchResult(query=q, total_results=0, results=[])

    genres = [genre] if genre else None
    if q.strip():
        docs, err = series_service.get_search_candidates(
            q, genres=genres, min_rating=min_rating, language=language,
            year=year, status=status, content_type=content_type,
        )
    else:
        docs, err = series_service.get_catalog_snapshot()
    if err:
        return SeriesSearchResult(query=q, total_results=0, results=[])
    filtered = series_service.search_series(
        docs, query=q, genres=genres, min_rating=min_rating,
        language=language, year=year, status=status, content_type=content_type,
    )
    results = [_doc_to_summary(d) for d in filtered[offset:offset + limit]]
    return SeriesSearchResult(query=q, total_results=len(filtered), results=results)


@router.get("/suggest", response_model=List[SeriesSuggestion])
def suggest(
    q: str = Query("", description="Search query for suggestions"),
    content_type: Optional[str] = Query(None, description="Filter by content type (tv_series|movie|anime)"),
    limit: int = Query(8, ge=1, le=20, description="Max suggestions to return"),
):
    """Lightweight typeahead suggestions for the search boxes."""
    if not q or len(q.strip()) < 1:
        return []
    docs, err = series_service.get_search_candidates(
        q, content_type=content_type or None, limit=200,
    )
    if err:
        return []

    seen: set = set()
    suggestions: List[SeriesSuggestion] = []
    for d in series_service.search_series(docs, query=q, content_type=content_type):
        sid = d["series_id"]
        if sid in seen:
            continue
        seen.add(sid)
        premiered = d.get("premiered") or ""
        suggestions.append(SeriesSuggestion(
            series_id=sid,
            name=d.get("name") or "Untitled",
            content_type=d.get("content_type") or "tv_series",
            rating=d.get("rating"),
            year=premiered[:4] if len(premiered) >= 4 and premiered[:4].isdigit() else None,
            image=build_poster_url(d.get("image_medium") or d.get("image_original")),
        ))
        if len(suggestions) >= limit:
            break
    return suggestions


@router.get("/{series_id}", response_model=SeriesDetail)
def get_series(series_id: int):
    doc, err = series_service.get_series_by_id(series_id)
    if err:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=err)
    return _doc_to_detail(doc)
