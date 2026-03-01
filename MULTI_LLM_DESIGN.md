# Multi-LLM Provider Support Design

**Goal**: Support multiple LLM API providers beyond Claude (OpenAI, Gemini, Qwen)

**Status**: Design phase

---

## Current State

**Only supports**: Claude API (Anthropic)

**Usage locations**:
1. `pipeline/summarize.py` - Video summarization (TL;DR + segments)
2. `pipeline/rag.py` - RAG answer generation

---

## Proposed Architecture

### 1. Unified LLM Client Interface

Create `pipeline/llm_client.py` with a unified interface:

```python
class LLMClient:
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Unified interface for all LLM providers"""
        pass

class ClaudeLLMClient(LLMClient):
    """Claude API (Anthropic)"""

class OpenAILLMClient(LLMClient):
    """OpenAI API (GPT-4, GPT-4o, etc.)"""

class GeminiLLMClient(LLMClient):
    """Google Gemini API"""

class QwenLLMClient(LLMClient):
    """Alibaba Qwen API (if accessible)"""
```

---

## Supported Providers

### 1. Claude (Anthropic) ✅ Current

**Models**:
- `claude-haiku-4-5-20251001` - Fast & Cheap
- `claude-sonnet-4-5-20250929` - Balanced (recommended)
- `claude-opus-4-6` - Best quality

**API Key**: `ANTHROPIC_API_KEY`

**Pros**:
- ✅ Excellent at following instructions
- ✅ Great for structured output (JSON)
- ✅ Strong bilingual support (EN/ZH)

**Cost** (per 1M tokens):
- Haiku: Input $0.80 / Output $4.00
- Sonnet: Input $3.00 / Output $15.00
- Opus: Input $15.00 / Output $75.00

---

### 2. OpenAI 🆕

**Models**:
- `gpt-4o-mini` - Fast & Cheap (Haiku equivalent)
- `gpt-4o` - Balanced (Sonnet equivalent)
- `o1` - Reasoning (Opus equivalent)

**API Key**: `OPENAI_API_KEY`

**Pros**:
- ✅ Wide adoption, stable API
- ✅ Good multilingual support
- ✅ Fast inference

**Cost** (per 1M tokens):
- GPT-4o-mini: Input $0.15 / Output $0.60
- GPT-4o: Input $2.50 / Output $10.00
- o1: Input $15.00 / Output $60.00

**Cheaper than Claude!** 💰

---

### 3. Google Gemini 🆕

**Models**:
- `gemini-1.5-flash` - Fast & Cheap
- `gemini-1.5-pro` - Balanced
- `gemini-2.0-flash` - Latest (Dec 2024)

**API Key**: `GOOGLE_API_KEY`

**Pros**:
- ✅ Very cheap
- ✅ Large context window (1M+ tokens)
- ✅ Good multilingual support
- ✅ Free tier available

**Cost** (per 1M tokens):
- Flash: Input $0.075 / Output $0.30
- Pro: Input $1.25 / Output $5.00

**Cheapest option!** 💰💰💰

---

### 4. Qwen (Alibaba) 🆕

**Models**:
- `qwen-turbo` - Fast
- `qwen-plus` - Balanced
- `qwen-max` - Best quality

**API Key**: `DASHSCOPE_API_KEY` (Alibaba Cloud)

**Pros**:
- ✅ Excellent Chinese support (trained on Chinese data)
- ✅ Competitive pricing
- ✅ Good for Chinese users (no VPN needed)

**Cons**:
- ⚠️ Requires Alibaba Cloud account
- ⚠️ May have content restrictions

**Cost** (per 1M tokens):
- Turbo: ~$0.40 / $1.20
- Plus: ~$2.00 / $6.00
- Max: ~$10.00 / $30.00

**When to use**: If targeting Chinese users or need best Chinese performance

---

## Implementation Plan

### Phase 1: Create Unified Interface ✅

**File**: `pipeline/llm_client.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
import os

class LLMClient(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> str:
        """Generate text from prompt"""
        pass

class ClaudeLLMClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    def generate(self, prompt, max_tokens=2000, temperature=0.7, model="claude-sonnet-4-5-20250929"):
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt, max_tokens=2000, temperature=0.7, model="gpt-4o"):
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

class GeminiLLMClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None):
        import google.generativeai as genai
        genai.configure(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        self.client = genai

    def generate(self, prompt, max_tokens=2000, temperature=0.7, model="gemini-1.5-pro"):
        model_obj = self.client.GenerativeModel(model)
        response = model_obj.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return response.text

class QwenLLMClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None):
        import dashscope
        dashscope.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.dashscope = dashscope

    def generate(self, prompt, max_tokens=2000, temperature=0.7, model="qwen-plus"):
        response = self.dashscope.Generation.call(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.output.text

# Factory function
def get_llm_client(provider: str, api_key: Optional[str] = None) -> LLMClient:
    """Get LLM client by provider name"""
    providers = {
        "claude": ClaudeLLMClient,
        "openai": OpenAILLMClient,
        "gemini": GeminiLLMClient,
        "qwen": QwenLLMClient
    }

    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(providers.keys())}")

    return providers[provider](api_key)
```

---

### Phase 2: Update Config

**File**: `pipeline/config.py`

```python
# LLM Providers
LLM_PROVIDERS = {
    "claude": {
        "name": "Anthropic Claude",
        "models": {
            "haiku": {
                "id": "claude-haiku-4-5-20251001",
                "name": "Claude 4.5 Haiku",
                "cost": "💰 $0.03/video",
            },
            "sonnet": {
                "id": "claude-sonnet-4-5-20250929",
                "name": "Claude 4.5 Sonnet",
                "cost": "💰💰 $0.10/video",
            },
            "opus": {
                "id": "claude-opus-4-6",
                "name": "Claude 4.6 Opus",
                "cost": "💰💰💰 $0.30/video",
            }
        },
        "api_key_env": "ANTHROPIC_API_KEY"
    },
    "openai": {
        "name": "OpenAI",
        "models": {
            "mini": {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "cost": "💰 $0.01/video (Cheapest!)",
            },
            "standard": {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "cost": "💰 $0.06/video",
            },
            "reasoning": {
                "id": "o1",
                "name": "o1",
                "cost": "💰💰💰 $0.25/video",
            }
        },
        "api_key_env": "OPENAI_API_KEY"
    },
    "gemini": {
        "name": "Google Gemini",
        "models": {
            "flash": {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash",
                "cost": "💰 $0.005/video (Ultra cheap!)",
            },
            "pro": {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "cost": "💰 $0.03/video",
            },
            "flash2": {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "cost": "💰 $0.01/video",
            }
        },
        "api_key_env": "GOOGLE_API_KEY"
    },
    "qwen": {
        "name": "Alibaba Qwen",
        "models": {
            "turbo": {
                "id": "qwen-turbo",
                "name": "Qwen Turbo",
                "cost": "💰 $0.02/video",
            },
            "plus": {
                "id": "qwen-plus",
                "name": "Qwen Plus",
                "cost": "💰💰 $0.08/video",
            },
            "max": {
                "id": "qwen-max",
                "name": "Qwen Max",
                "cost": "💰💰 $0.15/video",
            }
        },
        "api_key_env": "DASHSCOPE_API_KEY"
    }
}
```

---

### Phase 3: Update UI

**File**: `app.py` - Add provider selection

```python
# In view_new_video() and view_ask_ai()

col1, col2, col3 = st.columns(3)

with col1:
    selected_provider = st.selectbox(
        "LLM Provider",
        options=list(LLM_PROVIDERS.keys()),
        format_func=lambda x: LLM_PROVIDERS[x]["name"],
        index=0  # Default to Claude
    )

with col2:
    available_models = LLM_PROVIDERS[selected_provider]["models"]
    selected_model = st.selectbox(
        "Model",
        options=list(available_models.keys())
    )

with col3:
    model_info = available_models[selected_model]
    st.caption(f"{model_info['cost']}")
```

---

### Phase 4: Update Pipeline

**File**: `pipeline/summarize.py`

```python
# Replace direct Anthropic calls with unified client

from pipeline.llm_client import get_llm_client

def summarize_transcript(transcript, video_id, provider="claude", model="sonnet"):
    # Get LLM client
    llm = get_llm_client(provider)
    model_id = LLM_PROVIDERS[provider]["models"][model]["id"]

    # Generate summary
    prompt = SUMMARIZATION_PROMPT.format(transcript=formatted_transcript)
    response_text = llm.generate(
        prompt=prompt,
        max_tokens=4096,
        temperature=0.7,
        model=model_id
    )

    # Parse JSON response (same for all providers)
    result = json.loads(response_text)
    return result
```

**File**: `pipeline/rag.py` - Same pattern

---

## Dependencies to Add

```bash
# requirements.txt
openai>=1.0.0              # For OpenAI
google-generativeai>=0.3.0 # For Gemini
dashscope>=1.14.0          # For Qwen (optional)
```

---

## Environment Variables

**`.env` file**:

```bash
# Choose one or more providers

# Claude (current)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (new)
OPENAI_API_KEY=sk-proj-...

# Gemini (new)
GOOGLE_API_KEY=AIza...

# Qwen (optional, for Chinese users)
DASHSCOPE_API_KEY=sk-...
```

---

## Cost Comparison (Per Video)

Assuming 1 video = ~10K input tokens + 500 output tokens:

| Provider | Model | Cost/Video | Notes |
|----------|-------|------------|-------|
| **Gemini** | Flash | **$0.005** | 🏆 Cheapest |
| OpenAI | GPT-4o-mini | $0.01 | Very cheap |
| Gemini | Flash 2.0 | $0.01 | Latest |
| Qwen | Turbo | $0.02 | Good for Chinese |
| Gemini | Pro | $0.03 | Balanced |
| Claude | Haiku | $0.03 | Fast |
| OpenAI | GPT-4o | $0.06 | Balanced |
| Qwen | Plus | $0.08 | Better Chinese |
| Claude | Sonnet | $0.10 | Current default |
| Qwen | Max | $0.15 | Best Chinese |
| OpenAI | o1 | $0.25 | Reasoning |
| Claude | Opus | $0.30 | Best quality |

**Savings potential**: Switching to Gemini Flash = **95% cost reduction!**

---

## Recommendation

### For English content:
1. **Gemini Flash** - Ultra cheap, good quality
2. **OpenAI GPT-4o-mini** - Very cheap, reliable
3. **Claude Sonnet** - Best quality (current)

### For Chinese content:
1. **Qwen Plus** - Best Chinese understanding
2. **Gemini Pro** - Good multilingual
3. **Claude Sonnet** - Good bilingual

### For most users:
**Start with Gemini Flash** → If quality not enough → **GPT-4o** → If still not enough → **Claude Sonnet**

---

## Implementation Timeline

- **Phase 1**: Unified interface (2-3 hours)
- **Phase 2**: Config updates (1 hour)
- **Phase 3**: UI updates (1 hour)
- **Phase 4**: Pipeline integration (2 hours)
- **Testing**: (2 hours)

**Total**: ~8-9 hours

---

## Testing Strategy

1. Process same video with different providers
2. Compare output quality
3. Verify bilingual support
4. Test RAG with different providers
5. Measure actual costs

---

**Ready to implement?** Let me know if you want to:
1. Implement all providers at once
2. Start with one (e.g., OpenAI or Gemini)
3. Adjust the design first
