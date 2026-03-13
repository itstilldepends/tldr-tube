# CLAUDE.md - tldr-tube Development Guide

## Project Overview

**tldr-tube** is a Python Streamlit app that generates timestamp-anchored summaries for YouTube videos (with future support for local/S3 files). The goal is to save time taking notes by providing:
- A concise TL;DR of the entire video
- Segmented summaries with clickable timestamps to jump back to the source
- Caching to avoid reprocessing the same video
- Collections to group related videos (e.g., course lectures)

---

## Core Architecture Decisions

### 1. Single-Pass Summarization (Not Chunked Processing)

**Decision**: Send the entire transcript to Claude in one API call, generate both TL;DR and segmented summaries together.

**Rationale**:
- Claude Sonnet 4.5 has 200K token context window
- A 1-hour video transcript ≈ 3K-10K tokens (trivial for Claude)
- Processing segments separately would **lose context** (e.g., concepts introduced early, referenced later)
- Single-pass allows Claude to maintain semantic coherence across segments

**Implementation**:
- Pipeline sends full transcript (with timestamps) to Claude
- Prompt asks for: `{video_type, tldr, segments: [{start, end, summary}]}`
- Claude sees entire video context when writing each segment summary

### 2. Store Raw Transcripts in Database

**Decision**: Save raw transcript as JSON text field in `Video` table.

**Rationale**:
- Transcripts are small (10-100KB) - no storage concern for SQLite/Postgres
- Enables re-summarization with different prompts without re-fetching
- Essential for Whisper transcripts (can't re-fetch from YouTube API)
- Useful for debugging and future features (search, export)

### 3. Video Metadata Storage

**Decision**: Fetch and store `duration`, `channel_name`, `thumbnail_url` using yt-dlp.

**Rationale**:
- Improves UX in history/collection views
- Minimal additional API call (yt-dlp metadata extraction is fast)
- Thumbnail URLs are stored as strings (not downloaded)

### 4. Sequential Collection Processing

**Decision**: Process videos in a collection one-by-one, not in parallel.

**Rationale**:
- Simpler implementation and UI (clear progress indicator)
- Avoids rate limit complications with Claude API
- Typical collections (5-20 videos) are manageable sequentially

### 5. Apple Silicon Only (For Now)

**Decision**: Use `mlx-whisper` for ASR fallback, targeting macOS Apple Silicon only.

**Rationale**:
- Developer's local environment is Apple Silicon
- `mlx-whisper` is highly optimized for M1/M2/M3 chips
- Cross-platform support (openai-whisper) is a future TODO

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Framework** | Streamlit | Rapid UI prototyping, built-in components |
| **Transcript Fetching** | youtube-transcript-api | Fetch YouTube captions (manual/auto) |
| **ASR Fallback** | mlx-whisper | Transcribe audio when no captions exist |
| **Audio Download** | yt-dlp | Download audio for Whisper, fetch metadata |
| **Summarization** | Anthropic Claude API | Generate TL;DR + segmented summaries |
| **Database** | SQLAlchemy + SQLite | ORM for portability (Postgres-ready) |
| **Environment** | python-dotenv | Manage secrets |

**Python Version**: 3.11+

---

## Database Schema

```python
class Collection(Base):
    __tablename__ = "collections"

    id: int                      # PK
    title: str                   # e.g., "MIT 6.006 Algorithms"
    description: str             # Optional, nullable
    created_at: datetime

class Video(Base):
    __tablename__ = "videos"

    id: int                      # PK
    source_type: str             # "youtube" | "local" | "s3"
    source_url: str              # Full URL or path
    video_id: str                # Unique: YouTube ID or MD5(source_url)

    # Metadata
    title: str
    duration_seconds: int
    channel_name: str
    thumbnail_url: str

    # Content
    raw_transcript: str          # JSON: [{"start": 0.5, "duration": 2.3, "text": "..."}]
    video_type: str              # "tutorial" | "podcast" | "lecture" | "other"
    tldr: str                    # Overall summary (5-7 sentences)
    transcript_source: str       # "youtube_api" | "whisper"

    # Relationships
    collection_id: int           # Nullable FK → Collection.id
    order_index: int             # Nullable, order within collection

    processed_at: datetime

class Segment(Base):
    __tablename__ = "segments"

    id: int                      # PK
    video_id: int                # FK → Video.id
    start_seconds: float
    end_seconds: float
    timestamp: str               # "MM:SS" format for display
    summary: str                 # 3-5 sentence summary of this segment
```

**Key Indexes**:
- `Video.video_id` (unique) - fast cache lookup
- `Video.collection_id` - collection queries
- `Segment.video_id` - fetch segments for a video

---

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Input: YouTube URL                                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ Extract video_id from URL                                   │
│ Check DB: SELECT * FROM videos WHERE video_id = ?          │
└───────────────┬─────────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │ Found in cache? │
        └───────┬────────┘
                │
        ┌───────┴────────┐
        │ YES            │ NO
        │                │
        ▼                ▼
    Return          ┌────────────────────────────────┐
    cached          │ Fetch metadata with yt-dlp     │
    result          │ (title, duration, channel, etc)│
                    └────────────┬───────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────────────┐
                    │ Try youtube-transcript-api     │
                    │ Prefer: manual > auto-generated│
                    └────────────┬───────────────────┘
                                 │
                         ┌───────┴────────┐
                         │ Success?       │
                         └───────┬────────┘
                                 │
                    ┌────────────┴─────────────┐
                    │ YES                      │ NO
                    │                          │
                    ▼                          ▼
        ┌───────────────────────┐  ┌──────────────────────────┐
        │ Got transcript        │  │ Download audio (yt-dlp)  │
        │ with timestamps       │  │ → mlx-whisper transcribe │
        └───────────┬───────────┘  └──────────┬───────────────┘
                    │                         │
                    └─────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────┐
                │ Check if auto-generated (no punct)  │
                │ If yes: Claude punctuation restore  │
                └─────────────┬───────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────┐
                │ Claude Summarization (single call)  │
                │ Input: full transcript + timestamps │
                │ Output: {video_type, tldr, segments}│
                └─────────────┬───────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────┐
                │ Persist to Database:                │
                │ - Insert Video (with raw_transcript)│
                │ - Insert Segments (batch)           │
                └─────────────┬───────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────┐
                │ Return result to UI                 │
                └─────────────────────────────────────┘
```

---

## Prompts (pipeline/prompts.py)

All Claude prompts are stored as named constants in `pipeline/prompts.py`. **Never inline prompts elsewhere.**

### Example Prompts

```python
PUNCTUATION_RESTORE_PROMPT = """
The following is a YouTube auto-generated transcript without punctuation.
Please restore punctuation and paragraphing while keeping the original text unchanged.

Transcript:
{transcript}
"""

SUMMARIZATION_PROMPT = """
You are given a complete video transcript with timestamps.

Analyze the content and return a JSON response with this structure:
{{
  "video_type": "tutorial" | "podcast" | "lecture" | "other",
  "tldr": "5-7 sentence overall summary of the entire video",
  "segments": [
    {{
      "start_seconds": 0.0,
      "end_seconds": 285.5,
      "summary": "3-5 sentence summary of this segment (maintain coherence with previous segments)"
    }},
    ...
  ]
}}

Requirements:
1. Segments should be naturally divided by topic/content, typically 3-5 minutes each
2. Each segment summary should be concise (3-5 sentences) but coherent with the full context
3. Since you can see the entire transcript, maintain references and continuity
4. Detect video_type based on content style and structure
5. Return valid JSON only, no markdown code blocks

Transcript:
{transcript}
"""
```

**Key Principle**: Claude sees the **entire transcript** when generating segments, so summaries can reference earlier content naturally.

---

## Code Conventions

### General
- **Python 3.11+** syntax (use type hints everywhere)
- **Docstrings**: All functions must have clear docstrings (Google style)
- **Keep functions small**: Single responsibility, max ~50 lines
- **Avoid over-engineering**: Optimize for readability, not cleverness

### Database
- **Always use SQLAlchemy**, never raw `sqlite3` module
- Connection string from `DATABASE_URL` env var (default: `sqlite:///data/tldr_tube.db`)
- Use context managers for sessions:
  ```python
  with Session() as session:
      # query here
      session.commit()
  ```

### Error Handling
- **Fail fast**: If Claude API fails, raise exception immediately (no retries for MVP)
- Use descriptive error messages for user-facing errors
- Log errors with context (video URL, step that failed)

### Prompts
- **All prompts in `pipeline/prompts.py`** as module-level constants
- Use f-strings for variable substitution
- Never inline prompts in business logic

### File Organization
- **Pipeline logic**: Pure functions, no Streamlit code
- **Streamlit UI**: Only in `app.py`, no business logic
- **Models**: Only SQLAlchemy models in `db/models.py`

---

## Project Structure

```
tldr-tube/
├── app.py                      # Streamlit UI (sidebar, views, rendering)
│
├── pipeline/
│   ├── transcript.py           # fetch_youtube_transcript(video_id)
│   ├── whisper.py              # transcribe_audio(audio_path) using mlx-whisper
│   ├── summarize.py            # summarize_transcript(transcript, video_id)
│   ├── prompts.py              # PUNCTUATION_RESTORE_PROMPT, SUMMARIZATION_PROMPT, NOTE_GENERATION_PROMPT
│   ├── metadata.py             # fetch_video_metadata(url) using yt-dlp
│   ├── keyframes.py            # Keyframe extraction pipeline (CV: pHash, SSIM, blur replacement)
│   ├── keyframe_notes.py       # Concept-based note generation (multimodal LLM)
│   ├── worker.py               # Background queue worker (video processing + note generation)
│   └── utils.py                # format_timestamp(seconds), hash_video_id(url)
│
├── db/
│   ├── models.py               # Collection, Video, Segment, Keyframe, Note, ProcessingJob (SQLAlchemy)
│   ├── session.py              # engine, Session setup, init_db()
│   └── operations.py           # Collection/Job CRUD operations
│
├── scripts/
│   ├── test_keyframes.py       # Keyframe extraction test → HTML report
│   └── test_notes.py           # Note generation test → HTML report
│
├── data/                       # .gitignored
│   ├── tldr_tube.db            # SQLite database
│   └── keyframes/              # Extracted keyframe images
│       └── {video_id}/
│
├── pyproject.toml              # Dependencies & project config
├── .env.example
├── .gitignore
├── CLAUDE.md                   # This file
└── README.md                   # User-facing documentation
```

---

## Streamlit UI Structure

### Layout
- **Sidebar**: Navigation menu
  - "➕ New Video" - single URL input
  - "📚 New Collection" - batch URL input
  - "📜 History" - clickable list of videos/collections
- **Main area**: Dynamic content based on sidebar selection

### Views

#### 1. New Video View
```
┌─────────────────────────────────────┐
│ Enter YouTube URL:                  │
│ [________________________]  [Submit]│
└─────────────────────────────────────┘

After submit:
┌─────────────────────────────────────┐
│ 🎬 Video Title                      │
│ 📺 Channel Name | ⏱️ 1:23:45        │
│ 📝 Transcript source: YouTube API   │
│                                     │
│ ━━━ TL;DR ━━━                       │
│ This video covers...                │
│                                     │
│ ━━━ Timeline ━━━                    │
│ [00:00] Introduction to the topic...│
│ [05:23] First main concept...       │
│ [10:45] Code demonstration...       │
└─────────────────────────────────────┘
```

Timestamps are clickable links: `https://youtu.be/{video_id}?t={start_seconds}`

#### 2. New Collection View
```
┌─────────────────────────────────────┐
│ Collection Title:                   │
│ [_________________________________] │
│                                     │
│ Description (optional):             │
│ [_________________________________] │
│                                     │
│ Paste YouTube URLs (one per line):  │
│ ┌─────────────────────────────────┐ │
│ │ https://youtu.be/abc123         │ │
│ │ https://youtu.be/def456         │ │
│ │ https://youtu.be/ghi789         │ │
│ └─────────────────────────────────┘ │
│                        [Process All]│
└─────────────────────────────────────┘

After submit: show progress for each video, then collection summary view
```

#### 3. Collection View (from history)
```
┌─────────────────────────────────────┐
│ 📚 MIT 6.006 Algorithms             │
│ 12 videos                           │
│                                     │
│ ▼ Lecture 1: Introduction           │
│   TL;DR: This lecture introduces... │
│   [Show full summary] [🗑️ Delete]   │
│                                     │
│ ▼ Lecture 2: Binary Search          │
│   TL;DR: Covers binary search...    │
│   [Show full summary] [🗑️ Delete]   │
│                                     │
│ [🗑️ Delete Collection]              │
└─────────────────────────────────────┘
```

#### 4. Password Gate
On app load:
```
┌─────────────────────────────────────┐
│         🔒 tldr-tube                │
│                                     │
│ Password: [_______________] [Enter] │
│                                     │
│ (Set APP_PASSWORD in .env)         │
└─────────────────────────────────────┘
```

### Delete Confirmation
Before deleting video or collection:
```python
st.warning("⚠️ Delete this video? This cannot be undone.")
col1, col2 = st.columns(2)
with col1:
    if st.button("Cancel"):
        st.rerun()
with col2:
    if st.button("Delete", type="primary"):
        # perform deletion
```

---

## Environment Variables

`.env.example`:
```bash
# Anthropic API key for Claude
ANTHROPIC_API_KEY=sk-ant-...

# Password to access the app
APP_PASSWORD=your_secure_password

# Database connection string (SQLite default, Postgres-ready)
DATABASE_URL=sqlite:///data/tldr_tube.db
```

Load with:
```python
from dotenv import load_dotenv
load_dotenv()
```

Add `.env` to `.gitignore`.

---

## Dependencies (pyproject.toml)

All dependencies are declared in `pyproject.toml`. `mlx-whisper` (Apple Silicon only) is an optional dependency under `[project.optional-dependencies] asr`.

---

## Development Workflow

### Initial Setup
```bash
# Clone/create project
cd tldr-tube

# Create conda environment
conda create -n tldr-tube python=3.11 -y
conda activate tldr-tube

# Install dependencies (editable mode + ASR support)
pip install -e ".[asr]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python -c "from db.session import init_db; init_db()"

# Run app
streamlit run app.py
```

### Database Migrations
For schema changes:
1. Update `db/models.py`
2. For SQLite (dev): delete `data/tldr_tube.db` and recreate (acceptable for MVP)
3. For production (Postgres): use Alembic (future TODO)

### Testing
Manual testing for MVP:
1. Test YouTube URL processing
2. Test collection creation
3. Test cache retrieval (same URL twice)
4. Test deletion with confirmation
5. Test password gate

Future: Add `pytest` suite.

---

## Future Features (TODOs)

### High Priority
- [ ] **Local file upload**: Upload MP4/MOV, extract audio → Whisper
- [ ] **S3 support**: Process videos from S3 URLs
- [ ] **Export summaries**: Download as Markdown or PDF
- [x] **Keyframe note generation**: Extract keyframes + generate bilingual concept-based study notes
  - Design doc: `NOTE_GENERATION.md`
- [ ] **Cross-platform Whisper**: Fallback to `openai-whisper` on non-Apple Silicon

### Medium Priority
- [ ] **Search**: Full-text search across summaries
- [ ] **Edit summaries**: Allow manual editing of TL;DR/segments
- [ ] **Reprocess video**: Re-summarize with different prompt
- [ ] **Collection reordering**: Drag-and-drop videos within collection
- [ ] **Batch export**: Export entire collection as single document

### Low Priority
- [ ] **Postgres migration guide**: Document switching from SQLite
- [ ] **Rate limiting**: Handle Claude API rate limits gracefully
- [ ] **User accounts**: Multi-user support (requires auth system)
- [ ] **Share links**: Generate shareable links for summaries

---

## Cost Estimates

### Claude API (Sonnet 4.5)
- Input: ~$0.003 per 1K tokens
- Output: ~$0.015 per 1K tokens

**Per video (1 hour)**:
- Input: ~8K tokens (transcript) = $0.024
- Output: ~500 tokens (TL;DR + segments) = $0.0075
- **Total**: ~$0.03-0.05 per video

**For a 20-video course**: ~$0.60-1.00

---

## Common Issues & Solutions

### Issue: `mlx-whisper` installation fails
- **Cause**: Not on Apple Silicon or incompatible Python version
- **Solution**: Ensure macOS with M1/M2/M3 chip, Python 3.11+

### Issue: YouTube transcript not found
- **Expected**: Falls back to Whisper automatically
- **Check**: Ensure `yt-dlp` can download audio (some videos are restricted)

### Issue: Database locked (SQLite)
- **Cause**: Concurrent writes (rare in Streamlit single-user)
- **Solution**: Use WAL mode: `PRAGMA journal_mode=WAL;` in session.py

### Issue: Claude API rate limit
- **For MVP**: Fail with clear error message
- **Future**: Implement exponential backoff retry

---

## Git Ignore

`.gitignore`:
```
# Environment
.env
venv/
__pycache__/

# Data
data/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
```

---

## Notes for Claude Code (AI Assistant)

When implementing this project:
1. **Write clean, documented code** - this will be actively iterated
2. **Keep functions small** - single responsibility principle
3. **No over-engineering** - clarity > cleverness
4. **Test incrementally** - build pipeline step-by-step, test each component
5. **Preserve timestamps** - they're critical for the core feature
6. **Follow the structure** - don't create unnecessary files/abstractions
7. **Ask before major changes** - if requirements seem unclear, clarify first

**Key files to implement first**:
1. `db/models.py` + `db/session.py` - database foundation
2. `pipeline/transcript.py` - YouTube transcript fetching
3. `pipeline/prompts.py` + `pipeline/summarize.py` - Claude integration
4. `app.py` - basic Streamlit UI
5. Iterate from there

Good luck! 🚀
