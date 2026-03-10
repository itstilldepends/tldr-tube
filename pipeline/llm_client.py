"""
Unified LLM client interface supporting multiple providers.

Currently supported:
- Claude (Anthropic)
- Gemini (Google)
"""

from abc import ABC, abstractmethod
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            model: Model ID to use (provider-specific)

        Returns:
            Generated text
        """
        pass

    def generate_with_images(
        self,
        text: str,
        image_paths: list[str],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> str:
        """
        Generate text from a prompt that includes images.

        Args:
            text: The text prompt
            image_paths: List of local image file paths to include
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            model: Model ID to use (provider-specific)

        Returns:
            Generated text

        Raises:
            NotImplementedError: If provider doesn't support multimodal
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support multimodal generation")


class ClaudeLLMClient(LLMClient):
    """Anthropic Claude API client."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        logger.info("Claude client initialized")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "claude-sonnet-4-5-20250929"
    ) -> str:
        """Generate text using Claude API."""
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_with_images(
        self,
        text: str,
        image_paths: list[str],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: str = "claude-sonnet-4-5-20250929"
    ) -> str:
        """Generate text using Claude API with image inputs."""
        import base64

        content = []
        for path in image_paths:
            with open(path, "rb") as f:
                img_data = base64.standard_b64encode(f.read()).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_data,
                }
            })
        content.append({"type": "text", "text": text})

        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": content}]
        )
        return response.content[0].text


class GeminiLLMClient(LLMClient):
    """Google Gemini API client."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        genai.configure(api_key=api_key)
        self.genai = genai
        logger.info("Gemini client initialized")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "gemini-1.5-flash"
    ) -> str:
        """Generate text using Gemini API."""
        model_obj = self.genai.GenerativeModel(model)

        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        response = model_obj.generate_content(
            prompt,
            generation_config=generation_config
        )

        # Gemini may block responses due to safety settings
        if not response.text:
            if response.prompt_feedback:
                raise ValueError(f"Gemini blocked prompt: {response.prompt_feedback}")
            raise ValueError("Gemini returned empty response")

        return response.text


class OpenAILLMClient(LLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Run: pip install openai"
            )

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "gpt-4o"
    ) -> str:
        """Generate text using OpenAI API."""
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class DeepSeekLLMClient(LLMClient):
    """DeepSeek API client (OpenAI-compatible)."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Run: pip install openai"
            )

        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")

        # DeepSeek uses OpenAI-compatible API with custom base_url
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        logger.info("DeepSeek client initialized")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "deepseek-chat"
    ) -> str:
        """Generate text using DeepSeek API."""
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class QwenLLMClient(LLMClient):
    """Qwen API client (OpenAI-compatible via Alibaba Cloud DashScope)."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Qwen client.

        Args:
            api_key: DashScope API key (defaults to DASHSCOPE_API_KEY env var)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Run: pip install openai"
            )

        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not found in environment variables")

        # Qwen uses OpenAI-compatible API via DashScope
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        logger.info("Qwen client initialized")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "qwen-plus"
    ) -> str:
        """Generate text using Qwen API."""
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class OllamaLLMClient(LLMClient):
    """Local Ollama client via OpenAI-compatible API (http://localhost:11434/v1)."""

    def __init__(self, **kwargs):
        """
        Initialize Ollama client.

        Reads OLLAMA_BASE_URL from environment (default: http://localhost:11434/v1).
        No API key required — Ollama runs locally.
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        logger.info(f"Ollama client initialized at {base_url}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: str = "qwen2.5:7b"
    ) -> str:
        """Generate text using local Ollama model."""
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


def get_llm_client(provider: str, api_key: Optional[str] = None) -> LLMClient:
    """
    Get LLM client by provider name.

    Args:
        provider: Provider name ("claude", "gemini", "openai", "deepseek", "qwen")
        api_key: Optional API key (defaults to env var)

    Returns:
        LLMClient instance

    Raises:
        ValueError: If provider is unknown
    """
    providers = {
        "claude": ClaudeLLMClient,
        "gemini": GeminiLLMClient,
        "openai": OpenAILLMClient,
        "deepseek": DeepSeekLLMClient,
        "qwen": QwenLLMClient,
        "ollama": OllamaLLMClient,
    }

    if provider.lower() not in providers:
        available = ", ".join(providers.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")

    return providers[provider.lower()](api_key)
