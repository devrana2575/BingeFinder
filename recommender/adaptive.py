"""
recommender/adaptive.py
=========================
Adaptive recommendation pipeline using a contextual bandit.

Architecture:
    Candidate Generator (existing hybrid model)
        ↓
    Quality Threshold
        ↓
    Context Feature Builder
        ↓
    Adaptive Ranker (LinUCB)
        ↓
    Diversity Re-ranking
        ↓
    Final Top-K Results

The existing content-based recommender remains the candidate generator.
The adaptive layer decides which candidates should be ranked higher
for a particular user/context.

DO NOT use deep RL. This is a lightweight contextual-bandit-style
ranking approach using reward-based user interaction feedback.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Adaptive pipeline configuration
# ---------------------------------------------------------------------------

# Exploration parameter for UCB (higher = more exploration)
ALPHA = 0.5

# Minimum hybrid relevance to consider a candidate
MIN_RELEVANCE = 0.15

# Maximum from same genre/network for diversity
_MAX_PER_GENRE = 3
_MAX_PER_NETWORK = 2


def _normalize(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize an array to [0, 1]."""
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-10:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


class AdaptiveRanker:
    """
    Contextual bandit ranker that sits on top of the hybrid candidate generator.

    For each user request:
        1. Build user context from interaction history
        2. Build candidate features from metadata
        3. Score each candidate using LinUCB
        4. Return reranked candidates with both relevance and adaptive scores
    """

    def __init__(self, alpha: float = ALPHA):
        self.alpha = alpha
        self.A = None
        self.b = None

    def _init_matrices(self, dim: int) -> None:
        """Initialize or reset A and b matrices."""
        self.A = np.eye(dim, dtype=np.float64)
        self.b = np.zeros(dim, dtype=np.float64)

    def update(self, arm: np.ndarray, reward: float) -> None:
        """Update model with a single observation."""
        self.A += np.outer(arm, arm)
        self.b += reward * arm

    def predict(self, arms: np.ndarray) -> np.ndarray:
        """
        Predict UCB scores for each arm.

        Returns scores where higher = more recommended.
        """
        try:
            A_inv = np.linalg.inv(self.A)
        except np.linalg.LinAlgError:
            A_inv = np.linalg.pinv(self.A)

        theta = A_inv @ self.b
        scores = np.zeros(len(arms), dtype=np.float64)

        for i, arm in enumerate(arms):
            mean = float(np.dot(theta, arm))
            uncertainty = self.alpha * float(np.sqrt(np.dot(arm, A_inv @ arm)))
            scores[i] = mean + uncertainty

        return scores


def build_user_context(
    reward_matrix: List[Dict[str, Any]],
    series_metadata: Dict[int, Dict[str, Any]],
    all_genres: List[str],
    top_languages: List[str],
) -> np.ndarray:
    """
    Build a user context vector from their interaction history.

    Features:
        genre_preference (len(all_genres)) — weighted genre distribution
        rating_preference (1) — avg rating of interacted series
        interaction_density (1) — normalized total interaction weight
        language_preference (len(top_languages)) — weighted language distribution

    Total dimensions: len(all_genres) + 1 + 1 + len(top_languages)
    """
    dim = len(all_genres) + 1 + 1 + len(top_languages)
    ctx = np.zeros(dim, dtype=np.float32)

    if not reward_matrix:
        # Cold start: uniform genre prefs, neutral rating
        ctx[:len(all_genres)] = 1.0 / len(all_genres)
        ctx[len(all_genres)] = 0.5  # neutral rating
        return ctx

    genre_counts = np.zeros(len(all_genres), dtype=np.float32)
    lang_counts = np.zeros(len(top_languages), dtype=np.float32)
    ratings = []
    total_abs_reward = 0.0

    for entry in reward_matrix:
        tid = entry.get("series_id")
        reward = entry.get("total_reward", 0.0)
        if tid is None or tid not in series_metadata:
            continue

        meta = series_metadata[tid]
        weight = max(0.1, abs(reward))

        for g in (meta.get("genres") or []):
            if g in all_genres:
                genre_counts[all_genres.index(g)] += weight

        lang = meta.get("language")
        if lang in top_languages:
            lang_counts[top_languages.index(lang)] += weight

        r = meta.get("rating")
        if isinstance(r, (int, float)):
            ratings.append(r)

        total_abs_reward += abs(reward)

    genre_sum = genre_counts.sum()
    if genre_sum > 0:
        genre_counts /= genre_sum
    else:
        genre_counts = np.ones(len(all_genres)) / len(all_genres)

    lang_sum = lang_counts.sum()
    if lang_sum > 0:
        lang_counts /= lang_sum

    avg_rating = (np.mean(ratings) / 10.0) if ratings else 0.5
    interaction_density = min(1.0, total_abs_reward / 20.0)

    offset = 0
    ctx[offset:offset + len(all_genres)] = genre_counts
    offset += len(all_genres)
    ctx[offset] = avg_rating
    offset += 1
    ctx[offset] = interaction_density
    offset += 1
    ctx[offset:offset + len(top_languages)] = lang_counts

    return ctx


def build_arm_features(
    candidate_meta: Dict[str, Any],
    user_ctx: np.ndarray,
    all_genres: List[str],
    top_languages: List[str],
    free_provider_count: int = 0,
) -> np.ndarray:
    """
    Build arm feature vector for a candidate series.

    Features align with user context dimensions for dot product:
        genre_match (len(all_genres)) — 1 if candidate has genre, 0 otherwise
        rating_fit (1) — rating relative to user preference
        interaction_signal (1) — user's interaction density
        language_match (len(top_languages)) — 1 if candidate matches language
    """
    dim = len(all_genres) + 1 + 1 + len(top_languages)
    arm = np.zeros(dim, dtype=np.float32)

    # Genre features
    cand_genres = set(candidate_meta.get("genres") or [])
    for i, g in enumerate(all_genres):
        arm[i] = 1.0 if g in cand_genres else 0.0

    # Rating relative to user preference
    rating = candidate_meta.get("rating")
    avg_rating = user_ctx[len(all_genres)]
    if isinstance(rating, (int, float)):
        arm[len(all_genres)] = rating / 10.0
    else:
        arm[len(all_genres)] = 0.5

    # Interaction density (user's engagement level)
    arm[len(all_genres) + 1] = user_ctx[len(all_genres) + 1]

    # Language overlap
    lang = candidate_meta.get("language")
    lang_offset = len(all_genres) + 2
    if lang in top_languages:
        arm[lang_offset + top_languages.index(lang)] = 1.0

    return arm


def apply_diversity_reranking(
    ranked_indices: np.ndarray,
    candidates: List[Dict[str, Any]],
    adaptive_scores: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Apply light diversity re-ranking. Returns candidates in final order.
    Relevance remains primary — diversity only demotes.
    """
    genre_counts: Dict[str, int] = {}
    network_counts: Dict[str, int] = {}
    result: List[Dict[str, Any]] = []

    for idx in ranked_indices:
        cand = candidates[idx]
        cand_genres = cand.get("genres") or []
        cand_network = cand.get("network") or "unknown"

        genre_ok = all(genre_counts.get(g, 0) < _MAX_PER_GENRE for g in cand_genres) if cand_genres else True
        network_ok = network_counts.get(cand_network, 0) < _MAX_PER_NETWORK

        if not genre_ok or not network_ok:
            continue

        result.append(cand)
        for g in cand_genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        network_counts[cand_network] = network_counts.get(cand_network, 0) + 1

    return result


def adaptive_rerank(
    candidates: List[Dict[str, Any]],
    reward_matrix: List[Dict[str, Any]],
    series_metadata: Dict[int, Dict[str, Any]],
    all_genres: List[str],
    top_languages: List[str],
    free_provider_counts: Optional[Dict[int, int]] = None,
    alpha: float = ALPHA,
) -> List[Dict[str, Any]]:
    """
    Rerank candidates using the contextual bandit.

    Returns candidates with both relevance_score and adaptive_score.
    Falls back to original ordering if bandit fails.
    """
    if not candidates or len(candidates) < 3:
        return candidates

    free_provider_counts = free_provider_counts or {}

    try:
        user_ctx = build_user_context(reward_matrix, series_metadata, all_genres, top_languages)

        bandit = LinUCBAdaptiveRanker(alpha=alpha)

        # Update bandit from reward history
        for entry in reward_matrix:
            tid = entry.get("series_id")
            reward = entry.get("total_reward", 0.0)
            if tid is None or tid not in series_metadata:
                continue
            arm = build_arm_features(series_metadata[tid], user_ctx, all_genres, top_languages, free_provider_counts.get(tid, 0))
            bandit.update(arm, reward)

        # Build arm features for all candidates
        arms = []
        for cand in candidates:
            tid = cand.get("series_id")
            meta = series_metadata.get(tid, {})
            arm = build_arm_features(meta, user_ctx, all_genres, top_languages, free_provider_counts.get(tid, 0))
            arms.append(arm)

        arms = np.array(arms, dtype=np.float64)
        adaptive_scores = bandit.predict(arms)

        # Attach adaptive scores and sort
        for i, cand in enumerate(candidates):
            cand["adaptive_score"] = round(float(adaptive_scores[i]), 4)

        ranked_indices = np.argsort(adaptive_scores)[::-1]

        # Apply diversity
        result = apply_diversity_reranking(ranked_indices, candidates, adaptive_scores)

        return result

    except Exception as exc:
        logger.warning("Adaptive reranking failed, using original order: %s", exc)
        return candidates


class LinUCBAdaptiveRanker:
    """Thin wrapper around LinUCB for the adaptive pipeline."""

    def __init__(self, alpha: float = ALPHA):
        self.alpha = alpha
        self.A = None
        self.b = None

    def update(self, arm: np.ndarray, reward: float) -> None:
        if self.A is None:
            dim = len(arm)
            self.A = np.eye(dim, dtype=np.float64)
            self.b = np.zeros(dim, dtype=np.float64)
        self.A += np.outer(arm, arm)
        self.b += reward * arm

    def predict(self, arms: np.ndarray) -> np.ndarray:
        if self.A is None:
            return np.zeros(len(arms), dtype=np.float64)

        try:
            A_inv = np.linalg.inv(self.A)
        except np.linalg.LinAlgError:
            A_inv = np.linalg.pinv(self.A)

        theta = A_inv @ self.b
        scores = np.zeros(len(arms), dtype=np.float64)
        for i, arm in enumerate(arms):
            mean = float(np.dot(theta, arm))
            uncertainty = self.alpha * float(np.sqrt(np.dot(arm, A_inv @ arm)))
            scores[i] = mean + uncertainty
        return scores
