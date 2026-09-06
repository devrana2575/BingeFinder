"""
tests/test_settings.py
========================
User settings/preferences persistence (region, languages, genres).
"""

from database.users import UserManager
from backend.services.user_service import update_settings, get_settings


def test_preferences_roundtrip(seeded_mongo_manager):
    um = UserManager(seeded_mongo_manager)
    um.create_user("Alice", "alice@example.com", "password123")

    user = um.authenticate_user("alice@example.com", "password123")
    assert user is not None
    user_id = user["user_id"]

    # Fresh user: no preferences yet.
    assert um.get_preferences(user_id) == {}
    assert user.get("preferences") == {}

    ok = um.update_preferences(user_id, {
        "region": "DE", "languages": ["German", "English"], "genres": ["Drama", "Crime"],
    })
    assert ok is True
    assert um.get_preferences(user_id) == {
        "region": "DE", "languages": ["German", "English"], "genres": ["Drama", "Crime"],
    }


def test_preferences_merge_is_partial(seeded_mongo_manager):
    um = UserManager(seeded_mongo_manager)
    um.create_user("Bob", "bob@example.com", "password456")
    bob_id = um.authenticate_user("bob@example.com", "password456")["user_id"]

    ok, err = update_settings(bob_id, {"region": "IN"})
    assert ok and err is None
    ok, err = update_settings(bob_id, {"languages": ["Hindi"]})
    assert ok and err is None

    stored, _ = get_settings(bob_id)
    assert stored["region"] == "IN"
    assert stored["languages"] == ["Hindi"]


def test_get_settings_for_unknown_user_is_empty(seeded_mongo_manager):
    stored, err = get_settings("does-not-exist")
    assert stored == {}
    assert err is None


def test_create_user_stores_empty_preferences(seeded_mongo_manager):
    um = UserManager(seeded_mongo_manager)
    um.create_user("Carol", "carol@example.com", "password789")
    doc = {}
    from database.mongo_client import MongoDBManager
    raw = seeded_mongo_manager._db["users"].find_one({"email": "carol@example.com"})
    assert raw is not None
    assert raw.get("preferences") is None or raw.get("preferences") == {}
    assert raw["password_hash"]


def test_authenticate_returns_preferences(seeded_mongo_manager):
    um = UserManager(seeded_mongo_manager)
    um.create_user("Dave", "dave@example.com", "passwordabc")
    um.update_preferences(
        um.authenticate_user("dave@example.com", "passwordabc")["user_id"],
        {"region": "JP"},
    )
    user = um.authenticate_user("dave@example.com", "passwordabc")
    assert user["preferences"]["region"] == "JP"