"""backend/model_router/exceptions.py - Exception classes for Project Alpha Model Router."""

from __future__ import annotations

from typing import Optional


class ModelRouterError(Exception):
    """Base exception for all Model Router and provider client failures."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model


class RateLimitError(ModelRouterError, RuntimeError):
    """Raised when an LLM provider returns HTTP 429 Too Many Requests or quota exhaustion.

    Inherits from RuntimeError for compatibility with legacy test assertions.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message, provider=provider, model=model)
        self.retry_after = retry_after


class ProviderUnavailableError(ModelRouterError):
    """Raised when an LLM provider is unreachable, times out, has an invalid key, or returns 5xx."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message, provider=provider, model=model)
        self.status_code = status_code


class AuthenticationError(ModelRouterError):
    """Raised when an API key is missing, invalid, or unauthorized (HTTP 401/403)."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(message, provider=provider, model=model)


class ContextWindowExceededError(ModelRouterError):
    """Raised when a prompt exceeds the model's supported context window."""

    def __init__(
        self,
        message: str,
        token_count: Optional[int] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(message, provider=provider, model=model)
        self.token_count = token_count
        self.max_tokens = max_tokens


# Alias for backward compatibility
ContextLengthExceededError = ContextWindowExceededError


class CAOAuditBlockedError(ModelRouterError):
    """Raised when CAO models fail and cannot be fallen back without violating audit isolation."""

    def __init__(
        self,
        message: str,
        agent_role: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(message, provider=provider, model=model)
        self.agent_role = agent_role


class CAOAuditUnavailableError(CAOAuditBlockedError):
    """Raised when a CAO audit model fails and sub-tier degradation is prohibited."""
    pass


class AllProvidersFailedError(ModelRouterError):
    """Raised when all providers in the fallback cascade fail."""
    pass


class BudgetExceededError(ModelRouterError):
    """Raised when the CFO token budget cap is breached for paid cloud inference."""
    pass


class InvalidRequestError(ModelRouterError):
    """Raised when a request is malformed or parameters are out of bounds."""
    pass
