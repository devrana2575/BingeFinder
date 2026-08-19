"""
database/database.py
=====================
SQLite persistence layer for the `series` table.

This module owns all direct SQL access. Other modules (e.g.
update_database.py, and future recommender/UI modules) should go through
`DatabaseManager` rather than opening their own sqlite3 connections, so
that connection handling, schema creation, and upsert logic stay in one
place (avoids duplicate code).
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from config import DATABASE_PATH, SCHEMA_PATH
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class DatabaseManager:
    """
    Manages the SQLite connection lifecycle and all read/write operations
    against the `series` table.
    """

    def __init__(self, db_path: Optional[str] = None, schema_path: Optional[Path] = None) -> None:
        """
        Initialize the database manager and ensure the schema exists.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                config.DATABASE_PATH.
            schema_path: Path to the .sql schema file. Defaults to
                config.SCHEMA_PATH.
        """
        self.db_path: str = db_path or DATABASE_PATH
        self.schema_path: Path = schema_path or SCHEMA_PATH
        self._initialize_schema()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager that yields a SQLite connection and guarantees it
        is properly closed (and rolled back on error) afterwards.

        Yields:
            An open `sqlite3.Connection` with row factory set to
            `sqlite3.Row` for dict-like access.
        """
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        # Enforce foreign keys / sane defaults for every connection.
        connection.execute("PRAGMA foreign_keys = ON;")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # Columns that may be missing from a `series` table created by an
    # older version of schema.sql. Mapping of column name -> the SQL
    # type/default clause used to add it via ALTER TABLE ... ADD COLUMN.
    # Kept in sync with the CREATE TABLE series statement in schema.sql.
    _SERIES_MIGRATION_COLUMNS: Dict[str, str] = {
        "original_name": "TEXT",
        "tagline": "TEXT",
        "status": "TEXT",
        "last_air_date": "TEXT",
        "number_of_seasons": "INTEGER",
        "number_of_episodes": "INTEGER",
        "origin_country": "TEXT",
        "homepage": "TEXT",
    }

    def _initialize_schema(self) -> None:
        """
        Create the `series` table and all supporting lookup/junction
        tables (genres, cast, keywords, providers, etc.) if they do not
        already exist, using the SQL statements in schema.sql. Then run
        a lightweight migration pass that adds any columns to `series`
        that are missing on a pre-existing database file, so older
        `bingefinder.db` files keep their data and simply gain the new
        columns/tables rather than needing to be deleted and recreated.

        Raises:
            DatabaseError: If the schema file is missing or invalid SQL
                is encountered.
        """
        if not self.schema_path.exists():
            raise DatabaseError(f"Schema file not found at: {self.schema_path}")

        # Migrate any pre-existing `series` table BEFORE running schema.sql:
        # schema.sql's CREATE TABLE IF NOT EXISTS is a no-op on a database
        # that already has a `series` table from an older schema version,
        # but schema.sql also creates indexes (e.g. idx_series_status) on
        # the new columns, which would fail if those columns don't exist
        # yet. Adding missing columns first makes the rest of schema.sql
        # safe to run unconditionally.
        self._migrate_series_columns()

        try:
            schema_sql = self.schema_path.read_text(encoding="utf-8")
            with self._get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            logger.info("Database schema verified/initialized at %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to initialize database schema: %s", exc)
            raise DatabaseError(f"Failed to initialize database schema: {exc}") from exc

    def _migrate_series_columns(self) -> None:
        """
        Add any of `_SERIES_MIGRATION_COLUMNS` to the `series` table that
        are missing (i.e. the table pre-dates those columns being added
        to schema.sql). Safe to run on every startup, including against a
        brand-new database file that has no `series` table yet (in which
        case this is a no-op and schema.sql creates the table with every
        column already present). Existing columns and data are always
        left untouched.

        Raises:
            DatabaseError: If inspecting or altering the table fails.
        """
        try:
            with self._get_connection() as conn:
                table_exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'series';"
                ).fetchone()
                if not table_exists:
                    # Fresh database: schema.sql (run right after this) will
                    # create `series` with every column already included.
                    return

                existing_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(series);")
                }
                missing_columns = {
                    column: ddl_type
                    for column, ddl_type in self._SERIES_MIGRATION_COLUMNS.items()
                    if column not in existing_columns
                }
                for column, ddl_type in missing_columns.items():
                    conn.execute(f"ALTER TABLE series ADD COLUMN {column} {ddl_type};")
                    logger.info("Migrated `series` table: added missing column '%s'.", column)
                if missing_columns:
                    conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to migrate `series` table columns: %s", exc)
            raise DatabaseError(f"Failed to migrate `series` table columns: {exc}") from exc

    @staticmethod
    def _row_to_series_tuple(series: Dict[str, Any]) -> tuple:
        """
        Normalize a raw TMDb TV series dict (already mapped to our column
        names by the caller) into a tuple matching the INSERT column order.

        Accepts both the slim rows produced by the TMDb list endpoints
        (trending/popular/etc.) and the richer rows produced by the TMDb
        `/tv/{id}` details endpoint — any key not present for a given row
        simply defaults to NULL (existing stored values are preserved via
        the caller's upsert, not overwritten with NULL, only on UPDATE of
        columns present in this tuple, since every column is always sent).

        Args:
            series: Dictionary with keys matching the `series` table columns.

        Returns:
            A tuple of values ready for parameterized SQL execution.
        """
        genre_ids = series.get("genre_ids")
        # A full TV-details payload has "genres" (list of {id, name} dicts)
        # rather than "genre_ids"; fall back to deriving the id list from
        # it so the legacy genre_ids column still gets populated.
        if genre_ids is None and series.get("genres"):
            genre_ids = [g["id"] for g in series["genres"] if isinstance(g, dict) and "id" in g]
        # Store genre_ids as a JSON string since SQLite has no native array type.
        genre_ids_json = json.dumps(genre_ids) if genre_ids is not None else json.dumps([])

        # Store origin_country as a JSON string. Unlike genre_ids (always
        # supplied by existing callers), origin_country may genuinely be
        # absent from a slim row, so distinguish "key missing" (-> NULL,
        # so ON CONFLICT's COALESCE preserves any prior stored value) from
        # "key present but empty" (-> "[]").
        origin_country_json = json.dumps(series["origin_country"]) if "origin_country" in series and series["origin_country"] is not None else None

        return (
            series.get("id"),
            series.get("name"),
            series.get("original_name"),
            series.get("overview"),
            series.get("tagline"),
            series.get("status"),
            series.get("first_air_date"),
            series.get("last_air_date"),
            series.get("number_of_seasons"),
            series.get("number_of_episodes"),
            series.get("vote_average"),
            series.get("vote_count"),
            series.get("popularity"),
            series.get("original_language"),
            origin_country_json,
            genre_ids_json,
            series.get("poster_path"),
            series.get("backdrop_path"),
            series.get("homepage"),
            1 if series.get("adult") else 0,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def upsert_series(self, series_list: List[Dict[str, Any]]) -> int:
        """
        Insert new series or update existing ones (matched by TMDb `id`),
        avoiding duplicates. All rows are committed as a single transaction
        so a partial failure does not leave the database in a mixed state.

        Accepts both the slim rows returned by TMDb's list endpoints
        (trending/popular/etc.) and the richer rows returned by TMDb's
        `/tv/{id}` details endpoint — pass whichever fields are available;
        anything not supplied is stored as NULL rather than left unset.

        Args:
            series_list: List of dictionaries with keys matching the
                `series` table columns (id, name, original_name, overview,
                tagline, status, first_air_date, last_air_date,
                number_of_seasons, number_of_episodes, vote_average,
                vote_count, popularity, original_language, origin_country,
                genre_ids, poster_path, backdrop_path, homepage, adult).

        Returns:
            The number of rows successfully upserted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        if not series_list:
            logger.info("No series provided to upsert; skipping.")
            return 0

        upsert_sql = """
            INSERT INTO series (
                id, name, original_name, overview, tagline, status,
                first_air_date, last_air_date, number_of_seasons,
                number_of_episodes, vote_average, vote_count, popularity,
                original_language, origin_country, genre_ids, poster_path,
                backdrop_path, homepage, adult, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name                = excluded.name,
                -- Detail-only fields (original_name, tagline, status, ...)
                -- are NULL when this upsert came from a slim list-endpoint
                -- sync rather than the /tv/{id} details endpoint. COALESCE
                -- keeps any previously-stored detail value in that case
                -- instead of clobbering it with NULL.
                original_name       = COALESCE(excluded.original_name, original_name),
                overview            = excluded.overview,
                tagline             = COALESCE(excluded.tagline, tagline),
                status              = COALESCE(excluded.status, status),
                first_air_date      = excluded.first_air_date,
                last_air_date       = COALESCE(excluded.last_air_date, last_air_date),
                number_of_seasons   = COALESCE(excluded.number_of_seasons, number_of_seasons),
                number_of_episodes  = COALESCE(excluded.number_of_episodes, number_of_episodes),
                vote_average        = excluded.vote_average,
                vote_count          = excluded.vote_count,
                popularity          = excluded.popularity,
                original_language   = excluded.original_language,
                origin_country      = COALESCE(excluded.origin_country, origin_country),
                genre_ids           = excluded.genre_ids,
                poster_path         = excluded.poster_path,
                backdrop_path       = excluded.backdrop_path,
                homepage            = COALESCE(excluded.homepage, homepage),
                adult               = excluded.adult,
                last_updated        = excluded.last_updated;
        """

        rows = [self._row_to_series_tuple(series) for series in series_list if series.get("id") is not None]

        try:
            with self._get_connection() as conn:
                conn.executemany(upsert_sql, rows)
                conn.commit()
            logger.info("Upserted %d series into the database.", len(rows))
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to upsert series batch: %s", exc)
            raise DatabaseError(f"Failed to upsert series batch: {exc}") from exc

    def get_series_count(self) -> int:
        """
        Return the total number of series currently stored.

        Returns:
            Row count of the `series` table.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) AS count FROM series;")
                row = cursor.fetchone()
                return int(row["count"]) if row else 0
        except sqlite3.Error as exc:
            logger.error("Failed to count series: %s", exc)
            raise DatabaseError(f"Failed to count series: {exc}") from exc

    def get_all_series(self) -> List[Dict[str, Any]]:
        """
        Fetch every series row from the database.

        Returns:
            A list of dictionaries, one per row, keyed by column name.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM series;")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to fetch all series: %s", exc)
            raise DatabaseError(f"Failed to fetch all series: {exc}") from exc

    # ------------------------------------------------------------------
    # Genres
    # ------------------------------------------------------------------
    def upsert_genres(self, genres: List[Dict[str, Any]]) -> int:
        """
        Insert or update rows in the `genres` lookup table, matched by
        TMDb genre `id` (avoids duplicates).

        Args:
            genres: List of raw TMDb genre dicts, each with "id" and "name"
                (e.g. as returned by `TMDbClient.fetch_tv_genres`).

        Returns:
            The number of genre rows upserted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [(g.get("id"), g.get("name")) for g in genres if g.get("id") is not None]
        if not rows:
            logger.info("No genres provided to upsert; skipping.")
            return 0

        upsert_sql = """
            INSERT INTO genres (id, name)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name;
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(upsert_sql, rows)
                conn.commit()
            logger.info("Upserted %d genres into the database.", len(rows))
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to upsert genres batch: %s", exc)
            raise DatabaseError(f"Failed to upsert genres batch: {exc}") from exc

    def set_series_genres(self, series_id: int, genre_ids: List[int]) -> int:
        """
        Link a series to its genres in `series_genres`. The referenced
        genres must already exist in `genres` (call `upsert_genres` first)
        or this will fail on the foreign key constraint.

        Args:
            series_id: TMDb series ID.
            genre_ids: List of TMDb genre IDs to link to this series.

        Returns:
            The number of (series_id, genre_id) links attempted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [(series_id, genre_id) for genre_id in genre_ids if genre_id is not None]
        if not rows:
            logger.info("No genre links provided for series %s; skipping.", series_id)
            return 0

        link_sql = "INSERT OR IGNORE INTO series_genres (series_id, genre_id) VALUES (?, ?);"
        try:
            with self._get_connection() as conn:
                conn.executemany(link_sql, rows)
                conn.commit()
            logger.info("Linked %d genre(s) to series %s.", len(rows), series_id)
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to link genres for series %s: %s", series_id, exc)
            raise DatabaseError(f"Failed to link genres for series {series_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Cast
    # ------------------------------------------------------------------
    def upsert_cast(self, cast_members: List[Dict[str, Any]]) -> int:
        """
        Insert or update rows in the `cast` lookup table, matched by TMDb
        person `id` (avoids duplicates).

        Args:
            cast_members: List of raw TMDb cast-credit dicts, each with
                "id", "name", and "profile_path" (e.g. as returned by
                `TMDbClient.fetch_tv_credits`).

        Returns:
            The number of cast rows upserted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [
            (member.get("id"), member.get("name"), member.get("profile_path"))
            for member in cast_members
            if member.get("id") is not None
        ]
        if not rows:
            logger.info("No cast members provided to upsert; skipping.")
            return 0

        upsert_sql = """
            INSERT INTO "cast" (id, name, profile_path)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name         = excluded.name,
                profile_path = excluded.profile_path;
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(upsert_sql, rows)
                conn.commit()
            logger.info("Upserted %d cast members into the database.", len(rows))
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to upsert cast batch: %s", exc)
            raise DatabaseError(f"Failed to upsert cast batch: {exc}") from exc

    def set_series_cast(self, series_id: int, cast_members: List[Dict[str, Any]]) -> int:
        """
        Link a series to its cast in `series_cast`, storing each actor's
        character name and billing order. The referenced cast members must
        already exist in `cast` (call `upsert_cast` first) or this will
        fail on the foreign key constraint. Re-running for the same series
        updates the character/order rather than creating duplicates.

        Args:
            series_id: TMDb series ID.
            cast_members: List of raw TMDb cast-credit dicts, each with
                "id" (cast member id), "character", and "order" (e.g. the
                top-10 list returned by `TMDbClient.fetch_tv_credits`).

        Returns:
            The number of (series_id, cast_id) links attempted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [
            (series_id, member.get("id"), member.get("character"), member.get("order"))
            for member in cast_members
            if member.get("id") is not None
        ]
        if not rows:
            logger.info("No cast links provided for series %s; skipping.", series_id)
            return 0

        link_sql = """
            INSERT INTO series_cast (series_id, cast_id, character_name, cast_order)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(series_id, cast_id) DO UPDATE SET
                character_name = excluded.character_name,
                cast_order     = excluded.cast_order;
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(link_sql, rows)
                conn.commit()
            logger.info("Linked %d cast member(s) to series %s.", len(rows), series_id)
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to link cast for series %s: %s", series_id, exc)
            raise DatabaseError(f"Failed to link cast for series {series_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Keywords
    # ------------------------------------------------------------------
    def upsert_keywords(self, keywords: List[Dict[str, Any]]) -> int:
        """
        Insert or update rows in the `keywords` lookup table, matched by
        TMDb keyword `id` (avoids duplicates).

        Args:
            keywords: List of raw TMDb keyword dicts, each with "id" and
                "name" (e.g. as returned by `TMDbClient.fetch_tv_keywords`).

        Returns:
            The number of keyword rows upserted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [(k.get("id"), k.get("name")) for k in keywords if k.get("id") is not None]
        if not rows:
            logger.info("No keywords provided to upsert; skipping.")
            return 0

        upsert_sql = """
            INSERT INTO keywords (id, name)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name;
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(upsert_sql, rows)
                conn.commit()
            logger.info("Upserted %d keywords into the database.", len(rows))
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to upsert keywords batch: %s", exc)
            raise DatabaseError(f"Failed to upsert keywords batch: {exc}") from exc

    def set_series_keywords(self, series_id: int, keywords: List[Dict[str, Any]]) -> int:
        """
        Link a series to its keywords in `series_keywords`. The referenced
        keywords must already exist in `keywords` (call `upsert_keywords`
        first) or this will fail on the foreign key constraint.

        Args:
            series_id: TMDb series ID.
            keywords: List of raw TMDb keyword dicts, each with "id" (e.g.
                as returned by `TMDbClient.fetch_tv_keywords`).

        Returns:
            The number of (series_id, keyword_id) links attempted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [(series_id, k.get("id")) for k in keywords if k.get("id") is not None]
        if not rows:
            logger.info("No keyword links provided for series %s; skipping.", series_id)
            return 0

        link_sql = "INSERT OR IGNORE INTO series_keywords (series_id, keyword_id) VALUES (?, ?);"
        try:
            with self._get_connection() as conn:
                conn.executemany(link_sql, rows)
                conn.commit()
            logger.info("Linked %d keyword(s) to series %s.", len(rows), series_id)
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to link keywords for series %s: %s", series_id, exc)
            raise DatabaseError(f"Failed to link keywords for series {series_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Watch providers
    # ------------------------------------------------------------------
    def upsert_providers(self, providers: List[Dict[str, Any]]) -> int:
        """
        Insert or update rows in the `providers` lookup table, matched by
        TMDb watch-provider `id` (avoids duplicates).

        Args:
            providers: List of raw TMDb watch-provider dicts, each with
                "provider_id", "provider_name", and "logo_path" (TMDb's
                watch-provider objects use these keys rather than plain
                "id"/"name").

        Returns:
            The number of provider rows upserted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = [
            (p.get("provider_id"), p.get("provider_name"), p.get("logo_path"))
            for p in providers
            if p.get("provider_id") is not None
        ]
        if not rows:
            logger.info("No providers provided to upsert; skipping.")
            return 0

        upsert_sql = """
            INSERT INTO providers (id, name, logo_path)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name      = excluded.name,
                logo_path = excluded.logo_path;
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(upsert_sql, rows)
                conn.commit()
            logger.info("Upserted %d providers into the database.", len(rows))
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to upsert providers batch: %s", exc)
            raise DatabaseError(f"Failed to upsert providers batch: {exc}") from exc

    def set_series_providers(
        self, series_id: int, country_code: str, providers_by_type: Dict[str, List[Dict[str, Any]]]
    ) -> int:
        """
        Link a series to its watch providers in `series_providers` for a
        single region. The referenced providers must already exist in
        `providers` (call `upsert_providers` first) or this will fail on
        the foreign key constraint.

        Args:
            series_id: TMDb series ID.
            country_code: ISO 3166-1 country code the providers apply to,
                e.g. "IN" (BingeFinder's primary market — see
                `TMDbClient.fetch_tv_watch_providers`).
            providers_by_type: Mapping of TMDb offer type ("flatrate",
                "free", "ads", "rent", "buy") to a list of raw TMDb
                provider dicts, i.e. the region-scoped dict returned by
                `TMDbClient.fetch_tv_watch_providers`.

        Returns:
            The number of (series_id, provider_id, country_code,
            provider_type) links attempted.

        Raises:
            DatabaseError: If the transaction fails and is rolled back.
        """
        rows = []
        for provider_type, provider_list in providers_by_type.items():
            if provider_type not in ("flatrate", "free", "ads", "rent", "buy"):
                # Ignore non-offer keys in the payload, e.g. TMDb's "link".
                continue
            if not isinstance(provider_list, list):
                continue
            for provider in provider_list:
                provider_id = provider.get("provider_id")
                if provider_id is None:
                    continue
                rows.append((series_id, provider_id, country_code, provider_type))

        if not rows:
            logger.info(
                "No provider links provided for series %s in region %s; skipping.",
                series_id, country_code,
            )
            return 0

        link_sql = """
            INSERT OR IGNORE INTO series_providers (series_id, provider_id, country_code, provider_type)
            VALUES (?, ?, ?, ?);
        """
        try:
            with self._get_connection() as conn:
                conn.executemany(link_sql, rows)
                conn.commit()
            logger.info(
                "Linked %d provider offering(s) to series %s in region %s.",
                len(rows), series_id, country_code,
            )
            return len(rows)
        except sqlite3.Error as exc:
            logger.error("Failed to link providers for series %s: %s", series_id, exc)
            raise DatabaseError(f"Failed to link providers for series {series_id}: {exc}") from exc
