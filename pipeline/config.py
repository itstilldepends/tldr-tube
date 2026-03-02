"""
Configuration constants for tldr-tube.

Model options and their characteristics.
"""

# Whisper ASR models (mlx-whisper optimized for Apple Silicon)
WHISPER_MODELS = {
    "tiny": {
        "name": "mlx-community/whisper-tiny-mlx",
        "size": "39MB",
        "speed": "⚡⚡⚡ Very Fast",
        "accuracy": "⭐⭐ Low"
    },
    "base": {
        "name": "mlx-community/whisper-base-mlx",
        "size": "140MB",
        "speed": "⚡⚡ Fast",
        "accuracy": "⭐⭐⭐ Good"
    },
    "small": {
        "name": "mlx-community/whisper-small-mlx",
        "size": "244MB",
        "speed": "⚡ Medium",
        "accuracy": "⭐⭐⭐⭐ Better"
    },
    "medium": {
        "name": "mlx-community/whisper-medium-mlx",
        "size": "769MB",
        "speed": "🐢 Slow",
        "accuracy": "⭐⭐⭐⭐⭐ Best"
    },
    "large": {
        "name": "mlx-community/whisper-large-v3-mlx",
        "size": "1.5GB",
        "speed": "🐢🐢 Very Slow",
        "accuracy": "⭐⭐⭐⭐⭐⭐ Excellent"
    }
}

# Claude models (Anthropic API)
CLAUDE_MODELS = {
    "haiku": {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude 4.5 Haiku",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐ Good",
        "cost": "💰 Cheap (~$0.01/video)",
        "description": "Fastest, cheapest. Good for simple content."
    },
    "sonnet": {
        "id": "claude-sonnet-4-5-20250929",
        "name": "Claude 4.5 Sonnet",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "💰💰 Moderate (~$0.05/video)",
        "description": "Best balance. Recommended for most use cases."
    },
    "opus": {
        "id": "claude-opus-4-6",
        "name": "Claude 4.6 Opus",
        "speed": "⚡ Slower",
        "quality": "⭐⭐⭐⭐⭐⭐ Best",
        "cost": "💰💰💰 Expensive (~$0.15/video)",
        "description": "Highest quality. Use for complex/important content."
    }
}

# Gemini models (Google API)
GEMINI_MODELS = {
    "flash": {
        "id": "gemini-1.5-flash",
        "name": "Gemini 1.5 Flash",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐⭐ Good",
        "cost": "💰 Ultra Cheap (~$0.005/video)",
        "description": "Fastest, cheapest. Great for most content. 95% cheaper than Claude!"
    },
    "flash-2": {
        "id": "gemini-2.0-flash-exp",
        "name": "Gemini 2.0 Flash (Experimental)",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐⭐ Good",
        "cost": "💰 Very Cheap (~$0.01/video)",
        "description": "Latest experimental model. Fast and affordable."
    },
    "pro": {
        "id": "gemini-1.5-pro",
        "name": "Gemini 1.5 Pro",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "💰 Cheap (~$0.03/video)",
        "description": "Best quality. Still 50% cheaper than Claude Sonnet."
    }
}

# OpenAI models
OPENAI_MODELS = {
    "mini": {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐⭐ Good",
        "cost": "💰 Very Cheap (~$0.01/video)",
        "description": "Fast and affordable. Good for most content."
    },
    "standard": {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "💰💰 Moderate (~$0.06/video)",
        "description": "Balanced quality and cost. Reliable for complex content."
    },
    "reasoning": {
        "id": "o1",
        "name": "o1",
        "speed": "⚡ Slower",
        "quality": "⭐⭐⭐⭐⭐⭐ Best",
        "cost": "💰💰💰 Expensive (~$0.25/video)",
        "description": "Advanced reasoning model. Best for complex analysis."
    }
}

# DeepSeek models (OpenAI-compatible)
DEEPSEEK_MODELS = {
    "chat": {
        "id": "deepseek-chat",
        "name": "DeepSeek Chat",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "💰 Cheapest! (~$0.003/video)",
        "description": "General chat model. 95% cheaper than Claude! 50% cheaper than Gemini!"
    },
    "reasoner": {
        "id": "deepseek-reasoner",
        "name": "DeepSeek Reasoner",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐⭐⭐ Best",
        "cost": "💰 Ultra Cheap (~$0.005/video)",
        "description": "Advanced reasoning mode. Still 90% cheaper than competitors!"
    }
}

# Qwen models (Alibaba Cloud - OpenAI-compatible)
QWEN_MODELS = {
    "turbo": {
        "id": "qwen-turbo",
        "name": "Qwen Turbo",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐⭐ Good",
        "cost": "💰 Cheap (~$0.02/video)",
        "description": "Fast and affordable. Good for most content."
    },
    "plus": {
        "id": "qwen-plus",
        "name": "Qwen Plus",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "💰 Cheap (~$0.05/video)",
        "description": "Balanced model. Excellent Chinese understanding."
    },
    "max": {
        "id": "qwen-max",
        "name": "Qwen Max",
        "speed": "⚡ Medium",
        "quality": "⭐⭐⭐⭐⭐⭐ Best",
        "cost": "💰💰 Moderate (~$0.12/video)",
        "description": "Best quality. Top-tier Chinese language processing."
    }
}

# Ollama models (local, free — user must have them pulled via `ollama pull <model>`)
OLLAMA_MODELS = {
    "qwen2.5:7b": {
        "id": "qwen2.5:7b",
        "name": "Qwen 2.5 7B",
        "speed": "⚡⚡ Fast",
        "quality": "⭐⭐⭐⭐ Good",
        "cost": "🆓 Free (local, ~4GB RAM)",
        "description": "Best balance for local use. Strong Chinese support."
    },
    "qwen2.5:3b": {
        "id": "qwen2.5:3b",
        "name": "Qwen 2.5 3B",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐ Decent",
        "cost": "🆓 Free (local, ~2GB RAM)",
        "description": "Lightest Qwen option. Good for shorter videos."
    },
    "qwen2.5:14b": {
        "id": "qwen2.5:14b",
        "name": "Qwen 2.5 14B",
        "speed": "⚡ Slower",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "🆓 Free (local, ~8GB RAM)",
        "description": "Best quality local Qwen. Requires more RAM."
    },
    "llama3.2:3b": {
        "id": "llama3.2:3b",
        "name": "Llama 3.2 3B",
        "speed": "⚡⚡⚡ Very Fast",
        "quality": "⭐⭐⭐ Decent",
        "cost": "🆓 Free (local, ~2GB RAM)",
        "description": "Fast and lightweight. Better for English content."
    },
    "phi4": {
        "id": "phi4",
        "name": "Phi 4 14B",
        "speed": "⚡ Slower",
        "quality": "⭐⭐⭐⭐⭐ Excellent",
        "cost": "🆓 Free (local, ~8GB RAM)",
        "description": "Microsoft's compact but capable model."
    },
}

# Unified LLM provider configuration (sorted by recommendation: quality first, then price)
LLM_PROVIDERS = {
    "claude": {
        "name": "Anthropic Claude",
        "models": CLAUDE_MODELS,
        "default_model": "sonnet",
        "api_key_env": "ANTHROPIC_API_KEY"
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": DEEPSEEK_MODELS,
        "default_model": "chat",
        "api_key_env": "DEEPSEEK_API_KEY"
    },
    "gemini": {
        "name": "Google Gemini",
        "models": GEMINI_MODELS,
        "default_model": "flash",
        "api_key_env": "GOOGLE_API_KEY"
    },
    "openai": {
        "name": "OpenAI",
        "models": OPENAI_MODELS,
        "default_model": "mini",
        "api_key_env": "OPENAI_API_KEY"
    },
    "qwen": {
        "name": "Qwen (Alibaba)",
        "models": QWEN_MODELS,
        "default_model": "plus",
        "api_key_env": "DASHSCOPE_API_KEY"
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": OLLAMA_MODELS,
        "default_model": "qwen2.5:7b",
        "api_key_env": None,
        "setup_hint": "Ollama not running. Start it with: ollama serve  (install: brew install ollama)"
    }
}

# Default choices
DEFAULT_WHISPER_MODEL = "medium"
DEFAULT_CLAUDE_MODEL = "sonnet"
DEFAULT_LLM_PROVIDER = "claude"  # Default to Claude Sonnet (best quality and reliability)
DEFAULT_GEMINI_MODEL = "flash"


def get_claude_model_id(model_name: str) -> str:
    """
    Get Claude model ID from model name.

    Args:
        model_name: Model name ("haiku", "sonnet", "opus")

    Returns:
        Model ID string for Anthropic API

    Raises:
        ValueError: If model_name is invalid
    """
    model_name_lower = model_name.lower()
    if model_name_lower not in CLAUDE_MODELS:
        raise ValueError(f"Invalid model name: {model_name}. Must be one of: {list(CLAUDE_MODELS.keys())}")

    return CLAUDE_MODELS[model_name_lower]["id"]


def get_model_id(provider: str, model_name: str) -> str:
    """
    Get model ID for any provider.

    Args:
        provider: Provider name ("claude", "gemini")
        model_name: Model name (e.g., "sonnet", "flash")

    Returns:
        Model ID string for the API

    Raises:
        ValueError: If provider or model_name is invalid
    """
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"Invalid provider: {provider}. Must be one of: {list(LLM_PROVIDERS.keys())}")

    models = LLM_PROVIDERS[provider]["models"]
    if model_name not in models:
        raise ValueError(f"Invalid model for {provider}: {model_name}. Must be one of: {list(models.keys())}")

    return models[model_name]["id"]


def _check_ollama_running() -> bool:
    """Check if Ollama server is reachable at localhost:11434."""
    import urllib.request
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        urllib.request.urlopen(base_url, timeout=1)
        return True
    except Exception:
        return False


def check_api_key_configured(provider: str) -> bool:
    """
    Check if a provider is ready to use.

    For API providers: checks that the API key env var is set.
    For Ollama: checks that the local server is reachable.

    Args:
        provider: Provider name (e.g., "claude", "gemini", "ollama")

    Returns:
        True if provider is ready, False otherwise
    """
    if provider not in LLM_PROVIDERS:
        return False

    if provider == "ollama":
        return _check_ollama_running()

    api_key_env = LLM_PROVIDERS[provider]["api_key_env"]
    api_key = os.getenv(api_key_env)
    return api_key is not None and api_key.strip() != ""


def get_available_providers() -> dict:
    """
    Get all providers with their availability status.

    Returns:
        Dictionary with provider names as keys and availability status as values
        Format: {provider: {"available": bool, "api_key_env": str, "name": str}}
    """
    result = {}
    for provider, config in LLM_PROVIDERS.items():
        result[provider] = {
            "available": check_api_key_configured(provider),
            "api_key_env": config["api_key_env"],
            "setup_hint": config.get("setup_hint"),
            "name": config["name"]
        }
    return result
