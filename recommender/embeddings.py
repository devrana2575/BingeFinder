"""
recommender/embeddings.py
===========================
Lightweight semantic embedding layer using sentence-transformers.

Provides:
    get_model()           -> cached SentenceTransformer instance
    encode_texts(texts)   -> numpy array of L2-normalized embeddings

The model (all-MiniLM-L6-v2, ~80MB, 384-dim) is auto-downloaded on
first use and cached in-memory per process.  Subsequent calls return
the cached instance instantly.
"""

from __future__ import annotations

from typing import List

import numpy as np

from config import EMBEDDING_MODEL_NAME
from utils.logger import get_logger

logger = get_logger(__name__)

_model = None


def get_model():
    """
    Return the cached SentenceTransformer model, loading it on first call.

    The model is downloaded from Hugging Face Hub on the very first
    invocation and kept in a module-level singleton thereafter.

    Returns:
        A ``sentence_transformers.SentenceTransformer`` instance.
    """
    global _model
    if _model is not None:
        return _model

    logger.info("Loading embedding model '%s' (first load may download ~80 MB)...", EMBEDDING_MODEL_NAME)
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded: %s (dim=%d)", EMBEDDING_MODEL_NAME, _model.get_embedding_dimension())
    except Exception as exc:
        logger.error("Failed to load embedding model: %s", exc)
        raise

    return _model


def encode_texts(texts: List[str], batch_size: int = 256, show_progress: bool = False) -> np.ndarray:
    """
    Encode a list of text strings into L2-normalized embeddings.

    Args:
        texts: List of plain-text strings (content soups).
        batch_size: How many texts to encode per forward pass.
        show_progress: Whether to show a progress bar during encoding.

    Returns:
        A 2-D numpy array of shape ``(len(texts), dim)`` where ``dim``
        is the model's embedding dimension (384 for all-MiniLM-L6-v2).
        Rows are L2-normalized so cosine similarity equals dot product.
    """
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,
    )
    return np.asarray(embeddings, dtype=np.float32)
