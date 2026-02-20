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

# Default choices
DEFAULT_WHISPER_MODEL = "medium"
DEFAULT_CLAUDE_MODEL = "sonnet"
