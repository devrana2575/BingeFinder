"""
tests/test_cold_start.py
==========================
Cold-start personalization: a user with no interaction history must receive
a quality/preference-aware pick (never an empty failure), with honest match
scores derived from real catalog data.
"""

from backend.services.rec_service import _cold_start_recommendations


def test_cold_start_returns_picks_for_new_user(seeded_mongo_manager):
    recs, err = _cold_start_recommendations("some-new-user-id", top_n=6)
    assert err is None
    assert isinstance(recs, list)
    assert len(recs) > 0
    for rec in recs:
        assert rec["series_id"]
        assert rec["title"]
        assert 0.0 <= rec["relevance_score"] <= 1.0
        # Posters must be absolute URLs (never frontend-relative paths);
        # a missing poster is a valid "no image" state, but a present image
        # must never be a bare relative path.
        assert rec["image"] is None or str(rec["image"]).startswith("http")


def test_cold_start_top_n_is_respected(seeded_mongo_manager):
    recs, _ = _cold_start_recommendations("some-new-user-id", top_n=3)
    assert len(recs) <= 3


def test_cold_start_with_genre_preferences_boosts_match(seeded_mongo_manager):
    from database.users import UserManager

    um = UserManager(seeded_mongo_manager)
    um.create_user("Cold", "cold@example.com", "password123")
    user_id = um.authenticate_user("cold@example.com", "password123")["user_id"]
    um.update_preferences(user_id, {"genres": ["Drama"]})

    recs, err = _cold_start_recommendations(user_id, top_n=6)
    assert err is None
    assert len(recs) > 0
    # The top pick should match the stated preference more than a random
    # title (genre-aware scoring keeps preference hits ranked highest).
    top_genres = recs[0]["genres"]
    assert "Drama" in top_genres
    assert recs[0]["relevance_score"] > 0.4