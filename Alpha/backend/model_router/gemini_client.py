"""backend/model_router/gemini_client.py - Google Gemini Client for Tier 4 Inference.

Supports high-context generation (1M token window), Google Generative AI SDK,
REST API fallback, and hermetic offline testing.
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

logger = logging.getLogger("alpha.model_router.gemini")

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini Generative AI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_GEMINI_MODEL,
        timeout: float = 30.0,
        mock_mode: Optional[bool] = None,
    ):
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        super().__init__(
            api_key=resolved_key,
            default_model=default_model,
            timeout=timeout,
            mock_mode=mock_mode,
        )
        self._genai_sdk = None
        if not self.mock_mode and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai_sdk = genai
            except ImportError:
                self._genai_sdk = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return self._default_model or DEFAULT_GEMINI_MODEL

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

        # Path A: Using google.generativeai SDK
        if self._genai_sdk is not None:
            try:
                gen_config = self._genai_sdk.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                m = self._genai_sdk.GenerativeModel(
                    model_name=model_name,
                    system_instruction=sys_instruction if sys_instruction else None,
                    generation_config=gen_config,
                )
                resp = m.generate_content(prompt)
                latency_ms = (time.time() - start_time) * 1000.0
                content = resp.text if hasattr(resp, "text") else ""

                usage = getattr(resp, "usage_metadata", None)
                p_tok = getattr(usage, "prompt_token_count", estimate_tokens(prompt + sys_instruction))
                c_tok = getattr(usage, "candidates_token_count", estimate_tokens(content))

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=4,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    finish_reason="stop",
                )
            except Exception as e:
                self._map_and_raise(e, model_name)

        # Path B: Direct REST endpoint
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
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if sys_instruction:
            payload["system_instruction"] = {"parts": [{"text": sys_instruction}]}
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.time() - start_time) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    content = ""
                else:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join([p.get("text", "") for p in parts])

                usage = data.get("usageMetadata", {})
                p_tok = usage.get("promptTokenCount") or estimate_tokens(prompt + sys_instruction)
                c_tok = usage.get("candidatesTokenCount") or estimate_tokens(content)

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=4,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    finish_reason=candidates[0].get("finishReason", "stop") if candidates else "stop",
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError(f"Gemini 429: Quota exceeded for {model_name}", provider=self.provider_name, model=model_name)
            if e.code in (400, 401, 403):
                raise AuthenticationError(f"Gemini API key error: HTTP {e.code}", provider=self.provider_name, model=model_name)
            raise ProviderUnavailableError(f"Gemini HTTP {e.code}: {e.reason}", provider=self.provider_name, model=model_name)
        except Exception as e:
            raise ProviderUnavailableError(f"Gemini network failure: {e}", provider=self.provider_name, model=model_name)

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
            tokens = [f"[{model_name}]", " Technical", " Spec:", " High", " context", " architecture", " plan."]
            for tok in tokens:
                yield tok
            return

        if self._genai_sdk is not None:
            try:
                m = self._genai_sdk.GenerativeModel(model_name=model_name)
                resp = m.generate_content(prompt, stream=True)
                for chunk in resp:
                    text = chunk.text if hasattr(chunk, "text") else ""
                    if text:
                        yield text
            except Exception as e:
                self._map_and_raise(e, model_name)
        else:
            res = self.generate(prompt, sys_instruction, model=model_name, temperature=temperature, max_tokens=max_tokens, **kwargs)
            yield res.content

    def _map_and_raise(self, exc: Exception, model_name: str) -> None:
        err_msg = str(exc)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            raise RateLimitError(f"Gemini 429: {err_msg}", provider=self.provider_name, model=model_name)
        if "API_KEY_INVALID" in err_msg or "403" in err_msg or "401" in err_msg:
            raise AuthenticationError(f"Gemini auth error: {err_msg}", provider=self.provider_name, model=model_name)
        raise ProviderUnavailableError(f"Gemini error: {err_msg}", provider=self.provider_name, model=model_name)

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
        latency_ms = (time.time() - start_time) * 1000.0 or 22.0
        return ModelResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            tier=4,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=latency_ms,
            cost_usd=0.0,
            finish_reason="stop",
        )
