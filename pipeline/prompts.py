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

# Main summarization prompt - generates bilingual (EN + ZH) summaries
SUMMARIZATION_PROMPT = """
You are analyzing a video transcript with timestamps to generate a bilingual structured summary (English and Chinese).

**Input**: Complete video transcript with precise timestamps
**Output**: JSON object with the following structure

{{
  "video_type": "tutorial" | "podcast" | "lecture" | "other",
  "tldr": "5-7 sentence overall summary of the entire video in English",
  "tldr_zh": "5-7句中文整体总结",
  "segments": [
    {{
      "start_seconds": 0.0,
      "end_seconds": 285.5,
      "summary": "Concise 3-5 sentence summary in English",
      "summary_zh": "简洁的3-5句中文总结"
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

2. **tldr** (English): Write a 5-7 sentence summary capturing:
   - Main topic and purpose
   - Key points covered
   - Conclusions or takeaways
   - Keep it concise but informative

3. **tldr_zh** (Chinese): Write the same summary in Chinese
   - 用简洁的中文总结视频主要内容
   - 5-7句话
   - 涵盖主题、要点和结论

4. **segments**: Divide the video into logical segments
   - Each segment should be 3-5 minutes long (adjust based on natural topic breaks)
   - Segments should align with content shifts, not arbitrary time intervals
   - Each segment needs BOTH English and Chinese summaries:
     - **summary** (English): Concise 3-5 sentence summary
     - **summary_zh** (Chinese): 简洁的3-5句中文总结
   - **IMPORTANT**: You can see the entire transcript, so maintain coherence
     - Reference concepts introduced earlier
     - Note connections between segments
     - Preserve narrative flow
   - Use exact start/end times from the transcript

5. **Output format**:
   - Return ONLY valid JSON (RFC 8259 compliant)
   - **CRITICAL**: Use DOUBLE QUOTES (") for all keys and string values, NOT single quotes (')
   - Do NOT wrap in markdown code blocks (no ```json```)
   - Do NOT add any commentary or explanation
   - **CRITICAL**: In Chinese text, do NOT use Chinese quotation marks (""''「」)
   - For quotes within Chinese text, use alternative characters like 『』 or just remove them
   - Example of CORRECT format: {{"key": "value"}}
   - Example of WRONG format: {{'key': 'value'}}

**Transcript**:
{transcript}
"""

# Future prompts can be added here:
# - KEYFRAME_SELECTION_PROMPT (for tutorial screenshot selection)
# - EXPORT_FORMATTING_PROMPT (for markdown/PDF export)
# - etc.
