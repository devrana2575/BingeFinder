"""
regions.py
==========
Single source of truth for BingeFinder's supported streaming regions.

This is the only place that decides:
  * which countries users can pick from,
  * the friendly, user-facing country name for each code,
  * the fallback region used when auto-detection fails.

The watch-availability pipeline (api/watch_providers.py, api/tmdb.py) and the
user-settings storage both consume this module, so changing region support
touches exactly one file.

Region codes are ISO 3166-1 alpha-2 (the codes TMDb itself uses for its
watch-provider responses). Only the country-level code is ever stored or
processed - no IP addresses and no precise location are collected.
"""

from typing import Dict, List, Optional

# Default region used when the user's country can't be detected and they
# haven't chosen one. US is used purely as a neutral, widely-served default;
# it is never treated as a "permanent" market for availability lookups.
DEFAULT_REGION = "US"

# Curated set of supported countries. Kept deliberately small (not "hundreds
# of technical options") so the selector stays usable, while covering the
# major streaming markets across every region of the world.
SUPPORTED_REGIONS: List[Dict[str, str]] = [
    {"code": "US", "name": "United States"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "CA", "name": "Canada"},
    {"code": "AU", "name": "Australia"},
    {"code": "NZ", "name": "New Zealand"},
    {"code": "IE", "name": "Ireland"},
    {"code": "IN", "name": "India"},
    {"code": "DE", "name": "Germany"},
    {"code": "FR", "name": "France"},
    {"code": "ES", "name": "Spain"},
    {"code": "IT", "name": "Italy"},
    {"code": "PT", "name": "Portugal"},
    {"code": "NL", "name": "Netherlands"},
    {"code": "BE", "name": "Belgium"},
    {"code": "AT", "name": "Austria"},
    {"code": "CH", "name": "Switzerland"},
    {"code": "SE", "name": "Sweden"},
    {"code": "NO", "name": "Norway"},
    {"code": "DK", "name": "Denmark"},
    {"code": "FI", "name": "Finland"},
    {"code": "PL", "name": "Poland"},
    {"code": "CZ", "name": "Czechia"},
    {"code": "BR", "name": "Brazil"},
    {"code": "MX", "name": "Mexico"},
    {"code": "AR", "name": "Argentina"},
    {"code": "CL", "name": "Chile"},
    {"code": "CO", "name": "Colombia"},
    {"code": "PE", "name": "Peru"},
    {"code": "JP", "name": "Japan"},
    {"code": "KR", "name": "South Korea"},
    {"code": "TW", "name": "Taiwan"},
    {"code": "HK", "name": "Hong Kong"},
    {"code": "SG", "name": "Singapore"},
    {"code": "MY", "name": "Malaysia"},
    {"code": "TH", "name": "Thailand"},
    {"code": "ID", "name": "Indonesia"},
    {"code": "PH", "name": "Philippines"},
    {"code": "VN", "name": "Vietnam"},
    {"code": "SA", "name": "Saudi Arabia"},
    {"code": "AE", "name": "United Arab Emirates"},
    {"code": "IL", "name": "Israel"},
    {"code": "TR", "name": "Türkiye"},
    {"code": "ZA", "name": "South Africa"},
    {"code": "NG", "name": "Nigeria"},
    {"code": "EG", "name": "Egypt"},
    {"code": "RU", "name": "Russia"},
]

_REGION_CODE_TO_NAME: Dict[str, str] = {r["code"]: r["name"] for r in SUPPORTED_REGIONS}
_SUPPORTED_CODES = set(_REGION_CODE_TO_NAME.keys())


def normalize_region(region: Optional[str]) -> str:
    """Validate and normalize a region code.

    Returns the uppercased code if it's supported, otherwise the default
    region. Never raises - an unknown/empty code degrades gracefully to the
    fallback so availability lookups never hard-fail on a typo.
    """
    if region:
        code = str(region).strip().upper()
        if code in _SUPPORTED_CODES:
            return code
    return DEFAULT_REGION


def is_supported_region(region: Optional[str]) -> bool:
    """Whether a region code is one BingeFinder explicitly supports."""
    return bool(region) and str(region).strip().upper() in _SUPPORTED_CODES


def get_region_name(region: Optional[str]) -> str:
    """Friendly country name for a region code (for user-facing messages).

    Falls back to "your region" so UIs can render a graceful message even
    for an unknown/absent code.
    """
    if is_supported_region(region):
        return _REGION_CODE_TO_NAME[region.strip().upper()]
    return "your region"


def region_options() -> List[Dict[str, str]]:
    """Ordered [{code, name}] list for the region selector UI."""
    return [{"code": r["code"], "name": r["name"]} for r in SUPPORTED_REGIONS]