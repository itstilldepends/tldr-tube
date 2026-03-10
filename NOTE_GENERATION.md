# Keyframe Extraction & Note Generation

Design doc for the lecture video note-taking pipeline.
Status: **Fully implemented** — frame extraction, note generation, DB persistence, app UI, queue-based processing.

---

## Key Decisions (locked)

### Video source: DeepLearning.AI / YouTube
- User clicks "Generate Notes" on an already-processed video
- For DeepLearning.AI: HLS stream URL extracted from page `__NEXT_DATA__` tRPC state (`getLessonVideo` query)
- For YouTube: yt-dlp downloads video-only at 720p to `data/videos/{video_id}.mp4`
- Existing `raw_transcript` from DB is used as subtitles — no need to re-fetch

### Note content: keyframe images + raw transcript
- **Do NOT use `segment.summary`** as note content — summaries lack visual context and are too coarse
- Use `raw_transcript` windowed to each keyframe's time range — captures teacher's actual words
- **DO use** existing TL;DR + segment summaries as **context/outline** for the LLM (not as content)

### Single-pass LLM note generation (not two-pass)
- **Do NOT** separately extract structured slide content (title/bullets) then generate notes
- Send keyframe images + corresponding subtitle text directly to multimodal LLM
- Rationale: structured extraction is lossy — diagrams, formulas, code, layout info all get lost
- LLM adapts to content type automatically (PPT, code, whiteboard, diagrams)

### Smart batch merging with context
- Use existing `segment` time boundaries to initially group keyframes
- **Merge strategy** (default, toggleable in UI):
  - Small adjacent sections (≤7 frames each) are greedily merged up to 15 frames per batch
  - Large sections (>7 frames) stay intact as their own batch
  - Maximizes context per LLM call while respecting token limits
  - Reduces total LLM calls and improves cross-section coherence
- **Per-section mode** (optional): each segment becomes its own batch, no merging
- Every batch includes TL;DR + all section summaries as a lightweight "outline" (~400 tokens)
- LLM knows where this section fits in the overall video without receiving full transcript
- If any batch exceeds 15 keyframes, it is split further by count

### Talking head filtering
- Keyframes with Laplacian sharpness < 600 are classified as "talking head" (no useful visual content)
- These frames are excluded from LLM input entirely
- Their subtitle text is merged into adjacent visual keyframes' time windows (no information loss)

### Concept-based notes (not frame-based)
- **Do NOT** generate one note per keyframe — this is rigid and unnatural
- Send all keyframes + subtitles for a section to the LLM and let it organize by **concepts/topics**
- LLM decides which keyframes to group together (e.g., scrolling notebook = one topic with multiple frames)
- LLM decides which keyframes to skip (title slides, transitions, repeated content)
- LLM gives each topic a title for easy scanning
- Output reads like human-written lecture notes, not a frame-by-frame log

### Why not ffmpeg scene detection?
- `select='gt(scene,N)'` compares each frame to its **immediate predecessor**
- Misses gradual changes: PPT adding bullets one by one, code typed line by line
- pHash comparing consecutive frames + keeping **last frame** of each stable period captures complete slides correctly

---

## Tested Parameters

Validated on DeepLearning.AI "Agentic AI - What is agentic AI?" (5 min, 313 frames → 17 keyframes).

| Step | Parameter | Value | Notes |
|------|-----------|-------|-------|
| Dark frame filter | brightness threshold | 15 | Mean pixel value |
| pHash coarse filter | hamming distance | ≥ 5 | Compare consecutive frames, keep last of stable period |
| SSIM fine filter | similarity threshold | < 0.85 | Catches pHash false positives |
| Debounce | window | 4 seconds | Keeps last frame of animation bursts |
| Global dedup | hamming distance | < 12 | Looser threshold for recurring slides |
| Blur detection | absolute threshold | 300 | Laplacian variance |
| Blur detection | relative threshold | 0.85 | vs median of ±2 neighbor keyframes |
| Blur replacement | search window | ±1 second | Direct 10fps sampling from video |
| Talking head | sharpness threshold | < 600 | Text-only for LLM, no image |

---

## Pipeline

### Phase 1: Frame Extraction (local CV, no API calls)

#### Step 1 — Extract frames at 1fps

```bash
ffmpeg -i input.mp4 -vf "fps=1,scale=1280:-1" -q:v 3 frames/frame_%05d.jpg
```

- 60-min video → 3600 frames
- Delete non-keyframes after filtering to reclaim ~500MB

#### Step 1.5 — Filter dark/black frames

Remove frames with mean brightness < 15 (intro/outro/transitions).

#### Step 2 — pHash coarse filter (keep last frame of stable period)

Compare each frame to its **immediate predecessor** (consecutive comparison). When a big change is detected at frame N, keep frame N-1 as the "final state" of the previous slide.

This captures complete slides, not partial builds. Gradual changes (adding bullets one by one) don't trigger the threshold, so the whole build-up is treated as one stable period and we keep the final frame.

```python
def coarse_filter(frame_paths, threshold=5):
    prev_hash = imagehash.phash(Image.open(frame_paths[0]))
    segment_last = frame_paths[0]
    candidates = []
    for path in frame_paths[1:]:
        h = imagehash.phash(Image.open(path))
        if prev_hash - h >= threshold:
            candidates.append(segment_last)  # last frame of previous segment
        segment_last = path
        prev_hash = h
    candidates.append(segment_last)  # final segment
    return candidates
```

#### Step 3 — SSIM fine filter

Catches pHash false positives (lighting shift, compression artifacts). Compares each candidate to its predecessor — if SSIM is high (looks the same), replace the older one with the newer one.

#### Step 4 — Debounce (4s window)

Keep last frame of each burst of changes within 4 seconds (animation settling).

#### Step 5 — Global dedup (pHash < 12)

Remove recurring slides (agenda, recap). Pairwise comparison, keep first occurrence.

#### Step 6 — Blur replacement

For each keyframe with low Laplacian variance (absolute < 300 OR < 85% of neighbor median):
1. Use ffmpeg to sample frames at 10fps within ±1 second directly from the video source
2. Pick the sharpest frame from those samples
3. Replace the blurry keyframe

This is better than searching existing 1fps frames because:
- Narrower window (±1s vs ±3s) = won't land on a different slide
- Higher density (20 candidates vs 2) = more likely to find a sharp frame

---

### Phase 2: Note Generation (LLM calls)

#### Step 7 — Filter and align

1. Remove talking head frames (sharpness < 600), keep only visual keyframes
2. Align subtitles: each visual keyframe gets all transcript text from its timestamp to the next visual keyframe's timestamp (talking head subtitle text naturally merges into adjacent visual frames)

#### Step 8 — Smart batch merging

Group visual keyframes by segment boundaries, then merge small adjacent batches:

```
Raw segments:
  Segment 1 (00:00–05:00) → [kf_0, kf_1, kf_2]           (3 frames, small)
  Segment 2 (05:00–10:00) → [kf_3, kf_4]                  (2 frames, small)
  Segment 3 (10:00–25:00) → [kf_5, ..., kf_14]            (10 frames, large)
  Segment 4 (25:00–30:00) → [kf_15, kf_16]                (2 frames, small)

After merge (default):
  Batch 1: [kf_0, ..., kf_4]    (segments 1+2 merged, 5 frames)
  Batch 2: [kf_5, ..., kf_14]   (segment 3 alone, large section stays intact)
  Batch 3: [kf_15, kf_16]       (segment 4, too small to merge with batch 2)

Per-section mode (no merge):
  Batch 1: [kf_0, kf_1, kf_2]   Batch 2: [kf_3, kf_4]   Batch 3: [kf_5, ..., kf_14]   Batch 4: [kf_15, kf_16]
```

Users can toggle between strategies via "Merge sections" in the UI.

#### Step 9 — LLM concept-based note generation (per batch)

Each batch request contains:

1. **Context header** (~400 tokens, same for every batch):
   ```
   ## Video Overview
   {tldr}

   ## Outline
   1. [00:00–15:30] Introduction to sequence models
   2. [15:30–32:00] Attention mechanism fundamentals  ← CURRENT SECTION
   3. [32:00–48:00] Multi-head attention
   ...
   ```

2. **Previous notes context** (for batch 2+):
   ```
   ## Notes So Far
   - **Attention Mechanism Overview**: The attention mechanism allows the decoder...
   - **Scaled Dot-Product Attention**: The attention score is computed as...
   ```
   Each previous note = title + first 200 chars of content. Gives LLM enough to avoid
   repeating already-covered concepts and maintain continuity, without bloating the prompt.
   First batch sees `(This is the first section)`.

3. **Keyframe images** (base64) with numbered labels and subtitle windows

4. **Prompt** instructs LLM to:
   - Organize notes by **concepts/topics**, not by individual frames
   - **Group** related keyframes into one topic (e.g., notebook scrolling = one topic)
   - **Skip** low-information keyframes (title slides, transitions)
   - Give each topic a **title** for easy scanning
   - Adapt style to content type (slides → bullets, code → annotations, diagrams → descriptions)
   - Reference keyframe numbers so they can be displayed alongside notes
   - Avoid repeating concepts from previous notes, maintain continuity

**Output format** (bilingual):
```json
[
  {
    "title": "What is Agentic AI",
    "title_zh": "什么是智能代理AI",
    "keyframe_indices": [1, 2],
    "notes": "Agentic AI refers to AI systems that...",
    "notes_zh": "智能代理AI是指..."
  },
  {
    "title": "Four Agentic Workflow Patterns",
    "title_zh": "四种智能代理工作流模式",
    "keyframe_indices": [5, 6, 7, 8],
    "notes": "The instructor outlines four key patterns...",
    "notes_zh": "讲师概述了四种关键模式..."
  }
]
```

**Model**: Default to project's configured model (currently Sonnet). Can override per-call.

---

## Output Format

Concept-based bilingual notes with keyframe references:
```json
[
  {
    "title": "Attention Mechanism Overview",
    "title_zh": "注意力机制概述",
    "keyframe_indices": [3, 4, 5],
    "notes": "The attention mechanism allows the decoder to look back at all encoder hidden states...",
    "notes_zh": "注意力机制允许解码器回顾所有编码器的隐藏状态..."
  }
]
```

Each topic references one or more keyframes. Some keyframes may not be referenced (skipped by LLM as low-information). The UI displays the referenced keyframe images alongside the notes. EN and ZH are generated in the same LLM call for consistency.

---

## Database Extension

Two new models:

```python
class Keyframe(Base):
    """Individual extracted keyframe image."""
    __tablename__ = "keyframes"

    id: int                    # PK
    video_id: int              # FK → Video.id
    timestamp_seconds: float
    timestamp_str: str         # "MM:SS"
    frame_path: str            # relative: data/keyframes/{video_id}/frame_{t}.jpg
    sharpness: float           # Laplacian variance score
    is_visual: bool            # True = slide/code, False = talking head

class Note(Base):
    """Concept-based note entry referencing one or more keyframes."""
    __tablename__ = "notes"

    id: int                    # PK
    video_id: int              # FK → Video.id
    order_index: int           # Display order
    title: str                 # Topic title (English)
    title_zh: str              # Topic title (Chinese)
    notes: str                 # LLM-generated note content (English)
    notes_zh: str              # LLM-generated note content (Chinese)
    keyframe_ids: str          # JSON array of Keyframe.id references
```

---

## Dependencies

```
imagehash              # pHash computation
scikit-image           # SSIM
opencv-python-headless # image loading/resizing, Laplacian
ffmpeg                 # frame extraction (CLI)
```

---

## Implementation Order

1. ✅ **`pipeline/keyframes.py`** — Frame extraction + filtering (Steps 1–6)
   - Ported from `scripts/test_keyframes.py`, validated on test video

2. ✅ **`pipeline/keyframe_notes.py`** — Note generation (Steps 7–9)
   - Subtitle alignment, smart batch merging, concept-based bilingual notes
   - Previous notes context passed to each batch for continuity
   - `merge_batches` toggle: merge small sections (default) or keep per-section
   - Tested end-to-end, produces quality bilingual notes

3. ✅ **`db/models.py`** — `Keyframe` + `Note` models, `ProcessingJob.job_type` for queue

4. ✅ **`app.py`** — UI integration
   - "Generate Notes" button (queue-based, non-blocking)
   - "Merge sections" toggle with descriptive tooltip
   - Regenerate confirmation dialog
   - Notes display with keyframe images + bilingual tabs
   - Progress visible in Queue view

### Test scripts

- `scripts/test_keyframes.py` — Frame extraction pipeline test → HTML report
- `scripts/test_notes.py` — End-to-end note generation test → HTML report

```bash
python scripts/test_keyframes.py <deeplearning_ai_lesson_url>
python scripts/test_notes.py <deeplearning_ai_lesson_url>
python scripts/test_notes.py <deeplearning_ai_lesson_url> --compare  # side-by-side merged vs per-section
```
