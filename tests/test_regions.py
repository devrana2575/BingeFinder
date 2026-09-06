"""
tests/test_regions.py
======================
Tests for the shared regions module and the /api/regions endpoint.
"""

import pytest

from regions import (
    DEFAULT_REGION,
    SUPPORTED_REGIONS,
    get_region_name,
    is_supported_region,
    normalize_region,
    region_options,
)


def test_supported_regions_have_unique_codes_and_names():
    codes = [r["code"] for r in SUPPORTED_REGIONS]
    names = [r["name"] for r in SUPPORTED_REGIONS]
    assert len(codes) == len(set(codes))
    assert all(c.isupper() and c.isalpha() and len(c) == 2 for c in codes)
    assert len(names) == len(set(names))
    assert all(n and n.strip() for n in names)


def test_includes_all_major_markets():
    codes = {r["code"] for r in SUPPORTED_REGIONS}
    for expected in ("IN", "US", "GB", "CA", "AU", "DE", "BR", "JP", "KR", "FR"):
        assert expected in codes


def test_region_options_are_selector_ready():
    opts = region_options()
    assert opts == [
        {"code": r["code"], "name": r["name"]} for r in SUPPORTED_REGIONS
    ]


def test_normalize_region_passthrough_and_fallback():
    assert normalize_region("in") == "IN"
    assert normalize_region(" In ") == "IN"
    assert normalize_region("US") == "US"
    assert normalize_region(None) == DEFAULT_REGION
    assert normalize_region("") == DEFAULT_REGION
    assert normalize_region("ZZ") == DEFAULT_REGION


def test_is_supported_region():
    assert is_supported_region("IN") is True
    assert is_supported_region("in") is True
    assert is_supported_region(None) is False
    assert is_supported_region("ZZ") is False


def test_get_region_name():
    assert get_region_name("IN") == "India"
    assert get_region_name("US") == "United States"
    # Graceful fallback for unknown codes - never raises.
    assert get_region_name("ZZ") == "your region"
    assert get_region_name(None) == "your region"


def test_json_regions_endpoint():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    resp = client.get("/api/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == len(SUPPORTED_REGIONS)
    assert data["default"] == DEFAULT_REGION
    assert data["regions"][0]["code"] == "US"

    resolve = client.get("/api/regions/in")
    assert resolve.status_code == 200
    assert resolve.json() == {"code": "IN", "name": "India"}