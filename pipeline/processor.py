"""
Main video processing pipeline.

Orchestrates all steps: metadata fetch → transcript → summarization → DB storage.
"""

import os
import json
from typing import Dict, Optional
from datetime import datetime

from db.session import get_session
from db.models import Video, Segment
from pipeline.utils import extract_video_id, format_timestamp
from pipeline.metadata import fetch_video_metadata, download_audio
from pipeline.transcript import fetch_youtube_transcript, format_transcript_for_llm
from pipeline.whisper import transcribe_audio
from pipeline.summarize import restore_punctuation, summarize_transcript


def process_youtube_video(
    url: str,
    collection_id: Optional[int] = None,
    order_index: Optional[int] = None
) -> Video:
    """
    Process a YouTube video through the complete pipeline.

    Steps:
    1. Extract video_id and check cache
    2. Fetch metadata (title, duration, channel, thumbnail)
    3. Try YouTube transcript API → fallback to Whisper if needed
    4. Restore punctuation if auto-generated
    5. Summarize with Claude (TL;DR + segments)
    6. Persist to database
    7. Return Video object

    Args:
        url: YouTube video URL
        collection_id: Optional - ID of collection this video belongs to
        order_index: Optional - Order within collection

    Returns:
        Video object with all fields populated

    Raises:
        Exception: If any step fails

    Example:
        >>> video = process_youtube_video("https://www.youtube.com/watch?v=abc123")
        >>> print(video.title)
        'Introduction to Algorithms'
        >>> print(video.tldr)
        'This lecture introduces...'
    """
    # Step 1: Extract video_id and check cache
    video_id = extract_video_id(url)

    with get_session() as session:
        existing = session.query(Video).filter_by(video_id=video_id).first()
        if existing:
            print(f"✅ Video {video_id} found in cache, returning existing result")
            return existing

    print(f"📹 Processing new video: {video_id}")

    # Step 2: Fetch metadata
    print(f"  ⏱️  Fetching metadata...")
    metadata = fetch_video_metadata(url)
    print(f"  ✅ Title: {metadata['title']}")

    # Step 3: Fetch transcript
    transcript = None
    transcript_source = None
    is_auto_generated = False

    print(f"  📝 Fetching transcript...")
    try:
        # Try YouTube transcript API first
        transcript, is_auto_generated = fetch_youtube_transcript(video_id)
        transcript_source = "youtube_api"
        print(f"  ✅ Transcript fetched from YouTube ({'auto-generated' if is_auto_generated else 'manual'})")
    except Exception as e:
        # Fallback to Whisper
        print(f"  ⚠️  YouTube transcript not available: {str(e)}")
        print(f"  🎤 Downloading audio for Whisper transcription...")

        # Create temp directory for audio
        audio_dir = "./data/audio"
        os.makedirs(audio_dir, exist_ok=True)

        audio_path = download_audio(url, audio_dir)
        print(f"  ✅ Audio downloaded: {audio_path}")

        print(f"  🎤 Transcribing with mlx-whisper...")
        transcript = transcribe_audio(audio_path)
        transcript_source = "whisper"
        is_auto_generated = False  # Whisper output has punctuation
        print(f"  ✅ Transcription complete")

        # Clean up audio file
        try:
            os.remove(audio_path)
        except:
            pass

    # Step 4: Restore punctuation if auto-generated
    if is_auto_generated:
        print(f"  🔧 Restoring punctuation in auto-generated transcript...")
        transcript = restore_punctuation(transcript)
        print(f"  ✅ Punctuation restored")

    # Step 5: Summarize with Claude
    print(f"  🤖 Generating summary with Claude...")
    video_type, tldr, segments = summarize_transcript(transcript, video_id)
    print(f"  ✅ Summary generated (type: {video_type}, {len(segments)} segments)")

    # Step 6: Persist to database
    print(f"  💾 Saving to database...")

    # Prepare raw transcript as JSON string
    raw_transcript_json = json.dumps(transcript, ensure_ascii=False)

    # Create Video object
    video = Video(
        source_type="youtube",
        source_url=url,
        video_id=video_id,
        title=metadata["title"],
        duration_seconds=metadata["duration_seconds"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        raw_transcript=raw_transcript_json,
        video_type=video_type,
        tldr=tldr,
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
            summary=seg["summary"]
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

    print(f"  ✅ Saved to database (ID: {video.id})")
    print(f"✅ Processing complete!")

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
