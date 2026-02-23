"""
Semantic and hybrid search for videos using BGE-M3 embeddings.

This module provides:
1. Semantic search: Find similar videos using embedding similarity
2. Keyword search: Exact text matching in title/tldr
3. Hybrid search: Combine semantic + keyword results (recommended)
"""

import numpy as np
from typing import List, Tuple, Optional
from db.session import get_session
from db.models import Video
from pipeline.embeddings import load_model, bytes_to_embedding, embedding_to_bytes


def semantic_search(query: str, top_k: int = 10, min_score: float = 0.3) -> List[Tuple[Video, float]]:
    """
    Find videos semantically similar to the query using BGE-M3 embeddings.

    Args:
        query: Search query text (any language)
        top_k: Maximum number of results to return
        min_score: Minimum similarity score threshold (0-1)

    Returns:
        List of (Video, similarity_score) tuples, sorted by score descending

    Example:
        >>> results = semantic_search("machine learning basics", top_k=5)
        >>> for video, score in results:
        >>>     print(f"{score:.3f} - {video.title}")
    """
    # Generate query embedding
    model = load_model()
    query_embeddings = model.encode(
        [query],
        batch_size=1,
        max_length=8192
    )
    query_vector = query_embeddings['dense_vecs'][0]

    # Fetch all videos with embeddings
    with get_session() as session:
        videos = session.query(Video).filter(Video.embedding.isnot(None)).all()

        if not videos:
            return []

        # Compute similarities
        results = []
        for video in videos:
            video_vector = bytes_to_embedding(video.embedding)

            # Cosine similarity (both vectors are L2-normalized by BGE-M3)
            similarity = float(np.dot(query_vector, video_vector))

            if similarity >= min_score:
                results.append((video, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]


def keyword_search(query: str, top_k: int = 10) -> List[Tuple[Video, str]]:
    """
    Find videos matching keywords in title/tldr (case-insensitive).

    Args:
        query: Search query text
        top_k: Maximum number of results to return

    Returns:
        List of (Video, match_type) tuples where match_type is:
        - "title" if matched in title
        - "tldr" if matched in English TL;DR
        - "tldr_zh" if matched in Chinese TL;DR
        - "title+tldr" if matched in both

    Example:
        >>> results = keyword_search("python tutorial", top_k=5)
        >>> for video, match_type in results:
        >>>     print(f"{match_type} - {video.title}")
    """
    query_lower = query.lower()

    with get_session() as session:
        videos = session.query(Video).all()

        results = []
        for video in videos:
            matches = []

            # Check title
            if query_lower in video.title.lower():
                matches.append("title")

            # Check English TL;DR
            if video.tldr and query_lower in video.tldr.lower():
                matches.append("tldr")

            # Check Chinese TL;DR
            if video.tldr_zh and query_lower in video.tldr_zh.lower():
                matches.append("tldr_zh")

            if matches:
                match_type = "+".join(matches)
                results.append((video, match_type))

        return results[:top_k]


def hybrid_search(
    query: str,
    top_k: int = 10,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    min_semantic_score: float = 0.3
) -> List[Tuple[Video, float, str]]:
    """
    Combine semantic search and keyword search for best results.

    This is the RECOMMENDED search method. It:
    1. Runs semantic search (finds conceptually similar videos)
    2. Runs keyword search (finds exact matches)
    3. Merges results with score boosting for keyword matches
    4. Returns unified ranked list

    Args:
        query: Search query text (any language)
        top_k: Maximum number of results to return
        semantic_weight: Weight for semantic similarity (0-1)
        keyword_weight: Weight for keyword match boost (0-1)
        min_semantic_score: Minimum similarity threshold for semantic results

    Returns:
        List of (Video, combined_score, match_info) tuples where match_info is:
        - "💡 Semantic" for semantic-only matches
        - "🎯 Keyword: {match_type}" for keyword-only matches
        - "🎯💡 Keyword + Semantic" for hybrid matches (best)

    Example:
        >>> results = hybrid_search("deep learning tutorial")
        >>> for video, score, match_info in results:
        >>>     print(f"{score:.3f} {match_info} - {video.title}")
    """
    # Get semantic results
    semantic_results = semantic_search(query, top_k=top_k*2, min_score=min_semantic_score)

    # Get keyword results
    keyword_results = keyword_search(query, top_k=top_k*2)

    # Build unified result set
    video_scores = {}  # video_id -> (video, semantic_score, keyword_match_type)

    # Add semantic results
    for video, sem_score in semantic_results:
        video_scores[video.id] = {
            'video': video,
            'semantic_score': sem_score,
            'keyword_match': None
        }

    # Add/merge keyword results
    for video, match_type in keyword_results:
        if video.id in video_scores:
            # Hybrid match - boost existing semantic result
            video_scores[video.id]['keyword_match'] = match_type
        else:
            # Keyword-only match
            video_scores[video.id] = {
                'video': video,
                'semantic_score': 0.0,
                'keyword_match': match_type
            }

    # Compute combined scores
    results = []
    for vid_id, data in video_scores.items():
        video = data['video']
        sem_score = data['semantic_score']
        keyword_match = data['keyword_match']

        # Compute combined score
        if keyword_match and sem_score > 0:
            # Hybrid: both semantic and keyword
            combined_score = (sem_score * semantic_weight) + keyword_weight
            match_info = "🎯💡 Keyword + Semantic"
        elif keyword_match:
            # Keyword only
            combined_score = keyword_weight
            match_info = f"🎯 Keyword: {keyword_match}"
        else:
            # Semantic only
            combined_score = sem_score * semantic_weight
            match_info = "💡 Semantic"

        results.append((video, combined_score, match_info))

    # Sort by combined score descending
    results.sort(key=lambda x: x[1], reverse=True)

    return results[:top_k]


def get_videos_without_embeddings() -> List[Video]:
    """
    Get all videos that don't have embeddings yet.

    Useful for backfilling embeddings on existing videos.

    Returns:
        List of Video objects with embedding = NULL
    """
    with get_session() as session:
        return session.query(Video).filter(Video.embedding.is_(None)).all()
