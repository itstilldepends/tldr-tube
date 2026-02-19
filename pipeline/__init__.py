"""
Pipeline module for tldr-tube.

This module contains all the logic for processing videos:
- Fetching transcripts from YouTube
- Transcribing audio with Whisper (fallback)
- Fetching video metadata
- Summarizing with Claude API
"""
