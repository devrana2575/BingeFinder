"""
tests/test_auth.py
====================
Tests for user authentication: signup, login, logout, duplicate handling.

Run with:
    pytest tests/test_auth.py -v
"""

import pytest


def _get_user_manager(mongo_manager):
    """Create a UserManager backed by the test mongomock instance."""
    from database.users import UserManager
    return UserManager(mongo_manager)


def test_signup_success(seeded_mongo_manager):
    """Successful signup should return 'created'."""
    um = _get_user_manager(seeded_mongo_manager)
    result = um.create_user("Alice", "alice@test.com", "password123")
    assert result == "created"


def test_signup_duplicate_email(seeded_mongo_manager):
    """Signup with an existing email should return 'email_exists'."""
    um = _get_user_manager(seeded_mongo_manager)
    um.create_user("Alice", "dup@test.com", "password123")
    result = um.create_user("Alice2", "dup@test.com", "password456")
    assert result == "email_exists"


def test_login_success(seeded_mongo_manager):
    """Correct credentials should return user data."""
    um = _get_user_manager(seeded_mongo_manager)
    um.create_user("Bob", "bob@test.com", "secret123")

    user = um.authenticate_user("bob@test.com", "secret123")
    assert user is not None
    assert user["name"] == "Bob"
    assert user["email"] == "bob@test.com"
    assert "user_id" in user


def test_login_invalid_password(seeded_mongo_manager):
    """Wrong password should return None."""
    um = _get_user_manager(seeded_mongo_manager)
    um.create_user("Bob", "bob2@test.com", "secret123")

    user = um.authenticate_user("bob2@test.com", "wrongpassword")
    assert user is None


def test_login_nonexistent_email(seeded_mongo_manager):
    """Non-existent email should return None."""
    um = _get_user_manager(seeded_mongo_manager)
    user = um.authenticate_user("nobody@test.com", "password")
    assert user is None


def test_get_user_by_id(seeded_mongo_manager):
    """Looking up a user by ID should return their data."""
    um = _get_user_manager(seeded_mongo_manager)
    um.create_user("Carol", "carol@test.com", "pass1234")

    user = um.authenticate_user("carol@test.com", "pass1234")
    found = um.get_user_by_id(user["user_id"])

    assert found is not None
    assert found["name"] == "Carol"
    assert found["email"] == "carol@test.com"


def test_get_user_by_id_not_found(seeded_mongo_manager):
    """Looking up a non-existent user ID should return None."""
    um = _get_user_manager(seeded_mongo_manager)
    found = um.get_user_by_id("nonexistent_id_12345")
    assert found is None


def test_password_is_hashed(seeded_mongo_manager):
    """Stored password should be a bcrypt hash, not plain text."""
    um = _get_user_manager(seeded_mongo_manager)
    um.create_user("Dave", "dave@test.com", "mypassword")

    from database.users import USERS_COLLECTION_NAME
    raw_doc = um._collection.find_one({"email": "dave@test.com"})
    assert raw_doc["password_hash"] != "mypassword"
    assert raw_doc["password_hash"].startswith("$2")
