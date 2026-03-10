"""
Generate concept-based study notes from keyframe images + transcript.

Notes are organized by topics/concepts, not one-per-keyframe. The LLM decides
which keyframes to group, skip, and how to structure the notes.

Pipeline:
1. Filter to visual-only keyframes (skip talking head frames)
2. Align subtitles to keyframe time windows
3. Batch keyframes by existing segment boundaries
4. For each batch, send images + subtitles + context to multimodal LLM
5. LLM returns concept-based notes with keyframe references

Functions:
- generate_keyframe_notes: Full pipeline from keyframes to notes
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from pipeline.keyframes import KeyframeInfo, format_time
from pipeline.prompts import NOTE_GENERATION_PROMPT
from pipeline.llm_client import get_llm_client
from pipeline.config import DEFAULT_LLM_PROVIDER, LLM_PROVIDERS, get_model_id

logger = logging.getLogger(__name__)

MAX_KEYFRAMES_PER_BATCH = 15


@dataclass
class ConceptNote:
    """A concept-based note referencing one or more keyframes (bilingual)."""
    title: str
    title_zh: str
    notes: str
    notes_zh: str
    keyframe_indices: list[int]  # indices into the visual_keyframes list
    keyframes: list[KeyframeInfo] = field(default_factory=list)  # resolved keyframe refs


def _align_subtitles(
    keyframes: list[KeyframeInfo],
    transcript: list[dict],
    video_duration: int,
) -> list[str]:
    """Align subtitle text to each keyframe's time window.

    Each keyframe gets all subtitle text from its timestamp until
    the next keyframe's timestamp.
    """
    result = []
    for i, kf in enumerate(keyframes):
        end = keyframes[i + 1].timestamp if i + 1 < len(keyframes) else video_duration
        text = " ".join(
            entry["text"] for entry in transcript
            if entry["start"] >= kf.timestamp and entry["start"] < end
        )
        result.append(text)
    return result


def _batch_by_segments(
    keyframes: list[KeyframeInfo],
    segments: list[dict],
    merge: bool = True,
) -> list[list[int]]:
    """Group keyframe indices by segment boundaries, then merge small adjacent batches.

    Strategy:
    1. Split keyframes by segment time boundaries
    2. Greedily merge adjacent batches while total ≤ MAX_KEYFRAMES_PER_BATCH
    3. Split any batch still over the limit by count

    This maximizes context per LLM call while respecting token limits.
    """
    # Step 1: Split by segments
    if not segments:
        raw_batches = [list(range(len(keyframes)))]
    else:
        raw_batches = []
        for seg in segments:
            seg_start = seg["start_seconds"]
            seg_end = seg["end_seconds"]
            batch = [
                i for i, kf in enumerate(keyframes)
                if kf.timestamp >= seg_start and kf.timestamp < seg_end
            ]
            if batch:
                raw_batches.append(batch)

        # Catch keyframes outside all segments
        assigned = {i for batch in raw_batches for i in batch}
        remaining = [i for i in range(len(keyframes)) if i not in assigned]
        if remaining:
            raw_batches.append(remaining)

    if not raw_batches:
        return [list(range(len(keyframes)))]

    if not merge:
        # No merging — split oversized batches only
        final = []
        for batch in raw_batches:
            if len(batch) > MAX_KEYFRAMES_PER_BATCH:
                for j in range(0, len(batch), MAX_KEYFRAMES_PER_BATCH):
                    final.append(batch[j:j + MAX_KEYFRAMES_PER_BATCH])
            else:
                final.append(batch)
        return final

    # Step 2: Merge adjacent small batches, keep large sections intact
    # A section with > half the limit is "large" — give it its own batch
    # to avoid splitting a cohesive topic across batches
    merge_threshold = MAX_KEYFRAMES_PER_BATCH // 2  # 7

    merged = []
    pending: list[int] = []  # small sections accumulating

    for batch in raw_batches:
        if len(batch) > merge_threshold:
            # Large section: flush pending small ones first, then add as own batch
            if pending:
                merged.append(pending)
                pending = []
            merged.append(batch)
        else:
            # Small section: try to merge with pending
            if len(pending) + len(batch) <= MAX_KEYFRAMES_PER_BATCH:
                pending.extend(batch)
            else:
                if pending:
                    merged.append(pending)
                pending = list(batch)

    if pending:
        merged.append(pending)

    # Step 3: Split any batch still over the limit
    final = []
    for batch in merged:
        if len(batch) > MAX_KEYFRAMES_PER_BATCH:
            for j in range(0, len(batch), MAX_KEYFRAMES_PER_BATCH):
                final.append(batch[j:j + MAX_KEYFRAMES_PER_BATCH])
        else:
            final.append(batch)

    return final


def _build_outline(segments: list[dict], current_batch_indices: list[int], keyframes: list[KeyframeInfo]) -> str:
    """Build outline string from segments, marking the current section."""
    if not segments:
        return "(No segment outline available)"

    batch_start = keyframes[current_batch_indices[0]].timestamp

    lines = []
    for i, seg in enumerate(segments):
        start_str = format_time(int(seg["start_seconds"]))
        end_str = format_time(int(seg["end_seconds"]))
        summary = seg.get("summary", "")[:100]
        marker = " ← CURRENT" if seg["start_seconds"] <= batch_start and seg["end_seconds"] > batch_start else ""
        lines.append(f"{i+1}. [{start_str}–{end_str}] {summary}{marker}")

    return "\n".join(lines)


def _build_keyframes_text(
    keyframes: list[KeyframeInfo],
    subtitles: list[str],
    indices: list[int],
) -> tuple[str, list[str]]:
    """Build keyframes section text and collect image paths.

    Returns (keyframes_text, image_paths).
    Labels use 1-based indexing local to this batch.
    """
    text_parts = []
    image_paths = []

    for local_idx, global_idx in enumerate(indices):
        kf = keyframes[global_idx]
        sub = subtitles[global_idx]
        label = local_idx + 1

        image_paths.append(kf.path)
        text_parts.append(f"[{label}] {kf.timestamp_str}\nTranscript: {sub}")

    return "\n\n".join(text_parts), image_paths


def _parse_notes_response(response_text: str, batch_indices: list[int]) -> list[dict]:
    """Parse LLM JSON response into concept notes with global indices.

    The LLM returns local keyframe_indices (1-based within batch).
    This maps them back to global indices.
    """
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Strip opening fence (```json or ```) and closing fence (```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import ast
        try:
            result = ast.literal_eval(text)
        except Exception:
            logger.error(f"Failed to parse notes response: {text[:500]}")
            return [{"title": "Notes", "keyframe_indices": batch_indices, "notes": "(Failed to parse LLM response)"}]

    if not isinstance(result, list):
        logger.error(f"Expected list, got {type(result)}")
        return [{"title": "Notes", "keyframe_indices": batch_indices, "notes": "(Unexpected LLM response format)"}]

    # Map local 1-based indices to global indices
    notes = []
    for item in result:
        if not isinstance(item, dict):
            continue
        local_indices = item.get("keyframe_indices", [])
        global_indices = []
        for li in local_indices:
            if isinstance(li, int) and 1 <= li <= len(batch_indices):
                global_indices.append(batch_indices[li - 1])
        notes.append({
            "title": item.get("title", "Untitled"),
            "title_zh": item.get("title_zh", ""),
            "keyframe_indices": global_indices,
            "notes": item.get("notes", ""),
            "notes_zh": item.get("notes_zh", ""),
        })

    return notes


def generate_keyframe_notes(
    keyframes: list[KeyframeInfo],
    transcript: list[dict],
    video_duration: int,
    tldr: str,
    segments: list[dict],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status_callback: Optional[Callable] = None,
    merge_batches: bool = True,
) -> list[ConceptNote]:
    """Generate concept-based notes for keyframes using multimodal LLM.

    Args:
        keyframes: All keyframes from extract_keyframes()
        transcript: Raw transcript [{"start": float, "duration": float, "text": str}]
        video_duration: Total video duration in seconds
        tldr: Video TL;DR summary (for context)
        segments: List of segment dicts with start_seconds, end_seconds, summary
        provider: LLM provider (default: project default)
        model: Model name (default: provider default)
        status_callback: Optional progress callback

    Returns:
        List of ConceptNote organized by topics
    """
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    if model is None:
        model = LLM_PROVIDERS[provider]["default_model"]

    model_id = get_model_id(provider, model)

    # Filter to visual keyframes only
    visual_keyframes = [kf for kf in keyframes if kf.is_visual]
    logger.info(f"Generating notes for {len(visual_keyframes)} visual keyframes "
                f"(skipped {len(keyframes) - len(visual_keyframes)} talking head frames)")

    if not visual_keyframes:
        logger.warning("No visual keyframes to generate notes for")
        return []

    # Align subtitles to visual keyframes
    subtitles = _align_subtitles(visual_keyframes, transcript, video_duration)

    # Batch strategy: single batch if few enough keyframes, otherwise split by segments
    seg_dicts = [{"start_seconds": s["start_seconds"], "end_seconds": s["end_seconds"],
                  "summary": s.get("summary", "")}
                 for s in segments] if segments else []

    batches = _batch_by_segments(visual_keyframes, seg_dicts, merge=merge_batches)
    logger.info(f"Split into {len(batches)} batches")

    # Get LLM client
    llm = get_llm_client(provider)

    # Process each batch
    all_notes: list[ConceptNote] = []

    for batch_idx, indices in enumerate(batches):
        if not indices:
            logger.warning(f"Batch {batch_idx} has no keyframes, skipping")
            continue
        if status_callback:
            status_callback(f"Generating notes (batch {batch_idx + 1}/{len(batches)})...")

        outline = _build_outline(seg_dicts, indices, visual_keyframes)
        keyframes_text, image_paths = _build_keyframes_text(visual_keyframes, subtitles, indices)

        # Build previous notes context for continuity
        if all_notes:
            prev_parts = []
            for note in all_notes:
                prev_parts.append(f"- **{note.title}**: {note.notes[:200]}")
            previous_notes = "\n".join(prev_parts)
        else:
            previous_notes = "(This is the first section)"

        prompt = NOTE_GENERATION_PROMPT.format(
            tldr=tldr,
            outline=outline,
            keyframes_text=keyframes_text,
            previous_notes=previous_notes,
        )

        logger.info(f"Batch {batch_idx + 1}: {len(indices)} keyframes, {len(image_paths)} images")
        try:
            response = llm.generate_with_images(
                text=prompt,
                image_paths=image_paths,
                max_tokens=4096,
                temperature=0.3,
                model=model_id,
            )

            parsed = _parse_notes_response(response, indices)
            for item in parsed:
                note = ConceptNote(
                    title=item["title"],
                    title_zh=item.get("title_zh", ""),
                    notes=item["notes"],
                    notes_zh=item.get("notes_zh", ""),
                    keyframe_indices=item["keyframe_indices"],
                    keyframes=[visual_keyframes[i] for i in item["keyframe_indices"]],
                )
                all_notes.append(note)

        except Exception as e:
            logger.error(f"Batch {batch_idx + 1} failed: {e}")
            all_notes.append(ConceptNote(
                title=f"Section {batch_idx + 1}",
                title_zh="",
                notes=f"(Error generating notes: {e})",
                notes_zh="",
                keyframe_indices=indices,
                keyframes=[visual_keyframes[i] for i in indices],
            ))

    logger.info(f"Generated {len(all_notes)} concept notes")
    return all_notes
