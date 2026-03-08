"""
Fetch video transcripts from YouTube and Bilibili.

Functions:
- fetch_youtube_transcript: Get transcript with timestamps from YouTube API
- fetch_bilibili_transcript: Get subtitles from Bilibili via yt-dlp
- format_transcript_for_llm: Format transcript entries for LLM input
"""

import os
import re
import tempfile
from typing import List, Dict, Tuple

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


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


def _vtt_time_to_seconds(time_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    parts = time_str.strip().replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def _parse_vtt(path: str) -> List[Dict]:
    """
    Parse a WebVTT subtitle file into standard transcript format.

    Args:
        path: Path to .vtt file

    Returns:
        List of [{"start": float, "duration": float, "text": str}, ...]
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    # Split on blank lines to get cue blocks
    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        lines = block.strip().splitlines()
        # Find the timing line: "HH:MM:SS.mmm --> HH:MM:SS.mmm"
        timing_idx = None
        for i, line in enumerate(lines):
            if "-->" in line:
                timing_idx = i
                break
        if timing_idx is None:
            continue

        timing = lines[timing_idx]
        start_str, end_str = timing.split("-->")
        # Strip any positioning tags after the end time
        end_str = end_str.split()[0]

        start = _vtt_time_to_seconds(start_str.strip())
        end = _vtt_time_to_seconds(end_str.strip())
        duration = end - start

        # Text is everything after the timing line, stripped of tags
        text_lines = lines[timing_idx + 1:]
        text = " ".join(text_lines).strip()
        # Remove VTT inline tags like <00:00:01.000><c>text</c>
        text = re.sub(r"<[^>]+>", "", text).strip()

        if text:
            entries.append({"start": start, "duration": duration, "text": text})

    return entries


def fetch_bilibili_transcript(url: str) -> Tuple[List[Dict], bool]:
    """
    Fetch subtitles for a Bilibili video using yt-dlp.

    Tries to download CC subtitles (manual first, then auto-generated).
    Prefers Chinese subtitles, falls back to English.

    Args:
        url: Full Bilibili video URL

    Returns:
        Tuple of:
        - List of transcript entries: [{"start": float, "duration": float, "text": str}, ...]
        - is_auto_generated: bool

    Raises:
        NoTranscriptFound: If no subtitles are available for this video
    """
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh-Hans", "zh", "zh-CN", "en"],
            "skip_download": True,
            "outtmpl": os.path.join(tmpdir, "sub"),
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        vtt_files = sorted(
            [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        )
        if not vtt_files:
            raise NoTranscriptFound("No subtitles found for this Bilibili video")

        # Prefer manual subtitles (files without "auto" in name)
        manual = [f for f in vtt_files if "auto" not in f.lower()]
        chosen = manual[0] if manual else vtt_files[0]
        is_auto = "auto" in chosen.lower()

        transcript = _parse_vtt(os.path.join(tmpdir, chosen))
        if not transcript:
            raise NoTranscriptFound("Subtitle file was empty or could not be parsed")

        return transcript, is_auto


def fetch_deeplearning_transcript(url: str) -> Tuple[List[Dict], bool]:
    """
    Fetch transcript for a DeepLearning.AI lesson.

    Parses the __NEXT_DATA__ JSON embedded in the page HTML to extract captions
    from the getLessonVideoSubtitle tRPC query.

    Args:
        url: Full DeepLearning.AI lesson URL

    Returns:
        Tuple of:
        - List of transcript entries: [{"start": float, "duration": float, "text": str}, ...]
        - is_auto_generated: always False (manual captions)

    Raises:
        NoTranscriptFound: If no captions are found in the page
    """
    import requests
    import json

    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if not match:
        raise Exception("Could not find __NEXT_DATA__ in page")

    data = json.loads(match.group(1))

    trpc_state = data["props"]["pageProps"]["trpcState"]
    captions = None
    for query in trpc_state.get("json", {}).get("queries", []):
        key = query.get("queryKey", [])
        # key[0] is a list like ['course', 'getLessonVideoSubtitle']
        if key and isinstance(key[0], list) and "getLessonVideoSubtitle" in key[0]:
            captions = query["state"]["data"]["captions"]
            break

    if not captions:
        session_data = data["props"]["pageProps"].get("session")
        if not session_data:
            raise Exception(
                "No captions found. This lesson requires a DeepLearning.AI account. "
                "Please log in and try again."
            )
        raise Exception("No captions found for this lesson.")

    transcript = [
        {
            "start": float(c["startInSeconds"]),
            "duration": float(c["endInSeconds"]) - float(c["startInSeconds"]),
            "text": c["text"],
        }
        for c in captions
    ]
    return transcript, False


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
