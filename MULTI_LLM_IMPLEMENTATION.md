# Multi-LLM Provider Implementation

**实施日期**: 2026-02-22
**状态**: ✅ 已完成

---

## 📊 已实现的提供商

| Provider | Status | API 兼容性 | 默认模型 | 成本/视频 |
|----------|--------|-----------|---------|----------|
| **DeepSeek** | ✅ 已实现 | OpenAI 兼容 | deepseek-chat | ~$0.003 |
| **Gemini** | ✅ 已实现 | 原生 SDK | flash | ~$0.005 |
| **OpenAI** | ✅ 已实现 | 原生 SDK | mini | ~$0.01 |
| **Qwen** | ✅ 已实现 | OpenAI 兼容 | plus | ~$0.05 |
| **Claude** | ✅ 已实现 | 原生 SDK | sonnet | ~$0.10 |

---

## 🚀 实现细节

### 1. DeepSeek (最推荐)

**官方文档**: [DeepSeek API Docs](https://api-docs.deepseek.com/)

**实现方式**: OpenAI SDK + 自定义 base_url
```python
from openai import OpenAI
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)
```

**可用模型**:
- `deepseek-chat` - 通用对话模型 (推荐)
- `deepseek-reasoner` - 高级推理模型

**优势**:
- ✅ 价格最低 (~$0.28/M input, $0.42/M output)
- ✅ 质量接近 GPT-4
- ✅ OpenAI 完全兼容
- ✅ 支持 context caching (90% 节省)
- 🎁 新用户送 500万 tokens

**API Key 环境变量**: `DEEPSEEK_API_KEY`

---

### 2. Qwen (通义千问)

**官方文档**: [Qwen API Reference](https://www.alibabacloud.com/help/en/model-studio/qwen-api-reference/)

**实现方式**: OpenAI SDK + 自定义 base_url (Alibaba Cloud DashScope)
```python
from openai import OpenAI
client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
```

**可用模型**:
- `qwen-turbo` - 快速模型
- `qwen-plus` - 平衡模型 (推荐)
- `qwen-max` - 最高质量

**优势**:
- ✅ 中文理解能力最强
- ✅ OpenAI 完全兼容
- ✅ 阿里云官方支持
- ✅ 适合中文内容

**API Key 环境变量**: `DASHSCOPE_API_KEY`

---

### 3. Gemini

**官方文档**: [Gemini API Docs](https://ai.google.dev/docs)

**实现方式**: Google GenerativeAI SDK
```python
import google.generativeai as genai
genai.configure(api_key=GOOGLE_API_KEY)
```

**可用模型**:
- `gemini-1.5-flash` - 快速模型 (推荐)
- `gemini-2.0-flash-exp` - 实验性模型
- `gemini-1.5-pro` - 高质量模型

**优势**:
- ✅ 价格非常低
- ✅ 大上下文窗口 (1M+ tokens)
- ✅ 免费额度

**API Key 环境变量**: `GOOGLE_API_KEY`

---

### 4. OpenAI

**官方文档**: [OpenAI API Reference](https://platform.openai.com/docs/api-reference)

**实现方式**: OpenAI SDK
```python
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)
```

**可用模型**:
- `gpt-4o-mini` - 快速模型 (推荐)
- `gpt-4o` - 标准模型
- `o1` - 推理模型

**优势**:
- ✅ 稳定可靠
- ✅ 广泛采用
- ✅ 良好的多语言支持

**API Key 环境变量**: `OPENAI_API_KEY`

---

### 5. Claude

**官方文档**: [Claude API Docs](https://docs.anthropic.com/)

**实现方式**: Anthropic SDK
```python
from anthropic import Anthropic
client = Anthropic(api_key=ANTHROPIC_API_KEY)
```

**可用模型**:
- `claude-haiku-4-5-20251001` - 快速模型
- `claude-sonnet-4-5-20250929` - 平衡模型 (推荐)
- `claude-opus-4-6` - 最高质量

**优势**:
- ✅ 最高质量输出
- ✅ 优秀的指令遵循
- ✅ 强大的双语支持

**API Key 环境变量**: `ANTHROPIC_API_KEY`

---

## 📝 配置说明

### 1. 安装依赖

已在 `requirements.txt` 中包含所有必要的包：

```bash
pip install -r requirements.txt
```

包含的包：
- `openai>=1.0.0` - 用于 OpenAI、DeepSeek、Qwen
- `google-generativeai>=0.3.0` - 用于 Gemini
- `anthropic>=0.18.0` - 用于 Claude

---

### 2. 配置 API Keys

在 `.env` 文件中添加你需要的 API keys（选择一个或多个）：

```bash
# 推荐：DeepSeek (最便宜)
DEEPSEEK_API_KEY=sk-...

# 或者：Gemini (次便宜)
GOOGLE_API_KEY=AIza...

# 或者：OpenAI (可靠)
OPENAI_API_KEY=sk-proj-...

# 或者：Qwen (最佳中文)
DASHSCOPE_API_KEY=sk-...

# 或者：Claude (最高质量)
ANTHROPIC_API_KEY=sk-ant-...
```

参考 `.env.example` 获取详细说明。

---

### 3. 获取 API Keys

| Provider | 注册链接 |
|----------|---------|
| DeepSeek | https://platform.deepseek.com/ |
| Gemini | https://aistudio.google.com/apikey |
| OpenAI | https://platform.openai.com/api-keys |
| Qwen | https://dashscope.console.aliyun.com/ |
| Claude | https://console.anthropic.com/ |

---

## 🎯 使用建议

### 根据需求选择提供商

#### 1. **成本优先** → DeepSeek
- 价格：~$0.003/video
- 质量：优秀 (接近 GPT-4)
- 适合：日常使用、大批量处理

#### 2. **中文内容** → Qwen
- 价格：~$0.05/video
- 质量：中文最佳
- 适合：中文视频、中文课程

#### 3. **稳定可靠** → OpenAI
- 价格：~$0.01/video (mini)
- 质量：稳定
- 适合：生产环境

#### 4. **最高质量** → Claude
- 价格：~$0.10/video (sonnet)
- 质量：最佳
- 适合：重要内容、复杂分析

---

## 💰 成本对比

假设处理 1 小时视频（~10K input tokens + 500 output tokens）：

| Rank | Provider | Model | Cost/Video | vs DeepSeek | 备注 |
|------|----------|-------|-----------|-------------|------|
| 🥇 | DeepSeek | chat | $0.003 | - | **最便宜** |
| 🥈 | Gemini | flash | $0.005 | +67% | 次便宜 |
| 🥉 | OpenAI | mini | $0.01 | +233% | 性价比高 |
| 4 | Qwen | plus | $0.05 | +1567% | 中文最佳 |
| 5 | Claude | sonnet | $0.10 | +3233% | 质量最高 |

**结论**: DeepSeek 比 Claude 便宜 **97%**！

---

## 🧪 测试建议

### 测试步骤

1. **处理同一视频**
   - 用不同 provider 处理同一个视频
   - 对比输出质量

2. **测试中文内容**
   - 用 Qwen 处理中文视频
   - 对比其他 provider 的中文理解

3. **测试 Ask AI**
   - 用不同 provider 回答问题
   - 对比答案准确性和连贯性

---

## 📚 技术实现

### 文件修改列表

1. ✅ `pipeline/llm_client.py`
   - 添加 `DeepSeekLLMClient`
   - 添加 `QwenLLMClient`
   - 更新 `get_llm_client()` 函数

2. ✅ `pipeline/config.py`
   - 添加 `DEEPSEEK_MODELS`
   - 添加 `QWEN_MODELS`
   - 更新 `LLM_PROVIDERS`
   - 修改默认 provider 为 `deepseek`

3. ✅ `pipeline/processor.py`
   - 支持 `provider` 和 `model` 参数
   - 保留向后兼容性

4. ✅ `pipeline/summarize.py`
   - 支持 `provider` 和 `model` 参数

5. ✅ `pipeline/rag.py`
   - 支持 `provider` 和 `model` 参数

6. ✅ `app.py`
   - 在 "New Video" 页面添加 provider 选择
   - 在 "Ask AI" 页面添加 provider 选择
   - 更新 UI 显示

7. ✅ `requirements.txt`
   - 无需修改（已包含 `openai` 包）

8. ✅ `.env.example`
   - 添加所有新的 API key 说明

---

## 🐛 故障排除

### 问题 1: DeepSeek API Key 无效

**症状**: `ValueError: DEEPSEEK_API_KEY not found`

**解决**:
```bash
# 在 .env 文件中添加
DEEPSEEK_API_KEY=sk-...
```

---

### 问题 2: Qwen API 调用失败

**症状**: Connection error or authentication failed

**解决**:
1. 确认使用的是 DashScope API key (不是 Qwen.ai 的 key)
2. 检查 base_url 是否正确：`https://dashscope.aliyuncs.com/compatible-mode/v1`
3. 确认模型名称使用 `qwen-plus` 而不是 `qwen-plus-latest`

---

### 问题 3: OpenAI 包版本冲突

**症状**: `ImportError: cannot import name 'OpenAI'`

**解决**:
```bash
pip install --upgrade openai>=1.0.0
```

---

## ✨ 未来改进

- [ ] 添加更多 provider (Cohere, Mistral, etc.)
- [ ] 支持自定义 base_url
- [ ] 添加 provider 性能监控
- [ ] 实现智能 provider 选择（根据内容语言）
- [ ] 添加成本追踪和统计

---

## 📖 参考资料

- [DeepSeek API Docs](https://api-docs.deepseek.com/)
- [Qwen OpenAI Compatibility](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope)
- [Gemini API Docs](https://ai.google.dev/docs)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Claude API Docs](https://docs.anthropic.com/)

---

**实施完成！** 🎉

现在支持 5 个 LLM 提供商，用户可以根据需求自由选择！
