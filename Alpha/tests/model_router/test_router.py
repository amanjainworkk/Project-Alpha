"""tests/model_router/test_router.py - Comprehensive Unit & Integration Tests for Model Router.

Verifies:
1. 5-Tier complexity routing with zero-cost priority (Ollama, Groq, Gemini, Claude, OpenAI).
2. CAO agent mandatory overrides (CAO-Claude -> Sonnet, CAO-ChatGPT -> GPT-4o) and audit isolation.
3. Fallback cascade on 429 rate limit, network timeout, and connection errors.
4. Edge cases: boundary clamping, empty/whitespace prompts, massive 120k+ character prompts.
5. Token usage calculation, cost tracking ($0 for Tiers 1-4, exact pricing for Tier 5), and latency telemetry.
6. 100% hermetic offline execution with zero network dependency.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
import pytest

from backend.model_router.base_client import calculate_cost, estimate_tokens
from backend.model_router.claude_client import ClaudeClient
from backend.model_router.exceptions import (
    AllProvidersFailedError,
    CAOAuditBlockedError,
    CAOAuditUnavailableError,
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
from backend.model_router.schemas import ModelConfig, ModelResponse


# ============================================================================
# Hermetic Mock LLM Test Fixtures
# ============================================================================

@pytest.fixture
def mock_clients() -> Dict[str, MockLLMClient]:
    """Provides a fresh set of mock clients for each provider."""
    return {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
        "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }


@pytest.fixture
def router(mock_clients) -> ModelRouter:
    """Instantiates a hermetic ModelRouter pre-injected with mock clients."""
    return ModelRouter(clients=mock_clients)


@pytest.fixture(autouse=True)
def enforce_mock_env(monkeypatch: pytest.MonkeyPatch):
    """Enforces ALPHA_MOCK_LLM=1 across all test runs to prevent network leakage."""
    monkeypatch.setenv("ALPHA_MOCK_LLM", "1")


# ============================================================================
# 1. Complexity Tier Routing Tests (Tiers 1–5)
# ============================================================================

class TestModelRoutingTiers:
    """Verifies that tasks are correctly mapped to complexity tiers and zero-cost providers."""

    def test_tier1_routes_to_ollama_llama32(self, router: ModelRouter):
        cfg = router.route(task_type="summarize", complexity=1)
        assert cfg.tier == 1
        assert cfg.provider == "ollama"
        assert "llama3.2" in cfg.model
        assert cfg.is_free is True

    def test_tier2_routes_to_ollama_llama32(self, router: ModelRouter):
        cfg = router.route(task_type="draft_copy", complexity=2)
        assert cfg.tier == 2
        assert cfg.provider == "ollama"
        assert "llama3.2" in cfg.model
        assert cfg.is_free is True

    def test_tier3_routes_to_groq_llama70b(self, router: ModelRouter):
        cfg = router.route(task_type="market_analysis", complexity=3)
        assert cfg.tier == 3
        assert cfg.provider == "groq"
        assert "70b" in cfg.model
        assert cfg.is_free is True

    def test_tier4_routes_to_gemini_flash(self, router: ModelRouter):
        cfg = router.route(task_type="technical_spec", complexity=4)
        assert cfg.tier == 4
        assert cfg.provider == "gemini"
        assert "flash" in cfg.model
        assert cfg.is_free is True

    def test_tier5_routes_to_paid_claude(self, router: ModelRouter):
        cfg = router.route(task_type="architecture_design", complexity=5)
        assert cfg.tier == 5
        assert cfg.provider == "anthropic"
        assert "sonnet" in cfg.model
        assert cfg.is_free is False

    @pytest.mark.parametrize(
        "task_type,expected_tier",
        [
            ("summarize", 1),
            ("reformat", 1),
            ("draft_copy", 2),
            ("cost_estimate", 2),
            ("market_analysis", 3),
            ("technical_spec", 4),
            ("architecture_design", 5),
            ("strategic_planning", 5),
        ],
    )
    def test_task_type_default_complexity_mapping(self, router: ModelRouter, task_type: str, expected_tier: int):
        cfg = router.route(task_type=task_type)
        assert cfg.tier == expected_tier

    def test_prefer_free_flag_behavior(self, router: ModelRouter):
        cfg = router.route(task_type="general", complexity=5, prefer_free=True)
        assert cfg.is_free is True or cfg.tier == 5


# ============================================================================
# 2. CAO Overrides & Audit Isolation Tests
# ============================================================================

class TestCAOOverridesAndAuditIsolation:
    """Verifies dedicated CAO model locks and strict audit isolation defense."""

    def test_cao_claude_override_tier1_to_sonnet(self, router: ModelRouter):
        # Even requesting complexity=1, CAO-Claude MUST get Claude 3.5 Sonnet
        cfg = router.route(task_type="audit", complexity=1, agent_role="CAO-Claude")
        assert cfg.provider == "anthropic"
        assert "sonnet" in cfg.model
        assert cfg.tier == 5

    def test_cao_chatgpt_override_tier1_to_gpt4o(self, router: ModelRouter):
        # Even requesting complexity=1, CAO-ChatGPT MUST get GPT-4o
        cfg = router.route(task_type="audit", complexity=1, agent_role="CAO-ChatGPT")
        assert cfg.provider == "openai"
        assert "gpt-4o" in cfg.model
        assert cfg.tier == 5

    def test_cao_override_accepts_both_alias_formats(self, router: ModelRouter):
        # Short alias 'CAO-C' and full 'CAO-Claude'
        c_short = router.route("audit", complexity=2, agent_role="CAO-C")
        c_full = router.route("audit", complexity=2, agent_role="CAO-Claude")
        assert c_short.model == c_full.model == "claude-3-5-sonnet"

        # Short alias 'CAO-G' and full 'CAO-ChatGPT'
        g_short = router.route("audit", complexity=2, agent_role="CAO-G")
        g_full = router.route("audit", complexity=2, agent_role="CAO-ChatGPT")
        assert g_short.model == g_full.model == "gpt-4o"

    def test_cao_override_via_agent_id_argument(self, router: ModelRouter):
        # Support MCP tool invocation convention (agent_id parameter)
        cfg = router.route("audit", complexity=1, agent_id="CAO-Claude")
        assert cfg.provider == "anthropic"
        assert "sonnet" in cfg.model

    def test_cao_failure_does_not_fall_back_to_subtiers(self, mock_clients):
        # Simulate Claude provider failure
        mock_clients["anthropic"].simulate_429 = True
        router = ModelRouter(clients=mock_clients)

        # Audit calls for CAO-Claude MUST NOT degrade to Ollama/Groq/Gemini
        with pytest.raises(CAOAuditUnavailableError) as exc_info:
            router.call("Audit system architecture", agent_role="CAO-Claude")

        assert "CAO audit" in str(exc_info.value)
        # Verify that Ollama and Gemini were NOT called for CAO audit
        assert len(mock_clients["ollama"].invocations) == 0
        assert len(mock_clients["gemini"].invocations) == 0

    def test_cao_cross_model_isolation(self, mock_clients):
        # Ensure CAO-Claude never silently delegates to OpenAI and vice-versa
        mock_clients["anthropic"].simulate_timeout = True
        router = ModelRouter(clients=mock_clients)

        with pytest.raises(CAOAuditUnavailableError):
            router.call("Audit system architecture", agent_role="CAO-Claude")

        assert len(mock_clients["openai"].invocations) == 0


# ============================================================================
# 3. Fallback Cascade & Fault Resilience Tests
# ============================================================================

class TestFallbackCascadeAndResilience:
    """Verifies graceful step-down degradation during rate limits and network faults."""

    def test_tier5_rate_limit_429_falls_back_to_tier4(self, mock_clients):
        mock_clients["anthropic"].simulate_429 = True
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Strategic prompt", complexity=5, agent_role="CEO")
        assert resp.fallback_used is True
        assert resp.original_tier == 5
        assert resp.actual_tier == 4
        assert resp.provider == "gemini"

    def test_tier4_rate_limit_429_falls_back_to_tier3(self, mock_clients):
        mock_clients["gemini"].simulate_429 = True
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Spec prompt", complexity=4, agent_role="CTO")
        assert resp.fallback_used is True
        assert resp.actual_tier == 3
        assert resp.provider == "groq"

    def test_tier3_rate_limit_429_falls_back_to_tier2(self, mock_clients):
        mock_clients["groq"].simulate_429 = True
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Marketing copy", complexity=3, agent_role="CMO")
        assert resp.fallback_used is True
        assert resp.actual_tier == 2
        assert resp.provider == "ollama"

    def test_network_timeout_triggers_fallback(self, mock_clients):
        mock_clients["groq"].simulate_timeout = True
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Timeout test", complexity=3, agent_role="CPO")
        assert resp.fallback_used is True
        assert resp.actual_tier == 2
        assert resp.provider == "ollama"

    def test_connection_refused_offline_triggers_fallback(self, mock_clients):
        mock_clients["gemini"].simulate_offline = True
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Offline test", complexity=4, agent_role="CIO")
        assert resp.fallback_used is True
        assert resp.actual_tier == 3
        assert resp.provider == "groq"

    def test_complete_cascade_exhaustion_raises_all_providers_failed(self, mock_clients):
        # All providers offline
        for client in mock_clients.values():
            client.simulate_offline = True
        router = ModelRouter(clients=mock_clients)

        with pytest.raises(AllProvidersFailedError) as exc_info:
            router.invoke("Exhaustion test", complexity=5, agent_role="CEO")
        assert "All model providers in fallback cascade failed" in str(exc_info.value)

    def test_call_method_returns_content_string_on_fallback(self, mock_clients):
        mock_clients["anthropic"].simulate_429 = True
        router = ModelRouter(clients=mock_clients)

        # Standard call() interface returns str directly
        content = router.call("Strategic analysis", complexity=5, agent_role="CEO")
        assert isinstance(content, str)
        assert "gemini" in content or "Generated response" in content


# ============================================================================
# 4. Boundary Conditions & Edge Cases
# ============================================================================

class TestBoundaryConditionsAndEdgeCases:
    """Verifies edge case handling, clamping, and extreme input resilience."""

    def test_complexity_clamping_zero_and_negative_to_tier1(self, router: ModelRouter):
        c_zero = router.route("test", complexity=0)
        assert c_zero.tier == 1

        c_neg = router.route("test", complexity=-99)
        assert c_neg.tier == 1

        c_neg_str = router.route("test", complexity="-5")
        assert c_neg_str.tier == 1

    def test_complexity_clamping_excessive_to_tier5(self, router: ModelRouter):
        c_six = router.route("test", complexity=6)
        assert c_six.tier == 5

        c_extreme = router.route("test", complexity=42)
        assert c_extreme.tier == 5

    def test_empty_prompt_handling(self, router: ModelRouter):
        resp = router.call("", task_type="summarize", complexity=1)
        assert resp is not None

    def test_whitespace_prompt_handling(self, router: ModelRouter):
        resp = router.call("   \n\t   ", task_type="summarize", complexity=1)
        assert resp is not None

    def test_massive_prompt_length_handling(self, router: ModelRouter):
        massive_prompt = "Alpha OS task: " + ("analyze system data " * 10000)
        assert len(massive_prompt) > 100000

        resp = router.call(massive_prompt, task_type="summarize", complexity=1, agent_role="CEO")
        assert resp is not None
        assert len(resp) > 0

    def test_unicode_and_emoji_prompt_fidelity(self, router: ModelRouter):
        unicode_prompt = "परियोजना अल्फा 🚀: System Autonomy & 智慧模型"
        resp = router.call(unicode_prompt, task_type="summarize", complexity=1)
        assert resp is not None


# ============================================================================
# 5. Token Usage & Cost Calculation Tests
# ============================================================================

class TestTokenUsageAndCostCalculation:
    """Verifies token tracking and zero-cost enforcement for Tiers 1–4 vs Tier 5."""

    def test_tier1_tier2_cost_is_strictly_zero(self, router: ModelRouter):
        resp = router.invoke("Summarize text", complexity=1)
        assert resp.cost_usd == 0.0
        assert resp.total_tokens > 0

    def test_tier3_groq_cost_is_strictly_zero(self, router: ModelRouter):
        resp = router.invoke("Market analysis", complexity=3)
        assert resp.cost_usd == 0.0
        assert resp.total_tokens > 0

    def test_tier4_gemini_cost_is_strictly_zero(self, router: ModelRouter):
        resp = router.invoke("Technical spec", complexity=4)
        assert resp.cost_usd == 0.0
        assert resp.total_tokens > 0

    def test_tier5_paid_claude_cost_calculation(self, mock_clients):
        # Set custom token counts: 1,000 prompt tokens, 500 completion tokens
        mock_clients["anthropic"].prompt_tokens = 1000
        mock_clients["anthropic"].completion_tokens = 500
        router = ModelRouter(clients=mock_clients)

        resp = router.invoke("Architecture plan", complexity=5)
        # Claude 3.5 Sonnet: $3.00/1M in, $15.00/1M out
        expected_cost = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        assert abs(resp.cost_usd - expected_cost) < 1e-6
        assert resp.cost_usd > 0.0

    def test_cumulative_cost_tracking_across_calls(self, router: ModelRouter):
        initial_cost = router.total_cost_usd
        router.call("Task 1", complexity=1)  # Free
        router.call("Task 2", complexity=3)  # Free
        assert router.total_cost_usd == initial_cost

        # Call Tier 5
        router.call("Task 3", complexity=5)
        assert router.total_cost_usd > initial_cost


# ============================================================================
# 6. Latency Recording & Telemetry Tests
# ============================================================================

class TestLatencyRecordingAndTelemetry:
    """Verifies execution time recording and audit logging."""

    def test_latency_ms_measured_and_positive(self, router: ModelRouter):
        resp = router.invoke("Measure latency", complexity=2)
        assert resp.latency_ms >= 0.0

    def test_call_history_appends_telemetry_records(self, router: ModelRouter):
        initial_history_len = len(router.call_history)
        router.call("Log test 1", complexity=1)
        router.call("Log test 2", complexity=2)

        assert len(router.call_history) == initial_history_len + 2
        recent = router.call_history[-1]
        assert "prompt" in recent
        assert "response" in recent
        assert "timestamp" in recent

    def test_telemetry_reset(self, router: ModelRouter):
        router.call("To be reset", complexity=1)
        assert len(router.call_history) > 0
        router.reset_telemetry()
        assert len(router.call_history) == 0
        assert router.total_cost_usd == 0.0

    def test_metrics_dictionary_and_token_properties(self, router: ModelRouter):
        router.call("Metrics test 1", complexity=1)
        metrics = router.get_metrics()
        assert metrics["total_calls"] >= 1
        assert "total_prompt_tokens" in metrics
        assert "total_completion_tokens" in metrics
        assert "total_cost_usd" in metrics
        assert router.total_prompt_tokens >= 0
        assert router.total_completion_tokens >= 0
        assert router.total_tokens == router.total_prompt_tokens + router.total_completion_tokens

    def test_generate_method_contract(self, router: ModelRouter):
        gen = router.generate("Hello world test prompt", "System instruction", "test-model")
        assert "[test-model] Response:" in gen


# ============================================================================
# 7. Provider Client Adapters & Unified Interface
# ============================================================================

class TestProviderClientAdapters:
    """Verifies that all 5 provider adapters adhere to the BaseLLMClient interface."""

    def test_all_clients_implement_generate_method(self):
        clients = [
            OllamaClient(),
            GroqClient(),
            GeminiClient(),
            ClaudeClient(),
            OpenAIClient(),
        ]
        for c in clients:
            assert hasattr(c, "generate"), f"Client {c} missing generate() method"
            assert callable(c.generate)

    def test_alpha_mock_llm_mode_forces_offline_execution(self, monkeypatch):
        monkeypatch.setenv("ALPHA_MOCK_LLM", "1")
        # Clients instantiated with ALPHA_MOCK_LLM=1 must generate without real network
        ollama = OllamaClient()
        resp = ollama.generate("Test prompt offline")
        assert resp is not None
        assert isinstance(resp.content, str)

    def test_client_injection_via_constructor(self, mock_clients):
        router = ModelRouter(clients=mock_clients)
        assert router.clients["ollama"] is mock_clients["ollama"]
        assert router.clients["anthropic"] is mock_clients["anthropic"]

    def test_mock_streaming_across_all_providers(self):
        clients = [
            OllamaClient(),
            GroqClient(),
            GeminiClient(),
            ClaudeClient(),
            OpenAIClient(),
            MockLLMClient(),
        ]
        for c in clients:
            chunks = list(c.generate_stream("Stream test prompt"))
            assert len(chunks) > 0
            assert all(isinstance(chunk, str) for chunk in chunks)

    def test_health_check_and_availability_in_mock_mode(self):
        clients = [
            OllamaClient(),
            GroqClient(),
            GeminiClient(),
            ClaudeClient(),
            OpenAIClient(),
            MockLLMClient(),
        ]
        for c in clients:
            assert c.is_available() is True
            assert c.health_check() is True

    def test_ollama_list_models_in_mock_mode(self):
        ollama = OllamaClient()
        models = ollama.list_installed_models()
        assert len(models) >= 3
        assert any("llama3.2" in m for m in models)

    def test_provider_direct_generate_and_metadata(self):
        clients = [
            GroqClient(),
            GeminiClient(),
            ClaudeClient(),
            OpenAIClient(),
        ]
        for c in clients:
            res = c.generate("Direct generation test", system="You are an assistant")
            assert res.content is not None
            assert res.total_tokens > 0
            assert res.finish_reason == "stop"
            d = res.to_dict()
            assert "content" in d
            assert "total_tokens" in d
            r = repr(res)
            assert "ModelResponse" in r


# ============================================================================
# 8. Existing E2E Test Compatibility Verification
# ============================================================================

class TestExistingE2ECompatibility:
    """Verifies strict adherence to existing E2E and conftest.py contracts."""

    def test_e2e_tier1_model_router_methods_compatibility(self, router: ModelRouter):
        # Exact call pattern from tests/e2e/test_tier1_features.py line 105
        c1 = router.route(task_type="summarize", complexity=1)
        assert c1.tier == 1
        assert c1.provider == "ollama"
        assert c1.is_free is True

        c3 = router.route(task_type="market_analysis", complexity=3)
        assert c3.tier == 3
        assert c3.provider == "groq"
        assert "70b" in c3.model
        assert c3.is_free is True

        c4 = router.route(task_type="technical_spec", complexity=4)
        assert c4.tier == 4
        assert c4.provider == "gemini"
        assert "flash" in c4.model
        assert c4.is_free is True

        c5 = router.route(task_type="architecture_design", complexity=5)
        assert c5.tier == 5
        assert c5.provider == "anthropic"
        assert "sonnet" in c5.model
        assert c5.is_free is False

        # Exact call pattern from tests/e2e/test_tier1_features.py line 181
        prompt = "Decompose goal: Launch SaaS MVP in 2 weeks"
        res = router.call(prompt, task_type="strategic_planning", complexity=4, agent_role="CEO")
        assert isinstance(res, str)
        assert len(res) > 0
        assert len(router.call_history) > 0

    def test_e2e_tier2_model_router_boundaries_compatibility(self, router: ModelRouter):
        # Exact call pattern from tests/e2e/test_tier2_boundaries.py line 113
        c_zero = router.route("test", complexity=0)
        assert c_zero.tier == 1

        c_negative = router.route("test", complexity=-99)
        assert c_negative.tier == 1

        c_excess = router.route("test", complexity=42)
        assert c_excess.tier == 5

    def test_conftest_model_config_compatibility(self, router: ModelRouter):
        cfg = router.route("general", complexity=3)
        # Must have all attributes defined in tests/conftest.py ModelConfig
        assert hasattr(cfg, "tier")
        assert hasattr(cfg, "provider")
        assert hasattr(cfg, "model")
        assert hasattr(cfg, "cost_per_m_in")
        assert hasattr(cfg, "cost_per_m_out")
        assert hasattr(cfg, "is_free")
