"""
tests/test_posters.py
=====================
Regression tests for poster image URLs.

Stored image paths can be relative (/<hash>.jpg) or already-absolute. The
API must always hand the UI a fully-qualified image URL so cards render in
the browser (the frontend origin must never prefix a TMDb CDN path).
"""

from api.tmdb import build_image_url, build_poster_url
from backend.routes.series import _doc_to_summary, _doc_to_detail
from backend.routes.users import _doc_to_summary as user_summary


def test_build_image_url_wraps_relative_path():
    url = build_image_url("/abc123.jpg", "w500")
    assert url == "https://image.tmdb.org/t/p/w500/abc123.jpg"


def test_build_image_url_passes_absolute_urls_through():
    url = build_image_url("https://example.com/full/cover.jpg", "w500")
    assert url == "https://example.com/full/cover.jpg"


def test_build_image_url_none_safe():
    assert build_image_url(None, "w500") is None
    assert build_image_url("", "w500") is None


def test_build_poster_url_default_size():
    assert build_poster_url("/abc123.jpg") == "https://image.tmdb.org/t/p/w500/abc123.jpg"


def _doc_with_relative_image():
    return {
        "series_id": 1001,
        "name": "Ashfall City",
        "original_name": "Ashfall City",
        "rating": 8.2,
        "genres": ["Drama"],
        "language": "Korean",
        "premiered": "2022-06-01",
        "status": "Ended",
        "image_medium": "/relative_medium.jpg",
        "image_original": "/relative_original.jpg",
    }


def test_series_summary_image_is_absolute():
    summary = _doc_to_summary(_doc_with_relative_image())
    assert summary.image == "https://image.tmdb.org/t/p/w500/relative_medium.jpg"


def test_series_detail_image_is_absolute():
    detail = _doc_to_detail(_doc_with_relative_image())
    assert detail.image == "https://image.tmdb.org/t/p/w500/relative_original.jpg"


def test_user_summary_image_is_absolute():
    summary = user_summary(_doc_with_relative_image())
    assert summary.image == "https://image.tmdb.org/t/p/w500/relative_medium.jpg"
    assert summary.image.startswith("https://image.tmdb.org/")