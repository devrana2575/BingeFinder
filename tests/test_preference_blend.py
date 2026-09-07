"""
tests/test_preference_blend.py
================================
Verifies that explicitly-stated genre preferences (from the onboarding quiz)
bias the personalized recommendation hybrid score, so fresh users with few
interactions still get taste-aligned picks — while the ranking stays untouched
when no preferences have been provided (nothing is ever guessed/fabricated).
"""

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from database.interactions import InteractionManager
from database.users import UserManager


def _make_bundle():
    """A tiny synthetic model bundle.

    The three candidates (Drama/Comedy/Crime) are deliberately identical on
    every content + quality axis (orthogonal to the interacted series, equal
    rating), so the ONLY signal distinguishing them is the genre component.
    """
    tfidf_matrix = csr_matrix(
        [
            [1, 0, 0, 0],  # 1: Alpha Drama
            [0, 1, 0, 0],  # 2: Beta Comedy
            [0, 0, 1, 0],  # 3: Gamma Crime
            [0, 0, 0, 1],  # 4: Omega SciFi (interacted series)
        ],
        dtype=np.float32,
    )

    ortho = 1.0 / np.sqrt(2)
    semantic_embeddings = np.array(
        [
            [0.0, ortho, ortho],  # candidates share an embedding ...
            [0.0, ortho, ortho],
            [0.0, ortho, ortho],
            [1.0, 0.0, 0.0],  # ... orthogonal to the user vector
        ],
        dtype=np.float32,
    )

    def _meta(name, genres):
        return {
            "title": name,
            "rating": 8.0,
            "genres": list(genres),
            "genres_set": set(genres),
            "image": None,
            "channel_names": [],
        }

    return {
        "series_ids": [1, 2, 3, 4],
        "tfidf_matrix": tfidf_matrix,
        "semantic_embeddings": semantic_embeddings,
        "metadata": {
            1: _meta("Alpha Drama", ["Drama"]),
            2: _meta("Beta Comedy", ["Comedy"]),
            3: _meta("Gamma Crime", ["Crime"]),
            4: _meta("Omega SciFi", ["Science-Fiction"]),
        },
    }


def _prepare_user(manager, name, email, password, prefs, reacted_series):
    um = UserManager(manager)
    um.create_user(name, email, password)
    user_id = um.authenticate_user(email, password)["user_id"]
    if prefs:
        um.update_preferences(user_id, prefs)
    im = InteractionManager(manager)
    im.set_reaction(user_id, reacted_series, "love")
    return user_id


@pytest.fixture
def _synthetic_model(monkeypatch):
    """Swap the recommendation model + keep a handle to patch internals."""
    import recommender.recommend as rec_module

    bundle = _make_bundle()
    monkeypatch.setattr(rec_module, "load_model", lambda *a, **k: bundle)
    return rec_module


def _capture_hybrid(monkeypatch, _synthetic_model):
    """Patch _rank_and_filter to record the hybrid scores it receives."""
    captured = {}
    real = _synthetic_model._rank_and_filter

    def recorder(hybrid, candidate_rows, series_ids, metadata, **kwargs):
        captured["hybrid"] = hybrid.copy()
        captured["candidate_rows"] = candidate_rows.copy()
        return real(hybrid, candidate_rows, series_ids, metadata, **kwargs)

    monkeypatch.setattr(_synthetic_model, "_rank_and_filter", recorder)
    return captured


def test_genre_preferences_rank_taste_aligned_title_first(
    seeded_mongo_manager, _synthetic_model, monkeypatch
):
    from backend.services.rec_service import get_personalized_recommendations

    user_id = _prepare_user(
        seeded_mongo_manager,
        "Pref User", "pref@example.com", "password123",
        prefs={"genres": ["Drama"]},
        reacted_series=4,
    )
    captured = _capture_hybrid(monkeypatch, _synthetic_model)

    recs, err = get_personalized_recommendations(user_id, top_n=5)

    assert err is None
    assert len(recs) > 0
    assert recs[0]["series_id"] == 1  # Alpha Drama first thanks to the genre blend

    rows = captured["candidate_rows"]
    assert list(rows) == [0, 1, 2]
    hybrid = captured["hybrid"]
    # Drama is boosted by W_GENRE(0.2) * jaccard(1.0) over Comedy/Crime while
    # every content + quality component is equal.
    assert hybrid[0] > hybrid[1]
    assert hybrid[0] - hybrid[1] >= 0.19


def test_no_preferences_leaves_genre_signal_neutral(
    seeded_mongo_manager, _synthetic_model, monkeypatch
):
    from backend.services.rec_service import get_personalized_recommendations

    user_id = _prepare_user(
        seeded_mongo_manager,
        "Blank User", "blank@example.com", "password456",
        prefs=None,
        reacted_series=4,
    )
    captured = _capture_hybrid(monkeypatch, _synthetic_model)

    recs, err = get_personalized_recommendations(user_id, top_n=5)

    assert err is None
    hybrid = captured["hybrid"]
    # Without stated preferences no candidate benefits from the genre
    # component, so identically-scored candidates keep identical scores.
    assert float(hybrid[0]) == pytest.approx(float(hybrid[1]), abs=1e-6)
    assert float(hybrid[1]) == pytest.approx(float(hybrid[2]), abs=1e-6)