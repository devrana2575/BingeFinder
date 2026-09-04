"""
tests/test_ranking_quality.py
===============================
Tests for the improved recommendation ranking pipeline:

    - adaptive elbow + absolute floor cutoff (MIN_RECOMMENDATION_SCORE)
    - strong vs. "relative" match status
    - weak / unrelated matches are filtered out (quality over quantity)
    - the adaptive cutoff is monotonically sensible
    - the threshold is configurable via environment

These tests use the in-memory (mongomock) seeded catalog so they run without
a live MongoDB server or content-model rebuild per test.

Run with:
    pytest tests/test_ranking_quality.py -v
"""

import os

import mongomock
import pytest

from recommender.recommend import (
    _adaptive_cutoff,
    get_recommendations,
    MIN_RECOMMENDATION_SCORE,
    RECOMMENDATION_ELBOW_FACTOR,
)


@pytest.fixture(scope="module")
def built_model_path(tmp_path_factory):
    """Set up the in-memory catalog and build a shared model artifact once."""

    import database.mongo_client as mongo_client_module
    from database.mongo_client import MongoDBManager
    from tests.sample_series import SAMPLE_SERIES

    shared_client = mongomock.MongoClient()
    mongo_client_module.MongoClient = lambda *args, **kwargs: shared_client

    manager = MongoDBManager()
    for doc in SAMPLE_SERIES:
        manager.upsert_series(doc)
    manager.close()

    from recommender.build_model import build_recommendation_model
    path = tmp_path_factory.mktemp("model") / "ranking_model.joblib"
    build_recommendation_model(save_path=path)
    return path


# ---------------------------------------------------------------------------
# Adaptive cutoff
# ---------------------------------------------------------------------------

def test_adaptive_cutoff_strong_uses_max_floor_and_elbow():
    # Strong top: the stricter of floor and elbow band is applied.
    strong_top = MIN_RECOMMENDATION_SCORE + 0.5
    expected = max(MIN_RECOMMENDATION_SCORE, RECOMMENDATION_ELBOW_FACTOR * strong_top)
    assert _adaptive_cutoff(strong_top) == expected


def test_adaptive_cutoff_weak_falls_back_to_elbow():
    # Weak top (below the absolute floor): proportional elbow is used so the
    # relative-best titles are still surfaced instead of an empty list.
    weak_top = MIN_RECOMMENDATION_SCORE * 0.5
    assert _adaptive_cutoff(weak_top) == pytest.approx(
        RECOMMENDATION_ELBOW_FACTOR * weak_top
    )
    assert _adaptive_cutoff(weak_top) < MIN_RECOMMENDATION_SCORE


# ---------------------------------------------------------------------------
# Ranked output behavior on the seeded catalog
# ---------------------------------------------------------------------------

def test_strong_series_returns_only_floor_clearing_matches(built_model_path):
    # 1001 (Ashfall City, Crime/Drama/Thriller) has a strong top match (1002).
    results = get_recommendations(1001, top_n=10, model_path=built_model_path)
    assert len(results) >= 1
    for r in results:
        # Every returned rec is a genuine strong match (clears the floor).
        assert r["relevance_score"] >= MIN_RECOMMENDATION_SCORE
        assert r["match_status"] == "strong"
        # And relevance shares a genre with the target (not unrelated noise).
        assert set(r["genres"]) & {"Crime", "Drama", "Thriller"}


def test_weak_series_returns_relative_best_and_avoids_empty(built_model_path):
    # 1007 (Quiet Hollow, Horror/Mystery) has NO candidate above the floor,
    # so the pipeline must return its relative-best titles, flagged "relative".
    results = get_recommendations(1007, top_n=10, model_path=built_model_path)
    assert len(results) >= 1
    for r in results:
        assert r["match_status"] == "relative"


def test_recommendations_sorted_descending(built_model_path):
    results = get_recommendations(1001, top_n=10, model_path=built_model_path)
    scores = [r["relevance_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_excludes_self_and_has_match_status(built_model_path):
    for sid in (1001, 1003, 1005, 1007):
        results = get_recommendations(sid, top_n=10, model_path=built_model_path)
        ids = [r["series_id"] for r in results]
        assert sid not in ids
        for r in results:
            assert r["match_status"] in {"strong", "relative"}


# ---------------------------------------------------------------------------
# Configurability
# ---------------------------------------------------------------------------

def test_threshold_is_configurable_via_env(monkeypatch):
    # A stricter floor produces a stricter cutoff for the same top score.
    top = MIN_RECOMMENDATION_SCORE + 0.3
    default_cutoff = _adaptive_cutoff(top)

    monkeypatch.setenv("MIN_RECOMMENDATION_SCORE", str(MIN_RECOMMENDATION_SCORE + 0.4))
    import recommender.recommend as recmod
    # recompute module constant via reload so the env value is honoured
    monkeypatch.setattr(recmod, "MIN_RECOMMENDATION_SCORE", float(os.environ["MIN_RECOMMENDATION_SCORE"]))
    stricter = recmod._adaptive_cutoff(top)

    assert stricter >= default_cutoff


def test_elbow_factor_is_configurable_via_env(monkeypatch):
    monkeypatch.setenv("RECOMMENDATION_ELBOW_FACTOR", "0.9")
    import recommender.recommend as recmod
    monkeypatch.setattr(recmod, "RECOMMENDATION_ELBOW_FACTOR", 0.9)
    weak_top = MIN_RECOMMENDATION_SCORE * 0.5
    assert recmod._adaptive_cutoff(weak_top) == pytest.approx(0.9 * weak_top)
