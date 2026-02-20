"""
Transcribe audio using mlx-whisper (Apple Silicon optimized).

Functions:
- transcribe_audio: Transcribe audio file to text with timestamps

Note: This module requires Apple Silicon (M1/M2/M3) to run.
Cross-platform support (openai-whisper) is a future TODO.
"""

import mlx_whisper
from typing import List, Dict

from pipeline.config import WHISPER_MODELS, DEFAULT_WHISPER_MODEL


def transcribe_audio(audio_path: str, language: str = None, model: str = None) -> List[Dict]:
    """
    Transcribe audio file using mlx-whisper.

    Args:
        audio_path: Path to audio file (m4a, mp3, wav, etc.)
        language: Optional language code (e.g., "en", "zh"). If None, auto-detect.
        model: Whisper model size to use ("tiny", "base", "small", "medium", "large").
               Defaults to DEFAULT_WHISPER_MODEL from config.

    Returns:
        List of transcript entries: [{"start": float, "duration": float, "text": str}, ...]
        Format matches YouTube transcript API for consistency.

    Raises:
        Exception: If transcription fails

    Example:
        >>> transcript = transcribe_audio("./data/audio/video_id.m4a", model="medium")
        >>> print(transcript[0])
        {"start": 0.0, "duration": 2.5, "text": "Hello world"}

    Note:
        This function uses the mlx-whisper library, which is optimized for Apple Silicon.
        It will not work on Intel Macs or non-macOS systems.
    """
    # Use default model if not specified
    if model is None:
        model = DEFAULT_WHISPER_MODEL

    # Validate model choice
    if model not in WHISPER_MODELS:
        raise ValueError(f"Invalid Whisper model: {model}. Valid options: {list(WHISPER_MODELS.keys())}")

    model_path = WHISPER_MODELS[model]["name"]

    try:
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=model_path,
            language=language,
            word_timestamps=False,  # We use segment timestamps, not word-level
        )

        # Convert mlx-whisper output to our standard format
        # mlx-whisper returns: {"segments": [{"start": ..., "end": ..., "text": ...}]}
        transcript = []
        for segment in result.get("segments", []):
            transcript.append({
                "start": segment["start"],
                "duration": segment["end"] - segment["start"],
                "text": segment["text"].strip(),
            })

        return transcript

    except Exception as e:
        raise Exception(f"Whisper transcription failed for {audio_path}: {str(e)}")


# TODO: Cross-platform support
# def transcribe_audio_openai(audio_path: str, language: str = None) -> List[Dict]:
#     """
#     Fallback transcription using openai-whisper (works on all platforms).
#     Implement this when cross-platform support is needed.
#     """
#     pass
