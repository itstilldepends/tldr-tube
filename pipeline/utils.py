"""
Utility functions for the pipeline.

Functions:
- extract_video_id: Extract YouTube video ID from URL
- extract_bilibili_id: Extract Bilibili BV ID from URL
- detect_source_type: Detect whether a URL is YouTube or Bilibili
- validate_video_url: Validate YouTube or Bilibili URLs
- generate_timestamp_link: Generate platform-specific timestamp link
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


def extract_bilibili_id(url: str) -> str:
    """
    Extract video ID from a Bilibili URL.

    Supports:
    - https://www.bilibili.com/video/BV1GJ411x7h7
    - https://www.bilibili.com/video/av12345678

    Args:
        url: Bilibili URL string

    Returns:
        Video ID string (e.g. "BV1GJ411x7h7" or "av12345678")

    Raises:
        ValueError: If URL is invalid or video ID cannot be extracted
    """
    match = re.search(r"bilibili\.com/video/(BV[a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)

    match = re.search(r"bilibili\.com/video/av(\d+)", url)
    if match:
        return f"av{match.group(1)}"

    raise ValueError(f"Could not extract Bilibili video ID from URL: {url}")


def detect_source_type(url: str) -> str:
    """
    Detect the video platform from a URL.

    Args:
        url: Video URL string

    Returns:
        "youtube" or "bilibili"

    Raises:
        ValueError: If the URL is not from a supported platform
    """
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    raise ValueError(f"Unsupported video platform: {url}")


def validate_video_url(url: str) -> bool:
    """
    Check if a URL is a valid YouTube or Bilibili URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        source_type = detect_source_type(url)
        if source_type == "youtube":
            extract_video_id(url)
        elif source_type == "bilibili":
            extract_bilibili_id(url)
        return True
    except ValueError:
        return False


def generate_timestamp_link(source_url: str, source_type: str, seconds: int) -> str:
    """
    Generate a platform-specific clickable timestamp link.

    Args:
        source_url: Original video URL
        source_type: "youtube" or "bilibili"
        seconds: Timestamp in seconds

    Returns:
        URL with timestamp parameter appended
    """
    if source_type == "youtube":
        return f"{source_url}&t={seconds}s"
    elif source_type == "bilibili":
        base_url = source_url.split("?")[0]
        return f"{base_url}?t={seconds}"
    return source_url


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
