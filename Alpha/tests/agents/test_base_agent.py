"""tests/agents/test_base_agent.py - Comprehensive Unit Tests for BaseExecutiveAgent."""

from pathlib import Path
import pytest

from backend.agents.base_agent import BaseExecutiveAgent, JDParsedData
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


class ConcreteTestAgent(BaseExecutiveAgent):
    """Concrete subclass of BaseExecutiveAgent for testing abstract functionality."""
    pass


@pytest.fixture
def test_vault(tmp_path: Path) -> VaultManager:
    return VaultManager(
        vault_root=tmp_path / "vault",
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
    )


@pytest.fixture
def test_router() -> ModelRouter:
    clients = {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
        "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }
    return ModelRouter(clients=clients)


# ============================================================================
# 1. Initialization and JD Loading
# ============================================================================

def test_base_agent_initialization_defaults(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="TEST_AGENT",
        name="Test Executive",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    assert agent.agent_id == "TEST_AGENT"
    assert agent.role == "CTO"
    assert agent.name == "Test Executive"
    assert agent.vault_manager is test_vault
    assert agent.model_router is test_router
    assert isinstance(agent.working_memory, list)
    assert len(agent.working_memory) == 0
    assert agent.status == "active"


def test_base_agent_instantiation_loads_default_jd():
    agent = ConcreteTestAgent(
        agent_id="CEO",
        name="Alpha CEO",
        role="Chief Executive Officer",
    )
    assert agent.agent_id == "CEO"
    assert agent.role == "Chief Executive Officer"
    assert len(agent.system_prompt) > 0
    assert "CHIEF EXECUTIVE OFFICER" in agent.system_prompt
    assert len(agent.jd_data.responsibilities) > 0


def test_base_agent_loads_real_markdown_jd(test_vault, test_router):
    """Verifies that an agent loads actual JD markdown from Alpha/agents/job-descriptions/."""
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    assert agent.system_prompt is not None
    assert "Chief Technology Officer" in agent.system_prompt
    assert "CTO" in agent.system_prompt


def test_base_agent_missing_jd_graceful_fallback(tmp_path, test_vault, test_router):
    """Verifies agent constructs a default system prompt if JD is missing."""
    non_existent = tmp_path / "NonExistentJD.md"
    agent = ConcreteTestAgent(
        agent_id="CUSTOM",
        name="Custom Agent",
        role="CUSTOM_ROLE",
        jd_path=non_existent,
        vault_manager=test_vault,
        model_router=test_router,
    )
    assert agent.system_prompt is not None
    assert "CUSTOM_ROLE" in agent.system_prompt
    assert agent.jd_data.role_id == "alpha-agent-custom-v1"
    assert agent.status == "active"


def test_base_agent_parses_all_responsibilities_with_h3_subheaders():
    """Assert that JDs using ### R-01 through ### R-15 (e.g. CEO, CTO, CHRO)
    parse all 15 responsibilities instead of only 1 due to regex lookahead premature termination.
    """
    # 1. CEO Agent (uses ### R-01 through ### R-15)
    agent_ceo = ConcreteTestAgent(
        agent_id="CEO",
        name="Alpha CEO",
        role="CEO",
    )
    assert len(agent_ceo.jd_data.responsibilities) == 15
    assert "Strategic Goal Intake" in agent_ceo.jd_data.responsibilities[0]
    assert "Institutional Memory" in agent_ceo.jd_data.responsibilities[14]

    # 2. CTO Agent (uses ### 3.1 through ### 3.15)
    agent_cto = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
    )
    assert len(agent_cto.jd_data.responsibilities) == 15
    assert "Technical Strategy" in agent_cto.jd_data.responsibilities[0] or "Architecture" in agent_cto.jd_data.responsibilities[0]

    # 3. CHRO Agent (uses ### R-01 through ### R-15)
    agent_chro = ConcreteTestAgent(
        agent_id="CHRO",
        name="Alpha CHRO",
        role="CHRO",
    )
    assert len(agent_chro.jd_data.responsibilities) == 15


def test_base_agent_parses_markdown_table_boundaries():
    """Assert that boundaries formatted as tables or under subheadings are captured
    in constraints rather than dropping to empty fallback lists.
    """
    # 1. CEO Agent: Section 14 boundaries formatted in a Markdown table under '### 14.1 What the CEO Never Does'
    agent_ceo = ConcreteTestAgent(
        agent_id="CEO",
        name="Alpha CEO",
        role="CEO",
    )
    assert len(agent_ceo.jd_data.constraints) > 0
    assert any("Never deceives the user" in c for c in agent_ceo.jd_data.constraints)
    assert any("Never commits user resources" in c for c in agent_ceo.jd_data.constraints)
    assert any("Never overrides user decisions" in c for c in agent_ceo.jd_data.constraints)

    # 2. CTO Agent: Section 14 boundaries formatted under '### What CTO Will Never Do' with numbered items
    agent_cto = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
    )
    assert len(agent_cto.jd_data.constraints) > 0
    assert any("Never approve a system with unresolved Critical security vulnerabilities" in c for c in agent_cto.jd_data.constraints)
    assert any("Never recommend a technology without an ATSR score" in c for c in agent_cto.jd_data.constraints)

    # 3. Isolated synthetic test with explicit markdown table under boundaries section
    synthetic_jd = """# Role: Custom Sentinel
## 1. MISSION
Guarding system boundaries.

## 3. CORE RESPONSIBILITIES
### R-01: First Duty
Execute perimeter scan.
### R-02: Second Duty
Enforce isolation.

## 14. BOUNDARIES & NON-NEGOTIABLES
### 14.1 Prohibited Behaviors
| Boundary | Enforcement Protocol |
|---|---|
| **Never bypass MFA** | Strict rejection on unauthorized ingress |
| **Never leak session keys** | Zero-retention memory scrubbing |
"""
    parsed = agent_ceo.parse_jd_markdown(synthetic_jd, "custom-sentinel-v1")
    assert len(parsed.responsibilities) == 2
    assert len(parsed.constraints) >= 2
    assert any("Never bypass MFA" in c for c in parsed.constraints)
    assert any("Never leak session keys" in c for c in parsed.constraints)


# ============================================================================
# 2. Working Memory & Vault Persistence
# ============================================================================

def test_base_agent_record_thought_working_memory_and_vault(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    mem_id = agent.record_thought(thought="Designed microservices architecture", importance=7, project_id="proj_001")
    assert mem_id is not None
    assert len(agent.working_memory) == 1
    assert agent.working_memory[0]["content"] == "Designed microservices architecture"
    assert agent.working_memory[0]["importance"] == 7

    # Verify vault persistence
    recent = agent.get_recent_memories(n=5)
    assert len(recent) >= 1
    assert any("Designed microservices architecture" in (m.get("memory_content") or m.get("content", "")) for m in recent)


def test_base_agent_memory_without_vault_manager(test_router):
    """Verifies memory operations work in-memory even if vault_manager is None."""
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=None,
        model_router=test_router,
    )
    mem_id = agent.record_thought(thought="In-memory thought", importance=4)
    assert mem_id.startswith("mem_")
    assert len(agent.working_memory) == 1
    recent = agent.get_recent_memories(n=5)
    assert len(recent) == 1
    assert recent[0]["content"] == "In-memory thought"


def test_base_agent_importance_validation(test_vault, test_router):
    """Verifies importance rating validates strictly between 1 and 10."""
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    with pytest.raises(ValueError):
        agent.record_thought(thought="Invalid importance high", importance=15)

    with pytest.raises(ValueError):
        agent.record_thought(thought="Invalid importance low", importance=0)


def test_base_agent_record_decision(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CEO",
        name="Alpha CEO",
        role="CEO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    dec_id = agent.record_decision(
        summary="Adopt PostgreSQL for relational metrics",
        rationale="ACID compliance and JSONB flexibility",
        importance=8,
        project_id="proj_alpha",
    )
    assert dec_id is not None
    assert len(agent.working_memory) == 1
    entry = agent.working_memory[0]
    assert entry["type"] == "decision"
    assert "Adopt PostgreSQL" in entry["content"]
    assert "ACID compliance" in entry["content"]
    assert entry["importance"] == 8


# ============================================================================
# 3. Cognitive Operations (think & think_with_metadata)
# ============================================================================

def test_base_agent_think_invokes_model_router(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    response = agent.think(context="Evaluate GraphQL vs REST", complexity=3, task_type="technical_spec")
    assert isinstance(response, str)
    assert len(response) > 0
    assert len(test_router.call_history) == 1
    call = test_router.call_history[0]
    assert call["agent_role"] == "CTO"
    assert call["task_type"] == "technical_spec"


def test_base_agent_think_with_metadata(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    res = agent.think_with_metadata(context="Analyze database indexing", complexity=2)
    assert hasattr(res, "content")
    assert hasattr(res, "token_usage")
    assert hasattr(res, "latency_ms")
    assert res.total_tokens > 0
    assert agent.total_tokens_used > 0


def test_base_agent_think_without_router_fallback(test_vault):
    """Verifies agent produces deterministic output if model_router is None."""
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=None,
    )
    fallback = agent.think("Plan architecture")
    assert isinstance(fallback, str)
    assert "CTO" in fallback or "fallback" in fallback.lower()


# ============================================================================
# 4. Action Dispatching (act)
# ============================================================================

def test_base_agent_act_record_memory(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    result = agent.act("record_memory", {"content": "Action executed", "importance": 5})
    assert result.get("status") == "success"
    assert "memory_id" in result


def test_base_agent_act_unknown_action_handled_gracefully(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    result = agent.act("non_existent_action", {})
    assert result.get("status") == "error"
    assert "Unknown action" in result.get("error", "")


def test_base_agent_act_vault_read_write_search(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CEO",
        name="Alpha CEO",
        role="CEO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    write_res = agent.act("write_vault", {
        "path": "projects/proj_001/status.json",
        "data": {"status": "active", "lead": "CEO"},
    })
    assert write_res["success"] is True

    read_res = agent.act("read_vault", {"path": "projects/proj_001/status.json"})
    assert read_res["success"] is True
    assert read_res["data"]["status"] == "active"

    search_res = agent.act("search_vault", {"query": "active"})
    assert search_res["success"] is True
    assert isinstance(search_res["results"], list)


# ============================================================================
# 5. Context Packing & Resilience
# ============================================================================

def test_base_agent_context_packing_and_sliding_window_pruning(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    agent.record_thought("Short historical note", importance=3)

    # Moderate context includes relevant memories
    packed = agent.pack_context("Small task input")
    assert "TASK INPUT:" in packed
    assert "Small task input" in packed
    assert "RELEVANT AGENT MEMORY:" in packed

    # Massive prompt (>120,000 characters) triggering sliding-window middle pruning
    massive_input = "CRITICAL_INSTRUCTION_HEADER: Build OS. " + ("A" * 120_000) + " FINAL_INSTRUCTION_FOOTER: Finish."
    pruned = agent.pack_context(massive_input, max_input_tokens=1000)
    assert len(pruned) < len(massive_input)
    assert "omitted to prevent context window overflow" in pruned
    assert "CRITICAL_INSTRUCTION_HEADER" in pruned
    assert "FINAL_INSTRUCTION_FOOTER" in pruned


def test_base_agent_telemetry_tracking_and_reset(test_vault, test_router):
    agent = ConcreteTestAgent(
        agent_id="CTO",
        name="Alpha CTO",
        role="CTO",
        vault_manager=test_vault,
        model_router=test_router,
    )
    assert agent.total_tokens_used == 0
    assert agent.telemetry.total_calls == 0

    agent.think("Quick computation", complexity=1)
    assert agent.telemetry.total_calls == 1
    assert agent.total_tokens_used > 0

    state = agent.to_dict()
    assert state["agent_id"] == "CTO"
    assert state["telemetry"]["total_calls"] == 1

    agent.reset_telemetry()
    assert agent.total_tokens_used == 0
    assert agent.telemetry.total_calls == 0
