"""
tests/test_recommender.py
============================
Covers the Phase 3 requirements end-to-end:
    - model builds successfully
    - recommendations are returned
    - the selected series is excluded from its own recommendations
    - results are sorted by similarity
    - missing/incomplete data does not crash the system
    - an invalid series ID is handled (not a raw crash)
    - a saved model can be loaded back from disk

Run with:
    pytest tests/test_recommender.py -v
"""

import pytest

from recommender.build_model import build_recommendation_model
from recommender.exceptions import ModelNotBuiltError, SeriesNotFoundError
from recommender.recommend import get_recommendations, load_model


def _load_series():
    """Helper to get seeded series list from MongoDB."""
    from database.mongo_client import MongoDBManager
    manager = MongoDBManager()
    docs = manager.get_all_series()
    manager.close()
    return docs, None


def test_model_builds_successfully(seeded_mongo_manager, model_path):
    stats = build_recommendation_model(save_path=model_path)

    assert model_path.exists()
    # 9 sample docs; 1008 and 1009 have no usable text and are skipped.
    assert stats["total_in_db"] == 9
    assert stats["used"] == 7
    assert stats["skipped"] == 2
    assert stats["vocabulary_size"] > 0


def test_saved_model_can_be_loaded(seeded_mongo_manager, model_path):
    build_recommendation_model(save_path=model_path)

    bundle = load_model(model_path, force_reload=True)

    assert set(bundle.keys()) == {"vectorizer", "tfidf_matrix", "series_ids", "metadata", "built_at"}
    assert len(bundle["series_ids"]) == 7
    assert bundle["tfidf_matrix"].shape[0] == 7


def test_recommendations_are_returned_and_exclude_self(seeded_mongo_manager, model_path):
    build_recommendation_model(save_path=model_path)

    results = get_recommendations(1001, top_n=5, model_path=model_path)

    assert len(results) > 0
    assert all(r["series_id"] != 1001 for r in results)
    for r in results:
        assert set(r.keys()) == {"series_id", "title", "rating", "genres", "image", "similarity_score"}


def test_recommendations_are_sorted_by_similarity(seeded_mongo_manager, model_path):
    build_recommendation_model(save_path=model_path)

    results = get_recommendations(1001, top_n=10, model_path=model_path)

    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_similar_crime_shows_rank_above_unrelated_genres(seeded_mongo_manager, model_path):
    # 1001 (Ashfall City, Crime/Drama/Thriller) should rank 1002
    # (Harborline, Crime/Drama, shared cast member) above 1005
    # (The Bakeshop on Third, Comedy/Romance).
    build_recommendation_model(save_path=model_path)

    results = get_recommendations(1001, top_n=10, model_path=model_path)
    ids_in_order = [r["series_id"] for r in results]

    assert ids_in_order.index(1002) < ids_in_order.index(1005)


def test_missing_data_does_not_crash_build_or_recommend(seeded_mongo_manager, model_path):
    # 1008 has every optional field set to None/[]/empty and must not
    # crash the build. It has no usable text, so it's skipped and won't
    # appear in the model at all.
    stats = build_recommendation_model(save_path=model_path)
    assert stats["used"] == 7

    # 1007 (Quiet Hollow) has cast=None, network=None, web_channel=None,
    # image fields=None -- must still produce recommendations safely.
    results = get_recommendations(1007, top_n=5, model_path=model_path)
    assert isinstance(results, list)


def test_invalid_series_id_is_handled(seeded_mongo_manager, model_path):
    build_recommendation_model(save_path=model_path)

    with pytest.raises(SeriesNotFoundError):
        get_recommendations(999999, top_n=5, model_path=model_path)


def test_recommend_before_build_is_handled(model_path):
    # model_path points at a file that doesn't exist yet.
    with pytest.raises(ModelNotBuiltError):
        get_recommendations(1001, top_n=5, model_path=model_path)


# --- Search / discovery tests ---

def test_filter_series_exact_match_priority(seeded_mongo_manager):
    """Exact title match should rank above partial matches."""
    from ui.data_access import filter_series
    docs, _ = _load_series()
    # "Harborline" should be first when searching for "Harborline"
    results = filter_series(docs, query="Harborline")
    assert len(results) > 0
    assert results[0].get("name") == "Harborline"

def test_filter_series_partial_match(seeded_mongo_manager):
    """Partial query should return all matching series."""
    from ui.data_access import filter_series
    docs, _ = _load_series()
    # Search for a term that appears in multiple titles
    results = filter_series(docs, query="Horizon")
    names = [d.get("name") for d in results]
    assert any("Horizon" in (n or "") for n in names)

def test_filter_series_no_match():
    """Query matching nothing should return empty list."""
    from ui.data_access import filter_series
    docs = []
    results = filter_series(docs, query="Nonexistent")
    assert results == []

def test_hidden_gems_from_catalog(seeded_mongo_manager):
    """Hidden gems should prefer highly-rated, less-popular series."""
    from ui.data_access import get_hidden_gems
    docs, _ = _load_series()
    gems = get_hidden_gems(docs, limit=5)
    assert isinstance(gems, list)
    # All gems should have a rating >= 7.5
    for g in gems:
        assert g.get("rating") >= 7.5

# --- Watchlist tests ---

TEST_USER_ID = "test_user_001"
TEST_USER_ID_B = "test_user_002"

def test_watchlist_add_and_remove(seeded_mongo_manager):
    """Add and remove a series from a user's watchlist."""
    from database.watchlist import WatchlistManager
    wl = WatchlistManager(seeded_mongo_manager)

    result = wl.add_to_watchlist(TEST_USER_ID, 1001)
    assert result == "added"

    assert wl.is_in_watchlist(TEST_USER_ID, 1001) is True

    result = wl.add_to_watchlist(TEST_USER_ID, 1001)
    assert result == "already_exists"

    result = wl.remove_from_watchlist(TEST_USER_ID, 1001)
    assert result == "removed"

    assert wl.is_in_watchlist(TEST_USER_ID, 1001) is False

    result = wl.remove_from_watchlist(TEST_USER_ID, 1001)
    assert result == "not_found"

def test_watchlist_get_all(seeded_mongo_manager):
    """Get watchlist should return items sorted by added_at."""
    from database.watchlist import WatchlistManager
    wl = WatchlistManager(seeded_mongo_manager)

    wl.add_to_watchlist(TEST_USER_ID, 1001)
    wl.add_to_watchlist(TEST_USER_ID, 1002)
    wl.add_to_watchlist(TEST_USER_ID, 1003)

    items = wl.get_watchlist(TEST_USER_ID)
    assert len(items) == 3
    ids = [item["tvmaze_id"] for item in items]
    assert 1001 in ids
    assert 1002 in ids
    assert 1003 in ids

def test_watchlist_count(seeded_mongo_manager):
    """Watchlist count should reflect actual items."""
    from database.watchlist import WatchlistManager
    wl = WatchlistManager(seeded_mongo_manager)

    assert wl.get_watchlist_count(TEST_USER_ID) == 0
    wl.add_to_watchlist(TEST_USER_ID, 1001)
    assert wl.get_watchlist_count(TEST_USER_ID) == 1
    wl.remove_from_watchlist(TEST_USER_ID, 1001)
    assert wl.get_watchlist_count(TEST_USER_ID) == 0

def test_user_watchlist_isolation(seeded_mongo_manager):
    """User A's watchlist must not appear in User B's watchlist."""
    from database.watchlist import WatchlistManager
    wl = WatchlistManager(seeded_mongo_manager)

    wl.add_to_watchlist(TEST_USER_ID, 1001)
    wl.add_to_watchlist(TEST_USER_ID, 1002)

    wl.add_to_watchlist(TEST_USER_ID_B, 1003)

    items_a = wl.get_watchlist(TEST_USER_ID)
    items_b = wl.get_watchlist(TEST_USER_ID_B)

    ids_a = [item["tvmaze_id"] for item in items_a]
    ids_b = [item["tvmaze_id"] for item in items_b]

    assert 1001 in ids_a
    assert 1002 in ids_a
    assert 1003 not in ids_a

    assert 1003 in ids_b
    assert 1001 not in ids_b
    assert 1002 not in ids_b

# --- Preprocessing tests ---

def test_content_soup_includes_title(seeded_mongo_manager):
    """Content soup should include the series name."""
    from recommender.preprocess import build_content_soup
    docs, _ = _load_series()
    doc = next(d for d in docs if d.get("tvmaze_id") == 1001)
    soup = build_content_soup(doc)
    assert "Ashfall City" in soup

def test_content_soup_handles_missing_name():
    """Content soup should handle missing name gracefully."""
    from recommender.preprocess import build_content_soup
    doc = {"summary": "A show about things", "genres": ["Drama"]}
    soup = build_content_soup(doc)
    assert "A show about things" in soup

def test_content_soup_handles_empty_doc():
    """Empty doc should return empty string."""
    from recommender.preprocess import build_content_soup
    assert build_content_soup({}) == ""

# --- Recommendation quality tests ---

def test_recommendations_with_title_in_soup(seeded_mongo_manager, model_path):
    """Model built with title in soup should still produce valid recommendations."""
    build_recommendation_model(save_path=model_path)
    results = get_recommendations(1003, top_n=3, model_path=model_path)
    assert len(results) > 0
    for r in results:
        assert r["series_id"] != 1003
        assert 0.0 <= r["similarity_score"] <= 1.0

# --- UI import test ---

def test_ui_modules_importable():
    """All UI modules should be importable without Streamlit."""
    import importlib
    # These should not crash even without Streamlit running
    importlib.import_module("ui.explain")
    importlib.import_module("ui.vibes")
