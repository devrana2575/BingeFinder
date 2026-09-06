"""
tests/test_search_ranking.py
==============================
Search ranking tiers:

    exact > prefix > full-token-prefix > contains > fuzzy
and matching that spans the ORIGINAL (non-English) title is honoured.
"""

from backend.services.series_service import search_series


def _docs():
    return [
        {"series_id": 1, "name": "Money Heist: Korea – Joint Economic Area",
         "original_name": "Money Heist: Korea – Joint Economic Area",
         "genres": ["Crime"], "rating": 8.4, "language": "Korean"},
        {"series_id": 2, "name": "Money Heist", "original_name": "La Casa de Papel",
         "genres": ["Crime"], "rating": 8.2, "language": "Spanish"},
        {"series_id": 3, "name": "Breaking Bad", "original_name": "Breaking Bad",
         "genres": ["Drama"], "rating": 9.5, "language": "English"},
        {"series_id": 4, "name": "The Office", "original_name": "The Office",
         "genres": ["Comedy"], "rating": 8.9, "language": "English"},
        {"series_id": 5, "name": "Stranger Things", "original_name": "Stranger Things",
         "genres": ["Sci-Fi"], "rating": 8.6, "language": "English"},
    ]


def test_exact_title_ranks_first_and_spinoff_falls_behind():
    result = search_series(_docs(), query="money heist")
    ids = [d["series_id"] for d in result]
    # "Money Heist" (the original) outranks its longer Korean spin-off.
    assert ids[0] == 2
    assert ids[1] == 1


def test_prefix_rank_is_before_contains():
    result = search_series(_docs(), query="money")
    ids = [d["series_id"] for d in result]
    assert ids[0] == 2
    assert ids[1] == 1
    assert any(d["series_id"] == 3 for d in result) is False


def test_exact_orig_title_and_name_both_match():
    # Original title match ("La Casa de Papel") is honoured.
    result = search_series(_docs(), query="la casa de papel")
    assert result[0]["series_id"] == 2


def test_single_token_prefix_matches_multiword():
    result = search_series(_docs(), query="breaking")
    assert [d["series_id"] for d in result] == [3]


def test_fuzzy_kept_last_after_contains():
    docs = _docs() + [{"series_id": 9, "name": "The Office Space",
                       "original_name": "The Office Space", "genres": [], "rating": 7.0,
                       "language": "English"}]
    result = search_series(docs, query="offce")
    ids = [d["series_id"] for d in result]
    assert 4 in ids  # contains/fuzzy tier keeps it in scope
    assert ids[-1] == 4


def test_query_empty_returns_all_unranked():
    result = search_series(_docs(), query="")
    assert len(result) == len(_docs())


def test_year_filter_applies_together_with_query():
    docs = _docs()
    docs[3]["premiered"] = "2005-03-24"
    docs[4]["premiered"] = "2016-07-15"
    result = search_series(docs, query="the", year=2005)
    assert [d["series_id"] for d in result] == [4]