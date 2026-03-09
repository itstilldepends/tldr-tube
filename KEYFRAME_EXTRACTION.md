# Keyframe Extraction & Note Generation

Design doc for the lecture video note-taking pipeline.
Status: **Planned** — not yet implemented.

---

## Key Decisions (locked)

### Video source: YouTube auto-download
- User clicks "Generate Notes" on an already-processed YouTube video
- yt-dlp downloads video-only at 720p (~300–500MB) to `data/videos/{video_id}.mp4`
- File is kept after download so re-running notes doesn't require re-downloading
- Existing `raw_transcript` from DB is used as subtitles — no need to re-fetch

### Note content: raw transcript only (not summaries)
- **Do NOT use `segment.summary`** as LLM input — summaries were generated without visual context and are too coarse (5–10 min per segment vs 2 min per slide)
- Use `raw_transcript` windowed to each keyframe's time range → captures teacher's actual words, definitions, formulas
- Use `segment` time boundaries only for **section structure** (grouping keyframes into chapters)

### Output structure
```
## Section 1: 00:00 – 05:30
  [Keyframe 00:45]  <screenshot>
  Slide: "Q/K/V matrices"
  Explanation: "The attention score is computed by..." [from raw transcript]

  [Keyframe 02:30]  <screenshot>
  ...

## Section 2: 05:30 – 12:00
  ...
```

---

## Goal

Given a YouTube video already processed in the app (has transcript + segments in DB), generate structured notes on demand. Each note entry contains:
- Timestamp
- Keyframe screenshot
- Slide content (extracted by multimodal LLM)
- Teacher's explanation (from raw transcript window)

Target use case: lecture/course videos with PPT slides. Expected output: 20–40 keyframes per 60-minute video.

---

## Input / Output

**Input**
- `video_id` of an already-processed YouTube video in the DB
- `raw_transcript` from DB (JSON: `[{"start": 0.5, "duration": 2.3, "text": "..."}]`)
- `segments` from DB (for section boundaries only)
- Video file downloaded to `data/videos/{video_id}.mp4` (auto-downloaded if not present)

**Output**
```json
[
  {
    "timestamp": 125,
    "timestamp_str": "02:05",
    "frame_path": "data/keyframes/{video_id}/frame_00125.jpg",
    "slide_content": {
      "title": "Attention Mechanism",
      "bullets": ["Q/K/V matrices", "Scaled dot-product attention"],
      "has_diagram": true
    },
    "explanation": "The teacher explains how attention scores are computed..."
  }
]
```

---

## Pipeline

### Step 1 — Frame Extraction (1fps)

```bash
ffmpeg -i input.mp4 -vf "fps=1,scale=1280:-1" -q:v 3 frames/frame_%05d.jpg
```

- 1fps is sufficient for slide content (slides are static for minutes)
- 1280px width balances quality vs. processing speed
- Filename encodes timestamp: `frame_00125.jpg` → 125 seconds
- 60-min video → 3600 frames (before filtering)

**Storage note**: Delete non-keyframes after Step 3 to avoid accumulating ~500MB of temp files.

---

### Step 2 — pHash Coarse Filter

Iterate frames sequentially, compute pHash of each frame. Compare to previous frame using Hamming distance.

- **Distance < 5** → identical content, discard
- **Distance ≥ 5** → potential scene change, keep for Step 3

```python
import imagehash
from PIL import Image

def coarse_filter(frame_paths: list[str], threshold: int = 5) -> list[str]:
    candidates = [frame_paths[0]]
    prev_hash = imagehash.phash(Image.open(frame_paths[0]))
    for path in frame_paths[1:]:
        h = imagehash.phash(Image.open(path))
        if prev_hash - h >= threshold:
            candidates.append(path)
            prev_hash = h
    return candidates
```

Expected reduction: 3600 → 300–500 candidates.

---

### Step 3 — SSIM Fine Filter

For each candidate, compare against the last confirmed keyframe using SSIM. This catches cases where pHash passed but content is nearly identical (e.g. cursor moved, minor animation).

- **SSIM ≥ 0.85** → not a meaningful change, discard
- **SSIM < 0.85** → confirmed new keyframe

```python
from skimage.metrics import structural_similarity as ssim
import cv2

def fine_filter(candidates: list[str], threshold: float = 0.85) -> list[str]:
    keyframes = [candidates[0]]
    prev = cv2.imread(candidates[0], cv2.IMREAD_GRAYSCALE)
    prev = cv2.resize(prev, (640, 360))
    for path in candidates[1:]:
        curr = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        curr = cv2.resize(curr, (640, 360))
        score, _ = ssim(prev, curr, full=True)
        if score < threshold:
            keyframes.append(path)
            prev = curr
    return keyframes
```

---

### Step 4 — Debounce (Animation Settling)

Slide transitions often trigger multiple consecutive keyframe detections within a few seconds (animation frames). Keep only the final settled state.

**Important**: Process the full keyframe list as a post-processing step — do not apply debounce inline during Step 3, since you need lookahead.

```python
def debounce(keyframe_times: list[int], window: int = 4) -> list[int]:
    """Keep the last frame in each burst of changes within `window` seconds."""
    result = []
    i = 0
    while i < len(keyframe_times):
        j = i
        while j < len(keyframe_times) - 1 and keyframe_times[j + 1] - keyframe_times[i] < window:
            j += 1
        result.append(keyframe_times[j])
        i = j + 1
    return result
```

---

### Step 5 — Global Dedup

A slide may appear multiple times (e.g. recap, agenda slide revisited). Compare all remaining keyframes pairwise. Use a looser threshold than Step 2 since rendering conditions may vary.

- **Hamming distance < 12** across all pairs → merge group, keep first occurrence only

```python
def global_dedup(keyframe_paths: list[str], threshold: int = 12) -> list[str]:
    hashes = [(p, imagehash.phash(Image.open(p))) for p in keyframe_paths]
    seen = []
    for path, h in hashes:
        if not any(h - seen_h < threshold for _, seen_h in seen):
            seen.append((path, h))
    return [p for p, _ in seen]
```

---

### Step 6 — Subtitle Alignment

Load the subtitle file and associate each keyframe with the subtitle text spoken between it and the next keyframe.

```python
def align_subtitles(
    keyframe_times: list[int],
    subtitles: list[dict],  # [{"start": float, "duration": float, "text": str}]
    video_duration: int,
) -> list[dict]:
    result = []
    for i, t in enumerate(keyframe_times):
        end = keyframe_times[i + 1] if i + 1 < len(keyframe_times) else video_duration
        text = " ".join(
            s["text"] for s in subtitles
            if s["start"] >= t and s["start"] < end
        )
        result.append({"timestamp": t, "subtitle_text": text})
    return result
```

---

### Step 7 — Multimodal LLM: Slide Understanding

Send keyframe images to a multimodal LLM to extract structured slide content. Batch requests to reduce API round-trips (send up to 10 images per request with numbered labels).

**Model choice**: Start with a cheaper model (Gemini Flash or Claude Haiku) since slide OCR doesn't require strong reasoning.

**Prompt**:
```
Below are screenshots from a lecture presentation, labeled [1] through [N].
For each image, return a JSON object with:
- "title": the slide title or heading (empty string if none)
- "bullets": list of key points as strings
- "has_diagram": true if the slide contains charts, graphs, or diagrams
- "notes": any other relevant content (formulas, code snippets, etc.)

Return a JSON array of N objects in order.
```

---

### Step 8 — LLM: Note Generation

Send all structured entries (timestamp + slide content + subtitle text) to a single LLM call to generate coherent course notes.

**Input format per entry**:
```
[02:05] Slide: "Attention Mechanism" | Bullets: Q/K/V matrices, scaled dot-product
Teacher: "So the attention score is computed by taking the dot product of Q and K..."
```

**Output**: Structured markdown with sections per topic, key points, and timestamp backlinks.

---

## Calibration Metrics

After a test run on a known video, check:

| Metric | Target | Action if off |
|--------|--------|---------------|
| Total keyframes | 20–40 per 60 min | Too many → tighten Step 2/3 thresholds |
| Missing slides | 0 obvious gaps | Too few → loosen thresholds |
| Duplicate slides | ≤ 1 per unique slide | Too many → tighten Step 5 threshold |

Recommended tuning order: Step 2 (pHash) → Step 3 (SSIM) → Step 4 (debounce window).

**Suggested initial values**:
- Step 2 pHash threshold: `5`
- Step 3 SSIM threshold: `0.85`
- Step 4 debounce window: `4` seconds
- Step 5 global dedup threshold: `12`

---

## Database Extension

New model needed:

```python
class Keyframe(Base):
    __tablename__ = "keyframes"

    id: int                    # PK
    video_id: int              # FK → Video.id
    timestamp_seconds: float
    timestamp_str: str         # "MM:SS"
    frame_path: str            # relative path: data/keyframes/{video_id}/frame_{t}.jpg
    slide_title: str
    slide_bullets: str         # JSON array
    has_diagram: bool
    slide_notes: str
    explanation: str           # LLM-generated summary from subtitle window
```

Storage path: `data/keyframes/{video_id}/frame_{timestamp:05d}.jpg`

---

## Dependencies

```
imagehash        # pHash computation
scikit-image     # SSIM
opencv-python    # image loading/resizing
ffmpeg           # frame extraction (CLI, not Python package)
```

---

## Implementation Order

1. **`pipeline/keyframes.py`** — Steps 1–5 (frame extraction + filtering)
   - Test standalone with a local video file first before touching UI
   - Validate: 20–40 keyframes per 60-min lecture, no obvious missing slides
2. **Download logic** in `pipeline/keyframes.py` — `download_video(url, output_path)` via yt-dlp (720p video-only)
3. **`pipeline/keyframe_notes.py`** — Steps 6–8
   - `align_with_transcript(keyframe_times, transcript_json, segments, video_duration)` — returns per-keyframe subtitle window + section label
   - `describe_frames(entries)` — Claude Vision batched (10 images/request)
   - `generate_notes(entries)` — final note synthesis
4. **`db/models.py`** — add `Keyframe` model
5. **UI** — "📝 Generate Notes" button in video detail view, 4-stage progress, notes display

**Estimate**: 5–8 hours including calibration.

### Where to pick up next session
Start with step 1: implement and test `pipeline/keyframes.py` extraction + filtering logic on a sample video. Once keyframe count looks right (20–40 for 60 min), proceed to download integration and LLM steps.
