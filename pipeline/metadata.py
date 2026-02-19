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
        './data/audio/xxx.webm'
    """
    import os

    ydl_opts = {
        # Download best audio format available (usually webm or m4a)
        "format": "bestaudio/best",
        # Save as: output_path/video_id.ext
        "outtmpl": f"{output_path}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        # Don't use postprocessors - mlx-whisper can handle various formats
        # This avoids ffmpeg conversion issues
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]

            # Get the actual downloaded file extension
            # Usually webm, m4a, or opus
            requested_downloads = info.get("requested_downloads", [])
            if requested_downloads:
                filepath = requested_downloads[0]["filepath"]
                return filepath
            else:
                # Fallback: try common extensions
                for ext in ["webm", "m4a", "opus", "mp3"]:
                    potential_path = f"{output_path}/{video_id}.{ext}"
                    if os.path.exists(potential_path):
                        return potential_path

                # If still not found, raise error
                raise Exception(f"Downloaded file not found for video {video_id}")
    except Exception as e:
        raise Exception(f"Failed to download audio for {url}: {str(e)}")
