"""
Fetch YouTube transcripts using youtube-transcript-api.

Functions:
- fetch_youtube_transcript: Get transcript with timestamps from YouTube
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from typing import List, Dict, Tuple


def fetch_youtube_transcript(video_id: str) -> Tuple[List[Dict], bool]:
    """
    Fetch transcript for a YouTube video.

    Prefers manual captions over auto-generated ones.
    Returns transcript entries with timestamps and a flag indicating if auto-generated.

    Args:
        video_id: YouTube video ID (11 characters)

    Returns:
        Tuple of:
        - List of transcript entries: [{"start": float, "duration": float, "text": str}, ...]
        - is_auto_generated: bool (True if auto-generated, False if manual)

    Raises:
        NoTranscriptFound: If no transcript is available
        TranscriptsDisabled: If transcripts are disabled for this video

    Example:
        >>> transcript, is_auto = fetch_youtube_transcript("dQw4w9WgXcQ")
        >>> print(transcript[0])
        {"start": 0.0, "duration": 2.5, "text": "We're no strangers to love"}
        >>> print(is_auto)
        False
    """
    try:
        # Get list of available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to get manual transcript first (prefer English, then Chinese, then any language)
        try:
            # Try English manual transcript
            transcript_obj = transcript_list.find_manually_created_transcript(["en", "zh-CN", "zh-TW", "zh"])
            transcript = transcript_obj.fetch()
            is_auto_generated = False
        except NoTranscriptFound:
            # Fall back to auto-generated transcript
            try:
                transcript_obj = transcript_list.find_generated_transcript(["en", "zh-CN", "zh-TW", "zh"])
                transcript = transcript_obj.fetch()
                is_auto_generated = True
            except NoTranscriptFound:
                # If preferred languages not found, get any available transcript
                available = list(transcript_list)
                if not available:
                    raise NoTranscriptFound(f"No transcripts available for video {video_id}")

                # Use first available transcript
                transcript_obj = available[0]
                transcript = transcript_obj.fetch()
                is_auto_generated = transcript_obj.is_generated

        return transcript, is_auto_generated

    except TranscriptsDisabled:
        raise TranscriptsDisabled(f"Transcripts are disabled for video {video_id}")
    except NoTranscriptFound as e:
        raise NoTranscriptFound(f"No transcript found for video {video_id}: {str(e)}")


def format_transcript_for_llm(transcript: List[Dict]) -> str:
    """
    Format transcript entries into a readable text with timestamps.

    Args:
        transcript: List of transcript entries from fetch_youtube_transcript()

    Returns:
        Formatted string with timestamps, suitable for LLM processing

    Example:
        >>> entries = [
        ...     {"start": 0.0, "duration": 2.5, "text": "Hello"},
        ...     {"start": 2.5, "duration": 3.0, "text": "World"}
        ... ]
        >>> print(format_transcript_for_llm(entries))
        [00:00] Hello
        [00:02] World
    """
    from pipeline.utils import format_timestamp

    lines = []
    for entry in transcript:
        timestamp = format_timestamp(entry["start"])
        text = entry["text"].strip()
        lines.append(f"[{timestamp}] {text}")

    return "\n".join(lines)
