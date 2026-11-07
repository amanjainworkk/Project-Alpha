"""backend/model_router/groq_client.py - Groq Cloud Client for Tier 3 Inference.

Provides fast cloud inference with rate-limit detection, dual-mode SDK/REST support,
and hermetic offline test mode.
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
    estimate_tokens,
)

logger = logging.getLogger("alpha.model_router.groq")

DEFAULT_GROQ_MODEL = "llama-3.1-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClient(BaseLLMClient):
    """Client for Groq Cloud API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_GROQ_MODEL,
        timeout: float = 30.0,
        mock_mode: Optional[bool] = None,
    ):
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        super().__init__(
            api_key=resolved_key,
            default_model=default_model,
            timeout=timeout,
            mock_mode=mock_mode,
        )
        self._groq_sdk = None
        if not self.mock_mode and self.api_key:
            try:
                from groq import Groq
                self._groq_sdk = Groq(api_key=self.api_key)
            except ImportError:
                self._groq_sdk = None

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def default_model(self) -> str:
        return self._default_model or DEFAULT_GROQ_MODEL

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
        sys_instruction = system_prompt or system
        start_time = time.time()

        if self.mock_mode or not self.api_key:
            return self._mock_generate(prompt, sys_instruction, model_name, start_time, **kwargs)

        messages = []
        if sys_instruction:
            messages.append({"role": "system", "content": sys_instruction})
        messages.append({"role": "user", "content": prompt})

        # Path A: Using Groq SDK if installed
        if self._groq_sdk is not None:
            try:
                resp = self._groq_sdk.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency_ms = (time.time() - start_time) * 1000.0
                choice = resp.choices[0]
                content = choice.message.content or ""
                p_tok = resp.usage.prompt_tokens if resp.usage else estimate_tokens(prompt + sys_instruction)
                c_tok = resp.usage.completion_tokens if resp.usage else estimate_tokens(content)

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=3,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    finish_reason=choice.finish_reason or "stop",
                )
            except Exception as e:
                self._map_and_raise(e, model_name)

        # Path B: Standard REST fallback
        return self._call_rest(messages, model_name, temperature, max_tokens, start_time, prompt, sys_instruction)

    def _call_rest(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        start_time: float,
        prompt: str,
        sys_instruction: str,
    ) -> ModelResponse:
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        req = urllib.request.Request(
            GROQ_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.time() - start_time) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage = data.get("usage", {})
                p_tok = usage.get("prompt_tokens") or estimate_tokens(prompt + sys_instruction)
                c_tok = usage.get("completion_tokens") or estimate_tokens(content)

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=3,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    finish_reason=choice.get("finish_reason", "stop"),
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError(f"Groq 429: Rate limit exceeded for {model_name}", provider=self.provider_name, model=model_name)
            elif e.code in (401, 403):
                raise AuthenticationError(f"Groq {e.code}: Invalid or unauthorized API key", provider=self.provider_name, model=model_name)
            raise ProviderUnavailableError(f"Groq HTTP {e.code}: {e.reason}", provider=self.provider_name, model=model_name)
        except Exception as e:
            raise ProviderUnavailableError(f"Groq network error: {e}", provider=self.provider_name, model=model_name)

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
            tokens = [f"[{model_name}]", " High", " throughput", " Groq", " verified", " deliverable."]
            for tok in tokens:
                yield tok
            return

        if self._groq_sdk is not None:
            messages = []
            if sys_instruction:
                messages.append({"role": "system", "content": sys_instruction})
            messages.append({"role": "user", "content": prompt})
            try:
                stream = self._groq_sdk.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        yield delta
            except Exception as e:
                self._map_and_raise(e, model_name)
        else:
            res = self.generate(prompt, sys_instruction, model=model_name, temperature=temperature, max_tokens=max_tokens, **kwargs)
            yield res.content

    def _map_and_raise(self, exc: Exception, model_name: str) -> None:
        err_msg = str(exc)
        if "429" in err_msg or "rate_limit" in err_msg.lower():
            raise RateLimitError(f"Groq 429: {err_msg}", provider=self.provider_name, model=model_name)
        if "401" in err_msg or "403" in err_msg or "auth" in err_msg.lower():
            raise AuthenticationError(f"Groq auth error: {err_msg}", provider=self.provider_name, model=model_name)
        raise ProviderUnavailableError(f"Groq error: {err_msg}", provider=self.provider_name, model=model_name)

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
        latency_ms = (time.time() - start_time) * 1000.0 or 15.0
        return ModelResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            tier=3,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=latency_ms,
            cost_usd=0.0,
            finish_reason="stop",
        )
