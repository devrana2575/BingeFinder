"""
backend/schemas/discovery.py
=============================
Pydantic schemas for the discovery endpoints.
"""

from typing import List, Optional

from pydantic import BaseModel


class SurprisePick(BaseModel):
    """A single Surprise Me result, enriched with grounded reasons."""

    series_id: int
    name: str
    content_type: str = "tv_series"
    rating: Optional[float] = None
    genres: List[str] = []
    image: Optional[str] = None
    language: Optional[str] = None
    premiered: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    runtime: Optional[int] = None
    average_runtime: Optional[int] = None
    network: Optional[str] = None
    # Grounded "why this pick" reasons (may be empty when there are no
    # saved preferences to justify a reason against).
    why: List[str] = []