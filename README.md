# tldr-tube 🎬

Save time taking notes on YouTube and Bilibili videos with AI-powered, timestamp-anchored summaries.

---

## Features

✅ **YouTube & Bilibili Summarization**
- Paste a YouTube or Bilibili URL → Get instant TL;DR + segmented summaries
- Each summary segment has clickable timestamps to jump back to the source
- Automatically caches processed videos (never reprocess the same video)

✅ **Smart Transcript Handling**
- Prefers manual captions over auto-generated
- Falls back to mlx-whisper (Apple Silicon optimized) when no captions exist
- Restores punctuation in auto-generated transcripts using LLM

✅ **Context-Aware Summarization**
- Single-pass processing: LLM sees the entire video at once
- Maintains semantic coherence across segments
- Auto-detects video type (tutorial / podcast / lecture / other)
- Bilingual output (English + 中文) for every summary

✅ **Collections**
- Group related videos (e.g., a course with multiple lectures)
- Process batches of videos in order
- View collection summaries

✅ **Search & Ask AI**
- Keyword search across all summaries, titles, and descriptions
- Ask questions about your video library using RAG

✅ **Export**
- Download summaries as Markdown (English or Chinese)
- Perfect for Notion, Obsidian, or any note-taking app

---

## Tech Stack

- **Python 3.11+**
- **Streamlit** - Web UI
- **youtube-transcript-api** - Fetch YouTube captions
- **mlx-whisper** - Apple Silicon-optimized speech-to-text
- **yt-dlp** - Video metadata, audio download, and Bilibili subtitles
- **Multiple LLM providers** - Claude, Gemini, OpenAI, DeepSeek, Qwen
- **SQLAlchemy + SQLite** - Database (Postgres-ready)

---

## Installation

### Prerequisites

- **macOS with Apple Silicon** (M1/M2/M3) - required for mlx-whisper
- **Conda** (Miniconda or Anaconda) - [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html) or via Homebrew: `brew install --cask miniconda`
- **At least one LLM API key** (see [Environment Variables](#environment-variables) below)

### Setup

```bash
# Clone the repository
git clone https://github.com/itstilldepends/tldr-tube.git
cd tldr-tube

# Copy environment variables template and fill in your API key(s)
cp .env.example .env
# Edit .env — add at least one LLM API key (APP_PASSWORD is optional)

# Run the app
./run.sh
```

`run.sh` handles everything automatically: creates the conda environment, installs dependencies, and starts the app. The database tables are created on first run.

**Next time:**
```bash
./run.sh
```

The app opens at `http://localhost:8501`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in at least one LLM API key:

```bash
# LLM API Keys — add at least one

DEEPSEEK_API_KEY=sk-...        # Cheapest: ~$0.003/video
GOOGLE_API_KEY=AIza...         # Gemini: ~$0.005/video
OPENAI_API_KEY=sk-proj-...     # GPT-4o-mini: ~$0.01/video
DASHSCOPE_API_KEY=sk-...       # Qwen (best for Chinese content)
ANTHROPIC_API_KEY=sk-ant-...   # Claude: ~$0.10/video

# Optional: password-protect the app
# If unset, the app is accessible without a password
# APP_PASSWORD=your_secure_password

# Optional: database URL (defaults to SQLite)
# DATABASE_URL=sqlite:///data/tldr_tube.db
```

---

## Usage

### Process a Video

1. Click **➕ New Video** in the sidebar
2. Paste a YouTube or Bilibili URL
3. Click **Process Video**
4. Wait ~1-2 minutes while the pipeline runs
5. View the bilingual TL;DR and time-stamped segments
   - Click any `[MM:SS]` timestamp to jump to that moment in the video

### Collections

1. Click **📚 New Collection** in the sidebar
2. Give the collection a title (e.g., "MIT 6.006 Lectures")
3. Paste multiple URLs (one per line)
4. Click **Process All** — videos are processed sequentially with progress updates

### Search

Go to **📜 History** and use the **🔍 Search** box to find videos by title, summary content, description, or tags. Works in English and Chinese.

### Ask AI

Go to **🤖 Ask AI** to ask questions about your video library. Optionally narrow the scope to specific videos or collections.

### Export

After viewing a processed video, find the **💾 Export Summary** section and download as Markdown (English or Chinese).

---

## How It Works

```
YouTube / Bilibili URL
  ↓
Detect platform → Extract video ID → Check database cache
  ↓
Fetch metadata (title, duration, channel, thumbnail) via yt-dlp
  ↓
Try platform captions (YouTube API / Bilibili via yt-dlp)
  ├─ Success → Use transcript (restore punctuation if auto-generated)
  └─ Fail    → Download audio → mlx-whisper transcription
  ↓
Send full transcript to LLM
  ↓
LLM returns: {video_type, tldr (EN+ZH), segments (EN+ZH)}
  ↓
Save to database → Display results
```

**Why not chunk the transcript?** tldr-tube processes the entire transcript in one pass, preserving context so the LLM can reference earlier concepts and maintain narrative flow. Claude's 200K token context window handles even 3-hour videos (~30K tokens) with ease.

---

## Project Structure

```
tldr-tube/
├── app.py                  # Streamlit web UI
├── run.sh                  # Startup script (setup + launch)
├── db/
│   ├── models.py           # SQLAlchemy models (Collection, Video, Segment)
│   ├── session.py          # Database engine & session
│   └── operations.py       # Collection CRUD operations
├── pipeline/
│   ├── processor.py        # Main pipeline orchestrator
│   ├── transcript.py       # YouTube & Bilibili transcript fetching
│   ├── whisper.py          # mlx-whisper transcription
│   ├── summarize.py        # LLM summarization
│   ├── prompts.py          # All LLM prompts
│   ├── metadata.py         # yt-dlp metadata & audio download
│   ├── utils.py            # URL parsing, timestamp formatting
│   ├── export.py           # Markdown export
│   ├── search.py           # Keyword search
│   ├── rag.py              # Ask AI (retrieval-augmented generation)
│   ├── embeddings.py       # Semantic search embeddings (BGE-M3)
│   ├── llm_client.py       # Unified LLM client (multi-provider)
│   └── config.py           # Provider configuration
├── data/                   # SQLite database (gitignored)
├── requirements.txt
├── .env.example
├── CLAUDE.md               # Development guide
└── README.md               # This file
```

---

## Cost Estimates

Approximate cost per 1-hour video:

| Provider | Model | Cost/video |
|----------|-------|------------|
| DeepSeek | deepseek-chat | ~$0.003 |
| Gemini | 2.0 Flash | ~$0.005 |
| OpenAI | GPT-4o-mini | ~$0.01 |
| Qwen | qwen-plus | ~$0.05 |
| Claude | Sonnet | ~$0.10 |

---

## Roadmap

### Done
- [x] YouTube & Bilibili video summarization
- [x] Bilingual output (EN + ZH)
- [x] Collections (batch processing)
- [x] Export summaries to Markdown
- [x] Keyword search
- [x] Ask AI (RAG over your video library)
- [x] Multi-LLM provider support

### Planned
- [ ] Local file upload (MP4/MOV)
- [ ] Edit summaries manually
- [ ] Semantic search (for libraries > 50 videos)
- [ ] Cross-platform Whisper (Intel Mac / Linux)
- [ ] PDF export

---

## Troubleshooting

### `mlx-whisper` installation fails
**Cause**: Not on Apple Silicon or incompatible Python version
**Solution**: Ensure macOS with M1/M2/M3, Python 3.11+. Try `pip install --upgrade mlx-whisper`

### No captions found
**Expected**: Falls back to Whisper automatically. Some videos have download restrictions — yt-dlp will fail for these.

### Database locked
**Cause**: Concurrent writes (rare in Streamlit single-user mode)
**Solution**: Already using WAL mode in `db/session.py`

### LLM API error
Check that your API key is correctly set in `.env` and that you have sufficient credits.

---

## Contributing

Contributions welcome! Read `CLAUDE.md` for development guidelines before submitting PRs.

---

## License

MIT License

---

## Acknowledgments

- Powered by [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (Apple MLX)
- Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)
