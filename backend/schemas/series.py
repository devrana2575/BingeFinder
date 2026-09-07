"""
backend/schemas/series.py
==========================
Pydantic schemas for series endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SeriesSummary(BaseModel):
    series_id: int
    name: str
    rating: Optional[float] = None
    genres: List[str] = []
    image: Optional[str] = None
    language: Optional[str] = None
    premiered: Optional[str] = None
    status: Optional[str] = None
    # Free-availability hint for the "Free Tonight" rail (product-level only).
    free_tier: Optional[str] = None
    free_provider_names: List[str] = []
    # User reaction for this series when returned from /user/reactions only.
    reaction: Optional[str] = None


class SeriesDetail(BaseModel):
    series_id: int
    name: str
    summary: Optional[str] = None
    genres: List[str] = []
    rating: Optional[float] = None
    language: Optional[str] = None
    premiered: Optional[str] = None
    ended: Optional[str] = None
    status: Optional[str] = None
    runtime: Optional[int] = None
    average_runtime: Optional[int] = None
    image: Optional[str] = None
    network: Optional[str] = None
    web_channel: Optional[str] = None
    cast: List[str] = []


class SeriesSearchResult(BaseModel):
    query: str
    total_results: int
    results: List[SeriesSummary]


class CatalogCount(BaseModel):
    total: int
