"""backend/model_router/ollama_client.py - Local Ollama LLM Client for Tier 1 & 2.

Handles local inference via Ollama REST API (or SDK if installed) with
graceful offline detection and deterministic mock test execution.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional
import urllib.error
import urllib.request

from backend.model_router.base_client import (
    BaseLLMClient,
    ModelResponse,
    ProviderUnavailableError,
    estimate_tokens,
)

logger = logging.getLogger("alpha.model_router.ollama")

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


class OllamaClient(BaseLLMClient):
    """Client for local Ollama server running on host."""

    def __init__(
        self,
        host: Optional[str] = None,
        default_model: str = DEFAULT_OLLAMA_MODEL,
        timeout: float = 30.0,
        mock_mode: Optional[bool] = None,
    ):
        resolved_host = host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
        super().__init__(
            base_url=resolved_host.rstrip("/"),
            default_model=default_model,
            timeout=timeout,
            mock_mode=mock_mode,
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._default_model or DEFAULT_OLLAMA_MODEL

    def is_available(self) -> bool:
        """Fast non-blocking check if Ollama daemon is reachable."""
        if self.mock_mode:
            return True
        return self.health_check()

    def health_check(self) -> bool:
        """Probes Ollama /api/tags to confirm daemon is responsive."""
        if self.mock_mode:
            return True
        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Returns list of pulled model tags in local Ollama."""
        if self.mock_mode:
            return ["llama3.2:latest", "llama3.2:1b", "llama3.2:3b", "nomic-embed-text:latest"]
        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.debug("Failed to list Ollama models: %s", e)
            return []

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

        if self.mock_mode:
            return self._mock_generate(prompt, sys_instruction, model_name, start_time, **kwargs)

        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if sys_instruction:
            payload["system"] = sys_instruction
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.time() - start_time) * 1000.0
                body = json.loads(resp.read().decode("utf-8"))
                content = body.get("response", "")
                p_tokens = body.get("prompt_eval_count") or estimate_tokens(prompt + sys_instruction)
                c_tokens = body.get("eval_count") or estimate_tokens(content)

                tier = 1 if "1b" in model_name else 2

                return ModelResponse(
                    content=content,
                    model=model_name,
                    provider=self.provider_name,
                    tier=tier,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=p_tokens + c_tokens,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    finish_reason="stop",
                    metadata={"total_duration": body.get("total_duration")},
                )
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError) as e:
            logger.warning("Ollama connection failed: %s", e)
            raise ProviderUnavailableError(
                f"Ollama server at {self.base_url} is unreachable. Ensure 'ollama serve' is active.",
                provider=self.provider_name,
                model=model_name,
            ) from e

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

        if self.mock_mode:
            for chunk in self._mock_stream(prompt, model_name):
                yield chunk
            return

        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if sys_instruction:
            payload["system"] = sys_instruction
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if not line:
                        continue
                    chunk_obj = json.loads(line.decode("utf-8"))
                    text = chunk_obj.get("response", "")
                    if text:
                        yield text
                    if chunk_obj.get("done", False):
                        break
        except Exception as e:
            raise ProviderUnavailableError(
                f"Ollama streaming failed: {e}",
                provider=self.provider_name,
                model=model_name,
            ) from e

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
        latency_ms = (time.time() - start_time) * 1000.0 or 2.5
        tier = 1 if "1b" in model_name else 2
        return ModelResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            tier=tier,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=latency_ms,
            cost_usd=0.0,
            finish_reason="stop",
        )

    def _mock_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        tokens = [f"[{model_name}]", " Output:", " Local", " Ollama", " verified", " response."]
        for tok in tokens:
            yield tok
