"""backend/model_router/base_client.py - Abstract uniform interface for all LLM clients.

Provides:
- BaseLLMClient abstract class
- Token and pricing calculation utilities
- Model response normalization
"""

from __future__ import annotations

import abc
import os
import time
from typing import Any, Dict, Iterator, Optional

from backend.model_router.exceptions import (
    AuthenticationError,
    ContextLengthExceededError,
    ContextWindowExceededError,
    InvalidRequestError,
    ModelRouterError,
    ProviderUnavailableError,
    RateLimitError,
)
from backend.model_router.schemas import ModelConfig, ModelResponse, TokenUsage

# ---------------------------------------------------------------------------
# Pricing Table per 1M tokens (USD)
# ---------------------------------------------------------------------------
MODEL_PRICING: Dict[str, tuple[float, float]] = {
    # Free tiers
    "llama3.2": (0.0, 0.0),
    "llama3.2:1b": (0.0, 0.0),
    "llama3.2:3b": (0.0, 0.0),
    "llama-3.1-70b-versatile": (0.0, 0.0),
    "llama-3.1-8b-instant": (0.0, 0.0),
    "gemini-1.5-flash": (0.0, 0.0),
    "gemini-1.5-pro": (0.0, 0.0),
    # Paid tiers
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def estimate_tokens(text: str) -> int:
    """Heuristic token estimator: approx 1 token per 4 characters or 0.75 words."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(1, int((words * 1.33 + chars / 4.0) / 2.0))


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculates USD cost from prompt and completion token counts."""
    pricing = None
    lower_model = model.lower()
    for k, v in MODEL_PRICING.items():
        if k in lower_model:
            pricing = v
            break

    if not pricing:
        return 0.0

    in_cost = (prompt_tokens / 1_000_000.0) * pricing[0]
    out_cost = (completion_tokens / 1_000_000.0) * pricing[1]
    return round(in_cost + out_cost, 6)


class BaseLLMClient(abc.ABC):
    """Uniform client abstraction across Ollama, Groq, Gemini, Claude, and OpenAI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 30.0,
        mock_mode: Optional[bool] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self._default_model = default_model
        self.timeout = timeout

        # Resolve mock mode: explicit flag > ALPHA_MOCK_LLM > ALPHA_ENV=test
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            mock_env = os.getenv("ALPHA_MOCK_LLM", "").strip().lower() in ("1", "true", "yes")
            test_env = os.getenv("ALPHA_ENV", "").strip().lower() == "test"
            self.mock_mode = mock_env or test_env

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'ollama', 'groq', 'gemini', 'anthropic', 'openai')."""
        pass

    @property
    @abc.abstractmethod
    def default_model(self) -> str:
        """Default model identifier for this provider."""
        pass

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Synchronously generate text response for prompt and system instruction."""
        pass

    @abc.abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream generated text chunks as they arrive."""
        pass

    async def generate_async(
        self,
        prompt: str,
        system_prompt: str = "",
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Asynchronously generate response (default wraps synchronous generate)."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ),
        )

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Fast non-blocking check whether this client is configured and available."""
        pass

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Network/daemon probe confirming service responsiveness."""
        pass
