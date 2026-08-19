"""
ui/explain.py
================
"WHY THIS?" — turns a recommendation record that
`recommender.recommend.get_recommendations()` already returns
(title, rating, genres, similarity_score) into a short list of plain
reasons the title was suggested.

No new metadata is read, no new similarity is computed, and nothing is
invented: every reason line here is derived directly from fields the
existing TF-IDF + cosine similarity engine already produced. This is a
pure presentation helper — deleting this file and the `why_map` wiring
in streamlit_app.py's render_recommendations() removes the feature
without touching the recommender or the ranking it returns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_why_reasons(source_doc: Optional[Dict[str, Any]], rec: Dict[str, Any]) -> List[str]:
    """
    Plain-language reasons for one recommendation `rec`
    (as returned by recommender.recommend.get_recommendations), given
    the series the user started from (`source_doc`, a MongoDB document).
    """
    reasons: List[str] = []

    source_genres = set((source_doc or {}).get("genres") or [])
    rec_genres = [g for g in (rec.get("genres") or []) if g]
    shared = [g for g in rec_genres if g in source_genres]
    if shared:
        reasons.append(f"🎭 Shares {', '.join(shared[:3])} with the series you picked")

    sim = rec.get("similarity_score")
    if isinstance(sim, (int, float)):
        reasons.append(f"🎯 {sim * 100:.0f}% content match (TF-IDF on genres, summary, cast & network)")

    rating = rec.get("rating")
    if isinstance(rating, (int, float)):
        reasons.append(f"⭐ Rated {rating:.1f}/10 on TVmaze")

    if not reasons:
        reasons.append("📼 Closest overall match found in the catalog right now")

    return reasons


def build_why_map(
    source_doc: Optional[Dict[str, Any]], recs: List[Dict[str, Any]]
) -> Dict[int, List[str]]:
    """{series_id: [reason, ...]} for every recommendation, ready for render_series_grid(why_map=...)."""
    return {
        r["series_id"]: build_why_reasons(source_doc, r)
        for r in recs
        if r.get("series_id") is not None
    }
