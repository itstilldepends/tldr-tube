"""
Fetch video metadata using yt-dlp.

Functions:
- fetch_video_metadata: Get title, duration, channel, thumbnail for a YouTube video
"""

import yt_dlp
from typing import Dict, Optional


def fetch_video_metadata(url: str) -> Dict[str, any]:
    """
    Fetch metadata for a YouTube video using yt-dlp.

    Args:
        url: YouTube video URL

    Returns:
        Dictionary with keys:
        - title: str
        - duration_seconds: int
        - channel_name: str
        - thumbnail_url: str

    Raises:
        Exception: If metadata fetching fails

    Example:
        >>> metadata = fetch_video_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> print(metadata["title"])
        'Rick Astley - Never Gonna Give You Up'
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,  # Don't download video, only get info
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "title": info.get("title", "Unknown Title"),
                "duration_seconds": info.get("duration", 0),
                "channel_name": info.get("uploader", "Unknown Channel"),
                "thumbnail_url": info.get("thumbnail", ""),
            }
    except Exception as e:
        raise Exception(f"Failed to fetch metadata for {url}: {str(e)}")


def download_audio(url: str, output_path: str) -> str:
    """
    Download audio from YouTube video for Whisper transcription.

    Args:
        url: YouTube video URL
        output_path: Directory to save audio file

    Returns:
        Path to downloaded audio file

    Raises:
        Exception: If download fails

    Example:
        >>> audio_path = download_audio("https://youtu.be/xxx", "./data/audio/")
        >>> print(audio_path)
        './data/audio/xxx.m4a'
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
        }],
        "outtmpl": f"{output_path}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]
            return f"{output_path}/{video_id}.m4a"
    except Exception as e:
        raise Exception(f"Failed to download audio for {url}: {str(e)}")
