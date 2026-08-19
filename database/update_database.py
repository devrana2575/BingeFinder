"""
database/update_database.py
============================
Standalone script that fetches the latest web-series data from TMDb
across multiple list endpoints (trending, popular, top rated, on the air,
airing today), deduplicates it, and safely upserts it into the local
SQLite database. Each discovered series is then enriched with its full
details, genres, top-10 cast, keywords, and India watch-provider
availability.

This module only orchestrates calls into the existing `TMDbClient` and
`DatabaseManager` layers — no new fetching or storage logic is introduced
here.

Run directly:
    python -m database.update_database

Or scheduled via cron / Task Scheduler / GitHub Actions for periodic syncs.
"""

import sys
from typing import Any, Dict, List, Optional

# Allow running this file directly (`python database/update_database.py`)
# as well as as a module (`python -m database.update_database`) by ensuring
# the project root is importable in both cases.
if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from api.tmdb import DEFAULT_WATCH_REGION, TMDbAPIError, TMDbClient
from config import INITIAL_SYNC_PAGES, UPDATE_SYNC_PAGES
from database.database import DatabaseError, DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)


def _map_tmdb_result_to_series_row(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw TMDb TV result dictionary to the column names used by our
    `series` table. Centralizing this mapping avoids duplicating field
    translation logic across every fetch call site.

    Args:
        result: Raw TV series dictionary as returned by TMDb.

    Returns:
        Dictionary with keys matching the `series` table schema.
    """
    return {
        "id": result.get("id"),
        "name": result.get("name") or result.get("original_name"),
        "overview": result.get("overview"),
        "first_air_date": result.get("first_air_date"),
        "vote_average": result.get("vote_average"),
        "vote_count": result.get("vote_count"),
        "popularity": result.get("popularity"),
        "original_language": result.get("original_language"),
        "genre_ids": result.get("genre_ids", []),
        "poster_path": result.get("poster_path"),
        "backdrop_path": result.get("backdrop_path"),
        "adult": result.get("adult", False),
    }


def _deduplicate_series(series_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate series (same TMDb `id` appearing across multiple
    endpoints, e.g. a show that is both "trending" and "popular") while
    preserving the first occurrence encountered.

    Args:
        series_rows: List of mapped series row dictionaries, possibly
            containing duplicates by `id`.

    Returns:
        A list of series rows with unique `id` values.
    """
    seen_ids = set()
    unique_rows: List[Dict[str, Any]] = []
    for row in series_rows:
        series_id = row.get("id")
        if series_id is None or series_id in seen_ids:
            continue
        seen_ids.add(series_id)
        unique_rows.append(row)
    return unique_rows


def fetch_all_series(client: TMDbClient, pages_per_endpoint: int = UPDATE_SYNC_PAGES) -> List[Dict[str, Any]]:
    """
    Fetch series from every configured TMDb endpoint (Trending TV, Popular
    TV, Top Rated TV, On The Air, Airing Today) and merge the results.

    Each endpoint is fetched independently and failures are logged and
    skipped rather than aborting the entire sync, so a single flaky
    endpoint doesn't block updates from the others.

    Args:
        client: An initialized `TMDbClient`.
        pages_per_endpoint: Number of pages to fetch per endpoint. Defaults
            to `UPDATE_SYNC_PAGES`; `run_update` passes `INITIAL_SYNC_PAGES`
            instead when the database is empty.

    Returns:
        A deduplicated list of series rows ready for database upsert.
    """
    endpoint_fetchers = {
        "trending": client.fetch_trending_tv,
        "popular": client.fetch_popular_tv,
        "top_rated": client.fetch_top_rated_tv,
        "on_the_air": client.fetch_on_the_air_tv,
        "airing_today": client.fetch_airing_today_tv,
    }

    all_results: List[Dict[str, Any]] = []

    for endpoint_name, fetch_fn in endpoint_fetchers.items():
        for page in range(1, pages_per_endpoint + 1):
            try:
                raw_results = fetch_fn(page=page)
            except TMDbAPIError as exc:
                logger.warning(
                    "Skipping page %d of endpoint '%s' due to API error: %s",
                    page, endpoint_name, exc,
                )
                continue

            if not raw_results:
                # No more pages / no results for this endpoint; move on.
                break

            logger.info(
                "Fetched %d results from '%s' (page %d).",
                len(raw_results), endpoint_name, page,
            )
            all_results.extend(_map_tmdb_result_to_series_row(r) for r in raw_results)

    deduplicated = _deduplicate_series(all_results)
    logger.info(
        "Fetched %d total results across all endpoints; %d unique series after deduplication.",
        len(all_results), len(deduplicated),
    )
    return deduplicated


def _sync_genre_catalog(client: TMDbClient, db_manager: DatabaseManager) -> None:
    """
    Seed the shared `genres` lookup table once per run (not once per
    series) to avoid redundant TMDb calls. Per-series genre *links* are
    still set individually in `_enrich_series`, using the genre IDs
    already embedded in each series' own details payload.

    A failure here is logged and swallowed rather than raised: it should
    not abort the whole sync, since per-series genre linking simply has
    nothing to link against if this fails.

    Args:
        client: An initialized `TMDbClient`.
        db_manager: An initialized `DatabaseManager`.
    """
    try:
        genres = client.fetch_tv_genres()
        if genres:
            db_manager.upsert_genres(genres)
            logger.info("Synced official TMDb TV genre catalog (%d genres).", len(genres))
    except (TMDbAPIError, DatabaseError) as exc:
        logger.warning("Could not sync genre catalog; continuing without it: %s", exc)


def _enrich_series(client: TMDbClient, db_manager: DatabaseManager, series_id: int) -> None:
    """
    Fetch and save full details, genre links, top-10 cast, keywords, and
    India watch-provider availability for a single series, using only the
    TMDb fetch methods and database store methods that already exist.

    Any exception raised here (a failed TMDb request or a database error)
    is left to propagate — `run_update` is responsible for catching it,
    logging it, and counting it as a failed series without stopping the
    rest of the sync.

    Args:
        client: An initialized `TMDbClient`.
        db_manager: An initialized `DatabaseManager`.
        series_id: TMDb series ID to enrich.

    Raises:
        TMDbAPIError: If any TMDb request fails after retries.
        DatabaseError: If any database write fails.
    """
    # Full details -> populates original_name, tagline, status,
    # last_air_date, number_of_seasons, number_of_episodes,
    # origin_country, and homepage on the existing `series` row.
    details = client.fetch_tv_details(series_id)
    db_manager.upsert_series([details])

    # Genres: link using the IDs already embedded in the details payload
    # (no extra TMDb call needed; the full catalog was synced once already).
    genre_ids = [g["id"] for g in details.get("genres", []) if isinstance(g, dict) and "id" in g]
    if genre_ids:
        db_manager.set_series_genres(series_id, genre_ids)

    # Top 10 cast.
    cast = client.fetch_tv_credits(series_id, top_n=10)
    if cast:
        db_manager.upsert_cast(cast)
        db_manager.set_series_cast(series_id, cast)

    # Keywords.
    keywords = client.fetch_tv_keywords(series_id)
    if keywords:
        db_manager.upsert_keywords(keywords)
        db_manager.set_series_keywords(series_id, keywords)

    # Watch providers, scoped to India (TMDbClient's default region).
    providers_by_type = client.fetch_tv_watch_providers(series_id)
    if providers_by_type:
        flat_providers = [
            provider
            for provider_list in providers_by_type.values()
            if isinstance(provider_list, list)
            for provider in provider_list
        ]
        if flat_providers:
            db_manager.upsert_providers(flat_providers)
        db_manager.set_series_providers(series_id, DEFAULT_WATCH_REGION, providers_by_type)


def run_update(pages_per_endpoint: Optional[int] = None) -> int:
    """
    Orchestrate a full sync:
      1. Fetch series from all 5 TMDb list endpoints (deduplicated by ID).
      2. Upsert the basic series rows first.
      3. For each discovered series, fetch and save full details, genres,
         top-10 cast, keywords, and India watch providers.
      4. Print a final summary (Discovered / Inserted-Processed / Failed /
         Total database series).

    A failure enriching any single series (TMDb request or database write)
    is caught, logged, and counted — it never stops the rest of the sync.
    The database is never deleted or rebuilt; existing rows are upserted
    in place.

    Args:
        pages_per_endpoint: Number of pages to fetch per TMDb list
            endpoint. If not provided, `INITIAL_SYNC_PAGES` is used when
            the database is currently empty (first run) and
            `UPDATE_SYNC_PAGES` otherwise, so routine syncs stay fast
            while the first sync builds a broad catalog.

    Returns:
        The number of series successfully processed (basic upsert plus
        full enrichment) in this run.
    """
    discovered_count = 0
    processed_count = 0
    failed_count = 0

    try:
        db_manager = DatabaseManager()
    except DatabaseError as exc:
        logger.error("Aborting update: could not initialize database: %s", exc)
        return 0

    if pages_per_endpoint is None:
        is_initial_sync = db_manager.get_series_count() == 0
        pages_per_endpoint = INITIAL_SYNC_PAGES if is_initial_sync else UPDATE_SYNC_PAGES
        logger.info(
            "No pages_per_endpoint given; using %s sync default of %d page(s) per endpoint.",
            "initial" if is_initial_sync else "update", pages_per_endpoint,
        )

    try:
        with TMDbClient() as client:
            series_rows = fetch_all_series(client, pages_per_endpoint=pages_per_endpoint)
            discovered_count = len(series_rows)

            if not series_rows:
                logger.warning("No series data fetched; nothing to upsert.")
            else:
                try:
                    db_manager.upsert_series(series_rows)
                except DatabaseError as exc:
                    logger.error("Aborting update: failed to upsert basic series rows: %s", exc)
                    _print_summary(discovered_count, processed_count, failed_count, db_manager.get_series_count())
                    return processed_count

                _sync_genre_catalog(client, db_manager)

                for row in series_rows:
                    series_id = row.get("id")
                    if series_id is None:
                        failed_count += 1
                        continue
                    try:
                        _enrich_series(client, db_manager, series_id)
                        processed_count += 1
                    except (TMDbAPIError, DatabaseError) as exc:
                        failed_count += 1
                        logger.warning("Failed to enrich series %s: %s", series_id, exc)
                    except Exception as exc:  # defensive: one bad series must never kill the run
                        failed_count += 1
                        logger.error("Unexpected error enriching series %s: %s", series_id, exc)
    except TMDbAPIError as exc:
        logger.error("Aborting update: could not fetch series lists from TMDb: %s", exc)
    except Exception as exc:  # Catches ConfigError (missing API key) etc.
        logger.error("Aborting update: unexpected error during sync: %s", exc)

    total_in_db = db_manager.get_series_count()
    _print_summary(discovered_count, processed_count, failed_count, total_in_db)
    return processed_count


def _print_summary(discovered: int, processed: int, failed: int, total_in_db: int) -> None:
    """Print the final sync summary in the required format."""
    print("Discovered:", discovered)
    print("Inserted/Processed:", processed)
    print("Failed:", failed)
    print("Total database series:", total_in_db)


if __name__ == "__main__":
    run_update()
