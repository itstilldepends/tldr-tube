# TODO List - tldr-tube

Last updated: 2026-02-19

---

## ✅ 已完成 (Completed)

### Core Infrastructure
- [x] Database models (SQLAlchemy) - Collection, Video, Segment
- [x] Database session management with SQLite (WAL mode enabled)
- [x] Git repository initialized and pushed to GitHub (private)
- [x] Complete documentation (README.md, CLAUDE.md)
- [x] Environment setup (conda, requirements.txt)

### Pipeline Implementation
- [x] YouTube transcript fetching (youtube-transcript-api)
  - Prefers manual captions over auto-generated
  - Multi-language support (en, zh-CN, zh-TW)
- [x] mlx-whisper integration (Apple Silicon optimized)
  - Using **medium** model (769MB) for better accuracy
  - Auto-downloads model on first use
- [x] Video metadata fetching (yt-dlp)
  - Title, duration, channel name, thumbnail URL
- [x] Punctuation restoration for auto-generated transcripts
- [x] Claude API integration for summarization
  - Single-pass processing (maintains context)
  - Auto-detects video type (tutorial/podcast/lecture/other)
  - Generates TL;DR + segmented summaries

### Web UI (Streamlit)
- [x] Password gate (APP_PASSWORD in .env)
- [x] New Video view - process single YouTube URL
- [x] History view - list all processed videos
- [x] Video result display with clickable timestamps
- [x] Delete confirmation dialogs
- [x] Cache checking (avoid reprocessing)
- [x] Bilingual support (English + Chinese) in one API call
- [x] Rich metadata display (description, upload_date, tags)
- [x] Full transcript viewer with download button
- [x] Collapsible sections for description and transcript

### Configuration & Model Selection
- [x] User-configurable transcript source (Auto vs Force ASR)
- [x] Whisper model selection (tiny/base/small/medium/large)
- [x] Claude model selection (Haiku 4.5, Sonnet 4.5, Opus 4.6)
- [x] Model details display (speed, accuracy, cost estimates)
- [x] Dynamic progress messages showing selected models

---

## 🚧 To Do

### High Priority

#### 1. Background Task Queue
**Status**: Not started (user requested to postpone)
**Goal**: Allow tasks to run in background, enabling users to close the browser

**Current Limitation**:
- Users must keep browser tab open during processing (1-15 minutes)
- Closing tab/refreshing page/network disconnect → task is interrupted
- Tasks run in parallel without concurrency control

**Proposed Solution**:
- Implement lightweight task queue using Python `threading` + `queue`
- Tasks continue running even if browser is closed
- Show task status in History view: ⏳ Processing / ✅ Completed / ❌ Failed
- Allow submitting multiple videos that process sequentially
- Persist task state in SQLite database

**Implementation Approach**:
1. Create `pipeline/task_queue.py` with ThreadPoolExecutor
2. Add task status to database (new table or column)
3. Modify `process_youtube_video()` to run async
4. Add task list view in History page
5. Add polling/websocket for live status updates

**Alternatives Considered**:
- Celery + Redis (too complex for single-user local deployment)
- Current sync model (acceptable for now, but risky)

**Estimate**: ~3-4 hours
**Priority**: Medium (user can accept current limitation for now)

---

#### 2. Collection Support
**Status**: UI framework exists, backend not implemented
**Files to modify**:
- `app.py` - `view_new_collection()` function (currently shows "🚧 Coming soon")
- `pipeline/processor.py` - Add `process_collection(urls, title, description)` function
- `db/models.py` - Collection model exists, needs CRUD operations

**Implementation steps**:
1. Add collection creation form in `view_new_collection()`
2. Parse multiple URLs (one per line)
3. Process videos sequentially with progress bar
4. Save to Collection with `order_index`
5. Display collection summary view

**Estimate**: ~2-3 hours

---

#### 3. Export Summaries
**Status**: Not started
**Goal**: Export video summaries as Markdown or PDF

**Files to create**:
- `pipeline/export.py` - Export logic
- Add export button in video result view

**Features**:
- Markdown format:
  - Title, metadata
  - TL;DR
  - Segmented summaries with timestamps
- PDF format (optional, using `reportlab` or `weasyprint`)
- Export single video or entire collection

**Estimate**: ~3-4 hours

---

#### 4. Keyframe Extraction
**Status**: Not started (user requested to postpone)
**Goal**: Extract key screenshots for tutorial videos

**When to implement**: User will request when needed

**Planned approach**:
- Only for `video_type == "tutorial"`
- Extract frames at segment boundaries
- Store in `data/keyframes/{video_id}/frame_{timestamp}.jpg`
- Add `Keyframe` model to database
- Display thumbnails in UI next to segment summaries

**Estimate**: ~5-6 hours

---

### Medium Priority

#### 5. Search Functionality
**Status**: Not started
**Goal**: Full-text search across all video summaries

**Implementation**:
- Add search bar in History view
- Search in: title, tldr, segment summaries
- Use SQLite FTS5 (Full-Text Search) or simple LIKE query
- Display results with highlights

**Estimate**: ~2-3 hours

---

#### 6. Edit Summaries
**Status**: Not started
**Goal**: Allow manual editing of TL;DR and segment summaries

**Features**:
- Edit button in video result view
- Text area for TL;DR
- Editable segment summaries
- Save changes to database

**Estimate**: ~2 hours

---

#### 7. Reprocess Video
**Status**: Not started
**Goal**: Re-summarize a video with different prompts

**Use case**: User wants to adjust summary style or detail level

**Implementation**:
- "Reprocess" button in video detail view
- Optional: Let user customize prompt
- Keep original transcript, only re-run Claude summarization
- Optionally save multiple versions

**Estimate**: ~2-3 hours

---

### Low Priority

#### 8. Local File Upload
**Status**: Stub exists in code comments
**Goal**: Upload MP4/MOV files and process them

**Implementation**:
- Streamlit file uploader
- Extract audio with ffmpeg
- Transcribe with mlx-whisper
- Generate unique `video_id` via MD5 hash
- Process same as YouTube videos

**Estimate**: ~4-5 hours

---

#### 9. S3 Video Support
**Status**: Not started
**Goal**: Process videos from S3 URLs

**Dependencies**: Needs `boto3` and AWS credentials

**Estimate**: ~3-4 hours

---

#### 10. Cross-Platform Whisper Support
**Status**: mlx-whisper only works on Apple Silicon
**Goal**: Fallback to `openai-whisper` for Intel Macs / Linux

**Implementation**:
- Detect platform in `pipeline/whisper.py`
- Use `mlx-whisper` if Apple Silicon
- Use `openai-whisper` otherwise
- Add to requirements.txt as optional dependency

**Estimate**: ~2 hours

---

#### 11. PostgreSQL Migration Guide
**Status**: Currently using SQLite
**Goal**: Document how to switch to Postgres for production

**What to document**:
- Install Postgres
- Update `DATABASE_URL` in `.env`
- Run migrations (or recreate tables)
- Performance comparison

**Estimate**: ~1 hour (documentation only)

---

## 🐛 Known Issues

None currently reported.

---

## 💡 Future Enhancements

### User Experience
- [ ] Progress indicator for long videos (show estimated time)
- [ ] Thumbnail preview in History view
- [ ] Dark mode support
- [ ] Keyboard shortcuts (e.g., Ctrl+K to search)
- [ ] Video player embed (play YouTube video inline with synced highlights)

### Performance
- [ ] Parallel processing for collections (currently sequential)
- [ ] Rate limiting / retry logic for Claude API
- [ ] Caching Claude responses (avoid re-summarizing if prompt unchanged)
- [ ] Background job queue (for long-running tasks)

### Sharing & Collaboration
- [ ] Share links (generate public URLs for summaries)
- [ ] User accounts / multi-user support
- [ ] Team collections (shared collections)
- [ ] Comments / annotations on segments

### Advanced Features
- [ ] Automatic tagging (generate tags based on content)
- [ ] Related videos (find similar processed videos)
- [ ] Learning path builder (chain videos into a curriculum)
- [ ] Quiz generation (Claude generates questions from video content)
- [ ] Notion/Obsidian integration (export to note-taking apps)

---

## 🔧 Technical Debt

### Concurrency Limitations
- No task queue: multiple users processing videos simultaneously may cause:
  - High memory usage (multiple Whisper models loaded)
  - API rate limits (multiple concurrent Claude API calls)
  - System instability
- **Mitigation**: Currently single-user deployment, acceptable risk
- **Resolution**: Implement Background Task Queue (see TODO #1) when needed

### Session Dependency
- Tasks must complete while browser tab is open
- Accidental tab closure or network issue loses progress
- **Mitigation**: User is aware and can keep tab open
- **Resolution**: Background Task Queue will eliminate this dependency

---

## 📝 Notes for Next Session

### Project Status
- **Environment**: Conda (`tldr-tube` environment)
- **Database**: SQLite at `data/tldr_tube.db`
- **Whisper Model**: medium (769MB, auto-downloads on first use)
- **Git**: Initialized, pushed to https://github.com/itstilldepends/tldr-tube (private)

### Quick Start Commands
```bash
cd /Users/nzt/code/tldr-tube
conda activate tldr-tube
streamlit run app.py
```

### What Works Right Now
1. ✅ Process YouTube videos (paste URL → get summary)
2. ✅ View history of processed videos
3. ✅ Delete videos with confirmation
4. ✅ Clickable timestamps to jump to YouTube moments
5. ✅ Auto-caching (same video won't be reprocessed)

### What Doesn't Work Yet
1. ❌ Collection creation (UI exists, backend not implemented)
2. ❌ Export summaries (not implemented)
3. ❌ Keyframe extraction (postponed per user request)
4. ❌ Search (not implemented)
5. ❌ Local file upload (not implemented)

### Next Steps (when user returns)
1. Read this TODO.md to understand project state
2. Ask user what feature they want to implement next
3. If user reports bugs, add to "Known Issues" section
4. Update this file after completing tasks

---

**End of TODO.md**
