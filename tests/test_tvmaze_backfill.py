"""
tests/test_tvmaze_backfill.py
===============================
Tests for the keyless TVMaze catalog backfill module.
Uses an in-memory mongomock manager (no seeded docs) and a fake page
fetcher so no real network or MongoDB server is required.
"""

import mongomock
import pytest


def _raw_row(n, **overrides):
    """A realistic raw TVMaze show dict, matching the API's field names."""
    row = {
        "id": n,
        "name": f"Show {n}",
        "summary": "<p>A <b>summary</b> for show %d.</p>" % n,
        "genres": ["Drama"],
        "rating": {"average": 7.5},
        "language": "English",
        "premiered": "2020-01-01",
        "ended": None,
        "status": "Running",
        "runtime": 60,
        "averageRuntime": 45,
        "weight": 80,
        "updated": 1600000000,
        "image": {
            "medium": f"https://static.tvmaze.com/uploads/medium/{n}.jpg",
            "original": f"https://static.tvmaze.com/uploads/original/{n}.jpg",
        },
        "officialSite": f"https://show{n}.example.com",
        "network": {"id": 1, "name": "Example", "country": {"name": "United States", "code": "US"}},
        "web_channel": None,
        "externals": {"imdb": f"tt{n:05d}", "thetvdb": n},
    }
    row.update(overrides)
    return row


@pytest.fixture
def backfill_manager(monkeypatch):
    """A MongoDBManager backed by a fresh, EMPTY in-memory mongomock store."""
    import database.mongo_client as mongo_client_module

    shared_client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_client_module, "MongoClient", lambda *args, **kwargs: shared_client)

    from database.mongo_client import MongoDBManager

    manager = MongoDBManager()
    yield manager
    manager.close()


class FakeFetcher:
    """Return canned TVMaze index pages keyed by page number."""

    def __init__(self, pages):
        self._pages = pages  # {page_number: [rows]}

    def __call__(self, page):
        return self._pages.get(page, [])


def test_normalize_tvmaze_row_maps_fields():
    from backend.services.tvmaze_backfill import normalize_tvmaze_row

    doc = normalize_tvmaze_row(_raw_row(123))
    assert doc["series_id"] == 123
    assert doc["name"] == "Show 123"
    # Summary HTML is stripped to plain text.
    assert "<p>" not in doc["summary"] and "<b>" not in doc["summary"]
    assert "summary for show 123" in doc["summary"]
    assert doc["genres"] == ["Drama"]
    assert doc["rating"] == 7.5
    assert doc["weight"] == 80
    assert doc["image_medium"].startswith("https://static.tvmaze.com/uploads/medium/")
    assert doc["image_original"].startswith("https://static.tvmaze.com/uploads/original/")
    assert doc["network"]["name"] == "Example"
    assert doc["imdb_id"] == "tt00123"
    assert doc["thetvdb_id"] == 123
    # No invented cast.
    assert doc["cast"] == []
    assert doc["catalog_source"] == "tvmaze"


def test_ingest_rows_inserts_once_and_updates_duplicates(backfill_manager):
    from backend.services.tvmaze_backfill import ingest_rows

    rows = [_raw_row(1)]
    counts = ingest_rows(backfill_manager, rows)
    assert counts["inserted"] == 1
    assert backfill_manager.series.find_one({"series_id": 1})["name"] == "Show 1"

    # Re-ingesting an existing id updates in place, never duplicates.
    rows[0]["name"] = "Show 1 (Updated)"
    counts = ingest_rows(backfill_manager, rows)
    assert counts["updated"] == 1
    assert backfill_manager.series.count_documents({"series_id": 1}) == 1
    assert backfill_manager.series.find_one({"series_id": 1})["name"] == "Show 1 (Updated)"


def test_ingest_skips_rows_without_image_or_name(backfill_manager):
    from backend.services.tvmaze_backfill import ingest_rows

    rows = [
        _raw_row(1, image=None),          # no image -> skip (cards need one)
        {"id": 2, "name": None},          # no name -> skip
        {"name": "No id"},                # no id -> skip
    ]
    counts = ingest_rows(backfill_manager, rows)
    assert counts["skipped"] == 3
    assert backfill_manager.series.count_documents({}) == 0


def test_ingest_applies_min_weight(backfill_manager):
    from backend.services.tvmaze_backfill import ingest_rows

    rows = [_raw_row(1, weight=10), _raw_row(2, weight=50)]
    counts = ingest_rows(backfill_manager, rows, min_weight=25)
    assert counts["inserted"] == 1
    assert backfill_manager.series.find_one({})["weight"] == 50


def test_run_backfill_scans_pages_and_stops_at_max_new(backfill_manager):
    from backend.services.tvmaze_backfill import run_backfill

    fetcher = FakeFetcher({0: [_raw_row(1)], 1: [_raw_row(2), _raw_row(3)], 2: []})
    summary = run_backfill(
        start_page=0,
        pages=5,
        max_new=2,
        sleep_seconds=0,
        manager=backfill_manager,
        fetcher=fetcher,
    )
    # Page 0 inserts 1 (below max_new=2), page 1 inserts 2 more, crossing the
    # cap before page 2 (empty) is reached. The cap bounds, not truncates, a run.
    assert summary["total_inserted"] == 3
    assert backfill_manager.series.count_documents({}) == 3


def test_run_backfill_skips_existing_ids_on_rerun(backfill_manager):
    rows = [_raw_row(1)]
    fetcher = FakeFetcher({0: rows})
    from backend.services.tvmaze_backfill import run_backfill

    first = run_backfill(start_page=0, pages=3, max_new=100, sleep_seconds=0,
                         manager=backfill_manager, fetcher=fetcher)
    assert first["total_inserted"] == 1
    second = run_backfill(start_page=0, pages=3, max_new=100, sleep_seconds=0,
                          manager=backfill_manager, fetcher=fetcher)
    assert second["total_inserted"] == 0
    assert backfill_manager.series.count_documents({}) == 1
