"""
recommender/bandit.py
======================
Lightweight LinUCB contextual bandit for reranking recommendations.

The bandit sits on top of the existing hybrid candidate generator:
    1. Hybrid scoring produces top-N candidates.
    2. LinUCB reranks them using user context features.
    3. ~80% exploitation (best predicted reward), ~20% exploration (high UCB).

Context features (per user):
    - Genre preference vector (liked/watchlist genre distribution)
    - Rating preference (avg rating of interacted series)
    - Interaction density (total events, normalized)
    - Language preference vector (top 5 languages from interactions)

Context features (per candidate arm):
    - Genre overlap with user preference
    - Rating relative to user preference
    - Free provider availability
    - Popularity (series weight, normalized)

The bandit is stateless per request — it reads the reward matrix from
MongoDB and builds the model on the fly. No model persistence needed
(bandits adapt continuously).
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

# Exploration parameter for UCB
UCB_ALPHA = 0.5

# All possible genres (fixed feature space for consistent arm dimensions)
_ALL_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Drama",
    "Fantasy", "Horror", "Mystery", "Romance", "Science-Fiction",
    "Thriller", "Western", "Documentary", "Family", "History",
    "Musical", "War", "Biography", "Talk-Show",
]

# Top languages to track
_TOP_LANGUAGES = ["English", "Japanese", "Spanish", "Korean", "Hindi", "French", "German"]

# Feature dimensions: genre偏好(20) + rating(1) + interaction_density(1) + lang偏好(7) + quality(1) + free_provider(1) = 31
CONTEXT_DIM = len(_ALL_GENRES) + 1 + 1 + len(_TOP_LANGUAGES) + 1 + 1


def _build_user_context(
    reward_matrix: List[Dict[str, Any]],
    series_metadata: Dict[int, Dict[str, Any]],
) -> np.ndarray:
    """
    Build a context vector for the user from their interaction history.

    Args:
        reward_matrix: [{series_id, total_reward, event_count}] from MongoDB.
        series_metadata: {series_id: {genres, rating, ...}} from model bundle.

    Returns:
        Context vector of shape (CONTEXT_DIM,).
    """
    ctx = np.zeros(CONTEXT_DIM, dtype=np.float32)

    if not reward_matrix:
        # Cold start: uniform genre prefs, neutral rating
        ctx[:len(_ALL_GENRES)] = 1.0 / len(_ALL_GENRES)
        ctx[len(_ALL_GENRES)] = 0.5  # neutral rating
        ctx[len(_ALL_GENRES) + 1] = 0.0  # no interactions
        return ctx

    # Weight interactions by reward (positive interactions matter more)
    genre_counts = np.zeros(len(_ALL_GENRES), dtype=np.float32)
    lang_counts = np.zeros(len(_TOP_LANGUAGES), dtype=np.float32)
    ratings = []
    total_abs_reward = 0.0

    for entry in reward_matrix:
        tid = entry.get("series_id")
        reward = entry.get("total_reward", 0.0)
        if tid is None or tid not in series_metadata:
            continue

        meta = series_metadata[tid]
        weight = max(0.1, abs(reward))  # use abs reward as weight, minimum 0.1

        # Genre features
        for g in (meta.get("genres") or []):
            if g in _ALL_GENRES:
                idx = _ALL_GENRES.index(g)
                genre_counts[idx] += weight

        # Language features
        lang = meta.get("language")
        if lang in _TOP_LANGUAGES:
            idx = _TOP_LANGUAGES.index(lang)
            lang_counts[idx] += weight

        # Rating
        r = meta.get("rating")
        if isinstance(r, (int, float)):
            ratings.append(r)

        total_abs_reward += abs(reward)

    # Normalize
    genre_sum = genre_counts.sum()
    if genre_sum > 0:
        genre_counts /= genre_sum
    else:
        genre_counts = np.ones(len(_ALL_GENRES)) / len(_ALL_GENRES)

    lang_sum = lang_counts.sum()
    if lang_sum > 0:
        lang_counts /= lang_sum

    avg_rating = (np.mean(ratings) / 10.0) if ratings else 0.5
    interaction_density = min(1.0, total_abs_reward / 20.0)

    offset = 0
    ctx[offset:offset + len(_ALL_GENRES)] = genre_counts
    offset += len(_ALL_GENRES)
    ctx[offset] = avg_rating
    offset += 1
    ctx[offset] = interaction_density
    offset += 1
    ctx[offset:offset + len(_TOP_LANGUAGES)] = lang_counts
    offset += len(_TOP_LANGUAGES)
    # Quality and free_provider are per-arm, set to 0 in user context
    return ctx


def _build_arm_features(
    candidate_meta: Dict[str, Any],
    user_ctx: np.ndarray,
    free_provider_count: int = 0,
) -> np.ndarray:
    """
    Build arm feature vector for a candidate series.

    Features align with the user context dimensions for dot product:
        genre_overlap(20) + rating_fit(1) + interaction_bonus(1) + lang_overlap(7) + quality(1) + free(1)
    """
    arm = np.zeros(CONTEXT_DIM, dtype=np.float32)

    # Genre features: 1.0 if candidate has this genre, 0 otherwise
    cand_genres = set(candidate_meta.get("genres") or [])
    for i, g in enumerate(_ALL_GENRES):
        arm[i] = 1.0 if g in cand_genres else 0.0

    # Rating relative to user preference
    rating = candidate_meta.get("rating")
    avg_rating = user_ctx[len(_ALL_GENRES)]  # user's avg rating preference
    if isinstance(rating, (int, float)):
        arm[len(_ALL_GENRES)] = (rating / 10.0 - avg_rating + 0.5)  # centered around user pref
    else:
        arm[len(_ALL_GENRES)] = 0.5

    # Interaction density bonus (slight signal for popular series)
    arm[len(_ALL_GENRES) + 1] = user_ctx[len(_ALL_GENRES) + 1]

    # Language overlap
    lang = candidate_meta.get("language")
    lang_offset = len(_ALL_GENRES) + 2
    if lang in _TOP_LANGUAGES:
        idx = _TOP_LANGUAGES.index(lang)
        arm[lang_offset + idx] = 1.0

    # Quality signal
    quality_offset = lang_offset + len(_TOP_LANGUAGES)
    if isinstance(rating, (int, float)):
        arm[quality_offset] = rating / 10.0
    else:
        arm[quality_offset] = 0.5

    # Free provider signal
    arm[quality_offset + 1] = min(1.0, free_provider_count / 3.0)

    return arm


class LinUCBBandit:
    """
    LinUCB contextual bandit for reranking recommendations.

    This is a stateless, per-request model: it builds A and b matrices
    from the user's reward history and computes UCB scores for each arm.
    """

    def __init__(self, alpha: float = UCB_ALPHA):
        self.alpha = alpha
        self.A = np.eye(CONTEXT_DIM, dtype=np.float64)
        self.b = np.zeros(CONTEXT_DIM, dtype=np.float64)

    def update(self, context: np.ndarray, action: np.ndarray, reward: float) -> None:
        """Update the model with a single observation."""
        self.A += np.outer(action, action)
        self.b += reward * action

    def predict(self, context: np.ndarray, arms: np.ndarray) -> np.ndarray:
        """
        Predict UCB scores for each arm.

        Args:
            context: User context vector (CONTEXT_DIM,).
            arms: Arm feature matrix (n_arms, CONTEXT_DIM).

        Returns:
            UCB scores (n_arms,).
        """
        try:
            A_inv = np.linalg.inv(self.A)
        except np.linalg.LinAlgError:
            A_inv = np.linalg.pinv(self.A)

        theta = A_inv @ self.b

        scores = np.zeros(len(arms), dtype=np.float64)
        for i, arm in enumerate(arms):
            mean = np.dot(theta, arm)
            uncertainty = self.alpha * np.sqrt(np.dot(arm, A_inv @ arm))
            scores[i] = mean + uncertainty

        return scores

    def fit_from_rewards(
        self,
        reward_matrix: List[Dict[str, Any]],
        candidate_ids: List[int],
        series_metadata: Dict[int, Dict[str, Any]],
        user_ctx: np.ndarray,
        free_provider_counts: Optional[Dict[int, int]] = None,
    ) -> np.ndarray:
        """
        Fit the bandit from reward history and return reranked indices.

        Args:
            reward_matrix: User's reward history from MongoDB.
            candidate_ids: List of series_ids to rerank.
            series_metadata: {series_id: meta_dict} from model bundle.
            user_ctx: User context vector.
            free_provider_counts: {series_id: free_count} if available.

        Returns:
            Indices into candidate_ids, sorted by UCB score (descending).
        """
        free_provider_counts = free_provider_counts or {}

        # Update model from reward history
        for entry in reward_matrix:
            tid = entry.get("series_id")
            reward = entry.get("total_reward", 0.0)
            if tid is None or tid not in series_metadata:
                continue
            meta = series_metadata[tid]
            arm = _build_arm_features(meta, user_ctx, free_provider_counts.get(tid, 0))
            self.update(user_ctx, arm, reward)

        # Build arm matrix for candidates
        arms = np.zeros((len(candidate_ids), CONTEXT_DIM), dtype=np.float64)
        for i, tid in enumerate(candidate_ids):
            meta = series_metadata.get(tid, {})
            arms[i] = _build_arm_features(meta, user_ctx, free_provider_counts.get(tid, 0))

        # Predict UCB scores
        scores = self.predict(user_ctx, arms)

        # Return indices sorted by score (descending)
        return np.argsort(scores)[::-1]
