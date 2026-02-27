# RAG Question Answering System Design

**Goal**: Transform tldr-tube into a RAG system where users ask questions and get AI-generated answers based on processed video content.

**Status**: ✅ IMPLEMENTED (2026-02-23)

## 🎉 Implementation Summary

**Core Features Implemented**:
- ✅ Natural language Q&A interface
- ✅ Two-phase retrieval (video-level + segment-level)
- ✅ Context with summaries + transcript excerpts
- ✅ Citations with video titles and timestamps
- ✅ Cross-language support (auto-detect EN/ZH)
- ✅ **Video filtering (select specific videos/collections to search)**

**New Feature (2026-02-23)**: 🎯 **Search Scope Selection**
- Users can select which videos/collections to search
- Checkbox interface with "Select All" / "Deselect All"
- Default: all videos selected
- Improves accuracy by focusing search scope

**Files**:
- `pipeline/rag.py` - RAG pipeline with filtering support
- `app.py` - "🤖 Ask AI" page with search scope selector
- `scripts/test_rag.py` - Testing script

**How to Use**:
1. Open tldr-tube and click "🤖 Ask AI"
2. (Optional) Click "🎯 Search Scope" to select specific videos/collections
3. Enter your question
4. Click "🔍 Search & Answer"
5. View AI-generated answer with citations

**Performance**:
- Speed: ~8-14 seconds per query
- Cost: ~$0.02 per query (Sonnet)
- Accuracy: High (includes original transcript excerpts)

---

---

## 🎯 User Flow

```
User asks: "How do Python decorators work?"
    ↓
[Semantic Search] Find top 5 relevant videos
    ↓
[Extract Context] Get summaries + relevant segments
    ↓
[Claude API] Generate answer with citations
    ↓
Display: Answer + Referenced videos with timestamps
```

---

## 📊 Architecture Design

### Option A: Summary-Only RAG (Simple, Fast)

**What to retrieve**:
- Top 5 videos by semantic similarity
- For each video: title + tldr + all segment summaries

**Pros**:
- ✅ Fast (no heavy processing)
- ✅ Fits easily in context (5 videos × 2K tokens = 10K total)
- ✅ Clean, structured content

**Cons**:
- ⚠️ May miss fine details in transcript
- ⚠️ Can't quote exact words from video

**Token Budget**:
```
Question: 100 tokens
5 videos × (title + tldr + 10 segments × 100 tokens each): ~10K tokens
Answer generation: ~500 tokens
Total: ~11K tokens (well within 200K limit)
```

**Recommended for**: General Q&A, concept explanations, tutorial recommendations

---

### Option B: Transcript-Enhanced RAG (Detailed, Slower) ⭐ RECOMMENDED

**What to retrieve**:
1. **Phase 1 (Video-level search)**: Find top 3-5 videos by semantic similarity
2. **Phase 2 (Segment-level search)**: For each video, find top 3 most relevant segments
3. **Phase 3 (Context building)**:
   - Video metadata (title, channel, url)
   - Video TL;DR
   - For top 3 segments: summary + **original transcript excerpt**

**Pros**:
- ✅ Preserves fine details
- ✅ Can quote exact phrases from video
- ✅ Better accuracy for technical questions
- ✅ Still manageable token count

**Cons**:
- ⚠️ Slightly more complex
- ⚠️ +2 seconds processing time

**Token Budget**:
```
Question: 100 tokens
3 videos × (
    Metadata: 50 tokens
    TL;DR: 200 tokens
    3 segments × (summary: 100 + transcript: 300)
) = 3 × 1450 = ~4.5K tokens
Answer generation: ~500 tokens
Total: ~5K tokens (very safe)
```

**Recommended for**: All use cases (best quality/performance trade-off)

---

### Option C: Full Transcript RAG (Maximum Detail)

**What to retrieve**:
- Top 2-3 videos
- Full transcript for each video

**Pros**:
- ✅ No information loss

**Cons**:
- ❌ Very high token count (3 videos × 8K = 24K tokens)
- ❌ Slower processing
- ❌ More noise (irrelevant details)

**Not recommended** (Option B is better)

---

## 🏆 Recommended Implementation: Option B (Transcript-Enhanced RAG)

### Step-by-Step Process

#### 1. User Input
```python
# In app.py, new view: view_ask_ai()
question = st.text_area(
    "Ask a question about your processed videos",
    placeholder="e.g., How do Python decorators work?\nWhat is async programming?\n什么是装饰器？"
)
```

#### 2. Video-Level Search (Coarse)
```python
# Use existing hybrid_search
from pipeline.search import hybrid_search

video_results = hybrid_search(
    query=question,
    top_k=3,  # Top 3 most relevant videos
    min_semantic_score=0.4  # Higher threshold for relevance
)

# Result: [(video, score, match_info), ...]
```

#### 3. Segment-Level Search (Fine) - NEW FUNCTIONALITY

For each retrieved video, find the most relevant segments:

```python
def find_relevant_segments(question: str, video, top_k=3):
    """
    Find top K most relevant segments within a video.

    Returns: List of (segment, similarity_score) tuples
    """
    model = load_model()
    question_embedding = model.encode([question])

    # Get all segments for this video
    segments = session.query(Segment).filter_by(video_id=video.id).all()

    results = []
    for segment in segments:
        # Create segment text (for embedding)
        segment_text = f"{segment.summary} {segment.summary_zh}"
        segment_embedding = model.encode([segment_text])

        # Compute similarity
        similarity = cosine_similarity(question_embedding, segment_embedding)[0][0]
        results.append((segment, similarity))

    # Sort by similarity, return top K
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]
```

#### 4. Build Context (Retrieve Content)

```python
def build_rag_context(question: str, video_results, top_segments_per_video=3):
    """
    Build RAG context from retrieved videos and segments.

    Returns: Formatted context string for Claude
    """
    context_parts = []

    context_parts.append(f"User Question: {question}\n")
    context_parts.append("=" * 60)
    context_parts.append("\nRetrieved Video Content:\n")

    for i, (video, video_score, match_info) in enumerate(video_results, 1):
        context_parts.append(f"\n## Video {i}: {video.title}")
        context_parts.append(f"**Source**: {video.source_url}")
        context_parts.append(f"**Channel**: {video.channel_name}")
        context_parts.append(f"**Relevance**: {match_info} (score: {video_score:.3f})")
        context_parts.append(f"\n**Summary**: {video.tldr}\n")

        # Find relevant segments
        relevant_segments = find_relevant_segments(question, video, top_k=top_segments_per_video)

        context_parts.append("**Relevant Segments**:")
        for j, (segment, seg_score) in enumerate(relevant_segments, 1):
            context_parts.append(f"\n### [{segment.timestamp}] Segment {j} (similarity: {seg_score:.3f})")
            context_parts.append(f"**Summary**: {segment.summary}")

            # Get transcript excerpt for this segment
            transcript_excerpt = extract_transcript_excerpt(
                video.raw_transcript,
                segment.start_seconds,
                segment.end_seconds
            )
            context_parts.append(f"**Transcript**: {transcript_excerpt}")

    return "\n".join(context_parts)


def extract_transcript_excerpt(raw_transcript_json: str, start: float, end: float):
    """
    Extract transcript text for a specific time range.

    Args:
        raw_transcript_json: JSON string from Video.raw_transcript
        start: Start time in seconds
        end: End time in seconds

    Returns: Concatenated transcript text
    """
    import json
    transcript = json.loads(raw_transcript_json)

    excerpt_parts = []
    for entry in transcript:
        entry_start = entry.get('start', 0)
        entry_end = entry_start + entry.get('duration', 0)

        # Check if this entry overlaps with [start, end]
        if entry_end >= start and entry_start <= end:
            excerpt_parts.append(entry['text'])

    return " ".join(excerpt_parts)
```

#### 5. Generate Answer with Claude

```python
def generate_rag_answer(question: str, context: str, model: str = "sonnet"):
    """
    Generate answer using Claude with RAG context.

    Args:
        question: User's question
        context: Retrieved context (videos + segments + transcripts)
        model: Claude model to use

    Returns: AI-generated answer with citations
    """
    from anthropic import Anthropic
    import os

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""You are a helpful AI assistant answering questions based on YouTube video summaries and transcripts.

Context from retrieved videos:
{context}

User Question: {question}

Instructions:
1. Answer the question based ONLY on the provided video content
2. If the videos don't contain enough information, say so
3. Include citations with video titles and timestamps (e.g., "According to Video 1 [05:30], ...")
4. Be concise but thorough
5. If multiple videos cover the topic, synthesize the information
6. If the question is in Chinese, answer in Chinese; if in English, answer in English

Answer:"""

    response = client.messages.create(
        model=get_claude_model_id(model),
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

---

## 🎨 UI Design

### New Page: "🤖 Ask AI"

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 Ask AI about your videos                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Ask a question:                                              │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ How do Python decorators work?                       │    │
│ │                                                       │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│ [🔍 Search & Answer]  Claude Model: [Sonnet ▼]             │
│                                                              │
└─────────────────────────────────────────────────────────────┘

After clicking "Search & Answer":

┌─────────────────────────────────────────────────────────────┐
│ ⏳ Searching relevant videos... (3 found)                   │
│ ⏳ Analyzing segments... (9 segments)                       │
│ ⏳ Generating answer with Claude Sonnet...                  │
└─────────────────────────────────────────────────────────────┘

Then show results:

┌─────────────────────────────────────────────────────────────┐
│ 💡 Answer                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Python decorators are functions that modify the behavior    │
│ of other functions. According to Video 1 [05:30], they      │
│ use the @decorator syntax and are commonly used for...      │
│                                                              │
│ Key points from the videos:                                 │
│ 1. Basic syntax (Video 1 [03:15])                          │
│ 2. Decorators with arguments (Video 2 [08:45])             │
│ 3. Class decorators (Video 1 [12:00])                      │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ 📚 Referenced Videos                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 🎯 Video 1: Python Decorators Tutorial                      │
│    Match: 🎯💡 Keyword + Semantic (score: 0.87)            │
│    📺 TechWithTim | ⏱️ 45:30                                │
│    [📄 View Full Summary] [▶️ Watch Video]                  │
│                                                              │
│ 💡 Video 2: Advanced Python Patterns                        │
│    Match: 💡 Semantic (score: 0.64)                         │
│    📺 Corey Schafer | ⏱️ 1:23:45                           │
│    [📄 View Full Summary] [▶️ Watch Video]                  │
│                                                              │
│ 💡 Video 3: 装饰器详解                                       │
│    Match: 💡 Semantic (score: 0.61)                         │
│    📺 某Python教程 | ⏱️ 38:20                               │
│    [📄 View Full Summary] [▶️ Watch Video]                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Sidebar Menu Update

```python
# In app.py
menu_options = {
    "➕ New Video": view_new_video,
    "📚 New Collection": view_new_collection,
    "📜 History": view_history,
    "🤖 Ask AI": view_ask_ai,  # NEW!
}
```

---

## 📁 File Structure

New files to create:

```
pipeline/
├── rag.py                    # RAG logic (NEW)
│   ├── find_relevant_segments()
│   ├── build_rag_context()
│   ├── extract_transcript_excerpt()
│   └── generate_rag_answer()

app.py
└── view_ask_ai()             # NEW UI view
```

Modify existing:
```
pipeline/search.py
└── Add segment-level semantic search (if we want segment embeddings)
    OR use on-the-fly encoding (simpler, no DB changes needed)
```

---

## 🔧 Implementation Options

### Option 1: On-the-Fly Segment Encoding (Simpler) ⭐ RECOMMENDED

**Pros**:
- ✅ No database schema changes
- ✅ No need to backfill segment embeddings
- ✅ Simpler implementation

**Cons**:
- ⚠️ Slower for videos with many segments (~2-3 seconds per video)
- ⚠️ Re-encodes segments every query

**When to use**: Current video count < 100, acceptable latency

```python
# In find_relevant_segments()
for segment in segments:
    segment_text = f"{segment.summary} {segment.summary_zh}"
    segment_embedding = model.encode([segment_text])  # On-the-fly
    similarity = cosine_similarity(question_embedding, segment_embedding)
```

---

### Option 2: Precomputed Segment Embeddings (Faster, More Storage)

**Pros**:
- ✅ Very fast (~100ms per video, no re-encoding)
- ✅ Scales well to large video counts

**Cons**:
- ❌ Requires DB schema change (add `embedding` to Segment model)
- ❌ Need to backfill existing segments
- ❌ More storage (~1.5KB per segment)

**When to use**: Video count > 100, or latency is critical

```python
# In db/models.py
class Segment(Base):
    # ... existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # NEW

# In pipeline/processor.py
for segment in segments:
    segment.embedding = generate_segment_embedding(segment)  # During processing

# In find_relevant_segments()
for segment in segments:
    segment_emb = bytes_to_embedding(segment.embedding)  # Pre-computed
    similarity = cosine_similarity(question_embedding, segment_emb)
```

**Recommendation**: Start with Option 1, migrate to Option 2 if needed

---

## 🧪 Test Cases

### Test 1: Technical Question
```
Question: "How do async functions work in Python?"
Expected:
- Find videos about async/await
- Extract relevant segments with code examples
- Answer with technical details + citations
```

### Test 2: Cross-Language Query
```
Question: "什么是装饰器？"
Expected:
- Find Chinese videos about decorators
- Also find English videos (cross-language search)
- Answer in Chinese
```

### Test 3: No Relevant Content
```
Question: "How to build a spaceship?"
Expected:
- No videos found above threshold
- Answer: "I don't have any videos covering this topic. Please process relevant videos first."
```

### Test 4: Multiple Videos Cover Topic
```
Question: "Explain React hooks"
Expected:
- Find 3-5 videos about React hooks
- Synthesize information from all videos
- Include citations from multiple sources
```

---

## 📊 Performance Estimates

### Latency Breakdown (Option 1: On-the-Fly)

| Step | Time |
|------|------|
| Video-level search (3 videos) | 100ms |
| Segment-level search (3 videos × 10 segments) | 2-3s |
| Extract transcript excerpts | 100ms |
| Claude API call (answer generation) | 5-10s |
| **Total** | **8-14s** |

### Latency Breakdown (Option 2: Precomputed)

| Step | Time |
|------|------|
| Video-level search (3 videos) | 100ms |
| Segment-level search (pre-computed) | 200ms |
| Extract transcript excerpts | 100ms |
| Claude API call (answer generation) | 5-10s |
| **Total** | **6-11s** |

**Both are acceptable for a RAG system** ✅

---

## 💰 Cost Estimates

### Claude API Cost (per query)

**Input tokens** (context):
- Question: 100 tokens
- 3 videos × 1500 tokens = 4500 tokens
- **Total input**: ~4.6K tokens

**Output tokens** (answer):
- Answer: ~500 tokens

**Cost** (Sonnet 4.5):
- Input: 4.6K × $0.003 / 1K = $0.014
- Output: 500 × $0.015 / 1K = $0.0075
- **Total per query**: ~$0.02

**For 100 queries**: ~$2.00 (very affordable) ✅

---

## 🎯 Recommendation Summary

### Start With This:

1. **Retrieval Strategy**: Transcript-Enhanced RAG (Option B)
   - Video-level search (top 3 videos)
   - Segment-level search (top 3 segments per video)
   - Include segment summaries + transcript excerpts

2. **Segment Encoding**: On-the-Fly (Option 1)
   - No DB changes needed
   - Acceptable latency for current scale

3. **UI**: New "🤖 Ask AI" page
   - Question input
   - Search & answer button
   - Display answer + referenced videos

4. **Future Optimization** (if needed):
   - Add segment embeddings to database
   - Cache frequently asked questions
   - Add conversation history (multi-turn Q&A)

---

## 🚀 Next Steps

If you approve this design, I can implement:

1. **Phase 1** (Core RAG):
   - Create `pipeline/rag.py` with all retrieval logic
   - Add `view_ask_ai()` in `app.py`
   - Test with your existing videos

2. **Phase 2** (Polish):
   - Add loading indicators
   - Format answer with markdown
   - Add "Copy Answer" button
   - Add "Ask Follow-up" feature

3. **Phase 3** (Optimization - Optional):
   - Precomputed segment embeddings
   - Query caching
   - Multi-turn conversation

**Estimated time**: 3-4 hours for Phase 1

---

**Let me know if you want me to proceed with this design, or if you'd like to adjust anything!** 🚀
