"""
tests/test_user_features.py
=============================
Tests for user-specific features: likes, recently viewed, personalized
recommendations, and user-specific watchlist isolation.

Run with:
    pytest tests/test_user_features.py -v
"""

import pytest

from recommender.build_model import build_recommendation_model


USER_A = "user_a_test"
USER_B = "user_b_test"


# --- Like tests ---

def test_like_and_unlike(seeded_mongo_manager):
    """Like a series, verify it, unlike it, verify removal."""
    from database.likes import LikesManager
    lm = LikesManager(seeded_mongo_manager)

    result = lm.like(USER_A, 1001)
    assert result == "liked"
    assert lm.is_liked(USER_A, 1001) is True

    result = lm.like(USER_A, 1001)
    assert result == "already_liked"

    result = lm.unlike(USER_A, 1001)
    assert result == "unliked"
    assert lm.is_liked(USER_A, 1001) is False

    result = lm.unlike(USER_A, 1001)
    assert result == "not_found"


def test_liked_series_per_user(seeded_mongo_manager):
    """Each user's likes should be independent."""
    from database.likes import LikesManager
    lm = LikesManager(seeded_mongo_manager)

    lm.like(USER_A, 1001)
    lm.like(USER_A, 1002)

    lm.like(USER_B, 1003)

    ids_a = lm.get_liked_series_ids(USER_A)
    ids_b = lm.get_liked_series_ids(USER_B)

    assert 1001 in ids_a
    assert 1002 in ids_a
    assert 1003 not in ids_a

    assert 1003 in ids_b
    assert 1001 not in ids_b


def test_liked_count(seeded_mongo_manager):
    """Liked count should reflect actual likes."""
    from database.likes import LikesManager
    lm = LikesManager(seeded_mongo_manager)

    assert lm.get_liked_count(USER_A) == 0
    lm.like(USER_A, 1001)
    assert lm.get_liked_count(USER_A) == 1
    lm.like(USER_A, 1002)
    assert lm.get_liked_count(USER_A) == 2
    lm.unlike(USER_A, 1001)
    assert lm.get_liked_count(USER_A) == 1


# --- Recently Viewed tests ---

def test_record_and_get_recently_viewed(seeded_mongo_manager):
    """Record views and retrieve them with limit."""
    from database.recently_viewed import RecentlyViewedManager
    rvm = RecentlyViewedManager(seeded_mongo_manager)

    rvm.record_view(USER_A, 1001)
    rvm.record_view(USER_A, 1002)
    rvm.record_view(USER_A, 1003)

    recent = rvm.get_recently_viewed(USER_A, limit=2)
    assert len(recent) == 2

    ids = [r["series_id"] for r in recent]
    assert all(i in [1001, 1002, 1003] for i in ids)
    assert len(set(ids)) == 2

    # Full list has all 3
    all_recent = rvm.get_recently_viewed(USER_A, limit=10)
    all_ids = [r["series_id"] for r in all_recent]
    assert 1001 in all_ids
    assert 1002 in all_ids
    assert 1003 in all_ids


def test_record_view_updates_timestamp(seeded_mongo_manager):
    """Recording the same series again should update its timestamp."""
    from database.recently_viewed import RecentlyViewedManager
    rvm = RecentlyViewedManager(seeded_mongo_manager)

    rvm.record_view(USER_A, 1001)
    rvm.record_view(USER_A, 1002)
    rvm.record_view(USER_A, 1001)  # re-view 1001

    recent = rvm.get_recently_viewed(USER_A, limit=2)
    ids = [r["series_id"] for r in recent]
    assert ids[0] == 1001
    assert ids[1] == 1002


def test_recently_viewed_per_user(seeded_mongo_manager):
    """Each user's recently viewed list should be independent."""
    from database.recently_viewed import RecentlyViewedManager
    rvm = RecentlyViewedManager(seeded_mongo_manager)

    rvm.record_view(USER_A, 1001)
    rvm.record_view(USER_B, 1003)

    recent_a = rvm.get_recently_viewed_ids(USER_A)
    recent_b = rvm.get_recently_viewed_ids(USER_B)

    assert 1001 in recent_a
    assert 1003 not in recent_a

    assert 1003 in recent_b
    assert 1001 not in recent_b


def test_recently_viewed_pruning(seeded_mongo_manager):
    """Should not exceed MAX_RECENTLY_VIEWED entries per user."""
    from database.recently_viewed import RecentlyViewedManager, MAX_RECENTLY_VIEWED
    rvm = RecentlyViewedManager(seeded_mongo_manager)

    for i in range(MAX_RECENTLY_VIEWED + 10):
        rvm.record_view(USER_A, 1000 + i)

    count = rvm._collection.count_documents({"user_id": USER_A})
    assert count <= MAX_RECENTLY_VIEWED


# --- Personalized recommendations ---

def test_personalized_recommendations(seeded_mongo_manager, model_path):
    """Personalized recs should return results based on user activity."""
    build_recommendation_model(save_path=model_path)

    from database.watchlist import WatchlistManager
    wl = WatchlistManager(seeded_mongo_manager)
    wl.add_to_watchlist(USER_A, 1001)

    from backend.services.rec_service import get_personalized_recommendations
    recs, err = get_personalized_recommendations(USER_A, top_n=5)

    assert err is None
    assert len(recs) > 0
    assert all(r["series_id"] != 1001 for r in recs)
    for r in recs:
        assert "relevance_score" in r


def test_personalized_recommendations_empty_history(seeded_mongo_manager, model_path):
    """User with no activity should get empty results (not an error)."""
    build_recommendation_model(save_path=model_path)

    from backend.services.rec_service import get_personalized_recommendations
    recs, err = get_personalized_recommendations("user_no_activity", top_n=5)

    assert err is None
    assert len(recs) == 0


def test_personalized_recommendations_with_likes(seeded_mongo_manager, model_path):
    """Likes should also feed into personalized recs."""
    build_recommendation_model(save_path=model_path)

    from database.likes import LikesManager
    lm = LikesManager(seeded_mongo_manager)
    lm.like(USER_A, 1003)  # Lightless Frontier (Sci-Fi)

    from backend.services.rec_service import get_personalized_recommendations
    recs, err = get_personalized_recommendations(USER_A, top_n=5)

    assert err is None
    assert len(recs) > 0
    # Should recommend sci-fi shows, not comedy
    rec_ids = [r["series_id"] for r in recs]
    assert 1003 not in rec_ids
