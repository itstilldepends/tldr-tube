# 搜索功能规划 / Search Feature Roadmap

**更新日期 / Last Updated**: 2026-02-23

---

## 📋 总览 / Overview

搜索功能分为三个阶段实现，从简单到智能，逐步提升用户体验。

Search functionality is implemented in three stages, from simple to intelligent, gradually improving user experience.

---

## ✅ 阶段 1：关键词搜索（已完成）/ Stage 1: Keyword Search (Completed)

### 功能描述 / Features

基于 SQL LIKE 查询的简单关键词搜索，支持在多个字段中查找。

Simple keyword search based on SQL LIKE queries, supports searching across multiple fields.

### 搜索范围 / Search Scope

- ✅ 视频标题 / Video title
- ✅ TL;DR 摘要（中英文）/ TL;DR summary (EN & ZH)
- ✅ 分段摘要（中英文）/ Segment summaries (EN & ZH)
- ✅ 视频描述 / Video description
- ✅ 频道名称 / Channel name
- ✅ 标签 / Tags

### 使用方式 / Usage

```python
# In History view
search_query = st.text_input("Search videos...")

# Searches for exact substring match (case-insensitive)
# Example: "python" finds "Python", "python", "PYTHON"
```

### 特点 / Characteristics

- ✅ 实时搜索 / Real-time search
- ✅ 不区分大小写 / Case-insensitive
- ✅ 子字符串匹配 / Substring matching
- ✅ 支持中英文 / Supports Chinese and English
- ✅ 显示匹配数量 / Shows match count

### 适用场景 / Use Cases

1. **精确关键词搜索** / **Exact keyword search**
   - 搜索 "decorator" → 找到所有包含 "decorator" 的视频
   - Search "decorator" → Find all videos containing "decorator"

2. **记得部分内容** / **Remember partial content**
   - 搜索 "async" → 找到异步编程相关视频
   - Search "async" → Find async programming related videos

3. **按标签过滤** / **Filter by tags**
   - 搜索 "python" → 找到所有 Python 相关视频
   - Search "python" → Find all Python related videos

### 局限性 / Limitations

- ❌ 不支持同义词匹配（"decorator" 找不到 "wrapper"）
- ❌ 不支持概念匹配（"性能优化" 找不到 "caching"）
- ❌ 跨语言搜索有限（英文搜索可能找不到中文内容）
- ❌ 无相关性排序（结果按处理时间排序）

### 实现细节 / Implementation Details

**文件**: `app.py` - `view_history()` function

**逻辑**:
```python
# 1. 获取搜索关键词
query = search_query.strip().lower()

# 2. 遍历所有视频
for video in all_videos:
    # 3. 收集所有可搜索字段
    search_fields = [title, tldr, tldr_zh, description, tags, segments...]

    # 4. 检查是否有字段包含关键词
    if any(query in field for field in search_fields):
        filtered_videos.append(video)

# 5. 返回过滤后的结果
```

**性能**:
- 时间复杂度: O(n × m) - n = 视频数, m = 平均字段数
- 对于 < 100 视频，响应时间 < 100ms
- 对于 > 500 视频，可能需要优化

### 工作量 / Effort

- **开发时间**: 2 小时
- **测试时间**: 0.5 小时
- **总计**: 2.5 小时

---

## 🚧 阶段 2：本地语义搜索（计划中）/ Stage 2: Local Semantic Search (Planned)

### 何时实现 / When to Implement

**触发条件**:
- 视频数量 > 50 / Video count > 50
- 用户反馈"关键词搜索找不到相关内容" / User feedback about search limitations
- 有跨语言搜索需求 / Need for cross-language search

### 功能增强 / Feature Enhancements

**1. 同义词匹配** / **Synonym Matching**
```
搜索 "decorator" → 也能找到:
- "wrapper function"
- "function decorator"
- "装饰器"（中文）
```

**2. 概念匹配** / **Concept Matching**
```
搜索 "提升性能" → 也能找到:
- "caching"
- "optimization"
- "concurrent programming"
- "lazy loading"
```

**3. 跨语言搜索** / **Cross-language Search**
```
英文搜索 "decorators" → 能找到:
- 英文内容中的 "decorators"
- 中文内容中的 "装饰器"
```

**4. 相关性排序** / **Relevance Ranking**
```
搜索结果按相似度排序，最相关的在前
Results sorted by similarity score, most relevant first
```

### 数据库兼容性 / Database Compatibility

**好消息**：语义搜索代码在 SQLite 和 PostgreSQL 之间 **零改动** ✅

使用 SQLAlchemy + numpy bytes 存储方案：
- `embedding = Column(LargeBinary)`
- SQLite 和 PostgreSQL 都支持
- 迁移数据库时搜索代码不需要改

📖 详见 `DATABASE_AND_SEARCH_FAQ.md` 问题 1

### 技术方案 / Technical Approach

**使用 sentence-transformers 本地模型**:

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# 1. 选择模型（多语言小模型）
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# 模型特点:
# - 大小: ~500MB
# - 支持: 中英文 + 50+ 语言
# - 向量维度: 384
# - 速度: 在 M1 Mac 上 ~100 texts/second
```

**数据库改动**:

```python
# 在 Video model 添加 embedding 字段
class Video(Base):
    # ... existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # 存储 numpy array

# 在 Segment model 添加 embedding 字段
class Segment(Base):
    # ... existing fields ...
    embedding = Column(LargeBinary, nullable=True)
```

**处理流程**:

```python
# 1. 处理新视频时生成 embeddings
def process_video_with_embeddings(video, segments):
    model = load_model()  # 单例模式，只加载一次

    # 为视频生成 embedding
    video_text = f"{video.title} {video.tldr} {video.tldr_zh}"
    video.embedding = model.encode(video_text).tobytes()

    # 为每个 segment 生成 embedding
    for segment in segments:
        seg_text = f"{segment.summary} {segment.summary_zh}"
        segment.embedding = model.encode(seg_text).tobytes()

# 2. 语义搜索
def semantic_search(query, top_k=10):
    model = load_model()

    # 查询向量
    query_embedding = model.encode(query)

    # 从数据库加载所有 embeddings
    all_embeddings = []
    all_videos = []

    for video in videos:
        video_embedding = np.frombuffer(video.embedding, dtype=np.float32)
        all_embeddings.append(video_embedding)
        all_videos.append(video)

    # 计算余弦相似度
    similarities = cosine_similarity([query_embedding], all_embeddings)[0]

    # 排序并返回 top K
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    return [(all_videos[i], similarities[i]) for i in top_indices]
```

**混合搜索策略**（推荐）⭐:

```python
def hybrid_search(query):
    """
    Hybrid search: combines exact keyword matching with semantic similarity.
    Users get best of both worlds without choosing modes.
    """
    # 1. 关键词搜索（快速，精确）
    keyword_results = keyword_search(query)

    # 2. 语义搜索（智能，相关）
    semantic_results = semantic_search(query, top_k=20)

    # 3. 合并去重
    combined = {}

    # Exact matches: score 1.0, always ranked first
    for video in keyword_results:
        combined[video.id] = {
            'video': video,
            'score': 1.0,
            'type': 'exact',
            'icon': '🎯'
        }

    # Semantic matches: add related results
    for video, similarity in semantic_results:
        if video.id not in combined:  # De-duplicate
            combined[video.id] = {
                'video': video,
                'score': similarity,
                'type': 'semantic',
                'icon': '💡'
            }

    # 4. 按分数排序（精确匹配总是在前）
    return sorted(combined.values(), key=lambda x: x['score'], reverse=True)
```

**用户体验**（类似 Google）：
- **一个搜索框**，自动结合两种搜索
- **精确匹配**用 🎯 标识，分数 1.0，排在最前
- **相关结果**用 💡 标识，显示相似度百分比（如 "95% similar"）
- **跨语言发现**：英文搜索能找到中文内容
- **用户无需选择**搜索模式，自动给最佳结果

**为什么不让用户选择？**
- ✅ 简单：一个搜索框 vs 复杂的模式选项
- ✅ 智能：自动给最好的结果
- ✅ 不丢失精确匹配：🎯 总是排在前面
- ✅ 业界标准：Google、Bing 都是这么做的

### 成本估算 / Cost Estimation

**存储成本**:
- 每个 video embedding: 384 × 4 bytes = 1.5KB
- 每个 segment embedding: 1.5KB
- 100 videos × 5 segments = 600 embeddings
- 总存储: 600 × 1.5KB = **900KB** （可忽略）

**计算成本**:
- 首次下载模型: 500MB（一次性）
- 加载模型到内存: ~1GB RAM
- 生成 embedding: ~10ms per text（M1 Mac）
- 搜索时间: ~50ms for 100 videos

**总成本**: $0 （完全本地，无 API 费用）

### 优缺点 / Pros & Cons

**优点** / **Pros**:
- ✅ 零 API 成本 / Zero API cost
- ✅ 隐私安全（数据不离开本地）/ Privacy-safe (data stays local)
- ✅ 支持多语言 / Multi-language support
- ✅ 智能匹配 / Intelligent matching
- ✅ Apple Silicon MPS 加速 / Apple Silicon MPS acceleration

**缺点** / **Cons**:
- ❌ 需要下载 500MB 模型 / Need to download 500MB model
- ❌ 首次加载慢（3-5秒）/ Slow first load (3-5s)
- ❌ 内存占用 ~1GB / Memory usage ~1GB
- ❌ 需要修改数据库 schema / Requires database schema changes

### 实现步骤 / Implementation Steps

#### Phase 1: 数据库准备（安全，不丢数据）

**关键原则**：只添加新列，不删除旧数据 ✅

```python
# 1. 修改 db/models.py - 添加新字段
class Video(Base):
    # ... existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # 新增！

class Segment(Base):
    # ... existing fields ...
    embedding = Column(LargeBinary, nullable=True)  # 新增！
```

**迁移策略**：
- ✅ 新字段设为 `nullable=True` - 旧数据不受影响
- ✅ SQLAlchemy 自动添加列 - 已有数据保持不变
- ✅ 新处理的视频自动生成 embedding
- ✅ 旧视频可以按需批量生成

#### Phase 2: 安装依赖

```bash
pip install sentence-transformers
pip freeze > requirements.txt
```

#### Phase 3: Embedding 生成模块

创建 `pipeline/embeddings.py`:

```python
from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache

@lru_cache(maxsize=1)
def load_model():
    """Load model once, cache in memory"""
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

def generate_video_embedding(video):
    """Generate embedding for video"""
    model = load_model()
    text = f"{video.title} {video.tldr} {video.tldr_zh}"
    embedding = model.encode(text)
    return embedding.tobytes()

def generate_segment_embedding(segment):
    """Generate embedding for segment"""
    model = load_model()
    text = f"{segment.summary} {segment.summary_zh}"
    embedding = model.encode(text)
    return embedding.tobytes()
```

#### Phase 4: 修改视频处理流程

在 `pipeline/processor.py` 中集成：

```python
from pipeline.embeddings import generate_video_embedding, generate_segment_embedding

def process_youtube_video(...):
    # ... existing processing ...

    # Generate embeddings (new videos only)
    video.embedding = generate_video_embedding(video)

    for segment in segments:
        segment.embedding = generate_segment_embedding(segment)

    # Save to database
    session.add(video)
    session.commit()
```

#### Phase 5: 实现混合搜索

创建 `pipeline/search.py`:

```python
def keyword_search(query):
    """Existing keyword search (unchanged)"""
    # ... current implementation ...

def semantic_search(query, top_k=20):
    """Semantic search using embeddings"""
    from pipeline.embeddings import load_model
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    model = load_model()
    query_embedding = model.encode(query)

    results = []
    with get_session() as session:
        videos = session.query(Video).filter(Video.embedding.isnot(None)).all()

        for video in videos:
            video_emb = np.frombuffer(video.embedding, dtype=np.float32)
            similarity = cosine_similarity([query_embedding], [video_emb])[0][0]
            results.append((video, float(similarity)))

    # Return top K
    return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

def hybrid_search(query):
    """Combine keyword + semantic search"""
    # Implementation shown above
    ...
```

#### Phase 6: 更新 UI

修改 `app.py` 的 `view_history()`:

```python
def view_history():
    # ... existing code ...

    if search_query:
        # Use hybrid search if embeddings available
        has_embeddings = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).count() > 0

        if has_embeddings:
            results = hybrid_search(search_query)
        else:
            # Fallback to keyword search
            results = keyword_search(search_query)

        # Display results with icons
        for result in results:
            icon = result.get('icon', '🎬')
            st.expander(f"{icon} {result['video'].title}")

            if result.get('type') == 'exact':
                st.caption("🎯 Exact match")
            elif result.get('type') == 'semantic':
                similarity = int(result['score'] * 100)
                st.caption(f"💡 Related result - {similarity}% similar")
```

#### Phase 7: 批量生成旧视频的 Embeddings（可选）

创建 `scripts/generate_embeddings.py`:

```python
from db.session import get_session
from db.models import Video, Segment
from pipeline.embeddings import generate_video_embedding, generate_segment_embedding

def backfill_embeddings():
    """Generate embeddings for existing videos"""
    with get_session() as session:
        videos = session.query(Video).filter(Video.embedding.is_(None)).all()

        print(f"Processing {len(videos)} videos...")

        for i, video in enumerate(videos):
            print(f"[{i+1}/{len(videos)}] {video.title}")

            # Generate video embedding
            video.embedding = generate_video_embedding(video)

            # Generate segment embeddings
            for segment in video.segments:
                segment.embedding = generate_segment_embedding(segment)

            session.commit()

        print("✅ Done!")

if __name__ == "__main__":
    backfill_embeddings()
```

运行：
```bash
python scripts/generate_embeddings.py
```

### 工作量估算 / Effort Estimation

| 阶段 | 时间 | 风险 |
|-----|------|-----|
| 修改数据库 schema | 0.5h | ✅ 低（只添加列） |
| 安装依赖 + 测试 | 0.5h | ✅ 低 |
| Embedding 生成模块 | 1.5h | ✅ 低 |
| 修改处理流程 | 1h | ⚠️ 中（测试新视频） |
| 实现混合搜索 | 2h | ⚠️ 中 |
| 更新 UI | 1.5h | ✅ 低 |
| 批量生成旧数据 | 1h | ✅ 低（可选） |
| 测试和优化 | 2h | ⚠️ 中 |
| **总计** | **10h** | **整体低风险** |

### 数据安全保障

- ✅ **不删除旧列** - 只添加新的 `embedding` 列
- ✅ **新列可为空** - `nullable=True`，旧数据不受影响
- ✅ **渐进式迁移** - 新视频自动生成，旧视频按需生成
- ✅ **可回退** - 如果不满意，删除 embedding 列即可
- ✅ **SQLite 备份** - 改动前先 `cp data/tldr_tube.db data/tldr_tube.db.backup`

---

## 🌟 阶段 3：高级搜索（未来）/ Stage 3: Advanced Search (Future)

### 计划功能 / Planned Features

1. **高级过滤器** / **Advanced Filters**
   - 按视频类型筛选（tutorial / podcast / lecture）
   - 按日期范围筛选
   - 按时长筛选
   - 按频道筛选

2. **搜索历史** / **Search History**
   - 保存最近 10 次搜索
   - 快速重复搜索
   - 搜索建议

3. **正则表达式支持** / **Regex Support**
   - 高级用户的复杂查询
   - 模式匹配

4. **搜索结果高亮** / **Search Highlighting**
   - 在结果中高亮显示匹配的关键词
   - 显示上下文片段

5. **自动完成** / **Autocomplete**
   - 基于已有内容的搜索建议
   - 常见搜索词推荐

6. **保存搜索** / **Saved Searches**
   - 保存常用搜索查询
   - 创建智能 Collection（基于搜索结果）

### 工作量估算 / Effort Estimation

- **总计**: 8-12 小时（取决于功能范围）

---

## 📊 对比总结 / Comparison Summary

| 特性 / Feature | 阶段 1 关键词 | 阶段 2 语义 | 阶段 3 高级 |
|----------------|--------------|------------|------------|
| **实现难度** | ⭐ 简单 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 复杂 |
| **开发时间** | 2.5 小时 | 10 小时 | 12 小时 |
| **API 成本** | $0 | $0 | $0 |
| **存储需求** | 0 | +900KB | +2MB |
| **内存占用** | 低 | 中（1GB） | 中 |
| **搜索速度** | 快（<100ms） | 中（<200ms） | 中 |
| **精确匹配** | ✅ 优秀 | ✅ 优秀 | ✅ 优秀 |
| **同义词** | ❌ 不支持 | ✅ 支持 | ✅ 支持 |
| **跨语言** | ⚠️ 有限 | ✅ 支持 | ✅ 支持 |
| **概念匹配** | ❌ 不支持 | ✅ 支持 | ✅ 支持 |
| **相关性排序** | ❌ 无 | ✅ 有 | ✅ 有 |
| **适合场景** | < 50 videos | > 50 videos | 重度用户 |

---

## 🎯 实施建议 / Implementation Recommendations

### 当前阶段（视频 < 50）

✅ **阶段 1 已足够**
- 关键词搜索满足基本需求
- 快速、轻量、零成本
- 用户可以找到记得关键词的视频

### 成长阶段（视频 > 50）

🔄 **考虑阶段 2**
- 视频数量增多，搜索难度增加
- 用户可能记不清精确关键词
- 语义搜索提升体验

**决策标准**:
1. 用户反馈"搜索找不到想要的内容" → 升级
2. 视频数量 > 50 → 考虑升级
3. 有跨语言搜索需求 → 升级

### 成熟阶段（重度用户）

🚀 **考虑阶段 3**
- 视频数量 > 200
- 需要精细化管理
- 有复杂搜索需求

---

## 📝 决策检查清单 / Decision Checklist

**何时从阶段 1 升级到阶段 2？**

检查以下问题：
- [ ] 视频数量是否 > 50？
- [ ] 用户是否经常抱怨"搜不到想要的内容"？
- [ ] 是否需要跨语言搜索（英文查中文内容）？
- [ ] 是否愿意接受 500MB 模型下载和 1GB 内存占用？
- [ ] 是否有 10 小时开发时间？

**如果 3+ 个"是"，建议升级到阶段 2**

---

## 🔗 相关文档 / Related Documents

- `DATABASE_AND_SEARCH_FAQ.md` ⭐ - 数据库迁移和搜索方案详细 FAQ
- `TODO.md` - 项目待办事项 / Project TODO list
- `CLAUDE.md` - 开发指南 / Development guide
- `app.py` - 搜索功能实现 / Search implementation

---

**Made with ❤️ for efficient learning**
