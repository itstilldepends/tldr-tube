# Semantic Search Implementation Guide

**Last Updated**: 2026-02-23

**Status**: ✅ COMPLETED - Semantic search is now live!

---

## 🎉 Implementation Summary

### What Was Built

**Model**: BGE-M3 (BAAI/bge-m3)
- 768-dim embeddings (vs 384 planned in this doc)
- 8192 token limit (vs 512 in original plan)
- Hybrid retrieval support (dense + sparse + multi-vector)

**Features Implemented**:
1. ✅ Video-level embeddings (title + tldr + tldr_zh)
2. ✅ Automatic embedding generation for new videos
3. ✅ Hybrid search (keyword + semantic)
4. ✅ Database schema migration (zero data loss)
5. ✅ Backfill script for existing videos

**Files Created**:
- `pipeline/embeddings.py` - BGE-M3 model loading and embedding generation
- `pipeline/search.py` - Semantic, keyword, and hybrid search functions
- `scripts/migrate_add_embeddings.py` - Safe schema migration
- `scripts/backfill_embeddings.py` - Generate embeddings for existing videos

**Files Modified**:
- `db/models.py` - Added `embedding = Column(LargeBinary)` to Video model
- `pipeline/processor.py` - Integrated embedding generation into video processing
- `app.py` - Updated History view to use hybrid search
- `requirements.txt` - Added FlagEmbedding, transformers, scikit-learn

### Usage

**For Users**:
- Search in History view works automatically (hybrid: keyword + semantic)
- No configuration needed

**For Developers**:
- Run `python scripts/backfill_embeddings.py` to generate embeddings for existing videos
- New videos automatically get embeddings during processing

---

## Original Implementation Plan (For Reference)

**Note**: The plan below was written before implementation and uses a different model (MiniLM instead of BGE-M3). The actual implementation is documented above.

---

## 🎯 TL;DR

### Will I Lose Data?

**NO** ✅

- Only **ADD** new columns, never delete old data
- Existing videos remain untouched
- New videos automatically get embeddings
- Old videos can be batch-processed later
- Can revert by simply dropping the new column

### Implementation Time

**~10 hours total** for complete hybrid search (keyword + semantic)

---

## 📊 Database Schema Changes

### What Changes?

**Add 2 new columns** (both nullable):

```python
# Before (current)
class Video(Base):
    id = Column(Integer, primary_key=True)
    title = Column(String)
    tldr = Column(Text)
    tldr_zh = Column(Text)
    # ... other existing fields ...

class Segment(Base):
    id = Column(Integer, primary_key=True)
    summary = Column(Text)
    summary_zh = Column(Text)
    # ... other existing fields ...
```

```python
# After (with semantic search)
class Video(Base):
    id = Column(Integer, primary_key=True)
    title = Column(String)
    tldr = Column(Text)
    tldr_zh = Column(Text)
    # ... other existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # NEW! ✨

class Segment(Base):
    id = Column(Integer, primary_key=True)
    summary = Column(Text)
    summary_zh = Column(Text)
    # ... other existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # NEW! ✨
```

### What Happens to Existing Data?

**Nothing!** ✅

| Existing Field | Status | Value |
|---------------|--------|-------|
| `id`, `title`, `tldr`, etc. | ✅ Unchanged | Same as before |
| `embedding` (new) | ✅ Added | `NULL` for old videos |

**Old videos**:
- All fields remain the same
- New `embedding` field is `NULL`
- Still searchable with keyword search
- Can batch-generate embeddings later

**New videos**:
- All fields work as before
- `embedding` field automatically populated
- Searchable with both keyword and semantic search

---

## 🔧 Implementation Steps

### Step 0: Backup (Always!)

```bash
# Backup SQLite database
cp data/tldr_tube.db data/tldr_tube.db.backup_$(date +%Y%m%d)

# Verify backup
ls -lh data/*.backup*
```

**Restore if needed**:
```bash
cp data/tldr_tube.db.backup_20260223 data/tldr_tube.db
```

---

### Step 1: Modify Database Schema

**File**: `db/models.py`

```python
# Add this import at top
from sqlalchemy import Column, Integer, String, Text, LargeBinary

# Modify Video model
class Video(Base):
    __tablename__ = "videos"

    # ... existing fields (don't change!) ...

    # ADD THIS LINE ✨
    embedding = Column(LargeBinary, nullable=True)

# Modify Segment model
class Segment(Base):
    __tablename__ = "segments"

    # ... existing fields (don't change!) ...

    # ADD THIS LINE ✨
    embedding = Column(LargeBinary, nullable=True)
```

**Apply schema change**:

```python
# Create migration script: scripts/migrate_add_embeddings.py
from db.session import engine, init_db
from db.models import Base

def migrate():
    """Add embedding columns to existing database"""
    print("Adding embedding columns...")

    # SQLAlchemy will detect new columns and add them
    # Existing data is preserved!
    Base.metadata.create_all(engine)

    print("✅ Migration complete!")
    print("Existing data is safe, new columns added.")

if __name__ == "__main__":
    migrate()
```

Run migration:
```bash
python scripts/migrate_add_embeddings.py
```

**Verify**:
```bash
# Check database schema
sqlite3 data/tldr_tube.db ".schema videos" | grep embedding
# Should see: embedding BLOB

# Check existing data is intact
sqlite3 data/tldr_tube.db "SELECT COUNT(*), COUNT(embedding) FROM videos;"
# Should see: 50|0 (50 videos, 0 embeddings)
```

---

### Step 2: Install Dependencies

```bash
# Add to requirements.txt
echo "sentence-transformers>=2.2.0" >> requirements.txt
echo "scikit-learn>=1.3.0" >> requirements.txt

# Install
pip install -r requirements.txt

# First run will download model (~500MB)
# This happens automatically, takes ~2 minutes
```

---

### Step 3: Create Embedding Module

**File**: `pipeline/embeddings.py`

```python
"""
Embedding generation for semantic search.
Uses sentence-transformers with multilingual support.
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_model():
    """
    Load sentence-transformers model (cached, loaded once).

    Model: paraphrase-multilingual-MiniLM-L12-v2
    - Size: ~500MB
    - Languages: 50+ including English, Chinese
    - Embedding dimension: 384
    - Speed: ~100 texts/second on M1 Mac
    """
    logger.info("Loading sentence-transformers model (first time takes ~30s)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    logger.info("✅ Model loaded successfully")
    return model


def generate_video_embedding(video):
    """
    Generate embedding for a video.

    Combines: title + English TL;DR + Chinese TL;DR
    Returns: bytes (numpy array serialized)
    """
    model = load_model()

    # Combine multilingual content
    text = f"{video.title} {video.tldr} {video.tldr_zh}"

    # Generate embedding
    embedding = model.encode(text, convert_to_numpy=True)

    # Convert to bytes for database storage
    return embedding.tobytes()


def generate_segment_embedding(segment):
    """
    Generate embedding for a segment.

    Combines: English summary + Chinese summary
    Returns: bytes (numpy array serialized)
    """
    model = load_model()

    # Combine multilingual content
    text = f"{segment.summary} {segment.summary_zh}"

    # Generate embedding
    embedding = model.encode(text, convert_to_numpy=True)

    # Convert to bytes for database storage
    return embedding.tobytes()


def bytes_to_embedding(embedding_bytes):
    """
    Convert stored bytes back to numpy array.

    Args:
        embedding_bytes: bytes from database

    Returns:
        numpy array of shape (384,)
    """
    return np.frombuffer(embedding_bytes, dtype=np.float32)
```

**Test the module**:

```python
# scripts/test_embeddings.py
from pipeline.embeddings import load_model, generate_video_embedding
from db.models import Video

# Test model loading
model = load_model()
print(f"✅ Model loaded: {model}")

# Test embedding generation
class MockVideo:
    title = "Python Decorators Tutorial"
    tldr = "This video explains decorators"
    tldr_zh = "本视频讲解装饰器"

video = MockVideo()
embedding = generate_video_embedding(video)

print(f"✅ Embedding generated: {len(embedding)} bytes")
print(f"✅ Shape: 384 dimensions × 4 bytes = {384 * 4} bytes")
```

Run:
```bash
python scripts/test_embeddings.py
```

---

### Step 4: Integrate into Video Processing

**File**: `pipeline/processor.py`

```python
# Add import at top
from pipeline.embeddings import generate_video_embedding, generate_segment_embedding

def process_youtube_video(url, ...):
    """Process YouTube video (existing function)"""

    # ... existing code ...

    # After segments are created, before saving to database:

    try:
        # Generate video embedding
        video.embedding = generate_video_embedding(video)
        logger.info(f"✅ Generated video embedding")

        # Generate segment embeddings
        for segment in segments:
            segment.embedding = generate_segment_embedding(segment)

        logger.info(f"✅ Generated {len(segments)} segment embeddings")

    except Exception as e:
        # Don't fail video processing if embedding generation fails
        logger.warning(f"⚠️ Failed to generate embeddings: {e}")
        logger.warning("Video will be saved without embeddings (still keyword searchable)")

    # Save to database (existing code)
    session.add(video)
    for segment in segments:
        session.add(segment)
    session.commit()

    return video
```

**What this does**:
- ✅ New videos automatically get embeddings
- ✅ If embedding fails, video still gets saved (graceful degradation)
- ✅ Old code paths continue to work
- ✅ Adds ~5 seconds to processing time

---

### Step 5: Implement Semantic Search

**File**: `pipeline/search.py`

```python
"""
Search functionality: keyword, semantic, and hybrid search.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from db.session import get_session
from db.models import Video, Segment
from pipeline.embeddings import load_model, bytes_to_embedding


def keyword_search(query):
    """
    Existing keyword search (unchanged).

    Returns: list of Video objects
    """
    query = query.strip().lower()
    filtered_videos = []

    with get_session() as session:
        all_videos = session.query(Video).all()

        for video in all_videos:
            # Search in multiple fields (existing logic)
            search_fields = [
                video.title.lower() if video.title else "",
                video.tldr.lower() if video.tldr else "",
                video.tldr_zh.lower() if video.tldr_zh else "",
                # ... other fields ...
            ]

            if any(query in field for field in search_fields):
                filtered_videos.append(video)

    return filtered_videos


def semantic_search(query, top_k=20):
    """
    Semantic search using embeddings.

    Args:
        query: search query string
        top_k: return top K most similar videos

    Returns: list of (video, similarity_score) tuples
    """
    model = load_model()
    query_embedding = model.encode(query, convert_to_numpy=True)

    results = []

    with get_session() as session:
        # Only query videos with embeddings
        videos = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).all()

        for video in videos:
            # Convert bytes back to numpy array
            video_emb = bytes_to_embedding(video.embedding)

            # Calculate cosine similarity
            similarity = cosine_similarity(
                [query_embedding],
                [video_emb]
            )[0][0]

            results.append((video, float(similarity)))

    # Sort by similarity and return top K
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def hybrid_search(query):
    """
    Hybrid search: combines keyword + semantic search.

    Users get best of both worlds:
    - Exact matches (🎯) ranked first (score 1.0)
    - Semantic matches (💡) supplement related content

    Returns: list of dicts with structure:
        {
            'video': Video object,
            'score': float (0.0-1.0),
            'type': 'exact' or 'semantic',
            'icon': '🎯' or '💡'
        }
    """
    # 1. Keyword search (fast, exact)
    keyword_results = keyword_search(query)

    # 2. Semantic search (smart, related)
    # Check if any videos have embeddings
    with get_session() as session:
        has_embeddings = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).count() > 0

    if has_embeddings:
        semantic_results = semantic_search(query, top_k=20)
    else:
        # No embeddings yet, fallback to keyword only
        semantic_results = []

    # 3. Merge and deduplicate
    combined = {}

    # Exact matches: score 1.0, always ranked first
    for video in keyword_results:
        combined[video.id] = {
            'video': video,
            'score': 1.0,
            'type': 'exact',
            'icon': '🎯'
        }

    # Semantic matches: add related results (if not already in exact matches)
    for video, similarity in semantic_results:
        if video.id not in combined:
            combined[video.id] = {
                'video': video,
                'score': similarity,
                'type': 'semantic',
                'icon': '💡'
            }

    # 4. Sort by score (exact matches first, then by similarity)
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x['score'],
        reverse=True
    )

    return sorted_results
```

---

### Step 6: Update UI

**File**: `app.py` - Modify `view_history()` function

```python
def view_history():
    """Render the History view with search."""

    st.title("📜 History")

    # ... existing code ...

    # Search functionality
    st.markdown("### 🔍 Search")
    search_query = st.text_input(
        "Search videos by title, content, or tags",
        placeholder="e.g., Python decorators, async programming, 装饰器...",
        help="Smart search: finds exact matches + semantically related content",
        key="search_query"
    )

    # Filter videos based on search query
    if search_query and search_query.strip():
        from pipeline.search import hybrid_search

        results = hybrid_search(search_query.strip())

        if results:
            # Count result types
            exact_count = len([r for r in results if r['type'] == 'exact'])
            semantic_count = len([r for r in results if r['type'] == 'semantic'])

            # Show statistics
            if semantic_count > 0:
                st.success(
                    f"✅ Found {len(results)} result(s): "
                    f"{exact_count} exact match(es) 🎯 + "
                    f"{semantic_count} related result(s) 💡"
                )
            else:
                st.success(f"✅ Found {exact_count} exact match(es) 🎯")

            # Display results
            videos = [r['video'] for r in results]

            for i, result in enumerate(results):
                video = result['video']
                icon = result['icon']

                with st.expander(f"{icon} {video.title}", expanded=False):
                    # Show match type
                    if result['type'] == 'exact':
                        st.caption("🎯 **Exact match** - found in title/content")
                    else:
                        similarity_pct = int(result['score'] * 100)
                        st.caption(f"💡 **Related result** - {similarity_pct}% similar")

                    st.caption(f"📺 {video.channel_name}")
                    st.markdown(video.tldr[:200] + "..." if len(video.tldr) > 200 else video.tldr)

                    # Action buttons
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        if st.button(f"📄 View Full Summary", key=f"view_{video.id}"):
                            st.session_state.selected_video_id = video.id
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️", key=f"del_{video.id}"):
                            st.session_state.confirm_delete_video_id = video.id
                            st.rerun()

        else:
            st.warning(f"⚠️ No videos found matching '{search_query}'")
            st.info("💡 Try different keywords or check spelling")
            return

    else:
        # No search query, show all videos (existing logic)
        videos = get_all_videos()

    # ... rest of existing code ...
```

---

### Step 7: Batch Generate Embeddings for Old Videos (Optional)

**File**: `scripts/backfill_embeddings.py`

```python
"""
Batch generate embeddings for existing videos (without embeddings).
Run this after upgrading to semantic search.
"""

from db.session import get_session
from db.models import Video, Segment
from pipeline.embeddings import generate_video_embedding, generate_segment_embedding
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_embeddings():
    """Generate embeddings for all videos that don't have them."""

    with get_session() as session:
        # Find videos without embeddings
        videos = session.query(Video).filter(
            Video.embedding.is_(None)
        ).all()

        if not videos:
            print("✅ All videos already have embeddings!")
            return

        print(f"📊 Found {len(videos)} videos without embeddings")
        print(f"⏱️  Estimated time: ~{len(videos) * 10} seconds\n")

        success_count = 0
        error_count = 0

        for i, video in enumerate(videos, start=1):
            try:
                print(f"[{i}/{len(videos)}] Processing: {video.title[:50]}...")

                # Generate video embedding
                video.embedding = generate_video_embedding(video)

                # Generate segment embeddings
                segments = session.query(Segment).filter_by(video_id=video.id).all()
                for segment in segments:
                    segment.embedding = generate_segment_embedding(segment)

                session.commit()
                success_count += 1
                print(f"  ✅ Success ({len(segments)} segments)")

            except Exception as e:
                error_count += 1
                logger.error(f"  ❌ Error: {e}")
                session.rollback()

        print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"✅ Successfully processed: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    print("🚀 Starting embedding backfill...\n")
    backfill_embeddings()
    print("\n✨ Done!")
```

Run:
```bash
# This takes ~10 seconds per video
python scripts/backfill_embeddings.py
```

---

## 🧪 Testing

### Test 1: New Video Processing

```bash
# Process a new video
streamlit run app.py

# In UI:
# 1. Go to "➕ New Video"
# 2. Paste a YouTube URL
# 3. Process it
# 4. Check logs for "✅ Generated video embedding"
```

### Test 2: Search

```bash
# In UI:
# 1. Go to "📜 History"
# 2. Search for "decorator"
# 3. Should see:
#    - 🎯 Exact matches (if title/content contains "decorator")
#    - 💡 Semantic matches (related videos about wrappers, patterns, etc.)
```

### Test 3: Database Integrity

```bash
# Check old videos are intact
sqlite3 data/tldr_tube.db "SELECT id, title, tldr FROM videos WHERE embedding IS NULL LIMIT 5;"

# Check new videos have embeddings
sqlite3 data/tldr_tube.db "SELECT id, title, LENGTH(embedding) as emb_size FROM videos WHERE embedding IS NOT NULL LIMIT 5;"
# Should see emb_size = 1536 (384 dimensions × 4 bytes)
```

---

## 🔄 Rollback Plan (If Needed)

If you want to remove semantic search:

### Option 1: Keep Data, Remove Column

```python
# scripts/remove_embeddings.py
from sqlalchemy import text
from db.session import engine

# Remove embedding columns
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE videos DROP COLUMN embedding"))
    conn.execute(text("ALTER TABLE segments DROP COLUMN embedding"))
    conn.commit()

print("✅ Embedding columns removed")
```

### Option 2: Restore from Backup

```bash
# Restore backup
cp data/tldr_tube.db.backup_20260223 data/tldr_tube.db

# Restart app
streamlit run app.py
```

### Option 3: Keep Embeddings, Disable Feature

```python
# In app.py, change:
results = hybrid_search(query)

# To:
results = keyword_search(query)
```

**Data remains, feature disabled** ✅

---

## 📊 Performance Impact

### Storage

| Videos | Segments | Storage Added |
|--------|----------|---------------|
| 10 | 50 | ~75 KB |
| 50 | 250 | ~375 KB |
| 100 | 500 | ~750 KB |
| 500 | 2500 | ~3.75 MB |

**Negligible!** ✅

### Processing Time

| Operation | Before | After | Difference |
|-----------|--------|-------|------------|
| Process new video | 60s | 65s | +5s (8%) |
| Keyword search | 50ms | 50ms | No change |
| Semantic search | N/A | 100ms | New feature |
| Hybrid search | N/A | 150ms | New feature |

**Acceptable!** ✅

### Memory

| Component | Memory |
|-----------|--------|
| Model (loaded once) | ~1 GB |
| Per search | ~10 MB |

**On M1 Mac with 16GB RAM: No issues** ✅

---

## ✅ Summary

### Data Safety

- ✅ Only ADD columns, never delete
- ✅ Old data 100% preserved
- ✅ Can rollback anytime
- ✅ Backup before migration

### Implementation

- ⏱️ 10 hours total
- 🔧 7 steps, all documented
- 📦 One dependency: sentence-transformers
- 🧪 Full test plan included

### User Experience

- 🎯 Exact matches still work (priority)
- 💡 Discover related content (bonus)
- 🌍 Cross-language search enabled
- 🔍 One search box, automatic

### When to Implement

- Video count > 50 ✅
- Users report "can't find content" ✅
- Want cross-language search ✅

---

**Ready to implement? Follow the steps above!** 🚀
