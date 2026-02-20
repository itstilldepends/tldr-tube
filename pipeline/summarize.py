"""
Summarize video transcripts using Claude API.

Functions:
- restore_punctuation: Fix auto-generated transcripts without punctuation
- summarize_transcript: Generate TL;DR and segmented summaries
"""

import os
import json
import ast
from typing import List, Dict, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv

from pipeline.prompts import PUNCTUATION_RESTORE_PROMPT, SUMMARIZATION_PROMPT
from pipeline.transcript import format_transcript_for_llm
from pipeline.config import CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def restore_punctuation(transcript: List[Dict], model: str = None) -> List[Dict]:
    """
    Restore punctuation in auto-generated YouTube transcripts using Claude.

    Auto-generated transcripts often lack punctuation and paragraph breaks.
    This function uses Claude to lightly restore punctuation while preserving original text.

    Args:
        transcript: List of transcript entries without punctuation
        model: Claude model to use ("haiku", "sonnet", "opus").
               Defaults to DEFAULT_CLAUDE_MODEL from config.

    Returns:
        List of transcript entries with restored punctuation

    Example:
        >>> transcript = [{"start": 0, "duration": 5, "text": "hello world how are you"}]
        >>> fixed = restore_punctuation(transcript, model="sonnet")
        >>> print(fixed[0]["text"])
        "Hello world. How are you?"
    """
    # Use default model if not specified
    if model is None:
        model = DEFAULT_CLAUDE_MODEL

    # Validate model choice
    if model not in CLAUDE_MODELS:
        raise ValueError(f"Invalid Claude model: {model}. Valid options: {list(CLAUDE_MODELS.keys())}")

    model_id = CLAUDE_MODELS[model]["id"]

    # Format transcript as plain text
    text_only = " ".join([entry["text"] for entry in transcript])

    # Call Claude to restore punctuation
    prompt = PUNCTUATION_RESTORE_PROMPT.format(transcript=text_only)

    response = client.messages.create(
        model=model_id,
        max_tokens=len(text_only) + 1000,  # Allow some buffer for punctuation
        messages=[{"role": "user", "content": prompt}]
    )

    restored_text = response.content[0].text.strip()

    # Split restored text back into segments (approximate - keeps original timestamps)
    # This is a simple approach; for production could use more sophisticated alignment
    words = restored_text.split()
    original_words_count = sum(len(entry["text"].split()) for entry in transcript)

    # If word counts are similar, distribute words back to segments proportionally
    restored_transcript = []
    word_index = 0
    for entry in transcript:
        original_word_count = len(entry["text"].split())
        segment_words = words[word_index:word_index + original_word_count]
        restored_transcript.append({
            "start": entry["start"],
            "duration": entry["duration"],
            "text": " ".join(segment_words)
        })
        word_index += original_word_count

    return restored_transcript


def summarize_transcript(
    transcript: List[Dict],
    video_id: str,
    model: str = None
) -> Tuple[str, str, str, List[Dict]]:
    """
    Generate TL;DR and segmented summaries for a video transcript.

    This is a single-pass summarization: Claude sees the entire transcript
    and generates both the overall TL;DR and time-stamped segment summaries
    in one API call, preserving context and coherence.

    Args:
        transcript: List of transcript entries with timestamps
        video_id: YouTube video ID (for error reporting)
        model: Claude model to use ("haiku", "sonnet", "opus").
               Defaults to DEFAULT_CLAUDE_MODEL from config.

    Returns:
        Tuple of:
        - video_type: str ("tutorial" | "podcast" | "lecture" | "other")
        - tldr: str (5-7 sentence overall summary in English)
        - tldr_zh: str (5-7 sentence overall summary in Chinese)
        - segments: List[Dict] with keys:
            - start_seconds: float
            - end_seconds: float
            - summary: str (English)
            - summary_zh: str (Chinese)

    Raises:
        Exception: If Claude API call fails or returns invalid JSON

    Example:
        >>> transcript = [...]  # from fetch_youtube_transcript()
        >>> video_type, tldr, tldr_zh, segments = summarize_transcript(transcript, "abc123", model="sonnet")
        >>> print(video_type)
        'tutorial'
        >>> print(tldr)
        'This video teaches...'
        >>> print(tldr_zh)
        '这个视频讲解了...'
        >>> print(segments[0])
        {'start_seconds': 0.0, 'end_seconds': 285.5, 'summary': '...', 'summary_zh': '...'}
    """
    # Use default model if not specified
    if model is None:
        model = DEFAULT_CLAUDE_MODEL

    # Validate model choice
    if model not in CLAUDE_MODELS:
        raise ValueError(f"Invalid Claude model: {model}. Valid options: {list(CLAUDE_MODELS.keys())}")

    model_id = CLAUDE_MODELS[model]["id"]

    # Format transcript for LLM
    formatted_transcript = format_transcript_for_llm(transcript)

    # Build prompt
    prompt = SUMMARIZATION_PROMPT.format(transcript=formatted_transcript)

    try:
        # Call Claude API
        response = client.messages.create(
            model=model_id,
            max_tokens=4096,  # Enough for TL;DR + segments
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON response
        response_text = response.content[0].text.strip()

        # Remove markdown code blocks if present (sometimes Claude adds them)
        if response_text.startswith("```"):
            # Remove ```json and ``` wrappers
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text

        # Try to parse as JSON first (standard format)
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as json_error:
            # JSON parsing failed, try alternate strategies

            # Strategy 1: Claude might have used Python dict syntax (single quotes)
            # Try parsing with ast.literal_eval BEFORE cleaning Chinese quotes
            try:
                python_dict = ast.literal_eval(response_text)
                result = python_dict
            except:
                # Strategy 2: Clean Chinese quotation marks and retry JSON parsing
                # Remove Chinese quotes entirely (safest approach)
                cleaned_text = response_text
                cleaned_text = cleaned_text.replace('"', '').replace('"', '')  # Remove Chinese double quotes
                cleaned_text = cleaned_text.replace(''', "'").replace(''', "'")  # Chinese single → English single
                cleaned_text = cleaned_text.replace('「', '').replace('」', '')  # Remove Japanese quotes

                try:
                    result = json.loads(cleaned_text)
                except:
                    # If all strategies fail, raise original error with helpful message
                    raise json_error

        # Validate response structure
        required_fields = ["video_type", "tldr", "tldr_zh", "segments"]
        if not all(field in result for field in required_fields):
            raise ValueError(f"Claude response missing required fields. Got: {list(result.keys())}")

        video_type = result["video_type"]
        tldr = result["tldr"]
        tldr_zh = result["tldr_zh"]
        segments = result["segments"]

        # Validate video_type
        valid_types = ["tutorial", "podcast", "lecture", "other"]
        if video_type not in valid_types:
            video_type = "other"  # Default to "other" if invalid

        # Validate segments
        for segment in segments:
            required_segment_fields = ["start_seconds", "end_seconds", "summary", "summary_zh"]
            if not all(field in segment for field in required_segment_fields):
                raise ValueError(f"Segment missing required fields. Got: {list(segment.keys())}")

        return video_type, tldr, tldr_zh, segments

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Claude response as JSON for video {video_id}: {str(e)}\n\nResponse: {response_text}")
    except Exception as e:
        raise Exception(f"Summarization failed for video {video_id}: {str(e)}")
