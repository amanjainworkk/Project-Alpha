"""backend/model_router/schemas.py - Data models for Project Alpha Model Router.

Conforms strictly to:
- Interface Contract 2 in PROJECT.md
- tests/conftest.py (ModelConfig dataclass)
- Explorer 1, 2, and 3 architecture blueprints
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelProvider(str, Enum):
    """Supported LLM inference providers."""
    OLLAMA = "ollama"
    GROQ = "groq"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """Configuration for an individual model tier and provider.

    Must conform strictly to Interface Contract 2 in PROJECT.md and tests/conftest.py.
    """
    tier: int                                # 1 to 5
    provider: str                            # 'ollama', 'groq', 'gemini', 'anthropic', 'openai'
    model: str                               # Provider model ID (e.g., 'llama3.2:1b', 'claude-3-5-sonnet')
    cost_per_m_in: float = 0.0               # Cost per 1M input tokens in USD
    cost_per_m_out: float = 0.0              # Cost per 1M output tokens in USD
    is_free: bool = True                     # True for Tiers 1-4, False for Tier 5
    temperature: float = 0.7                 # Sampling temperature
    max_tokens: Optional[int] = None         # Maximum generation tokens
    timeout_seconds: float = 30.0            # Provider timeout threshold
    context_window: int = 8192               # Max context length in tokens


@dataclass
class TokenUsage:
    """Detailed token consumption and accounting metrics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @classmethod
    def calculate(
        cls,
        prompt_tokens: int,
        completion_tokens: int,
        config: ModelConfig,
    ) -> TokenUsage:
        """Calculate token usage and cost according to the model config."""
        total = prompt_tokens + completion_tokens
        if config.is_free:
            cost = 0.0
        else:
            cost = (prompt_tokens * config.cost_per_m_in + completion_tokens * config.cost_per_m_out) / 1_000_000.0
        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost_usd=round(cost, 6),
        )


@dataclass
class ModelResponse:
    """Standardized response envelope returned by all LLM clients and router invocations.

    Implements __str__(self) -> self.content for 100% backward compatibility with
    callers expecting string return types.
    """
    content: str
    model: str
    provider: str
    tier: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    finish_reason: str = "stop"
    fallback_used: bool = False
    fallback_occurred: bool = False
    original_tier: Optional[int] = None
    actual_tier: Optional[int] = None
    original_config: Optional[ModelConfig] = None
    model_config: Optional[ModelConfig] = None
    usage: Optional[TokenUsage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None
    call_timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.model_config is not None:
            self.tier = self.model_config.tier
            if self.actual_tier is None:
                self.actual_tier = self.model_config.tier

        if self.actual_tier is None:
            self.actual_tier = self.tier

        if self.total_tokens == 0 and (self.prompt_tokens > 0 or self.completion_tokens > 0):
            self.total_tokens = self.prompt_tokens + self.completion_tokens

        if self.usage is not None:
            if self.prompt_tokens == 0:
                self.prompt_tokens = self.usage.prompt_tokens
            if self.completion_tokens == 0:
                self.completion_tokens = self.usage.completion_tokens
            if self.total_tokens == 0:
                self.total_tokens = self.usage.total_tokens
            if self.cost_usd == 0.0 and self.usage.estimated_cost_usd > 0.0:
                self.cost_usd = self.usage.estimated_cost_usd
        else:
            self.usage = TokenUsage(
                prompt_tokens=self.prompt_tokens,
                completion_tokens=self.completion_tokens,
                total_tokens=self.total_tokens,
                estimated_cost_usd=self.cost_usd,
            )

        if self.fallback_used or self.fallback_occurred:
            self.fallback_used = True
            self.fallback_occurred = True

    def __str__(self) -> str:
        """Returns the text content directly for backward compatibility."""
        return self.content

    def __repr__(self) -> str:
        return (
            f"<ModelResponse provider='{self.provider}' model='{self.model}' "
            f"tier={self.tier} tokens={self.total_tokens} cost=${self.cost_usd:.6f} "
            f"latency={self.latency_ms:.1f}ms fallback={self.fallback_used}>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes response to a JSON-compatible dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "tier": self.tier,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "finish_reason": self.finish_reason,
            "fallback_used": self.fallback_used,
            "original_tier": self.original_tier,
            "actual_tier": self.actual_tier,
            "metadata": self.metadata,
        }


@dataclass
class RoutingDecision:
    """Detailed audit explanation of a routing resolution."""
    task_type: str
    requested_complexity: int
    clamped_complexity: int
    agent_role: Optional[str]
    selected_config: ModelConfig
    fallback_chain: List[ModelConfig]
    reasoning: str
