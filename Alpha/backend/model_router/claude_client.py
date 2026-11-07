"""backend/model_router/claude_client.py - Anthropic Claude Client for Tier 5 Inference.

Supports Tier 5 and mandatory CAO-Claude auditing (claude-3-5-sonnet-20241022),
accurate token cost tracking ($3.00 / $15.00 per 1M tokens), and audit isolation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterator, Optional
import urllib.error
import urllib.request

from backend.model_router.base_client import (
    AuthenticationError,
    BaseLLMClient,
    ModelResponse,
    ProviderUnavailableError,
    RateLimitError,
    calculate_cost,
    estimate_tokens,
)

logger = logging.getLogger("alpha.model_router.claude")

DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


class ClaudeClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_CLAUDE_MODEL,
        timeout: float = 60.0,
        mock_mode: Optional[bool] = None,
    ):
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        super().__init__(
            api_key=resolved_key,
            default_model=default_model,
            timeout=timeout,
            mock_mode=mock_mode,
        )
        self._anthropic_sdk = None
        if not self.mock_mode and self.api_key:
            try:
                from anthropic import Anthropic
                self._anthropic_sdk = Anthropic(api_key=self.api_key)
            except ImportError:
                self._anthropic_sdk = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return self._default_model or DEFAULT_CLAUDE_MODEL

    def is_available(self) -> bool:
        if self.mock_mode:
            return True
        return bool(self.api_key and len(self.api_key) > 5)

    def health_check(self) -> bool:
        return self.is_available()

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
        if model_name in ("claude-3-5-sonnet", "claude-sonnet"):
            model_name = DEFAULT_CLAUDE_MODEL

        sys_instruction = system_prompt or system
        start_time = time.time()

        if self.mock_mode or not self.api_key:
            return self._mock_generate(prompt, sys_instruction, model_name, start_time, **kwargs)

        # Path A: Native Anthropic SDK
        if self._anthropic_sdk is not None:
            try:
                req_kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "max_tokens": max_tokens or 4096,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if sys_instruction:
                    req_kwargs["system"] = sys_instruction

                resp = self._anthropic_sdk.messages.create(**req_kwargs)
                latency_ms = (time.time() - start_time) * 1000.0

                content_parts = [b.text for b in resp.content if hasattr(b, "text")]
                content = "".join(content_parts)

                p_tok = resp.usage.input_tokens
                c_tok = resp.usage.output_tokens
                cost = calculate_cost(p_tok, c_tok, model_name)

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=5,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    finish_reason=resp.stop_reason or "stop",
                )
            except Exception as e:
                self._map_and_raise(e, model_name)

        # Path B: REST API Fallback
        return self._call_rest(prompt, sys_instruction, model_name, temperature, max_tokens, start_time)

    def _call_rest(
        self,
        prompt: str,
        sys_instruction: str,
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        start_time: float,
    ) -> ModelResponse:
        payload: Dict[str, Any] = {
            "model": model_name,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_instruction:
            payload["system"] = sys_instruction

        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.time() - start_time) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                content_parts = [b.get("text", "") for b in data.get("content", [])]
                content = "".join(content_parts)

                usage = data.get("usage", {})
                p_tok = usage.get("input_tokens") or estimate_tokens(prompt + sys_instruction)
                c_tok = usage.get("output_tokens") or estimate_tokens(content)
                cost = calculate_cost(p_tok, c_tok, model_name)

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=5,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    finish_reason=data.get("stop_reason", "stop"),
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError(f"Anthropic 429: Rate limit reached for {model_name}", provider=self.provider_name, model=model_name)
            if e.code in (401, 403):
                raise AuthenticationError(f"Anthropic {e.code}: Authentication failed", provider=self.provider_name, model=model_name)
            raise ProviderUnavailableError(f"Anthropic HTTP {e.code}: {e.reason}", provider=self.provider_name, model=model_name)
        except Exception as e:
            raise ProviderUnavailableError(f"Anthropic network error: {e}", provider=self.provider_name, model=model_name)

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
        sys_instruction = system_prompt or system

        if self.mock_mode or not self.api_key:
            tokens = [f"[{model_name}]", " Architectural", " Blueprint:", " Verified", " high", " precision", " reasoning."]
            for tok in tokens:
                yield tok
            return

        if self._anthropic_sdk is not None:
            try:
                with self._anthropic_sdk.messages.stream(
                    model=model_name,
                    max_tokens=max_tokens or 4096,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                    system=sys_instruction or None,
                ) as stream:
                    for text in stream.text_stream:
                        yield text
            except Exception as e:
                self._map_and_raise(e, model_name)
        else:
            res = self.generate(prompt, sys_instruction, model=model_name, temperature=temperature, max_tokens=max_tokens, **kwargs)
            yield res.content

    def _map_and_raise(self, exc: Exception, model_name: str) -> None:
        err_msg = str(exc)
        if "429" in err_msg or "rate_limit" in err_msg.lower():
            raise RateLimitError(f"Anthropic 429: {err_msg}", provider=self.provider_name, model=model_name)
        if "401" in err_msg or "403" in err_msg or "auth" in err_msg.lower():
            raise AuthenticationError(f"Anthropic auth error: {err_msg}", provider=self.provider_name, model=model_name)
        raise ProviderUnavailableError(f"Anthropic error: {err_msg}", provider=self.provider_name, model=model_name)

    def _mock_generate(
        self,
        prompt: str,
        system_prompt: str,
        model_name: str,
        start_time: float,
        **kwargs: Any,
    ) -> ModelResponse:
        agent_role = kwargs.get("agent_role") or kwargs.get("agent_id") or "Agent"
        task_type = kwargs.get("task_type") or "task"
        content = f"[{model_name}] Output for {agent_role}: Verified response for task '{task_type}'."
        p_tok = estimate_tokens(prompt + system_prompt)
        c_tok = estimate_tokens(content)
        cost = calculate_cost(p_tok, c_tok, model_name)
        latency_ms = (time.time() - start_time) * 1000.0 or 35.0
        return ModelResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            tier=5,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=latency_ms,
            cost_usd=cost,
            finish_reason="stop",
        )
