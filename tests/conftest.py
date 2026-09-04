"""
tests/conftest.py
====================
Shared pytest fixtures for recommender tests.

`seeded_mongo_manager` swaps the real `pymongo.MongoClient` used inside
database/mongo_client.py for `mongomock.MongoClient` (an in-memory,
API-compatible stand-in) and seeds it with tests/sample_series.py.

This only exists because this sandbox has no reachable MongoDB server to
test against. The code under test (database/mongo_client.py,
recommender/*) is 100% unaware of this swap — it calls the exact same
MongoDBManager methods either way. Point MONGODB_URI/MONGODB_DATABASE at
a real MongoDB instance (already populated) to run the same test file
against real data instead.
"""

import os
import sys
from pathlib import Path

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017/")
os.environ.setdefault("MONGODB_DATABASE", "bingefinder_test")

from database.mongo_client import MongoDBManager
from tests.sample_series import SAMPLE_SERIES


@pytest.fixture
def seeded_mongo_manager(monkeypatch):
    """
    Yields a MongoDBManager backed by an in-memory mongomock client,
    pre-seeded with the sample series documents.
    """
    import database.mongo_client as mongo_client_module

    # A fresh mongomock.MongoClient() call creates independent in-memory
    # storage each time (it doesn't dedupe by URI the way a real
    # MongoClient talking to the same server would). Every
    # MongoDBManager() created during a test (both the one below and any
    # created inside the code under test, e.g. build_recommendation_model)
    # must land on the SAME in-memory store, so a single shared client
    # instance is returned regardless of the connection args passed in.
    shared_client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_client_module, "MongoClient", lambda *args, **kwargs: shared_client)

    manager = MongoDBManager()
    for doc in SAMPLE_SERIES:
        manager.upsert_series(doc)

    yield manager

    manager.close()


@pytest.fixture
def model_path(tmp_path):
    """A throwaway path for a model artifact, isolated per test."""
    return tmp_path / "recommendation_model.joblib"
