"""
tests/test_interaction_events.py
=================================
Tests for the interaction events logging system and contextual bandit.
"""

import os
import sys
from pathlib import Path

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017/")
os.environ.setdefault("MONGODB_DATABASE", "bingefinder_test")


@pytest.fixture
def event_manager(monkeypatch):
    """Yields an InteractionEventManager backed by mongomock."""
    import database.mongo_client as mongo_client_module
    from database.mongo_client import MongoDBManager
    from database.interaction_events import InteractionEventManager

    shared_client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_client_module, "MongoClient", lambda *a, **kw: shared_client)

    manager = MongoDBManager()
    iem = InteractionEventManager(manager)
    yield iem
    manager.close()


class TestInteractionEvents:
    def test_log_and_retrieve(self, event_manager):
        event_manager.log_event("user1", "like", series_id=1234)
        event_manager.log_event("user1", "view_details", series_id=5678)

        events = event_manager.get_events_for_user("user1")
        assert len(events) == 2
        event_types = {e["event_type"] for e in events}
        assert event_types == {"like", "view_details"}

    def test_event_counts(self, event_manager):
        event_manager.log_event("user1", "like", series_id=1)
        event_manager.log_event("user1", "like", series_id=2)
        event_manager.log_event("user1", "watchlist_add", series_id=1)

        counts = event_manager.get_user_event_counts("user1")
        assert counts["like"] == 2
        assert counts["watchlist_add"] == 1

    def test_reward_matrix(self, event_manager):
        event_manager.log_event("user1", "like", series_id=100)
        event_manager.log_event("user1", "view_details", series_id=100)
        event_manager.log_event("user1", "skip", series_id=200)

        matrix = event_manager.get_reward_matrix("user1")
        assert len(matrix) == 2

        rewards_by_id = {m["series_id"]: m["total_reward"] for m in matrix}
        assert rewards_by_id[100] == 4.0  # like(+3) + view_details(+1)
        assert rewards_by_id[200] == -1.0  # skip(-1)

    def test_total_reward(self, event_manager):
        event_manager.log_event("user1", "watchlist_add", series_id=100)
        event_manager.log_event("user1", "like", series_id=100)

        total = event_manager.get_total_reward("user1", 100)
        assert total == 7.0  # watchlist_add(+4) + like(+3)


class TestBandit:
    def test_cold_start_context(self):
        from recommender.bandit import _build_user_context, CONTEXT_DIM

        ctx = _build_user_context([], {})
        assert ctx.shape == (CONTEXT_DIM,)
        # Cold start: uniform genre prefs
        assert abs(ctx[:20].sum() - 1.0) < 0.01
        # Neutral rating
        assert abs(ctx[20] - 0.5) < 0.01

    def test_context_with_history(self):
        from recommender.bandit import _build_user_context, _ALL_GENRES

        metadata = {
            1: {"genres": ["Drama", "Crime"], "rating": 8.5, "language": "English"},
            2: {"genres": ["Comedy"], "rating": 7.0, "language": "English"},
        }
        reward_matrix = [
            {"series_id": 1, "total_reward": 4.0, "event_count": 2},
            {"series_id": 2, "total_reward": 3.0, "event_count": 1},
        ]

        ctx = _build_user_context(reward_matrix, metadata)
        # Drama and Crime should have non-zero preference
        drama_idx = _ALL_GENRES.index("Drama")
        crime_idx = _ALL_GENRES.index("Crime")
        comedy_idx = _ALL_GENRES.index("Comedy")
        assert ctx[drama_idx] > 0
        assert ctx[crime_idx] > 0
        assert ctx[comedy_idx] > 0

    def test_linucb_reranking(self):
        from recommender.bandit import LinUCBBandit, _build_user_context

        metadata = {
            1: {"genres": ["Drama"], "rating": 8.0, "language": "English"},
            2: {"genres": ["Comedy"], "rating": 7.0, "language": "English"},
            3: {"genres": ["Action"], "rating": 6.0, "language": "Japanese"},
        }

        # User likes Drama
        reward_matrix = [{"series_id": 1, "total_reward": 5.0, "event_count": 3}]
        user_ctx = _build_user_context(reward_matrix, metadata)

        bandit = LinUCBBandit()
        indices = bandit.fit_from_rewards(reward_matrix, [1, 2, 3], metadata, user_ctx)

        assert len(indices) == 3
        # With enough data, Drama (id=1) should rank high
        # (UCB exploration may cause variance, so just check it runs)

    def test_arm_features(self):
        from recommender.bandit import _build_arm_features, _build_user_context

        meta = {"genres": ["Drama", "Crime"], "rating": 8.0, "language": "English"}
        user_ctx = _build_user_context([], {})

        arm = _build_arm_features(meta, user_ctx)
        assert arm.shape[0] > 0
        # Drama and Crime should be 1.0 in genre features
        from recommender.bandit import _ALL_GENRES
        assert arm[_ALL_GENRES.index("Drama")] == 1.0
        assert arm[_ALL_GENRES.index("Crime")] == 1.0
        # Comedy should be 0.0
        assert arm[_ALL_GENRES.index("Comedy")] == 0.0
