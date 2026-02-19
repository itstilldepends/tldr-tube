"""
Utility functions for the pipeline.

Functions:
- extract_video_id: Extract YouTube video ID from URL
- format_timestamp: Convert seconds to MM:SS or HH:MM:SS format
- hash_video_id: Generate unique ID for local/S3 videos
"""

import re
import hashlib
from urllib.parse import urlparse, parse_qs


def extract_video_id(url: str) -> str:
    """
    Extract YouTube video ID from a URL.

    Supports multiple YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/watch?v=VIDEO_ID&t=123s
    - https://m.youtube.com/watch?v=VIDEO_ID

    Args:
        url: YouTube URL string

    Returns:
        Video ID (11 characters)

    Raises:
        ValueError: If URL is invalid or video ID cannot be extracted

    Example:
        >>> extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
    """
    # Pattern 1: youtu.be/VIDEO_ID
    if "youtu.be/" in url:
        match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)

    # Pattern 2: youtube.com/watch?v=VIDEO_ID
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        query_params = parse_qs(parsed.query)
        if "v" in query_params:
            video_id = query_params["v"][0]
            if len(video_id) == 11:
                return video_id

    raise ValueError(f"Could not extract video ID from URL: {url}")


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to MM:SS or HH:MM:SS timestamp format.

    Args:
        seconds: Time in seconds (can be float)

    Returns:
        Formatted timestamp string

    Example:
        >>> format_timestamp(65.5)
        '01:05'
        >>> format_timestamp(3661.2)
        '01:01:01'
        >>> format_timestamp(45)
        '00:45'
    """
    seconds = int(seconds)  # Round down to nearest second
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def hash_video_id(source_url: str) -> str:
    """
    Generate a unique video ID for local/S3 videos using MD5 hash.

    For YouTube videos, use extract_video_id() instead.

    Args:
        source_url: Full path or URL to the video file

    Returns:
        MD5 hash of the URL (first 16 characters)

    Example:
        >>> hash_video_id("/path/to/video.mp4")
        '5d41402abc4b2a76'
        >>> hash_video_id("s3://bucket/video.mp4")
        '7d793037a0760186'
    """
    md5_hash = hashlib.md5(source_url.encode("utf-8")).hexdigest()
    return md5_hash[:16]  # Use first 16 chars to keep it manageable


def validate_youtube_url(url: str) -> bool:
    """
    Check if a URL is a valid YouTube URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid YouTube URL, False otherwise

    Example:
        >>> validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        True
        >>> validate_youtube_url("https://example.com")
        False
    """
    try:
        extract_video_id(url)
        return True
    except ValueError:
        return False
