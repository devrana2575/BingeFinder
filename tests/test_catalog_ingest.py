"""
tests/test_catalog_ingest.py
===============================
Tests for the incremental, idempotent catalog ingestion module.
Uses the in-memory mongomock manager and a fake TMDb client so no real
network or MongoDB server is required.
"""

import time


class FakeTMDbClient:
    """Stand-in for api.tmdb.TMDbClient with controllable page data."""

    def __init__(self, rows_per_page=2, pages=1, genre_map=None):
        self.rows = []
        self.pages = pages
        self.rows_per_page = rows_per_page
        self.genre_map = genre_map or {10759: "Action & Adventure", 18: "Drama"}
        self.enriched = []

    def fetch_tv_genres(self):
        return [{"id": k, "name": v} for k, v in self.genre_map.items()]

    def _paginate(self, rows):
        out = []
        for i in range(self.pages):
            start = i * self.rows_per_page
            out.append(rows[start:start + self.rows_per_page])
        return out

    def fetch_popular_tv(self, page=1):
        rows = self._paginate([self._row(n) for n in range(1, 7)])
        return rows[page - 1]

    def fetch_top_rated_tv(self, page=1):
        return []

    def fetch_on_the_air_tv(self, page=1):
        return []

    def _row(self, n):
        return {
            "id": n,
            "name": f"Fake Show {n}",
            "original_name": f"Fake Show {n}",
            "original_language": "en",
            "genre_ids": [10759],
            "status": "Returning Series",
            "first_air_date": "2021-01-01",
            "vote_average": 7.5,
            "popularity": 100.0,
            "overview": "A fake description.",
            "poster_path": f"/poster{n}.jpg",
            "backdrop_path": f"/backdrop{n}.jpg",
            "origin_country": ["CA"],
        }

    def fetch_tv_details(self, tmdb_id):
        self.enriched.append(tmdb_id)
        return {
            "status": "Returning Series",
            "last_air_date": "2023-05-05",
            "number_of_episodes": 10,
            "number_of_seasons": 1,
            "homepage": "https://example.com",
            "networks": [{"id": 1, "name": "Netflix", "origin_country": "US"}],
            "episode_run_time": [45],
        }

    def fetch_tv_credits(self, tmdb_id, top_n=8):
        return [{"id": 1, "name": "Actress A", "character": "Lead", "profile_path": "/a.jpg"}]

    def fetch_movie_genres(self):
        return [{"id": k, "name": v} for k, v in (self.genre_map or {}).items()] + \
            [{"id": 16, "name": "Animation"}]

    def fetch_popular_movie(self, page=1):
        rows = self._paginate([self._movie_row(n) for n in range(1, 7)])
        return rows[page - 1]

    def fetch_top_rated_movie(self, page=1):
        return []

    def fetch_now_playing_movie(self, page=1):
        return []

    def _movie_row(self, n):
        return {
            "id": n + 100,
            "title": f"Fake Movie {n}",
            "original_title": f"Fake Movie {n}",
            "original_language": "en",
            "genre_ids": [10759],
            "release_date": "2022-02-02",
            "vote_average": 7.8,
            "popularity": 90.0,
            "overview": "A fake movie description.",
            "poster_path": f"/mposter{n}.jpg",
            "backdrop_path": f"/mbackdrop{n}.jpg",
            "adult": False,
        }

    def fetch_movie_details(self, tmdb_id):
        self.enriched.append(tmdb_id)
        return {
            "runtime": 128,
            "status": "Released",
            "homepage": "https://example.com",
            "release_date": "2022-02-02",
        }

    def fetch_movie_credits(self, tmdb_id, top_n=8):
        return [{"id": 2, "name": "Actor B", "character": "Star", "profile_path": "/b.jpg"}]

    def close(self):
        pass


def test_ingest_rows_inserts_and_updates(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    client = FakeTMDbClient()
    rows = [client._row(1)]
    # First pass inserts.
    counts = ingest_rows(seeded_mongo_manager, rows, genre_map=client.genre_map, enrich=False)
    assert counts["inserted"] == 1
    doc = seeded_mongo_manager.series.find_one({"series_id": 1})
    assert doc["name"] == "Fake Show 1"
    assert "last_synced_at" in doc

    # Second pass with the same id updates, not duplicates.
    rows[0]["name"] = "Fake Show 1 (Updated)"
    counts = ingest_rows(seeded_mongo_manager, rows, genre_map=client.genre_map, enrich=False)
    assert counts["updated"] == 1
    assert seeded_mongo_manager.series.count_documents({"series_id": 1}) == 1
    assert seeded_mongo_manager.series.find_one({"series_id": 1})["name"] == "Fake Show 1 (Updated)"


def test_ingest_maps_genres_and_language(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    client = FakeTMDbClient()
    ingest_rows(seeded_mongo_manager, [client._row(2)], genre_map=client.genre_map, enrich=False)
    doc = seeded_mongo_manager.series.find_one({"series_id": 2})
    assert doc["genres"] == ["Action & Adventure"]
    assert doc["language"] == "English"
    assert doc["premiered"] == "2021-01-01"


def test_ingest_skips_rows_without_id_or_name(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    rows = [{"id": None, "name": "No id"}, {"id": 3, "name": None}]
    counts = ingest_rows(seeded_mongo_manager, rows, enrich=False)
    assert counts["skipped"] == 2
    assert seeded_mongo_manager.series.find_one({"series_id": 3}) is None


def test_ingest_enriches_new_docs(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    client = FakeTMDbClient()
    ingest_rows(seeded_mongo_manager, [client._row(4)], genre_map=client.genre_map,
                enrich=True, client=client, enrich_limit=5)
    doc = seeded_mongo_manager.series.find_one({"series_id": 4})
    assert doc["network"]["name"] == "Netflix"
    assert doc["ended"] == "2023-05-05"
    assert doc["average_runtime"] == 45
    assert doc["cast"][0]["person_name"] == "Actress A"


def test_run_catalog_update_respects_pages(seeded_mongo_manager):
    from backend.services.catalog_ingest import run_catalog_update

    client = FakeTMDbClient(pages=2, rows_per_page=2)
    summary = run_catalog_update(
        pages_per_list=2,
        lists=["popular"],
        sleep_seconds=0,
        enrich=False,
        manager=seeded_mongo_manager,
        client_factory=lambda: client,
    )
    # 2 pages x 2 rows = 4 rows across pages 1..2 (3..6 remain).
    assert summary["total_inserted"] == 4
    assert "popular" in summary["lists"]
    assert summary["lists"]["popular"]["inserted"] == 4


def test_movie_rows_ingest_with_content_type(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    client = FakeTMDbClient()
    counts = ingest_rows(seeded_mongo_manager, [client._movie_row(1)],
                         genre_map=client.genre_map, enrich=False, content_type="movie")
    assert counts["inserted"] == 1
    doc = seeded_mongo_manager.series.find_one({"series_id": 101})
    assert doc["content_type"] == "movie"
    assert doc["name"] == "Fake Movie 1"
    assert doc["premiered"] == "2022-02-02"
    assert doc["genres"] == ["Action & Adventure"]
    assert doc["external_ids"]["tmdb"] == 101


def test_anime_content_type_derived_from_language_and_animation(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows, normalize_tmdb_row

    client = FakeTMDbClient()
    # Japanese + Animation genre -> anime, for both series and movies.
    row = client._row(50)
    row["original_language"] = "ja"
    row["genre_ids"] = [16, 10759]
    doc = normalize_tmdb_row(row, genre_map=client.genre_map)
    assert doc["content_type"] == "anime"

    mrow = client._movie_row(60)
    mrow["original_language"] = "ja"
    mrow["genre_ids"] = [16]
    from backend.services.catalog_ingest import normalize_tmdb_movie_row
    mdoc = normalize_tmdb_movie_row(mrow, genre_map=client.genre_map)
    assert mdoc["content_type"] == "anime"

    # Japanese alone is NOT anime — both signals are required.
    row2 = client._row(51)
    row2["original_language"] = "ja"
    row2["genre_ids"] = [10759]
    assert normalize_tmdb_row(row2, genre_map=client.genre_map)["content_type"] == "tv_series"


def test_movie_enrichment_adds_runtime_and_cast(seeded_mongo_manager):
    from backend.services.catalog_ingest import ingest_rows

    client = FakeTMDbClient()
    ingest_rows(seeded_mongo_manager, [client._movie_row(2)], genre_map=client.genre_map,
                enrich=True, client=client, enrich_limit=5, content_type="movie")
    doc = seeded_mongo_manager.series.find_one({"series_id": 102})
    assert doc["runtime"] == 128
    assert doc["status"] == "Released"
    assert doc["official_site"] == "https://example.com"
    assert doc["cast"][0]["person_name"] == "Actor B"


def test_run_catalog_update_movie_type_uses_movie_endpoints(seeded_mongo_manager):
    from backend.services.catalog_ingest import run_catalog_update

    client = FakeTMDbClient(pages=2, rows_per_page=2)
    summary = run_catalog_update(
        pages_per_list=2,
        lists=["popular"],
        sleep_seconds=0,
        enrich=False,
        manager=seeded_mongo_manager,
        client_factory=lambda: client,
        content_type="movie",
    )
    assert summary["total_inserted"] == 4
    for doc in seeded_mongo_manager.series.find({"series_id": {"$in": [101, 102, 103, 104]}}):
        assert doc["content_type"] == "movie"