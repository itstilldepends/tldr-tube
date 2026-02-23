"""
RAG (Retrieval-Augmented Generation) for video Q&A.

This module enables users to ask questions and get AI-generated answers
based on processed video content.
"""

import json
import numpy as np
from typing import List, Tuple, Optional
from db.session import get_session
from db.models import Video, Segment
from pipeline.embeddings import load_model, embedding_to_bytes, bytes_to_embedding
from pipeline.search import hybrid_search
from pipeline.config import get_claude_model_id
from anthropic import Anthropic
import os


def find_relevant_segments(
    question: str,
    video: Video,
    top_k: int = 3
) -> List[Tuple[Segment, float]]:
    """
    Find the most relevant segments within a video for the given question.

    Uses on-the-fly embedding encoding (no DB changes needed).

    Args:
        question: User's question
        video: Video object to search within
        top_k: Number of top segments to return

    Returns:
        List of (segment, similarity_score) tuples, sorted by relevance
    """
    model = load_model()

    # Encode question
    question_embeddings = model.encode([question], batch_size=1, max_length=8192)
    question_vector = question_embeddings['dense_vecs'][0]

    # Get all segments for this video
    with get_session() as session:
        segments = session.query(Segment).filter_by(video_id=video.id).all()

        if not segments:
            return []

        # Compute similarity for each segment
        results = []
        for segment in segments:
            # Combine bilingual content
            segment_text = f"{segment.summary} {segment.summary_zh}"

            # Encode segment (on-the-fly)
            segment_embeddings = model.encode([segment_text], batch_size=1, max_length=8192)
            segment_vector = segment_embeddings['dense_vecs'][0]

            # Compute cosine similarity
            similarity = float(np.dot(question_vector, segment_vector))

            results.append((segment, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]


def extract_transcript_excerpt(
    raw_transcript_json: str,
    start_seconds: float,
    end_seconds: float,
    max_words: int = 300
) -> str:
    """
    Extract transcript text for a specific time range.

    Args:
        raw_transcript_json: JSON string from Video.raw_transcript
        start_seconds: Segment start time
        end_seconds: Segment end time
        max_words: Maximum words to include (truncate if needed)

    Returns:
        Concatenated transcript text for the time range
    """
    try:
        transcript = json.loads(raw_transcript_json)
    except json.JSONDecodeError:
        return "[Transcript not available]"

    excerpt_parts = []

    for entry in transcript:
        entry_start = entry.get('start', 0)
        entry_duration = entry.get('duration', 0)
        entry_end = entry_start + entry_duration

        # Check if this entry overlaps with [start_seconds, end_seconds]
        if entry_end >= start_seconds and entry_start <= end_seconds:
            text = entry.get('text', '').strip()
            if text:
                excerpt_parts.append(text)

    full_excerpt = " ".join(excerpt_parts)

    # Truncate if too long
    words = full_excerpt.split()
    if len(words) > max_words:
        full_excerpt = " ".join(words[:max_words]) + "..."

    return full_excerpt if full_excerpt else "[No transcript for this segment]"


def build_rag_context(
    question: str,
    video_results: List[Tuple[Video, float, str]],
    top_segments_per_video: int = 3
) -> str:
    """
    Build RAG context from retrieved videos and segments.

    Args:
        question: User's question
        video_results: List of (video, score, match_info) from hybrid_search
        top_segments_per_video: Number of segments to retrieve per video

    Returns:
        Formatted context string for Claude API
    """
    context_parts = []

    context_parts.append("=" * 80)
    context_parts.append("RETRIEVED VIDEO CONTENT")
    context_parts.append("=" * 80)
    context_parts.append("")

    for i, (video, video_score, match_info) in enumerate(video_results, 1):
        context_parts.append(f"\n{'=' * 80}")
        context_parts.append(f"VIDEO {i}: {video.title}")
        context_parts.append(f"{'=' * 80}")
        context_parts.append(f"Source: {video.source_url}")
        context_parts.append(f"Channel: {video.channel_name}")
        context_parts.append(f"Duration: {video.duration_seconds // 60}:{video.duration_seconds % 60:02d}")
        context_parts.append(f"Relevance: {match_info} (score: {video_score:.3f})")
        context_parts.append("")
        context_parts.append(f"VIDEO SUMMARY:")
        context_parts.append(f"{video.tldr}")
        context_parts.append("")
        context_parts.append(f"CHINESE SUMMARY:")
        context_parts.append(f"{video.tldr_zh}")
        context_parts.append("")

        # Find relevant segments
        relevant_segments = find_relevant_segments(
            question,
            video,
            top_k=top_segments_per_video
        )

        if relevant_segments:
            context_parts.append(f"RELEVANT SEGMENTS (Top {len(relevant_segments)}):")
            context_parts.append("")

            for j, (segment, seg_score) in enumerate(relevant_segments, 1):
                context_parts.append(f"--- Segment {j} [{segment.timestamp}] (similarity: {seg_score:.3f}) ---")
                context_parts.append("")
                context_parts.append(f"Summary (English): {segment.summary}")
                context_parts.append("")
                context_parts.append(f"Summary (Chinese): {segment.summary_zh}")
                context_parts.append("")

                # Extract transcript excerpt for this segment
                transcript_excerpt = extract_transcript_excerpt(
                    video.raw_transcript,
                    segment.start_seconds,
                    segment.end_seconds,
                    max_words=300
                )
                context_parts.append(f"Original Transcript:")
                context_parts.append(f'"{transcript_excerpt}"')
                context_parts.append("")

        else:
            context_parts.append("(No segments found for this video)")
            context_parts.append("")

    return "\n".join(context_parts)


def generate_rag_answer(
    question: str,
    context: str,
    model: str = "sonnet",
    language_hint: Optional[str] = None
) -> str:
    """
    Generate answer using Claude with RAG context.

    Args:
        question: User's question
        context: Retrieved context (videos + segments + transcripts)
        model: Claude model to use ("haiku", "sonnet", "opus")
        language_hint: Optional language hint ("en", "zh", or None for auto-detect)

    Returns:
        AI-generated answer with citations
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Auto-detect language if not provided
    if language_hint is None:
        # Simple heuristic: if more than 30% Chinese characters, answer in Chinese
        chinese_chars = sum(1 for c in question if '\u4e00' <= c <= '\u9fff')
        language_hint = "zh" if chinese_chars / max(len(question), 1) > 0.3 else "en"

    language_instruction = {
        "en": "Answer in English.",
        "zh": "用中文回答。"
    }.get(language_hint, "Answer in English.")

    prompt = f"""You are a helpful AI assistant answering questions based on YouTube video summaries and transcripts.

The user has processed several videos and stored their summaries. Your task is to answer questions based ONLY on the provided video content.

{context}

{'=' * 80}
USER QUESTION: {question}
{'=' * 80}

INSTRUCTIONS:
1. Answer the question based ONLY on the provided video content above
2. If the videos don't contain enough information to answer the question, say so clearly
3. Include citations with video numbers and timestamps (e.g., "According to Video 1 [05:30], ...")
4. Be concise but thorough - aim for 3-5 paragraphs
5. If multiple videos cover the topic, synthesize the information
6. {language_instruction}
7. Structure your answer with clear paragraphs
8. At the end, include a "References" section listing which videos and timestamps you cited

ANSWER:"""

    response = client.messages.create(
        model=get_claude_model_id(model),
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def answer_question(
    question: str,
    top_k_videos: int = 3,
    top_k_segments: int = 3,
    model: str = "sonnet",
    min_video_score: float = 0.3
) -> dict:
    """
    Complete RAG pipeline: search → retrieve → generate answer.

    Args:
        question: User's question
        top_k_videos: Number of videos to retrieve
        top_k_segments: Number of segments per video
        model: Claude model to use
        min_video_score: Minimum similarity score for video retrieval

    Returns:
        Dictionary with:
        - 'answer': Generated answer text
        - 'videos': List of (video, score, match_info) tuples
        - 'status': 'success' or 'no_results'
    """
    # Step 1: Video-level search
    video_results = hybrid_search(
        query=question,
        top_k=top_k_videos,
        min_semantic_score=min_video_score
    )

    if not video_results:
        return {
            'status': 'no_results',
            'answer': "I couldn't find any relevant videos to answer this question. Please process more videos on this topic first.",
            'videos': []
        }

    # Step 2: Build context with segment-level retrieval
    context = build_rag_context(
        question,
        video_results,
        top_segments_per_video=top_k_segments
    )

    # Step 3: Generate answer with Claude
    answer = generate_rag_answer(
        question,
        context,
        model=model
    )

    return {
        'status': 'success',
        'answer': answer,
        'videos': video_results,
        'context': context  # For debugging
    }
