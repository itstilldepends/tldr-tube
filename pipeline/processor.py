"""
Main video processing pipeline.

Orchestrates all steps: metadata fetch → transcript → summarization → DB storage.
"""

import os
import json
from typing import Dict, Optional, Callable
from datetime import datetime

from db.session import get_session
from db.models import Video, Segment
from pipeline.utils import extract_video_id, format_timestamp
from pipeline.metadata import fetch_video_metadata, download_audio
from pipeline.transcript import fetch_youtube_transcript, format_transcript_for_llm
from pipeline.whisper import transcribe_audio
from pipeline.summarize import restore_punctuation, summarize_transcript
from pipeline.embeddings import generate_video_embedding


def process_youtube_video(
    url: str,
    collection_id: Optional[int] = None,
    order_index: Optional[int] = None,
    status_callback: Optional[Callable[[str, str], None]] = None,
    force_asr: bool = False,
    whisper_model: str = "medium",
    provider: str = None,
    model: str = None,
    # Deprecated parameters (kept for backward compatibility)
    claude_model: str = None
) -> Video:
    """
    Process a YouTube video through the complete pipeline.

    Steps:
    1. Extract video_id and check cache
    2. Fetch metadata (title, duration, channel, thumbnail)
    3. Try YouTube transcript API → fallback to Whisper if needed (or force Whisper if requested)
    4. Restore punctuation if auto-generated
    5. Summarize with LLM (TL;DR + segments)
    6. Persist to database
    7. Return Video object

    Args:
        url: YouTube video URL
        collection_id: Optional - ID of collection this video belongs to
        order_index: Optional - Order within collection
        status_callback: Optional - Callback function(step: str, status: str) to report progress
        force_asr: If True, skip YouTube transcript and always use Whisper ASR
        whisper_model: Whisper model size to use ("tiny", "base", "small", "medium", "large")
        provider: LLM provider ("claude", "gemini", "openai"). Defaults to config default.
        model: Model name (provider-specific). Defaults to provider default.
        claude_model: DEPRECATED - Use provider="claude" and model="haiku/sonnet/opus" instead

    Returns:
        Video object with all fields populated

    Raises:
        Exception: If any step fails

    Example:
        >>> video = process_youtube_video("https://www.youtube.com/watch?v=abc123", provider="gemini", model="flash")
        >>> print(video.title)
        'Introduction to Algorithms'
        >>> print(video.tldr)
        'This lecture introduces...'
    """
    # Helper function to update status
    def update_status(step: str, status: str = "running"):
        if status_callback:
            status_callback(step, status)
        # Keep print for terminal debugging
        if status == "running":
            print(f"  ⏳ {step}...")
        elif status == "success":
            print(f"  ✅ {step}")
        elif status == "error":
            print(f"  ❌ {step}")

    # Step 1: Extract video_id and check cache
    update_status("Extracting video ID", "running")
    video_id = extract_video_id(url)

    with get_session() as session:
        existing = session.query(Video).filter_by(video_id=video_id).first()
        if existing:
            update_status("Found in cache, returning existing result", "success")
            return existing

    update_status(f"Starting to process video: {video_id}", "success")

    # Step 2: Fetch metadata
    update_status("Fetching video metadata", "running")
    metadata = fetch_video_metadata(url)
    update_status(f"Metadata fetched: {metadata['title']}", "success")

    # Step 3: Fetch transcript
    transcript = None
    transcript_source = None
    is_auto_generated = False

    # Check if we should force ASR or try YouTube transcript first
    if force_asr:
        update_status(f"Using Whisper ASR ({whisper_model} model) as requested", "running")

        # Create temp directory for audio
        audio_dir = "./data/audio"
        os.makedirs(audio_dir, exist_ok=True)

        update_status("Downloading audio for transcription", "running")
        audio_path = download_audio(url, audio_dir)
        update_status("Audio downloaded successfully", "success")

        update_status(f"Transcribing with mlx-whisper ({whisper_model} model)", "running")
        transcript = transcribe_audio(audio_path, model=whisper_model)
        transcript_source = f"whisper_{whisper_model}"
        is_auto_generated = False  # Whisper output has punctuation
        update_status("Transcription complete", "success")

        # Clean up audio file
        try:
            os.remove(audio_path)
        except:
            pass
    else:
        update_status("Fetching transcript from YouTube", "running")
        try:
            # Try YouTube transcript API first
            transcript, is_auto_generated = fetch_youtube_transcript(video_id)
            transcript_source = "youtube_api"
            caption_type = "auto-generated" if is_auto_generated else "manual"
            update_status(f"Transcript fetched from YouTube ({caption_type})", "success")
        except Exception as e:
            # Fallback to Whisper
            update_status("YouTube transcript not available, using Whisper ASR", "running")

            # Create temp directory for audio
            audio_dir = "./data/audio"
            os.makedirs(audio_dir, exist_ok=True)

            update_status("Downloading audio for transcription", "running")
            audio_path = download_audio(url, audio_dir)
            update_status("Audio downloaded successfully", "success")

            update_status(f"Transcribing with mlx-whisper ({whisper_model} model)", "running")
            transcript = transcribe_audio(audio_path, model=whisper_model)
            transcript_source = f"whisper_{whisper_model}"
            is_auto_generated = False  # Whisper output has punctuation
            update_status("Transcription complete", "success")

            # Clean up audio file
            try:
                os.remove(audio_path)
            except:
                pass

    # Handle backward compatibility
    if claude_model is not None and provider is None:
        provider = "claude"
        model = claude_model

    # Step 4: Restore punctuation if auto-generated
    if is_auto_generated:
        update_status("Restoring punctuation (auto-generated transcript)", "running")
        transcript = restore_punctuation(transcript, provider=provider, model=model)
        update_status("Punctuation restored", "success")

    # Step 5: Summarize with LLM
    provider_display = provider or "default"
    model_display = model or "default"
    update_status(f"Generating bilingual summary with {provider_display} {model_display}", "running")
    video_type, tldr, tldr_zh, segments = summarize_transcript(transcript, video_id, provider=provider, model=model)
    update_status(f"Summary generated (type: {video_type}, {len(segments)} segments, EN+ZH)", "success")

    # Step 6: Persist to database
    update_status("Saving to database", "running")

    # Prepare raw transcript as JSON string
    raw_transcript_json = json.dumps(transcript, ensure_ascii=False)

    # Create Video object
    video = Video(
        source_type="youtube",
        source_url=url,
        video_id=video_id,
        title=metadata["title"],
        description=metadata.get("description"),
        upload_date=metadata.get("upload_date"),
        tags=metadata.get("tags"),
        duration_seconds=metadata["duration_seconds"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        raw_transcript=raw_transcript_json,
        video_type=video_type,
        tldr=tldr,
        tldr_zh=tldr_zh,
        transcript_source=transcript_source,
        collection_id=collection_id,
        order_index=order_index,
        processed_at=datetime.utcnow()
    )

    # Create Segment objects
    segment_objects = []
    for seg in segments:
        segment_objects.append(Segment(
            start_seconds=seg["start_seconds"],
            end_seconds=seg["end_seconds"],
            timestamp=format_timestamp(seg["start_seconds"]),
            summary=seg["summary"],
            summary_zh=seg["summary_zh"]
        ))

    # Save to database
    with get_session() as session:
        session.add(video)
        session.flush()  # Get video.id

        # Associate segments with video
        for seg_obj in segment_objects:
            seg_obj.video_id = video.id
            session.add(seg_obj)

        session.commit()
        session.refresh(video)  # Refresh to get relationships

    update_status(f"Saved to database (ID: {video.id})", "success")

    # Step 7: Generate semantic search embedding
    update_status("Generating semantic search embedding (BGE-M3)", "running")
    try:
        embedding_bytes = generate_video_embedding(video)

        # Save embedding to database
        with get_session() as session:
            video_to_update = session.query(Video).filter_by(id=video.id).first()
            video_to_update.embedding = embedding_bytes
            session.commit()
            session.refresh(video_to_update)
            video = video_to_update  # Update our local reference

        update_status("Semantic search embedding generated", "success")
    except Exception as e:
        # Don't fail the whole pipeline if embedding generation fails
        update_status(f"Warning: Embedding generation failed ({str(e)})", "error")
        print(f"  ⚠️ Continuing without embedding for this video")

    update_status("Processing complete!", "success")

    return video


def get_video_by_id(video_id: str) -> Optional[Video]:
    """
    Get a video from the database by its video_id.

    Args:
        video_id: YouTube video ID or hashed ID for local/S3 videos

    Returns:
        Video object if found, None otherwise
    """
    with get_session() as session:
        return session.query(Video).filter_by(video_id=video_id).first()


def get_all_videos() -> list[Video]:
    """
    Get all standalone videos (not in a collection).

    Returns:
        List of Video objects where collection_id is None
    """
    with get_session() as session:
        return session.query(Video).filter_by(collection_id=None).order_by(Video.processed_at.desc()).all()


def delete_video(video_id: int) -> bool:
    """
    Delete a video and its segments from the database.

    Args:
        video_id: Database ID (not YouTube video_id)

    Returns:
        True if deleted, False if not found
    """
    with get_session() as session:
        video = session.query(Video).filter_by(id=video_id).first()
        if video:
            session.delete(video)  # Cascade will delete segments
            session.commit()
            return True
        return False
