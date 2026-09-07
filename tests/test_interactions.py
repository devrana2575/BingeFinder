"""
tests/test_interactions.py
=============================
Tests for the unified LIKE / LOVE / NOT-FOR-ME (dislike) reaction model.
"""

import pytest


USER_A = "user_a_interact"
USER_B = "user_b_interact"


def test_set_like_and_clear(seeded_mongo_manager):
    """Set a like, verify it, clear it, verify removal."""
    from database.interactions import InteractionManager

    im = InteractionManager(seeded_mongo_manager)

    assert im.set_reaction(USER_A, 1001, "like") == "set"
    assert im.get_reaction(USER_A, 1001) == "like"

    assert im.clear_reaction(USER_A, 1001) == "cleared"
    assert im.get_reaction(USER_A, 1001) is None

    assert im.clear_reaction(USER_A, 1001) == "not_found"


def test_reaction_overwrites_not_duplicates(seeded_mongo_manager):
    """Setting a second reaction should overwrite the first, not duplicate."""
    from database.interactions import InteractionManager
    from database.interactions import INTERACTIONS_COLLECTION_NAME

    im = InteractionManager(seeded_mongo_manager)

    im.set_reaction(USER_A, 1001, "like")
    im.set_reaction(USER_A, 1001, "love")

    doc = seeded_mongo_manager._db[INTERACTIONS_COLLECTION_NAME].find_one(
        {"user_id": USER_A, "series_id": 1001}
    )
    assert doc["reaction"] == "love"

    # Unique index guarantees a single document per (user, series).
    count = seeded_mongo_manager._db[INTERACTIONS_COLLECTION_NAME].count_documents(
        {"user_id": USER_A, "series_id": 1001}
    )
    assert count == 1


def test_invalid_reaction_rejected(seeded_mongo_manager):
    """Unknown reactions raise ValueError and are never stored."""
    from database.interactions import InteractionManager

    im = InteractionManager(seeded_mongo_manager)

    with pytest.raises(ValueError):
        im.set_reaction(USER_A, 1001, "superlike")

    assert im.get_reaction(USER_A, 1001) is None


def test_reactions_are_per_user(seeded_mongo_manager):
    """Reactions must be isolated per user."""
    from database.interactions import InteractionManager

    im = InteractionManager(seeded_mongo_manager)

    im.set_reaction(USER_A, 1001, "love")
    im.set_reaction(USER_A, 1002, "dislike")
    im.set_reaction(USER_B, 1003, "like")

    assert im.get_reaction(USER_A, 1001) == "love"
    assert im.get_reaction(USER_A, 1002) == "dislike"
    assert im.get_reaction(USER_A, 1003) is None

    assert im.get_reaction(USER_B, 1003) == "like"
    assert im.get_reaction(USER_B, 1001) is None


def test_reaction_map_and_filters(seeded_mongo_manager):
    """Reaction map / filters should respect the reaction type."""
    from database.interactions import InteractionManager

    im = InteractionManager(seeded_mongo_manager)

    im.set_reaction(USER_A, 1001, "love")
    im.set_reaction(USER_A, 1002, "like")
    im.set_reaction(USER_A, 1003, "dislike")

    rmap = im.get_reaction_map(USER_A)
    assert rmap == {1001: "love", 1002: "like", 1003: "dislike"}

    assert im.get_series_with_reaction(USER_A, "love") == [1001]
    assert im.get_series_with_reaction(USER_A, "like") == [1002]
    assert im.get_series_with_reaction(USER_A, "dislike") == [1003]


def test_reaction_weights_ordering(seeded_mongo_manager):
    """Love must outweigh like; dislike must be negative."""
    from database.interactions import (
        REACTION_WEIGHTS,
        REACTION_LOVE,
        REACTION_LIKE,
        REACTION_DISLIKE,
    )

    assert REACTION_WEIGHTS[REACTION_LOVE] > REACTION_WEIGHTS[REACTION_LIKE] > 0
    assert REACTION_WEIGHTS[REACTION_DISLIKE] < 0