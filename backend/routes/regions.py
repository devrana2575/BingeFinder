"""
backend/routes/regions.py
==========================
GET /regions — the list of streaming regions the product supports.
"""

from fastapi import APIRouter

from regions import get_region_name, normalize_region, region_options

router = APIRouter()


@router.get("/regions")
def list_regions():
    """Return the ordered [{code, name}] region options for the selector."""
    options = region_options()
    return {
        "regions": options,
        "default": normalize_region(None),
        "count": len(options),
    }


@router.get("/regions/{region}")
def resolve_region(region: str):
    """Resolve a region code to its friendly name (graceful fallback)."""
    code = normalize_region(region)
    return {"code": code, "name": get_region_name(code)}