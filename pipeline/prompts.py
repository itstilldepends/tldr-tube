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

# Prompt for generating concept-based notes from keyframe images + transcript
NOTE_GENERATION_PROMPT = """
You are generating study notes from a lecture video. You receive numbered keyframe
screenshots with the teacher's spoken words during each keyframe's time window.

## Video Overview
{tldr}

## Outline
{outline}

## Notes So Far
{previous_notes}

## Keyframes for Current Section
{keyframes_text}

## Instructions
Organize your notes by **concepts and topics**, NOT one note per keyframe.

- **Group** related keyframes into a single topic (e.g., multiple slides about the same concept, or a scrolling notebook showing one piece of code)
- **Skip** keyframes that add no value — do NOT reference them. Common cases:
  - Talking head / webcam shots (person speaking without useful visual content)
  - Black or blank screens, loading screens, transitions
  - Title slides or section headers with no substantive content
  - Blurry or unreadable frames — mention "[blurry frame skipped]" so the reader knows content existed here but couldn't be captured
- **Deduplicate progressive content**: When multiple keyframes show the same slide/code/notebook at different stages (e.g., PPT adding bullets one by one, code executing line by line, notebook scrolling), reference ONLY the most complete version (all bullets visible, final code output, full notebook). Write notes based on that final state. Do NOT repeat content from intermediate frames
- **Give each topic a short title** that captures the key idea
- Adapt style to content type:
  - Slides: bullet points with key concepts, definitions, formulas
  - Code: annotated code snippets, highlight what matters
  - Diagrams: describe structure, relationships, data flow
  - Formulas: reproduce the formula and explain variables
- Write notes in the same language as the transcript
- Be concise but capture all key information — these notes should be sufficient for revision without rewatching
- If "Notes So Far" is provided, avoid repeating concepts already covered and maintain continuity

Return ONLY a valid JSON array (no markdown code blocks):
[
  {{"title": "Topic title", "title_zh": "主题标题", "keyframe_indices": [1, 2], "notes": "English notes...", "notes_zh": "中文笔记..."}},
  {{"title": "Another topic", "title_zh": "另一个主题", "keyframe_indices": [5, 6, 7], "notes": "...", "notes_zh": "..."}},
  ...
]

IMPORTANT:
- Provide BOTH English and Chinese for title and notes
- **CRITICAL**: In Chinese text, do NOT use Chinese quotation marks (""''「」). Use 『』 or just remove them.
- keyframe_indices should reference the [N] labels of the keyframes above
- A keyframe can appear in at most one topic. Not all keyframes need to be referenced.
"""
