"""
Claude API prompts for tldr-tube.

All prompts are stored as named constants here.
Never inline prompts in business logic - always reference these constants.
"""

# Prompt for restoring punctuation in auto-generated transcripts
PUNCTUATION_RESTORE_PROMPT = """
The following is a YouTube auto-generated transcript without punctuation.
Please restore punctuation and proper paragraph breaks while keeping the original text unchanged.

Only add punctuation marks (periods, commas, question marks, etc.) and paragraph breaks.
Do NOT modify, rephrase, or translate the text.
Return the corrected transcript directly without any commentary.

Transcript:
{transcript}
"""

# Main summarization prompt - generates video_type, TL;DR, and segments in one call
SUMMARIZATION_PROMPT = """
You are analyzing a video transcript with timestamps to generate a structured summary.

**Input**: Complete video transcript with precise timestamps
**Output**: JSON object with the following structure

{{
  "video_type": "tutorial" | "podcast" | "lecture" | "other",
  "tldr": "5-7 sentence overall summary of the entire video",
  "segments": [
    {{
      "start_seconds": 0.0,
      "end_seconds": 285.5,
      "summary": "Concise 3-5 sentence summary of this time segment"
    }},
    ...
  ]
}}

**Requirements**:

1. **video_type**: Detect based on content style
   - "tutorial": Step-by-step instructions, how-to, demonstrations
   - "podcast": Conversational, interviews, discussions
   - "lecture": Educational, academic, structured teaching
   - "other": Everything else

2. **tldr**: Write a 5-7 sentence summary capturing:
   - Main topic and purpose
   - Key points covered
   - Conclusions or takeaways
   - Keep it concise but informative

3. **segments**: Divide the video into logical segments
   - Each segment should be 3-5 minutes long (adjust based on natural topic breaks)
   - Segments should align with content shifts, not arbitrary time intervals
   - Each summary should be 3-5 sentences
   - **IMPORTANT**: You can see the entire transcript, so maintain coherence
     - Reference concepts introduced earlier
     - Note connections between segments
     - Preserve narrative flow
   - Use exact start/end times from the transcript

4. **Output format**:
   - Return ONLY valid JSON
   - Do NOT wrap in markdown code blocks
   - Do NOT add any commentary or explanation
   - Ensure all quotes are properly escaped

**Transcript**:
{transcript}
"""

# Future prompts can be added here:
# - KEYFRAME_SELECTION_PROMPT (for tutorial screenshot selection)
# - EXPORT_FORMATTING_PROMPT (for markdown/PDF export)
# - etc.
