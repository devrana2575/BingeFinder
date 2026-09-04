"""
backend/schemas/watch_providers.py
===================================
Pydantic schemas for watch provider endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProviderItem(BaseModel):
    provider_name: str
    logo_path: Optional[str] = None


class WatchProviderResponse(BaseModel):
    series_id: int
    providers: Dict[str, List[ProviderItem]]
    justwatch_url: Optional[str] = None
    watch_now_url: Optional[str] = None
    region: Optional[str] = None
    free_count: int = 0
    tmdb_configured: bool = True
