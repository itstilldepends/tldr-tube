"""
Fetch video metadata using yt-dlp.

Functions:
- fetch_video_metadata: Get title, duration, channel, thumbnail for a YouTube video
- fetch_deeplearning_metadata: Get metadata for a DeepLearning.AI lesson
- fetch_deeplearning_course_lessons: Get all lesson URLs from a DeepLearning.AI course
"""

import re
import yt_dlp
from typing import Dict, List, Optional, Tuple


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

            # Format upload date to YYYY-MM-DD if available
            upload_date = info.get("upload_date")
            if upload_date:
                # yt-dlp returns YYYYMMDD, convert to YYYY-MM-DD
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

            # Get tags as JSON array
            tags = info.get("tags", [])
            import json
            tags_json = json.dumps(tags, ensure_ascii=False) if tags else None

            return {
                "title": info.get("title", "Unknown Title"),
                "description": info.get("description", ""),
                "upload_date": upload_date,
                "tags": tags_json,
                "duration_seconds": info.get("duration", 0),
                "channel_name": info.get("uploader", "Unknown Channel"),
                "thumbnail_url": info.get("thumbnail", ""),
            }
    except Exception as e:
        raise Exception(f"Failed to fetch metadata for {url}: {str(e)}")


def fetch_deeplearning_metadata(url: str) -> Dict[str, any]:
    """
    Fetch metadata for a DeepLearning.AI lesson.

    Parses the __NEXT_DATA__ JSON embedded in the page HTML to extract
    course and lesson information.

    Args:
        url: Full DeepLearning.AI lesson URL

    Returns:
        Dictionary with keys:
        - title: str (e.g. "Build and Train an LLM with JAX - Final MiniGPT")
        - description: str (empty)
        - upload_date: str or None (YYYY-MM-DD)
        - tags: None
        - duration_seconds: int
        - channel_name: "DeepLearning.AI"
        - thumbnail_url: str (empty)

    Raises:
        Exception: If metadata fetching fails
    """
    import requests
    import json
    import re

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not match:
            raise Exception("Could not find __NEXT_DATA__ in page")

        data = json.loads(match.group(1))
        page_props = data["props"]["pageProps"]

        # Flat page props with slugs
        lesson_slug = page_props.get("lessonId", "")
        lesson_name_slug = page_props.get("lessonName", "")

        # Course and lesson info live in tRPC state queries
        trpc_state = page_props["trpcState"]
        course_data = {}
        lesson_data = {}
        for query in trpc_state.get("json", {}).get("queries", []):
            key = query.get("queryKey", [])
            if key and isinstance(key[0], list):
                route = key[0]
                state_data = query.get("state", {}).get("data", {})
                if "getCourseBySlug" in route:
                    course_data = state_data

        # Lookup lesson by slug in course lessons dict
        if course_data and lesson_slug:
            lessons = course_data.get("lessons", {})
            lesson_data = lessons.get(lesson_slug, {})

        course_name = course_data.get("name", "DeepLearning.AI Course")
        lesson_name = lesson_data.get("name", lesson_name_slug)
        title = f"{course_name} - {lesson_name}" if lesson_name else course_name

        duration = lesson_data.get("time", 0) or 0

        released_at = course_data.get("releasedAt", "")
        upload_date = released_at[:10] if released_at else None  # "YYYY-MM-DD"

        return {
            "title": title,
            "description": "",
            "upload_date": upload_date,
            "tags": None,
            "duration_seconds": duration,
            "channel_name": "DeepLearning.AI",
            "thumbnail_url": "",
        }
    except Exception as e:
        raise Exception(f"Failed to fetch DeepLearning.AI metadata for {url}: {str(e)}")


def fetch_deeplearning_course_lessons(url: str) -> Tuple[str, List[Dict]]:
    """
    Fetch all video lessons from a DeepLearning.AI course page.

    Parses the __NEXT_DATA__ JSON to get the course name and ordered lesson list,
    then constructs individual lesson URLs.

    Args:
        url: Course URL (e.g. https://learn.deeplearning.ai/courses/agent-skills-with-anthropic)

    Returns:
        Tuple of:
        - course_name: str (e.g. "Agent Skills with Anthropic")
        - lessons: List of dicts: [{"url": str, "title": str, "order_index": int}, ...]
          Only video-type lessons are included, in course order.

    Raises:
        Exception: If course data cannot be fetched or parsed
    """
    import requests
    import json

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not match:
            raise Exception("Could not find __NEXT_DATA__ in page")

        data = json.loads(match.group(1))
        page_props = data["props"]["pageProps"]
        trpc_state = page_props["trpcState"]

        course_data = None
        for query in trpc_state.get("json", {}).get("queries", []):
            key = query.get("queryKey", [])
            if key and isinstance(key[0], list) and "getCourseBySlug" in key[0]:
                course_data = query["state"]["data"]
                break

        if not course_data:
            raise Exception("Could not find course data in page")

        course_name = course_data["name"]
        course_slug = course_data["slug"]
        lessons_dict = course_data.get("lessons", {})

        _VIDEO_TYPES = {"video", "video_notebook"}

        # All video-type lessons sorted by index
        all_video = sorted(
            [l for l in lessons_dict.values() if l.get("type") in _VIDEO_TYPES],
            key=lambda l: l.get("index", 0),
        )

        # Separate accessible vs locked
        accessible = [l for l in all_video if l.get("accessControl") != "locked"]
        locked_count = len(all_video) - len(accessible)

        if not accessible:
            if all_video:
                raise Exception(
                    f"This course has {len(all_video)} video lesson(s) but all require authentication. "
                    "Please log in to your DeepLearning.AI account and try again."
                )
            raise Exception("No video lessons found in this course.")

        lessons = []
        for i, lesson in enumerate(accessible):
            lesson_slug = lesson["slug"]
            lesson_name = lesson.get("name", "")
            name_slug = re.sub(r"[^a-z0-9]+", "-", lesson_name.lower()).strip("-")
            lesson_url = f"https://learn.deeplearning.ai/courses/{course_slug}/lesson/{lesson_slug}/{name_slug}"
            lessons.append({
                "url": lesson_url,
                "title": lesson_name,
                "order_index": i,
                "locked": False,
            })

        return course_name, lessons, locked_count

    except Exception as e:
        raise Exception(f"Failed to fetch course lessons from {url}: {str(e)}")


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
