# tldr-tube 🎬

Save time taking notes on YouTube videos with AI-powered, timestamp-anchored summaries.

---

## Features

✅ **YouTube Video Summarization**
- Paste a YouTube URL → Get instant TL;DR + segmented summaries
- Each summary segment has clickable timestamps to jump back to the source
- Automatically caches processed videos (never reprocess the same video)

✅ **Smart Transcript Handling**
- Prefers manual captions over auto-generated
- Falls back to mlx-whisper (Apple Silicon optimized) when no captions exist
- Restores punctuation in auto-generated transcripts using Claude

✅ **Context-Aware Summarization**
- Single-pass processing: Claude sees the entire video at once
- Maintains semantic coherence across segments
- Auto-detects video type (tutorial / podcast / lecture / other)

✅ **Collections** (Future)
- Group related videos (e.g., a course with multiple lectures)
- Process batches of videos in order
- View collection summaries

✅ **Local & S3 Support** (Future)
- Upload local video files (MP4, MOV, etc.)
- Process videos from S3 URLs

---

## Tech Stack

- **Python 3.11+**
- **Streamlit** - Web UI
- **youtube-transcript-api** - Fetch YouTube captions
- **mlx-whisper** - Apple Silicon-optimized speech-to-text
- **Anthropic Claude API** - Summarization
- **yt-dlp** - Video metadata & audio download
- **SQLAlchemy + SQLite** - Database (Postgres-ready)

---

## Installation

### Prerequisites

- **macOS with Apple Silicon** (M1/M2/M3) - required for mlx-whisper
- **Conda** (Miniconda or Anaconda) - [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html) or via Homebrew: `brew install --cask miniconda`
- **Anthropic API key** - [Get one here](https://console.anthropic.com/)

### Setup

```bash
# Navigate to project directory
cd tldr-tube

# Create conda environment with Python 3.11
conda create -n tldr-tube python=3.11 -y

# Activate environment
conda activate tldr-tube

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY and APP_PASSWORD

# Initialize database
python -m db.session

# Run the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

**Next time you use the app:**
```bash
conda activate tldr-tube
streamlit run app.py
```

---

## Usage

### Process a Single Video

1. Click **➕ New Video** in the sidebar
2. Paste a YouTube URL
3. Click **Process Video**
4. Wait ~1-2 minutes while the pipeline runs:
   - Fetches transcript (YouTube API or Whisper fallback)
   - Generates summary with Claude
   - Saves to local database
5. View results:
   - Overall TL;DR at the top
   - Time-stamped segments below
   - Click any `[MM:SS]` timestamp to jump to that moment in the video

### View History

Click **📜 History** to see all processed videos. Click any video to view its full summary.

### Delete Videos

In the History view, click 🗑️ Delete next to any video. You'll be asked to confirm before deletion.

---

## How It Works

### Pipeline Flow

```
YouTube URL
  ↓
Extract video_id → Check database cache
  ↓
Fetch metadata (title, duration, channel, thumbnail) via yt-dlp
  ↓
Try YouTube transcript API
  ├─ Success → Use transcript (with punctuation restoration if auto-generated)
  └─ Fail → Download audio → mlx-whisper transcription
  ↓
Send full transcript to Claude API
  ↓
Claude returns: {video_type, tldr, segments}
  ↓
Save to database (Video + Segments)
  ↓
Display results in UI
```

### Why Not Chunk the Transcript?

Unlike some summarization tools that split long videos into chunks, tldr-tube processes the **entire transcript in one pass**. This preserves context and allows Claude to:
- Reference concepts introduced earlier
- Maintain narrative flow across segments
- Generate more coherent summaries

Claude Sonnet 4.5's 200K token context window easily handles even 3-hour videos (~10K-30K tokens).

---

## Environment Variables

Create a `.env` file with:

```bash
# Required: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional: Password protect the app
APP_PASSWORD=your_secure_password

# Optional: Database URL (defaults to SQLite)
DATABASE_URL=sqlite:///data/tldr_tube.db
```

---

## Project Structure

```
tldr-tube/
├── app.py                  # Streamlit web UI
├── db/
│   ├── models.py           # SQLAlchemy models (Collection, Video, Segment)
│   └── session.py          # Database engine & session
├── pipeline/
│   ├── processor.py        # Main pipeline orchestrator
│   ├── transcript.py       # YouTube transcript fetching
│   ├── whisper.py          # mlx-whisper transcription
│   ├── summarize.py        # Claude API integration
│   ├── prompts.py          # All Claude prompts
│   ├── metadata.py         # yt-dlp metadata fetching
│   └── utils.py            # Helper functions
├── data/                   # SQLite database (gitignored)
├── requirements.txt
├── .env.example
├── CLAUDE.md              # Development guide
└── README.md              # This file
```

---

## Cost Estimates

### Claude API (Sonnet 4.5)

- **1-hour video**: ~$0.03-0.05 per video
- **20-video course**: ~$0.60-1.00

Input pricing: ~$0.003 per 1K tokens
Output pricing: ~$0.015 per 1K tokens

---

## Roadmap

### High Priority

- [ ] **Collection support**: Batch process multiple videos
- [ ] **Export summaries**: Download as Markdown or PDF
- [ ] **Local file upload**: Process MP4/MOV files
- [ ] **S3 support**: Process videos from S3 URLs

### Medium Priority

- [ ] **Search**: Full-text search across summaries
- [ ] **Edit summaries**: Manual editing of TL;DR/segments
- [ ] **Reprocess videos**: Re-summarize with different prompts

### Low Priority

- [ ] **Cross-platform Whisper**: Support Intel Macs and Linux
- [ ] **Keyframe extraction**: Screenshots for tutorial videos
- [ ] **PostgreSQL migration guide**: Production deployment
- [ ] **Share links**: Generate public links for summaries

---

## Troubleshooting

### `mlx-whisper` installation fails

**Cause**: Not on Apple Silicon or incompatible Python version
**Solution**:
- Ensure macOS with M1/M2/M3 chip
- Verify conda environment: `conda activate tldr-tube && python --version` (should be 3.11+)
- Try reinstalling: `pip install --upgrade mlx-whisper`

### YouTube transcript not found

**Expected**: Falls back to Whisper automatically
**Check**: Some videos have download restrictions - yt-dlp will fail for these

### Database locked

**Cause**: Concurrent writes (rare in Streamlit)
**Solution**: Already using WAL mode in `db/session.py`

### Claude API rate limit

**For MVP**: App will fail with clear error message
**Future**: Implement exponential backoff retry

---

## Contributing

This is an early-stage project. Contributions welcome!

**Before submitting PRs**:
1. Read `CLAUDE.md` for development guidelines
2. Keep functions small and well-documented
3. Follow existing code style
4. Test incrementally

---

## License

MIT License - see LICENSE file for details

---

## Acknowledgments

- Built with [Claude](https://claude.ai) (Anthropic)
- Powered by [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (Apple MLX)
- Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)

---

**Made with ❤️ for efficient learning**
