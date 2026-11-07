"""backend/model_router/mock_client.py - Deterministic Mock LLM Client.

Provides hermetic offline execution for unit tests and CI without network calls.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

from backend.model_router.base_client import (
    BaseLLMClient,
    ModelResponse,
    ProviderUnavailableError,
    RateLimitError,
    calculate_cost,
    estimate_tokens,
)


class MockLLMClient(BaseLLMClient):
    """Hermetic mock client for unit and integration testing."""

    def __init__(
        self,
        provider: str = "mock",
        default_model: str = "mock-model",
        is_free: bool = True,
        simulate_failure: bool = False,
        simulate_rate_limit: bool = False,
        simulate_429: bool = False,
        simulate_timeout: bool = False,
        simulate_offline: bool = False,
        prompt_tokens: int = 150,
        completion_tokens: int = 50,
    ):
        super().__init__(mock_mode=True, default_model=default_model)
        self._provider_name = provider
        self.is_free = is_free
        self.simulate_failure = simulate_failure
        self.simulate_rate_limit = simulate_rate_limit
        self.simulate_429 = simulate_429
        self.simulate_timeout = simulate_timeout
        self.simulate_offline = simulate_offline
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.invocations: List[Dict[str, Any]] = []
        self.call_history: List[Dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def default_model(self) -> str:
        return self._default_model or "mock-model"

    def is_available(self) -> bool:
        return not (self.simulate_failure or self.simulate_offline)

    def health_check(self) -> bool:
        return not (self.simulate_failure or self.simulate_offline)

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
        model_name = model or self.default_model
        sys_instruction = system_prompt or system

        record = {
            "prompt": prompt,
            "system": sys_instruction,
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timestamp": time.time(),
        }
        self.invocations.append(record)

        if self.simulate_429 or self.simulate_rate_limit:
            raise RateLimitError(
                f"429 Too Many Requests from {self.provider_name}: rate limit exceeded for {model_name}.",
                provider=self.provider_name,
                model=model_name,
            )

        if self.simulate_timeout:
            raise ProviderUnavailableError(
                f"Connection timed out while communicating with {self.provider_name}.",
                provider=self.provider_name,
                model=model_name,
            )

        if self.simulate_failure or self.simulate_offline:
            raise ProviderUnavailableError(
                f"Connection refused: {self.provider_name} server is offline.",
                provider=self.provider_name,
                model=model_name,
            )

        agent_role = kwargs.get("agent_role") or kwargs.get("agent_id") or "Agent"
        task_type = kwargs.get("task_type") or "task"

        # Contract compliance with tests/conftest.py ContractModelRouter
        content = f"[{model_name}] Output for {agent_role}: Verified response for task '{task_type}'."

        p_tok = self.prompt_tokens if self.prompt_tokens > 0 else estimate_tokens(prompt + sys_instruction)
        c_tok = self.completion_tokens if self.completion_tokens > 0 else estimate_tokens(content)

        if self.is_free:
            cost = 0.0
        else:
            cost = calculate_cost(p_tok, c_tok, model_name)

        tier_map = {"ollama": 1, "groq": 3, "gemini": 4, "anthropic": 5, "openai": 5}
        tier = tier_map.get(self.provider_name, 1 if self.is_free else 5)

        res = ModelResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            tier=tier,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=12.5,
            cost_usd=cost,
            finish_reason="stop",
            metadata={"mock": True, "agent_role": agent_role, "task_type": task_type},
        )
        self.call_history.append({"prompt": prompt, "system_prompt": sys_instruction, "response": res})
        return res

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
        model_name = model or self.default_model
        res = self.generate(
            prompt,
            system_prompt=system_prompt,
            system=system,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        words = res.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
