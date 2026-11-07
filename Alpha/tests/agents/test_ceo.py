"""tests/agents/test_ceo.py - Comprehensive Unit & Integration Tests for CEOAgent."""

from pathlib import Path
import pytest

from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.ceo import CEOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


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


@pytest.fixture
def ceo_agent(test_vault, test_router) -> CEOAgent:
    return CEOAgent(vault_manager=test_vault, model_router=test_router)


# ============================================================================
# 1. Inheritance and Initialization
# ============================================================================

def test_ceo_agent_inherits_from_base_agent(ceo_agent):
    assert isinstance(ceo_agent, BaseExecutiveAgent)
    assert ceo_agent.role == "CEO"
    assert ceo_agent.name == "Alpha CEO"
    assert "Chief Executive Officer" in ceo_agent.system_prompt


# ============================================================================
# 2. Goal Ingestion & Workstream Decomposition (ingest_goal)
# ============================================================================

def test_ceo_ingest_goal_returns_valid_contract_structure(ceo_agent):
    goal_text = "Launch SaaS MVP in 2 weeks with Flutter UI and Stripe billing"
    result = ceo_agent.ingest_goal(goal_text, project_id="proj_001")

    assert "goal_id" in result
    assert result["project_id"] == "proj_001"
    assert "objectives" in result
    assert "assigned_roles" in result
    assert result["status"] == "ingested"
    assert isinstance(result["objectives"], list)
    assert len(result["objectives"]) >= 1
    assert isinstance(result["assigned_roles"], list)
    assert len(result["assigned_roles"]) >= 1


def test_ceo_ingest_goal_persists_to_vault(ceo_agent, test_vault):
    goal_text = "Build AI Executive Operating System"
    result = ceo_agent.ingest_goal(goal_text, project_id="proj_alpha_99")

    # Verify vault persistence
    saved = test_vault.read("projects/proj_alpha_99/goals.json")
    assert saved is not None
    assert saved["goal_id"] == result["goal_id"]
    assert saved["raw_goal"] == goal_text


def test_ceo_ingest_goal_empty_string_raises_value_error(ceo_agent):
    with pytest.raises(ValueError):
        ceo_agent.ingest_goal("   ")


def test_ceo_ingest_goal_appends_vault_memory(ceo_agent, test_vault):
    ceo_agent.ingest_goal("Expand agent roster", project_id="proj_hr")
    memories = ceo_agent.get_recent_memories(n=5)
    assert len(memories) >= 1
    assert any("Expand agent roster" in (m.get("memory_content") or m.get("content", "")) for m in memories)


# ============================================================================
# 3. Departmental Delegation & Brief Formatting (delegate_task)
# ============================================================================

@pytest.mark.parametrize("task_type,expected_role", [
    ("technical_architecture", "CTO"),
    ("gtm_marketing_campaign", "CMO"),
    ("budget_review_and_pricing", "CFO"),
    ("prd_user_stories", "CPO"),
    ("oled_wireframe_tokens", "CDO"),
    ("legal_compliance_audit", "CLO"),
    ("workflow_and_schedule", "COO"),
])
def test_ceo_delegate_task_role_mapping(ceo_agent, task_type, expected_role):
    res = ceo_agent.delegate_task(task_type, {"project_id": "proj_001"})
    assert res["target_agent"] == expected_role


def test_ceo_delegate_task_formats_complete_brief(ceo_agent):
    context = {
        "project_id": "proj_001",
        "priority": "URGENT",
        "deadline": "3 days",
        "context": "Need high-throughput REST API",
        "objective": "Build FastAPI backend endpoints",
        "deliverable_spec": "Modular routers with OpenAPI schema",
        "constraints": ["No paid external dependencies"],
        "success_criteria": "100% test coverage and <20ms latency",
    }
    result = ceo_agent.delegate_task("technical_spec", context)

    assert result["target_agent"] == "CTO"
    assert "formatted_brief" in result
    brief = result["formatted_brief"]
    assert "[AGENT_BRIEF]" in brief
    assert "TO: CTO" in brief
    assert "FROM: CEO" in brief
    assert "PRIORITY: URGENT" in brief
    assert "DEADLINE: 3 days" in brief
    assert "OBJECTIVE:" in brief
    assert "DELIVERABLE SPECIFICATION:" in brief
    assert "CONSTRAINTS:" in brief
    assert "SUCCESS CRITERIA:" in brief


def test_ceo_determine_department_override(ceo_agent):
    target = ceo_agent.determine_department("random_task", {"target_role": "CSO"})
    assert target == "CSO"


def test_ceo_delegate_task_none_context_graceful(ceo_agent):
    """Test delegate_task('gtm_campaign', None) to verify graceful fallback to {} without raising AttributeError."""
    result = ceo_agent.delegate_task("gtm_campaign", None)

    assert isinstance(result, dict)
    assert result["status"] == "dispatched"
    assert result["target_agent"] == "CMO"
    assert result["project_id"] == "default_project"
    assert "formatted_brief" in result
    brief = result["formatted_brief"]
    assert "[AGENT_BRIEF]" in brief
    assert "TO: CMO" in brief
    assert "FROM: CEO" in brief
    assert "PRIORITY: STANDARD" in brief


# ============================================================================
# 4. Output Synthesis & Conflict Adjudication (synthesize)
# ============================================================================

def test_ceo_synthesize_combines_multiple_reports(ceo_agent, test_vault):
    reports = [
        {"role": "CTO", "summary": "Engineered FastAPI backend and SQLite schemas."},
        {"role": "CMO", "summary": "Defined developer persona and GTM copy."},
        {"role": "CFO", "summary": "Zero-cost token budget maintained successfully."},
    ]
    briefing = ceo_agent.synthesize(reports, project_id="proj_001")

    assert briefing["status"] == "completed"
    assert briefing["reports_analyzed"] == 3
    assert set(briefing["participating_roles"]) == {"CTO", "CMO", "CFO"}
    assert "unified_briefing_md" in briefing
    assert "FastAPI" in briefing["unified_briefing_md"]
    assert "developer persona" in briefing["unified_briefing_md"]

    # Verify deliverable written to vault
    saved = test_vault.read("projects/proj_001/deliverables/executive_briefing.json")
    assert saved is not None
    assert saved["briefing_id"] == briefing["briefing_id"]


def test_ceo_synthesize_tier1_minor_conflict_resolved_internally(ceo_agent):
    reports = [
        {"role": "CTO", "summary": "Tech spec ready", "timeline_conflict": "Milestone 2 needs 2 extra days"},
        {"role": "COO", "summary": "Operations schedule on track"},
    ]
    briefing = ceo_agent.synthesize(reports, project_id="proj_001")

    assert briefing["status"] == "completed"
    assert len(briefing["resolutions"]) == 1
    assert briefing["resolutions"][0]["adjudication"] == "CEO Executive Adjustment"
    assert briefing["founder_escalation"] is None


def test_ceo_synthesize_escalates_critical_budget_breach(ceo_agent):
    reports = [
        {"role": "CTO", "summary": "High performance cluster deployed."},
        {"role": "CFO", "summary": "Budget overrun!", "budget_breach": True, "breach_details": "Cloud GPU costs exceed $500 monthly limit."},
    ]
    briefing = ceo_agent.synthesize(reports, project_id="proj_001")

    assert briefing["status"] == "escalation_required"
    assert briefing["founder_escalation"] is not None
    esc = briefing["founder_escalation"]
    assert esc["severity"] == "P0_CRITICAL"
    assert "costs exceed $500" in esc["issue"]
    assert len(esc["decision_options"]) >= 2
    assert "⚠️ Founder Escalation Required" in briefing["unified_briefing_md"]


def test_ceo_synthesize_escalates_critical_legal_blocker(ceo_agent):
    reports = [
        {"role": "CTO", "summary": "Integrated open source engine."},
        {"role": "CLO", "summary": "GPL violation detected", "risk": "critical", "risk_details": "GPLv3 library contaminates proprietary backend."},
    ]
    briefing = ceo_agent.synthesize(reports, project_id="proj_001")

    assert briefing["status"] == "escalation_required"
    assert briefing["founder_escalation"] is not None
    assert "GPLv3" in briefing["founder_escalation"]["issue"]


def test_ceo_synthesize_empty_reports_graceful(ceo_agent):
    briefing = ceo_agent.synthesize([])
    assert briefing["status"] == "completed"
    assert briefing["reports_analyzed"] == 0


def test_ceo_synthesize_multiple_simultaneous_critical_breaches(ceo_agent, test_vault):
    """Submit both CFO budget breach ($15k on $10k cap) and CLO legal blocker (GPL-3.0 contamination).

    Assert that BOTH breaches are preserved in the escalation structure and that
    both appear with options in unified_briefing_md.
    """
    reports = [
        {"role": "CTO", "summary": "Core engine deployed and running."},
        {
            "role": "CFO",
            "summary": "Monthly cloud infrastructure spending audit.",
            "budget_breach": True,
            "status": "over_budget",
            "breach_details": "Critical budget overrun: $15,000 spent against $10,000 allocated monthly budget.",
        },
        {
            "role": "CLO",
            "summary": "Third-party dependency license audit.",
            "risk": "critical",
            "license_violation": True,
            "risk_details": "Critical legal blocker: GPL-3.0 license contamination identified in core distribution.",
        },
    ]

    briefing = ceo_agent.synthesize(reports, project_id="proj_simultaneous_breaches")

    # 1. Status and conflict detection
    assert briefing["status"] == "escalation_required"
    assert len(briefing["conflicts_detected"]) == 2

    # 2. Both breaches preserved in escalation structure
    assert briefing["founder_escalation"] is not None
    esc = briefing["founder_escalation"]
    assert esc["severity"] == "P0_CRITICAL"

    # Verify both CFO budget breach and CLO legal blocker exist in escalation structure
    esc_str = str(esc)
    assert "$15,000" in esc_str or "budget" in esc_str.lower()
    assert "GPL-3.0" in esc_str or "gpl" in esc_str.lower()

    # Verify multi-escalation list or composite departments
    if "departments" in esc:
        assert "CFO" in esc["departments"]
        assert "CLO" in esc["departments"]
    if "founder_escalations" in briefing:
        assert len(briefing["founder_escalations"]) == 2
        escalated_depts = [e["department"] for e in briefing["founder_escalations"]]
        assert "CFO" in escalated_depts
        assert "CLO" in escalated_depts

    # 3. Both appear with options in unified_briefing_md
    md_text = briefing["unified_briefing_md"]
    assert "⚠️ Founder Escalation Required" in md_text
    assert "$15,000" in md_text
    assert "GPL-3.0" in md_text
    assert "Options for Founder (Aman Jain)" in md_text

    # Verify decision options exist for both breaches
    options = esc.get("decision_options", [])
    assert len(options) >= 2
    # Ensure options address both budget and legal decisions
    opt_labels = " ".join(o.get("label", "") + o.get("option_id", "") for o in options)
    assert "budget" in opt_labels.lower() or "cfo" in opt_labels.lower() or "resource" in opt_labels.lower() or len(options) >= 4
    assert "legal" in opt_labels.lower() or "clo" in opt_labels.lower() or "scope" in opt_labels.lower() or len(options) >= 4

