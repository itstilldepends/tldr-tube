# 数据库迁移与搜索功能 FAQ / Database Migration & Search FAQ

**更新日期 / Date**: 2026-02-23

---

## 🗄️ 问题 1：SQLite → PostgreSQL 迁移会影响语义搜索吗？

### 简短回答 / Short Answer

**基本不需要重新实现** ✅

使用 SQLAlchemy + numpy bytes 存储 embeddings 的方案，代码在 SQLite 和 PostgreSQL 之间几乎零改动。

---

### 详细说明 / Detailed Explanation

#### 当前规划的架构

```python
# 在 Video/Segment 模型中存储 embedding
class Video(Base):
    embedding = Column(LargeBinary, nullable=True)  # numpy array 转为 bytes

# 生成 embedding
video.embedding = model.encode(text).tobytes()  # numpy → bytes

# 搜索时加载
video_embedding = np.frombuffer(video.embedding, dtype=np.float32)  # bytes → numpy
similarity = cosine_similarity(query_embedding, video_embedding)
```

#### SQLite vs PostgreSQL 对比

| 特性 | SQLite | PostgreSQL | 影响 |
|-----|--------|------------|-----|
| **BLOB/Binary 类型** | ✅ 支持 | ✅ 支持 (bytea) | 无影响 |
| **SQLAlchemy LargeBinary** | ✅ 支持 | ✅ 支持 | 无影响 |
| **存储 numpy bytes** | ✅ 支持 | ✅ 支持 | 无影响 |
| **向量搜索** | ❌ 无原生支持 | ⚠️ 需要 pgvector 插件 | 可选优化 |
| **性能（< 1000 videos）** | 足够快 | 略快 | 差异不大 |
| **性能（> 1000 videos）** | 较慢 | 用 pgvector 快很多 | 可选优化 |

---

### 迁移步骤 / Migration Steps

**从 SQLite 迁移到 PostgreSQL**：

```bash
# 1. 更新环境变量
# .env
DATABASE_URL=postgresql://user:pass@localhost/tldr_tube

# 2. 重建表结构
python -c "from db.session import init_db; init_db()"

# 3. 迁移数据（SQLAlchemy 自动处理）
# embedding 字段 (LargeBinary) 在两个数据库中都是二进制类型
# 数据直接复制过去即可
```

**代码改动**：

```python
# 搜索代码完全不变！
def semantic_search(query):
    model = load_model()
    query_embedding = model.encode(query)

    # 这部分逻辑 SQLite 和 PostgreSQL 完全一样
    for video in videos:
        video_embedding = np.frombuffer(video.embedding, dtype=np.float32)
        similarity = cosine_similarity(query_embedding, video_embedding)

    return results
```

**改动量**：0 行代码 ✅

---

### 性能优化（可选）/ Optional Performance Optimization

如果将来视频数量 > 1000，可以考虑使用 **pgvector** 优化：

#### 什么是 pgvector？

PostgreSQL 的向量搜索插件，支持：
- 原生向量类型 `vector(384)`
- 高效的相似度搜索索引（IVFFlat, HNSW）
- SQL 中直接计算余弦相似度

#### 使用 pgvector 的改动

```python
# 1. 修改数据库 schema
from pgvector.sqlalchemy import Vector

class Video(Base):
    embedding = Column(Vector(384), nullable=True)  # 改用 Vector 类型

# 2. 修改搜索逻辑
def semantic_search_pgvector(query):
    query_embedding = model.encode(query)

    # 在 SQL 中搜索（比 Python 循环快 10-100x）
    results = session.query(Video).order_by(
        Video.embedding.cosine_distance(query_embedding)
    ).limit(10).all()

    return results
```

#### 性能对比

| 数据量 | Python 循环 (当前方案) | pgvector (优化方案) |
|-------|---------------------|-------------------|
| 100 videos | ~50ms | ~10ms |
| 1,000 videos | ~500ms | ~50ms |
| 10,000 videos | ~5s | ~200ms |

---

### 我的建议 / Recommendation

#### 短期（当前 - 1000 videos）

✅ **使用 SQLAlchemy + numpy bytes 方案**

**原因**：
- 代码可移植（SQLite ↔ PostgreSQL 零改动）
- 性能对 < 1000 videos 完全够用
- 不依赖额外插件
- 实现简单

#### 长期（> 1000 videos）

🔄 **考虑迁移到 pgvector**

**触发条件**：
- 视频数量 > 1000
- 搜索延迟 > 500ms
- 已经迁移到 PostgreSQL

**迁移工作量**：~3-4 小时
- 安装 pgvector 插件
- 修改 Video/Segment schema
- 重新生成 embeddings（或批量转换）
- 修改搜索逻辑

---

## 🔍 问题 2：语义搜索和关键词搜索如何共存？

### 简短回答 / Short Answer

**推荐使用混合搜索** - 一个搜索框，自动结合两种搜索，精确匹配优先。

用户无需选择，获得最佳体验 ✨

---

### 三种方案对比 / Three Approaches

#### 方案 A：混合搜索（推荐）⭐

**UI**：
```
┌─────────────────────────────────────┐
│ 🔍 Search videos...                │  ← 单个搜索框
│                                     │
│ ━━━ Results (5 exact + 3 related) ━│
│                                     │
│ 🎯 Python Decorators Tutorial      │  ← 精确匹配（加粗）
│    Found in: Title (exact match)    │
│                                     │
│ 🎯 Advanced Decorator Patterns     │  ← 精确匹配
│    Found in: TL;DR (exact match)    │
│                                     │
│ 💡 Function Wrappers in Python     │  ← 语义匹配
│    Found via: semantic search (95%) │
│                                     │
│ 💡 装饰器设计模式详解                │  ← 跨语言语义匹配
│    Found via: semantic search (92%) │
└─────────────────────────────────────┘
```

**实现逻辑**：

```python
def hybrid_search(query):
    # 1. 关键词搜索（精确、快速）
    keyword_results = keyword_search(query)

    # 2. 语义搜索（智能、相关）
    semantic_results = semantic_search(query, top_k=20)

    # 3. 合并去重
    all_results = {}

    # 关键词匹配：高分优先
    for video in keyword_results:
        all_results[video.id] = {
            'video': video,
            'score': 1.0,  # 精确匹配最高分
            'match_type': 'exact',
            'icon': '🎯'
        }

    # 语义匹配：补充相关结果
    for video, similarity in semantic_results:
        if video.id not in all_results:  # 去重
            all_results[video.id] = {
                'video': video,
                'score': similarity,  # 0.0 - 1.0
                'match_type': 'semantic',
                'icon': '💡'
            }

    # 4. 按分数排序
    sorted_results = sorted(
        all_results.values(),
        key=lambda x: x['score'],
        reverse=True
    )

    return sorted_results
```

**显示逻辑**：

```python
# 在 UI 中显示结果
for result in sorted_results:
    video = result['video']
    icon = result['icon']

    st.markdown(f"{icon} **{video.title}**")

    if result['match_type'] == 'exact':
        st.caption("Found in: Title (exact match)")
    else:
        similarity_pct = int(result['score'] * 100)
        st.caption(f"Found via: semantic search ({similarity_pct}%)")
```

**优点**：
- ✅ 用户体验最佳（一个搜索框搞定一切）
- ✅ 精确匹配优先显示（满足 exact match 需求）
- ✅ 语义匹配补充（发现更多相关内容）
- ✅ 类似 Google 的搜索体验
- ✅ 用户无需理解技术细节

**缺点**：
- ⚠️ 结果数量可能变多（但这通常是好事）
- ⚠️ 需要合理的分数权重调整

---

#### 方案 B：提供切换开关

**UI**：
```
┌─────────────────────────────────────┐
│ 🔍 Search videos...                │
│                                     │
│ Search Mode:                        │
│ ⚫ Smart Search (semantic + exact)  │
│ ⚪ Exact Match Only                 │
│                                     │
│ Results...                          │
└─────────────────────────────────────┘
```

**实现**：

```python
search_mode = st.radio(
    "Search Mode",
    ["Smart Search", "Exact Match Only"],
    help="Smart Search uses AI to find related content"
)

if search_mode == "Smart Search":
    results = hybrid_search(query)
else:
    results = keyword_search(query)
```

**优点**：
- ✅ 用户有控制权
- ✅ 高级用户可以选择 exact match
- ✅ 满足不同需求

**缺点**：
- ❌ 增加 UI 复杂度
- ❌ 大多数用户不知道选哪个
- ❌ 多数人会忽略这个选项

---

#### 方案 C：自动降级

**逻辑**：

```python
def auto_search(query):
    # 先用关键词搜索
    results = keyword_search(query)

    # 如果结果太少，自动补充语义搜索
    if len(results) < 3:
        semantic_results = semantic_search(query, top_k=10)
        results += semantic_results
        st.info("💡 Added related results via semantic search")

    return results
```

**优点**：
- ✅ 优先满足精确匹配
- ✅ 找不到时自动智能搜索
- ✅ 用户体验平滑

**缺点**：
- ❌ 可能错过一些语义相关的好结果
- ❌ 用户可能不理解为什么有时有语义结果，有时没有

---

### 推荐方案 / Recommendation

✅ **方案 A：混合搜索**

**原因**：

1. **用户体验最佳**
   - 一个搜索框，简单直观
   - 获得最全面的结果
   - 类似 Google 的体验

2. **精确匹配不会丢失**
   - 关键词匹配给高分（1.0）
   - 总是排在最前面
   - 用 🎯 图标标识

3. **语义搜索作为补充**
   - 发现用户可能感兴趣的相关内容
   - 用 💡 图标和相似度百分比标识
   - 用户一眼就能区分

4. **业界标准**
   - Google、Bing、DuckDuckGo 都是这么做的
   - 用户已经习惯这种体验

---

### 实现示例 / Implementation Example

**完整的混合搜索 UI**：

```python
def view_history_with_hybrid_search():
    st.title("📜 History")

    # 搜索框
    search_query = st.text_input(
        "🔍 Search videos",
        placeholder="e.g., Python decorators, async programming, 装饰器...",
        help="Smart search: finds exact matches + related content"
    )

    if search_query:
        # 混合搜索
        results = hybrid_search(search_query)

        # 显示统计
        exact_count = len([r for r in results if r['match_type'] == 'exact'])
        semantic_count = len([r for r in results if r['match_type'] == 'semantic'])

        st.success(
            f"✅ Found {len(results)} result(s): "
            f"{exact_count} exact match(es) 🎯 + "
            f"{semantic_count} related result(s) 💡"
        )

        # 显示结果
        for result in results:
            video = result['video']
            icon = result['icon']

            with st.expander(f"{icon} {video.title}"):
                # 显示匹配类型
                if result['match_type'] == 'exact':
                    st.caption("🎯 **Exact match** - found in title/content")
                else:
                    similarity = int(result['score'] * 100)
                    st.caption(f"💡 **Related result** - {similarity}% similarity")

                # 显示内容
                st.markdown(video.tldr[:200] + "...")

                # 查看按钮
                if st.button("📄 View Full Summary", key=f"view_{video.id}"):
                    st.session_state.selected_video_id = video.id
                    st.rerun()
```

---

### 用户场景示例 / User Scenarios

#### 场景 1：搜索 "decorator"

**返回结果**：
1. 🎯 Python Decorators Explained (exact - title match)
2. 🎯 Advanced Decorator Patterns (exact - content match)
3. 💡 Function Wrappers in Python (semantic - 95%)
4. 💡 装饰器设计模式 (semantic - 92%, cross-language)
5. 💡 Metaprogramming in Python (semantic - 87%)

**用户获益**：
- 找到了所有包含 "decorator" 的视频（exact）
- 还发现了讲 wrapper、装饰器（中文）的相关视频（semantic）

#### 场景 2：搜索 "提升性能"

**返回结果**：
1. 🎯 Python 性能优化技巧 (exact)
2. 💡 Caching Strategies (semantic - 91%)
3. 💡 Async Programming for Speed (semantic - 88%)
4. 💡 Database Query Optimization (semantic - 85%)

**用户获益**：
- 虽然只有一个视频标题包含"提升性能"
- 语义搜索找到了所有相关的性能优化内容

#### 场景 3：用户想要 exact match

**用户操作**：
- 搜索 "python tutorial"
- 看到 10 个结果，前 5 个是 🎯 exact
- 后 5 个是 💡 semantic
- 用户只看前 5 个，满足需求 ✅

**无需切换开关，自然满足需求**

---

## 📊 总结对比 / Summary

### 数据库迁移

| 方面 | SQLite | PostgreSQL (bytes) | PostgreSQL (pgvector) |
|-----|--------|-------------------|---------------------|
| **代码兼容性** | - | ✅ 100% 兼容 | ⚠️ 需要改代码 |
| **迁移成本** | - | ✅ 零成本 | ⚠️ 3-4 小时 |
| **性能 (< 1000)** | ✅ 够用 | ✅ 够用 | ✅ 更快 |
| **性能 (> 1000)** | ⚠️ 较慢 | ⚠️ 较慢 | ✅ 快很多 |
| **推荐时机** | 现在 | 迁移时 | > 1000 videos |

### 搜索方案

| 方面 | 混合搜索 | 切换开关 | 自动降级 |
|-----|---------|---------|---------|
| **用户体验** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **实现复杂度** | 中 | 低 | 中 |
| **结果全面性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **满足 exact match** | ✅ | ✅ | ✅ |
| **发现相关内容** | ✅ | ⚠️ | ⚠️ |
| **推荐** | ✅ 强烈推荐 | ❌ | ⚠️ 备选 |

---

## 🎯 实施建议 / Action Plan

### 立即执行（Stage 1 - 当前）
- [x] 使用 SQLite + 关键词搜索
- [x] LargeBinary 存储设计（为未来做准备）

### 中期执行（Stage 2 - 视频 > 50）
- [ ] 实现语义搜索（sentence-transformers）
- [ ] 使用混合搜索（关键词 + 语义）
- [ ] embedding 存为 numpy bytes（SQLite/PostgreSQL 通用）

### 长期执行（Stage 3 - 视频 > 1000）
- [ ] 迁移到 PostgreSQL（如果需要）
- [ ] 评估是否需要 pgvector 优化
- [ ] 如果搜索慢，再迁移到 pgvector

---

**Made with ❤️ for efficient learning**
