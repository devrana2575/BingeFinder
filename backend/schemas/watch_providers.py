"""
backend/schemas/watch_providers.py
===================================
Pydantic schemas for watch provider endpoints.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class ProviderItem(BaseModel):
    provider_name: str
    logo_url: Optional[str] = None
    # Alias for callers that expect the provider-logo convention.
    provider_logo: Optional[str] = None
    watch_url: Optional[str] = None
    category: Optional[str] = None
    # Backwards compatible: kept for any caller/tests relying on the raw path.
    logo_path: Optional[str] = None
    is_free: bool = False
    is_ads_supported: bool = False


class WatchProviderResponse(BaseModel):
    series_id: int
    providers: Dict[str, List[ProviderItem]]
    justwatch_url: Optional[str] = None
    watch_now_url: Optional[str] = None
    region: Optional[str] = None
    free_count: int = 0
    tmdb_configured: bool = True
    # Clean state machine for the frontend:
    #   "ok"               - availability retrieved (may have 0 providers)
    #   "not_configured"   - availability service has no credentials
    #   "error"            - availability request failed
    status: str = "ok"


class AvailableProviderItem(BaseModel):
    provider_id: int
    provider_name: str
    logo_url: Optional[str] = None


class AvailableProvidersResponse(BaseModel):
    region: Optional[str] = None
    providers: List[AvailableProviderItem] = []
    status: str = "ok"
