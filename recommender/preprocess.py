"""
recommender/preprocess.py
============================
Turns a raw `series` MongoDB document into the plain-text "content soup"
that the TF-IDF vectorizer is fitted on.

Only fields that actually exist in the `series` schema (see
database/update_mongo.py's `_map_tvmaze_show_to_document`) are read here.
Nothing is invented: any field that is missing, None, or an empty
list/dict on a given document simply contributes nothing to that
document's text, instead of raising an error.

Field usage (per the Phase 3 spec):
    - name     -> series title, added as the first token so TF-IDF can
                  distinguish shows with similar plots but different themes.
    - summary  -> primary signal, used as-is (already HTML-stripped by
                  api.tvmaze.clean_summary during ingestion).
    - genres   -> primary signal, repeated a few times so the vectorizer
                  weighs genre words more heavily than the other
                  (secondary) fields below. This is a simple, explainable
                  way to bias TF-IDF without hand-tuning per-term weights.
    - cast     -> secondary signal: top billed cast member names.
    - network / web_channel -> secondary signal: the broadcaster/streamer
      name. TVmaze stores these as nested objects (e.g.
      {"id": 1, "name": "HBO", "country": {...}}), never as plain
      strings, so the name is pulled out defensively.
"""

from typing import Any, Dict, List, Optional

# Genre terms are repeated this many times in the content soup so they
# carry more weight in the TF-IDF vector than cast/network terms, while
# still letting the (usually much longer) summary dominate naturally.
GENRE_WEIGHT = 3

# Only the top-billed cast members are used — TVmaze already orders cast
# by importance, and a full cast list would dilute the more meaningful
# summary/genre signal.
CAST_NAME_LIMIT = 5


def get_summary_text(doc: Dict[str, Any]) -> str:
    """Return the series' plain-text summary, or "" if missing."""
    summary = doc.get("summary")
    return summary if isinstance(summary, str) else ""


def get_genre_list(doc: Dict[str, Any]) -> List[str]:
    """Return the series' genre list, or [] if missing/malformed."""
    genres = doc.get("genres")
    if not isinstance(genres, list):
        return []
    return [g for g in genres if isinstance(g, str) and g.strip()]


def get_cast_names(doc: Dict[str, Any], limit: int = CAST_NAME_LIMIT) -> List[str]:
    """
    Return up to `limit` top-billed cast member names.

    `doc["cast"]` is either a list of {"person_id", "person_name",
    "character_name", "image_medium"} dicts, or None (when a sync run
    was made with fetch_cast=False). Entries with no person_name are
    skipped rather than inserting a blank token.
    """
    cast_entries = doc.get("cast")
    if not isinstance(cast_entries, list):
        return []
    names: List[str] = []
    for entry in cast_entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("person_name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
        if len(names) >= limit:
            break
    return names


def _extract_channel_name(channel_obj: Any) -> Optional[str]:
    """
    Pull a display name out of a `network` or `web_channel` field.

    TVmaze represents both as nested objects (or null), e.g.
    {"id": 8, "name": "HBO", "country": {"name": "United States", ...}}.
    Returns None if the field is missing, null, or has no "name".
    """
    if not isinstance(channel_obj, dict):
        return None
    name = channel_obj.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def get_channel_names(doc: Dict[str, Any]) -> List[str]:
    """Return the non-null network/web_channel display name(s)."""
    names = []
    for field in ("network", "web_channel"):
        name = _extract_channel_name(doc.get(field))
        if name:
            names.append(name)
    return names


def build_content_soup(doc: Dict[str, Any]) -> str:
    """
    Build the combined text feature ("content soup") for one series
    document, used as a single TF-IDF input document.

    Missing/empty fields are simply omitted, never faked — a series with
    only a summary (no genres/cast/network) still produces valid,
    non-empty text as long as it has *something*.

    Args:
        doc: A `series` MongoDB document (as returned by
            MongoDBManager.get_all_series() / get_series_by_id()).

    Returns:
        A single whitespace-joined string, or "" if the document has no
        usable text content at all.
    """
    content_parts: List[str] = []

    summary = get_summary_text(doc)
    if summary:
        content_parts.append(summary)

    genres = get_genre_list(doc)
    if genres:
        genre_text = " ".join(genres)
        content_parts.extend([genre_text] * GENRE_WEIGHT)

    cast_names = get_cast_names(doc)
    if cast_names:
        content_parts.append(" ".join(n.replace(" ", "_") for n in cast_names))

    channel_names = get_channel_names(doc)
    if channel_names:
        content_parts.append(" ".join(n.replace(" ", "_") for n in channel_names))

    if not content_parts:
        return ""

    series_name = doc.get("name")
    if isinstance(series_name, str) and series_name.strip():
        content_parts.insert(0, series_name.strip())

    return " ".join(content_parts).strip()
