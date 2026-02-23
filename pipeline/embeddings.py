"""
BGE-M3 embedding generation for semantic video search.

This module provides:
1. Model loading and caching (BAAI/bge-m3)
2. Video-level embedding generation (title + tldr + tldr_zh)
3. Embedding serialization (numpy → bytes for SQLite storage)
"""

import numpy as np
from FlagEmbedding import BGEM3FlagModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global model cache (lazy loaded)
_model: Optional[BGEM3FlagModel] = None


def load_model() -> BGEM3FlagModel:
    """
    Load BGE-M3 model (lazy initialization, cached globally).

    Returns:
        BGEM3FlagModel: The loaded model instance

    Notes:
        - First call downloads model (~560MB) and takes ~5 seconds to load
        - Subsequent calls return cached instance instantly
        - Model supports up to 8192 tokens (far more than our ~130 token average)
    """
    global _model

    if _model is None:
        logger.info("Loading BGE-M3 model (first time, ~5 seconds)...")
        _model = BGEM3FlagModel(
            'BAAI/bge-m3',
            use_fp16=True  # Use FP16 for faster inference on Apple Silicon
        )
        logger.info("✅ BGE-M3 model loaded successfully")

    return _model


def generate_video_embedding(video) -> bytes:
    """
    Generate embedding for a video (title + tldr + tldr_zh).

    Args:
        video: Video model instance with title, tldr, tldr_zh attributes

    Returns:
        bytes: Serialized embedding (768-dim float32 numpy array → bytes)

    Example:
        >>> video = session.query(Video).first()
        >>> embedding_bytes = generate_video_embedding(video)
        >>> video.embedding = embedding_bytes
        >>> session.commit()
    """
    model = load_model()

    # Combine text for embedding (same format as analyze_content_length.py)
    content = f"{video.title} {video.tldr} {video.tldr_zh}"

    # Generate dense embedding (768 dims)
    # BGE-M3 returns dict with 'dense_vecs', 'lexical_weights', 'colbert_vecs'
    # We only use dense_vecs for now (can add hybrid retrieval later)
    embeddings = model.encode(
        [content],
        batch_size=1,
        max_length=8192  # BGE-M3 max length (our content is ~130 tokens avg)
    )

    # Extract dense vector (shape: [1, 768])
    dense_vec = embeddings['dense_vecs'][0]

    # Convert to bytes for SQLite storage
    return embedding_to_bytes(dense_vec)


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """
    Convert numpy embedding to bytes for database storage.

    Args:
        embedding: numpy array (768-dim float32)

    Returns:
        bytes: Serialized embedding
    """
    # Ensure float32 for consistent size (768 * 4 bytes = 3072 bytes)
    embedding = np.array(embedding, dtype=np.float32)
    return embedding.tobytes()


def bytes_to_embedding(embedding_bytes: bytes) -> np.ndarray:
    """
    Convert bytes from database back to numpy embedding.

    Args:
        embedding_bytes: Serialized embedding from database

    Returns:
        np.ndarray: 768-dim float32 numpy array

    Example:
        >>> video = session.query(Video).first()
        >>> if video.embedding:
        >>>     emb = bytes_to_embedding(video.embedding)
        >>>     print(emb.shape)  # (768,)
    """
    return np.frombuffer(embedding_bytes, dtype=np.float32)


def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        embedding1: First embedding (768-dim)
        embedding2: Second embedding (768-dim)

    Returns:
        float: Cosine similarity score [0, 1] (higher = more similar)

    Note:
        BGE-M3 embeddings are already L2-normalized, so we can use dot product
        instead of full cosine similarity formula.
    """
    # Normalize if not already (BGE-M3 outputs normalized vectors)
    embedding1 = embedding1 / np.linalg.norm(embedding1)
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    # Cosine similarity = dot product for normalized vectors
    return float(np.dot(embedding1, embedding2))
