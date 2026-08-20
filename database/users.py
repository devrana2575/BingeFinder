"""
database/users.py
==================
User account management backed by MongoDB.

Design notes:
    - Passwords are hashed with bcrypt before storage.
    - A unique index on ``email`` prevents duplicate registrations.
    - User IDs are UUID4 hex strings (no sequential leaking).
    - The module reuses the existing ``MongoDBManager`` connection.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bcrypt
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

USERS_COLLECTION_NAME = "users"


class UserManager:
    """
    Manages user accounts in the ``users`` collection.

    Usage:
        mongo_manager = MongoDBManager()
        um = UserManager(mongo_manager)
        um.create_user("Alice", "alice@example.com", "secret123")
        user = um.authenticate_user("alice@example.com", "secret123")
    """

    def __init__(self, mongo_manager: MongoDBManager, bcrypt_rounds: int = 12) -> None:
        """
        Store a reference to the ``MongoDBManager`` and grab the users
        collection.  Creates a unique index on ``email`` (idempotent).

        Args:
            mongo_manager: An already-initialised ``MongoDBManager``.
            bcrypt_rounds: Number of bcrypt cost rounds (default 12).
        """
        self._mongo = mongo_manager
        self._bcrypt_rounds = bcrypt_rounds
        try:
            self._collection: Collection = mongo_manager._db[USERS_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access users collection: %s", exc)
            raise MongoDatabaseError(f"Failed to access users collection: {exc}") from exc

        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create a unique index on ``email`` (idempotent)."""
        try:
            self._collection.create_index(
                "email", unique=True, name="uniq_users_email"
            )
        except PyMongoError as exc:
            logger.error("Failed to create unique index on users.email: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create unique index on users.email: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password with bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _check_password(password: str, password_hash: str) -> bool:
        """Verify a password against a bcrypt hash."""
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_user(self, name: str, email: str, password: str) -> str:
        """
        Register a new user.

        Args:
            name: Display name.
            email: Email address (used as login identifier).
            password: Plain-text password (hashed before storage).

        Returns:
            ``"created"`` on success, or ``"email_exists"`` if the
            email is already registered.

        Raises:
            MongoDatabaseError: If the insert fails for a reason other
                than a duplicate key.
        """
        document = {
            "user_id": uuid.uuid4().hex,
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": self._hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self._collection.insert_one(document)
            logger.info("Created user %s (%s).", document["user_id"], document["email"])
            return "created"
        except PyMongoError as exc:
            if exc.code == 11000:
                logger.info("Email %s already registered.", email)
                return "email_exists"
            logger.error("Failed to create user %s: %s", email, exc)
            raise MongoDatabaseError(
                f"Failed to create user: {exc}"
            ) from exc

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify credentials and return user info.

        Args:
            email: Email address.
            password: Plain-text password.

        Returns:
            A dict with ``user_id``, ``name``, ``email`` on success,
            or ``None`` if credentials are invalid.
        """
        try:
            doc = self._collection.find_one({"email": email.strip().lower()})
        except PyMongoError as exc:
            logger.error("Failed to look up user %s: %s", email, exc)
            raise MongoDatabaseError(f"Failed to look up user: {exc}") from exc

        if doc is None:
            return None

        if not self._check_password(password, doc["password_hash"]):
            return None

        return {
            "user_id": doc["user_id"],
            "name": doc["name"],
            "email": doc["email"],
        }

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up a user by their ``user_id``.

        Returns:
            A dict with ``user_id``, ``name``, ``email``, ``created_at``,
            or ``None`` if not found.
        """
        try:
            doc = self._collection.find_one({"user_id": user_id})
        except PyMongoError as exc:
            logger.error("Failed to look up user %s: %s", user_id, exc)
            return None

        if doc is None:
            return None

        return {
            "user_id": doc["user_id"],
            "name": doc["name"],
            "email": doc["email"],
            "created_at": doc.get("created_at"),
        }
