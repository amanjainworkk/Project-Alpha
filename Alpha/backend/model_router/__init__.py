"""backend/model_router package

Exposes the unified Model Router, provider client adapters, data models,
and exception hierarchy for Project Alpha.
"""

from backend.model_router.base_client import (
    BaseLLMClient,
    calculate_cost,
    estimate_tokens,
)
from backend.model_router.claude_client import ClaudeClient
from backend.model_router.exceptions import (
    AllProvidersFailedError,
    AuthenticationError,
    BudgetExceededError,
    CAOAuditBlockedError,
    CAOAuditUnavailableError,
    ContextLengthExceededError,
    ContextWindowExceededError,
    InvalidRequestError,
    ModelRouterError,
    ProviderUnavailableError,
    RateLimitError,
)
from backend.model_router.gemini_client import GeminiClient
from backend.model_router.groq_client import GroqClient
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.ollama_client import OllamaClient
from backend.model_router.openai_client import OpenAIClient
from backend.model_router.router import ModelRouter
from backend.model_router.schemas import (
    ModelConfig,
    ModelProvider,
    ModelResponse,
    RoutingDecision,
    TokenUsage,
)

__all__ = [
    "ModelRouter",
    "ModelConfig",
    "ModelResponse",
    "TokenUsage",
    "ModelProvider",
    "RoutingDecision",
    "BaseLLMClient",
    "OllamaClient",
    "GroqClient",
    "GeminiClient",
    "ClaudeClient",
    "OpenAIClient",
    "MockLLMClient",
    "ModelRouterError",
    "RateLimitError",
    "ProviderUnavailableError",
    "AuthenticationError",
    "ContextWindowExceededError",
    "ContextLengthExceededError",
    "CAOAuditBlockedError",
    "CAOAuditUnavailableError",
    "AllProvidersFailedError",
    "BudgetExceededError",
    "InvalidRequestError",
    "estimate_tokens",
    "calculate_cost",
]
