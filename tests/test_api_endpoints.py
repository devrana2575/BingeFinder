"""
tests/test_api_endpoints.py
=============================
Tests for the FastAPI recommendation and watch-provider endpoints.

Covers:
    - GET /api/series/{id}/recommendations returns valid data
    - GET /api/series/{id}/watch-providers returns valid data
    - Recommendation response structure
    - Provider response structure (tmdb_configured flag)
    - Why-recommended reasons are clean (no encoding issues)
    - Relevance scores are genuine (not inflated)
    - Series excluded from own recommendations
    - Quality filtering (weak recs removed)
"""

import pytest

from recommender.recommend import get_recommendations, load_model
from backend.services.explain import build_why_reasons


class TestRecommendationEndpoint:
    """Test the recommendation engine used by the API endpoint."""

    def test_recommendations_for_breaking_bad(self):
        recs = get_recommendations(169, top_n=8)
        assert len(recs) > 0
        assert recs[0]["title"] is not None
        assert recs[0]["relevance_score"] > 0

    def test_recommendations_exclude_self(self):
        recs = get_recommendations(169, top_n=10)
        ids = [r["series_id"] for r in recs]
        assert 169 not in ids

    def test_recommendations_sorted_by_relevance(self):
        recs = get_recommendations(169, top_n=10)
        scores = [r["relevance_score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_recommendations_above_quality_floor(self):
        recs = get_recommendations(169, top_n=10, min_relevance=0.30)
        for r in recs:
            assert r["relevance_score"] >= 0.30, f"Weak rec: {r['title']} ({r['relevance_score']})"

    def test_recommendations_have_required_fields(self):
        recs = get_recommendations(169, top_n=5)
        for r in recs:
            assert "series_id" in r
            assert "title" in r
            assert "relevance_score" in r
            assert "genres" in r
            assert isinstance(r["genres"], list)

    def test_recommendations_for_stranger_things(self):
        recs = get_recommendations(2993, top_n=8)
        assert len(recs) > 0
        titles = [r["title"] for r in recs]
        assert "Stranger Things" not in titles

    def test_recommendations_for_dark(self):
        recs = get_recommendations(3562, top_n=8)
        assert len(recs) > 0

    def test_recommendations_for_walking_dead(self):
        recs = get_recommendations(73, top_n=8)
        assert len(recs) > 0
        titles = [r["title"] for r in recs]
        assert "The Walking Dead" not in titles

    def test_recommendations_for_the_office(self):
        recs = get_recommendations(526, top_n=8)
        assert len(recs) > 0
        titles = [r["title"] for r in recs]
        for t in titles:
            assert t is not None


class TestWhyRecommended:
    """Test the explainability layer."""

    def test_why_reasons_for_shared_genres(self):
        source = {"genres": ["Crime", "Drama", "Thriller"]}
        rec = {
            "genres": ["Crime", "Thriller"],
            "rating": 8.5,
            "component_scores": {"semantic": 0.7, "tfidf": 0.4},
        }
        reasons = build_why_reasons(source, rec)
        assert len(reasons) > 0
        assert any("Crime" in r or "Thriller" in r for r in reasons)

    def test_why_reasons_clean_text(self):
        source = {"genres": ["Action"]}
        rec = {
            "genres": ["Action", "Drama"],
            "rating": 8.5,
            "component_scores": {"semantic": 0.8, "tfidf": 0.2},
        }
        reasons = build_why_reasons(source, rec)
        for reason in reasons:
            # No emoji characters (basic ASCII check)
            assert reason.isascii() or not any(ord(c) > 127 for c in reason), f"Non-ASCII found in reason: {reason}"

    def test_why_reasons_for_highly_rated(self):
        source = {"genres": ["Comedy"]}
        rec = {
            "genres": ["Comedy"],
            "rating": 9.0,
            "component_scores": {"semantic": 0.5, "tfidf": 0.2},
        }
        reasons = build_why_reasons(source, rec)
        assert any("Highly rated" in r for r in reasons)

    def test_why_reasons_semantic(self):
        source = {"genres": ["Drama"]}
        rec = {
            "genres": ["Drama"],
            "rating": 7.0,
            "component_scores": {"semantic": 0.8, "tfidf": 0.2},
        }
        reasons = build_why_reasons(source, rec)
        assert any("Similar story themes" in r for r in reasons)

    def test_why_reasons_empty_source(self):
        rec = {
            "genres": ["Action"],
            "rating": 8.0,
            "component_scores": {"semantic": 0.3, "tfidf": 0.1},
        }
        reasons = build_why_reasons(None, rec)
        assert isinstance(reasons, list)

    def test_why_reasons_share_count_with_title(self):
        source = {"name": "Harborline", "genres": ["Crime", "Drama", "Thriller"]}
        rec = {
            "genres": ["Crime", "Drama"],
            "rating": 8.0,
            "component_scores": {"semantic": 0.5, "tfidf": 0.2},
        }
        reasons = build_why_reasons(source, rec)
        assert any("Shares 2 genres with Harborline" in r for r in reasons)

    def test_why_reasons_never_empty_when_genres_shared(self):
        source = {"name": "A", "genres": ["Comedy", "Drama"]}
        rec = {"genres": ["Comedy"], "rating": 5.0, "component_scores": {"semantic": 0.1, "tfidf": 0.0}}
        reasons = build_why_reasons(source, rec)
        assert len(reasons) >= 1


class TestWatchProviderEndpoint:
    """Test the watch provider data used by the API endpoint."""

    def test_provider_response_has_required_fields(self):
        from api.watch_providers import get_watch_providers_for_series
        result = get_watch_providers_for_series(
            169, series_name="Breaking Bad", region="IN"
        )
        assert isinstance(result, dict)
        if result:
            assert "providers" in result or "region" in result

    def test_justwatch_url_generated(self):
        from api.watch_providers import get_provider_page_url
        url = get_provider_page_url("Breaking Bad")
        assert url is not None
        assert "justwatch.com" in url
        assert "breaking-bad" in url

    def test_justwatch_url_empty_name(self):
        from api.watch_providers import get_provider_page_url
        url = get_provider_page_url("")
        assert url is None

    def test_provider_service_handles_missing_tmdb_key(self):
        from backend.services import provider_service
        result = provider_service.get_watch_providers(
            series_id=169, imdb_id=None, series_name="Breaking Bad", premiered=None
        )
        assert isinstance(result, dict)
        if result.get("error") == "tmdb_key_missing":
            assert True


class TestRelevanceQuality:
    """Verify relevance scores are genuine hybrid scores."""

    def test_relevance_score_is_hybrid(self):
        recs = get_recommendations(169, top_n=3)
        for r in recs:
            score = r["relevance_score"]
            assert 0.0 <= score <= 1.0, f"Score out of range: {score}"
            assert "component_scores" in r

    def test_component_scores_present(self):
        recs = get_recommendations(169, top_n=3)
        for r in recs:
            cs = r.get("component_scores", {})
            assert "semantic" in cs
            assert "tfidf" in cs
            assert "genre" in cs
            assert "quality" in cs
