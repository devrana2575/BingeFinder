"""
backend/services/catalog_ingest.py
====================================
Incremental, idempotent catalog ingestion from TMDb (the project's approved
external metadata source).

Design:
    - Pulls paginated TMDb list endpoints (popular / top_rated /
      on_the_air for TV; popular / top_rated / now_playing for movies)
      so the catalog can grow without one-off code per title.
    - Normalises raw TMDb rows into the generic `series` document schema
      (same field names the recommender, search and discovery already
      use) plus a `content_type` ("tv_series" / "movie" / "anime" /
      "special") so movies, series and anime share one engine. Anime is
      derived, never claimed: a title is "anime" only when its original
      language is Japanese AND it carries TMDb's Animation genre.
    - Upserts into MongoDB by `series_id`: inserts new documents and
      updates existing ones. The collection is NEVER wiped or recreated.
    - Rate-limit aware: optional sleep between requests plus the TMDb
      client's built-in retry/backoff for 429/5xx.
    - Timestamps: `last_synced_at` (added by MongoDBManager.upsert_series)
      plus `series_updated_at` on each normalised document.
    - Details enrichment (network/cast/episode counts for TV; runtime,
      status, cast for movies) is OPT-IN and capped, so a run never
      makes one detail call per title on a big page.

Run directly:
    python -m backend.services.catalog_ingest --type tv_series --pages 3 --enrich
    python -m backend.services.catalog_ingest --type movie --pages 3 --enrich
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from utils.logger import get_logger

logger = get_logger(__name__)

# Stable decade window used to judge "recent" metadata where relevant.
DEFAULT_LISTS = ("popular", "top_rated", "on_the_air")
MOVIE_DEFAULT_LISTS = ("popular", "top_rated", "now_playing")
DEFAULT_PAGE_SLEEP_SECONDS = 0.25
DEFAULT_ENRICH_LIMIT = 5

# Content types the catalog supports. `special` is reserved for verified,
# non-runtime titles (concerts, festivals); ingestion only ever writes
# "movie", "tv_series" or "anime".
CONTENT_TYPES = ("movie", "tv_series", "anime", "special")

# TMDb genre id -> display name. Used to derive content types (anime) and
# enrich documents; unknown ids are skipped, never invented.
ANIMATION_GENRE_ID = 16

# ISO 639-1 code -> English display name. The catalog stores display-style
# language names (e.g. "English", "Hindi"), so codes are mapped here.
# Unknown codes fall back to their ISO value (uppercased) — never invented.
LANGUAGE_NAME_MAP = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "de": "German", "ko": "Korean", "ja": "Japanese", "zh": "Chinese",
    "it": "Italian", "pt": "Portuguese", "ar": "Arabic", "ru": "Russian",
    "tr": "Turkish", "pl": "Polish", "nl": "Dutch", "sv": "Swedish",
    "th": "Thai", "id": "Indonesian", "vi": "Vietnamese", "da": "Danish",
}


def language_display_name(code: Optional[str]) -> Optional[str]:
    """Map an ISO 639-1 language code to a display name (see map above)."""
    if not code:
        return None
    code = code.strip().lower()
    if not code:
        return None
    return LANGUAGE_NAME_MAP.get(code) or code.upper()


def _steady_numeric(value: Any) -> Any:
    """Return a float/int as-is; coerce int-like strings; else None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _detect_content_type(
    original_language: Optional[str],
    genre_ids: Optional[List[Any]],
    *,
    base: str = "tv_series",
) -> str:
    """
    Derive the document's content type from TMDb signals.

    Anime is never guessed from a single signal: a title is classed as
    "anime" only when its original language is Japanese AND its genre
    list contains TMDb's Animation id (16). Everything else keeps its
    provider bucket (movie / tv_series).
    """
    base = base if base in CONTENT_TYPES else "tv_series"
    if (original_language or "").strip().lower() == "ja":
        ids = set()
        for gid in genre_ids or []:
            try:
                ids.add(int(gid))
            except (TypeError, ValueError):
                continue
        if ANIMATION_GENRE_ID in ids:
            return "anime"
    return base


def _resolve_genres(genre_ids: Optional[List[Any]], genre_map: Optional[Dict[int, str]]) -> List[str]:
    """Map TMDb genre ids to display names, preserving list order."""
    genres: List[str] = []
    if isinstance(genre_ids, list) and genre_map:
        for gid in genre_ids:
            try:
                gname = (genre_map or {}).get(int(gid))
            except (TypeError, ValueError):
                gname = None
            if gname and gname not in genres:
                genres.append(gname)
    return genres


def normalize_tmdb_row(row: Dict[str, Any], genre_map: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """
    Map a raw TMDb TV list result into the app's `series` document schema.

    Missing metadata is kept as None/[] — never fabricated. The numeric
    `series_id` is the stable TMDb id (matching existing catalog docs).
    Documents are stamped with `content_type` ("tv_series" or "anime")
    and a `content_type`-scoped `external_ids` block.
    """
    tmdb_id = row.get("id")
    try:
        series_id = int(tmdb_id) if tmdb_id is not None else None
    except (TypeError, ValueError):
        series_id = None

    name = row.get("name") or row.get("original_name") or None
    original_name = row.get("original_name") or None

    genre_ids = row.get("genre_ids") or []
    genres = _resolve_genres(genre_ids, genre_map)
    content_type = _detect_content_type(
        row.get("original_language"), genre_ids, base="tv_series"
    )

    locale = row.get("original_language")

    doc: Dict[str, Any] = {
        "series_updated_at": time.time(),
        "series_id": series_id,
        "content_type": content_type,
        "name": name,
        "original_name": original_name,
        "language": language_display_name(locale),
        "genres": genres,
        "status": row.get("status") or None,
        "premiered": row.get("first_air_date") or None,
        "rating": _steady_numeric(row.get("vote_average")),
        "weight": _steady_numeric(row.get("popularity")),
        "summary": row.get("overview") or None,
        "image_medium": row.get("poster_path") or None,
        "image_original": row.get("backdrop_path") or None,
        "origin_country": row.get("origin_country") or [],
        "external_ids": {"tmdb": series_id} if series_id is not None else {},
        "catalog_source": "tmdb",
    }
    return doc


def normalize_tmdb_movie_row(row: Dict[str, Any], genre_map: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """
    Map a raw TMDb movie list result into the same `series` document
    schema. Movie rows use `title`/`release_date` nomenclature; the doc
    keeps `name`/`premiered` so search, discovery and the recommender
    work identically for movies and series. `content_type` = "movie"
    (or "anime" for Japanese animation features).
    """
    tmdb_id = row.get("id")
    try:
        series_id = int(tmdb_id) if tmdb_id is not None else None
    except (TypeError, ValueError):
        series_id = None

    name = row.get("title") or row.get("original_title") or None
    original_name = row.get("original_title") or None

    genre_ids = row.get("genre_ids") or []
    genres = _resolve_genres(genre_ids, genre_map)
    content_type = _detect_content_type(
        row.get("original_language"), genre_ids, base="movie"
    )

    locale = row.get("original_language")

    doc: Dict[str, Any] = {
        "series_updated_at": time.time(),
        "series_id": series_id,
        "content_type": content_type,
        "name": name,
        "original_name": original_name,
        "language": language_display_name(locale),
        "genres": genres,
        "status": "Released" if row.get("release_date") else None,
        "premiered": row.get("release_date") or None,
        "rating": _steady_numeric(row.get("vote_average")),
        "weight": _steady_numeric(row.get("popularity")),
        "summary": row.get("overview") or None,
        "image_medium": row.get("poster_path") or None,
        "image_original": row.get("backdrop_path") or None,
        "origin_country": [],
        "external_ids": {"tmdb": series_id} if series_id is not None else {},
        "catalog_source": "tmdb",
    }
    return doc


def _doc_key(doc: Dict[str, Any]) -> Optional[int]:
    try:
        sid = doc.get("series_id")
        return int(sid) if isinstance(sid, (int, float, str)) and sid is not None else None
    except (TypeError, ValueError):
        return None


def ingest_rows(
    manager: Any,
    rows: List[Dict[str, Any]],
    genre_map: Optional[Dict[int, str]] = None,
    *,
    enrich: bool = False,
    client: Any = None,
    enrich_limit: int = DEFAULT_ENRICH_LIMIT,
    content_type: str = "tv_series",
) -> Dict[str, int]:
    """
    Normalise and upsert a batch of raw TMDb rows into the catalog.

    Returns counts: {"inserted": n, "updated": n, "skipped": n}. Rows
    without a usable id are skipped (counted as skipped), never written.
    `content_type` picks the row normalizer ("tv_series" vs "movie") and
    the detail enricher used for the (opt-in) enrichment step.
    """
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    enriched_count = 0
    planned_enrich = enrich and client is not None and enrich_limit > 0
    is_movie = content_type == "movie"

    for row in rows:
        if is_movie:
            doc = normalize_tmdb_movie_row(row, genre_map=genre_map)
        else:
            doc = normalize_tmdb_row(row, genre_map=genre_map)
        sid = _doc_key(doc)
        if sid is None or not doc.get("name"):
            counts["skipped"] += 1
            continue

        existing = manager.series.find_one({"series_id": sid})
        is_new = existing is None

        if planned_enrich and enriched_count < enrich_limit and (is_new or not existing.get("network")):
            if is_movie:
                doc = enrich_movie(client, doc)
            else:
                doc = enrich_series(client, doc)
            enriched_count += 1

        try:
            outcome = manager.upsert_series(doc)
        except Exception as exc:
            logger.warning("Failed to upsert series_id=%s: %s", sid, exc)
            counts["skipped"] += 1
            continue
        counts["inserted" if outcome == "inserted" else "updated"] += 1

    return counts


def enrich_series(client: Any, doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge a series document with richer detail fields from TMDb when those
    calls succeed (network, end date, episode/season counts, top cast).
    Idempotent and best-effort: any individual failure keeps the slim doc.
    """
    tmdb_id = _doc_key(doc)
    if tmdb_id is None:
        return doc

    try:
        details = client.fetch_tv_details(tmdb_id)
    except Exception:
        return doc

    merged = dict(doc)
    if details.get("status"):
        merged["status"] = details.get("status")
    if details.get("last_air_date"):
        merged["ended"] = details.get("last_air_date")
    if details.get("number_of_episodes") is not None:
        merged["episodes_count"] = details.get("number_of_episodes")
    if details.get("number_of_seasons") is not None:
        merged["seasons_count"] = details.get("number_of_seasons")
    if details.get("homepage"):
        merged["official_site"] = details.get("homepage")

    networks = details.get("networks") or []
    if networks:
        network = networks[0]
        merged["network"] = {
            "id": network.get("id"),
            "name": network.get("name"),
            "country": {"name": (network.get("origin_country") or "").upper() or None},
        }
        merged["web_channel"] = None

    if details.get("episode_run_time"):
        minutes = [int(m) for m in details["episode_run_time"] if isinstance(m, int)]
        merged["average_runtime"] = (sum(minutes) / len(minutes)) if minutes else None

    try:
        credits = client.fetch_tv_credits(tmdb_id, top_n=8)
    except Exception:
        credits = []
    if credits:
        merged["cast"] = [
            {
                "person_id": c.get("id"),
                "person_name": c.get("name"),
                "character_name": c.get("character"),
                "image_medium": c.get("profile_path"),
            }
            for c in credits
            if c.get("id") is not None and c.get("name")
        ]

    return merged


def enrich_movie(client: Any, doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge a movie document with richer detail fields from TMDb when those
    calls succeed (runtime, homepage, status, top cast). Idempotent and
    best-effort: any individual failure keeps the slim doc.
    """
    tmdb_id = _doc_key(doc)
    if tmdb_id is None:
        return doc

    try:
        details = client.fetch_movie_details(tmdb_id)
    except Exception:
        return doc

    merged = dict(doc)
    if details.get("runtime") is not None:
        merged["runtime"] = details.get("runtime")
    if details.get("status"):
        merged["status"] = details.get("status")
    if details.get("homepage"):
        merged["official_site"] = details.get("homepage")
    if details.get("release_date") and not merged.get("premiered"):
        merged["premiered"] = details.get("release_date")

    try:
        credits = client.fetch_movie_credits(tmdb_id, top_n=8)
    except Exception:
        credits = []
    if credits:
        merged["cast"] = [
            {
                "person_id": c.get("id"),
                "person_name": c.get("name"),
                "character_name": c.get("character"),
                "image_medium": c.get("profile_path"),
            }
            for c in credits
            if c.get("id") is not None and c.get("name")
        ]

    return merged


def _genre_map_from_client(client: Any, content_type: str = "tv_series") -> Dict[int, str]:
    fetch_fn = getattr(client, "fetch_movie_genres" if content_type == "movie" else "fetch_tv_genres", None)
    if fetch_fn is None:
        return {}
    try:
        genres = fetch_fn()
    except Exception as exc:
        logger.warning("Could not fetch TMDb genre list: %s", exc)
        return {}
    mapping: Dict[int, str] = {}
    for genre in genres:
        try:
            mapping[int(genre["id"])] = genre["name"]
        except (KeyError, TypeError, ValueError):
            continue
    return mapping


def run_catalog_update(
    pages_per_list: int = 3,
    lists: Optional[List[str]] = None,
    sleep_seconds: float = DEFAULT_PAGE_SLEEP_SECONDS,
    enrich: bool = True,
    manager: Any = None,
    client_factory: Any = None,
    content_type: str = "tv_series",
) -> Dict[str, Any]:
    """
    Fetch recent TMDb pages across the configured lists (for the chosen
    content type) and upsert everything into the catalog.

    Never deletes or recreates data — it only inserts/updates. Rate-limit
    aware: sleeps `sleep_seconds` between page requests (the TMDb client
    adds automatic retry/backoff for 429/5xx).

    Args:
        pages_per_list: how many pages to pull per list endpoint.
        lists: which TMDb list endpoints to pull. Defaults to the TV or
            movie defaults depending on `content_type`.
        sleep_seconds: delay between page requests.
        enrich: whether to enrich newly-added / network-less docs with details.
        manager: optional MongoDBManager (default: open one).
        client_factory: optional callable returning a TMDbClient (for tests).
        content_type: "tv_series" or "movie" — picks the list endpoints,
            genre lookup and normalizer used for the run.

    Returns:
        Summary dict with per-list counts and totals.
    """
    from api.tmdb import TMDbClient, TMDbAPIError
    from database.mongo_client import MongoDBManager

    is_movie = content_type == "movie"
    selected_lists = lists or (list(MOVIE_DEFAULT_LISTS) if is_movie else list(DEFAULT_LISTS))
    close_manager = manager is None
    manager = manager or MongoDBManager()
    own_client = client_factory is None
    client = client_factory() if client_factory else TMDbClient()

    genre_map = _genre_map_from_client(client, content_type=content_type)
    summary: Dict[str, Any] = {"lists": {}, "total_inserted": 0, "total_updated": 0, "total_skipped": 0}

    try:
        for list_name in selected_lists:
            per_list = {"inserted": 0, "updated": 0, "skipped": 0}
            suffix = "movie" if is_movie else "tv"
            fetch_fn = getattr(client, f"fetch_{list_name}_{suffix}", None)
            if fetch_fn is None:
                logger.warning("Unknown TMDb list '%s' for content_type '%s'; skipping.", list_name, content_type)
                continue
            for page in range(1, max(pages_per_list, 1) + 1):
                try:
                    rows = fetch_fn(page=page)
                except (TMDbAPIError, Exception) as exc:
                    logger.warning("Failed to fetch %s page %s: %s", list_name, page, exc)
                    break
                if not rows:
                    break
                counts = ingest_rows(
                    manager, rows, genre_map=genre_map, enrich=enrich, client=client,
                    content_type=content_type,
                )
                for key in ("inserted", "updated", "skipped"):
                    per_list[key] += counts[key]
                if page < max(pages_per_list, 1):
                    time.sleep(max(0.0, sleep_seconds))
            summary["lists"][list_name] = per_list
    finally:
        client.close()
        if close_manager:
            manager.close()

    summary["total_inserted"] = sum(v["inserted"] for v in summary["lists"].values())
    summary["total_updated"] = sum(v["updated"] for v in summary["lists"].values())
    summary["total_skipped"] = sum(v["skipped"] for v in summary["lists"].values())
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Incremental TMDb catalog update for BingeFinder.")
    parser.add_argument("--type", choices=("tv_series", "movie"), default="tv_series",
                        help="Content type to ingest (tv_series | movie).")
    parser.add_argument("--pages", type=int, default=3, help="Pages to pull per list endpoint.")
    parser.add_argument("--lists", nargs="+", default=None, help="TMDb list endpoints to pull.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_PAGE_SLEEP_SECONDS, help="Seconds between page requests.")
    parser.add_argument("--no-enrich", action="store_true", help="Disable detail enrichment.")
    args = parser.parse_args()

    result = run_catalog_update(
        pages_per_list=args.pages,
        lists=args.lists,
        sleep_seconds=args.sleep,
        enrich=not args.no_enrich,
        content_type=args.type,
    )
    print(result)