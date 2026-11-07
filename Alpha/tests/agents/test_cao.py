"""tests/agents/test_cao.py - Comprehensive Master Test Suite for Project Alpha Dual CAO System.

Covers 37 test methods across all 8 categories:
- Category 1: Individual CAO Persona Tests (5 tests)
- Category 2: 5-Axis Rubric Tests (4 tests)
- Category 3: Critical Veto Tests (4 tests)
- Category 4: Consensus Engine Tests (5 tests)
- Category 5: Strict 2-Round Escalation Cap Tests (5 tests)
- Category 6: Fault Tolerance & MockLLM Resilience Tests (4 tests)
- Category 7: Multi-Agent Integration Tests (4 tests)
- Category 8: Registry Factory Wiring & Subsystem Integration Tests (6 tests)
"""

import gc
import json
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.agents.agent_registry import AgentRegistry, reset_agent_registry
from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.cao import (
    AuditFinding,
    AuditReport,
    AxisScore,
    CAOAgent,
    CAOAuditGate,
    CAOAuditResult,
    CAOClaudeAgent,
    CAOGPTAgent,
    ConsolidatedAuditReport,
    ConsolidatedDefect,
    ConsolidatedFindings,
    DualCAO,
    FiveAxisScorecard,
    FiveAxisScores,
    SingleAuditReport,
)
from backend.agents.ceo import CEOAgent
from backend.agents.cfo import CFOAgent
from backend.agents.clo import CLOAgent
from backend.agents.cpo import CPOAgent
from backend.agents.cto import CTOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter, estimate_tokens
from backend.vault.vault_manager import VaultManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure clean registry before and after every test."""
    reset_agent_registry()
    yield
    reset_agent_registry()
    gc.collect()


@pytest.fixture
def test_vault(tmp_path: Path) -> VaultManager:
    """Create isolated test VaultManager."""
    vm = VaultManager(
        vault_root=tmp_path / "vault",
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
    )
    yield vm
    # Teardown to release Windows file handles
    if hasattr(vm, "sqlite") and hasattr(vm.sqlite, "close"):
        vm.sqlite.close()
    gc.collect()


@pytest.fixture
def test_router() -> ModelRouter:
    """Create test ModelRouter with Mock clients."""
    clients = {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
        "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }
    return ModelRouter(clients=clients)


@pytest.fixture
def test_registry(test_vault: VaultManager, test_router: ModelRouter) -> AgentRegistry:
    """Create AgentRegistry configured with test vault and router."""
    return AgentRegistry(vault_manager=test_vault, model_router=test_router)


@pytest.fixture
def dual_cao(test_vault: VaultManager, test_router: ModelRouter) -> DualCAO:
    """Create a fully configured DualCAO instance."""
    return DualCAO(vault_manager=test_vault, model_router=test_router)


@pytest.fixture
def clean_deliverables() -> Dict[str, Any]:
    """High quality test deliverables conforming to all requirements."""
    return {
        "project_id": "proj_master_001",
        "tech_spec": "Modular architecture following KISS and decoupled SOLID interfaces.",
        "prd": "Complete requirements specification with MoSCoW prioritization.",
        "code": "def process_data(item: str) -> bool:\n    if not item:\n        return False\n    return True\n",
        "tests": "def test_process():\n    assert process_data('valid') is True\n    assert process_data('') is False\n",
        "security": "All endpoints enforce Bearer token verification. Zero plaintext secrets.",
        "licensing": "Project Alpha core and dependencies are licensed under permissive MIT license.",
    }


# ============================================================================
# Category 1: Individual CAO Persona Tests (5 tests)
# ============================================================================

def test_cao_claude_initialization_and_inheritance(test_vault, test_router):
    """Verifies CAOClaudeAgent inherits BaseExecutiveAgent and configures Claude specialization."""
    agent = CAOClaudeAgent(vault_manager=test_vault, model_router=test_router)
    assert isinstance(agent, BaseExecutiveAgent)
    assert isinstance(agent, CAOAgent)
    assert agent.role == "CAO-Claude"
    assert agent.assigned_model == "claude-3-5-sonnet"
    assert agent.instance == "claude"
    assert "architectural" in agent.specialization.lower() or "rigor" in agent.specialization.lower()


def test_cao_chatgpt_initialization_and_inheritance(test_vault, test_router):
    """Verifies CAOGPTAgent inherits BaseExecutiveAgent and configures GPT specialization."""
    agent = CAOGPTAgent(vault_manager=test_vault, model_router=test_router)
    assert isinstance(agent, BaseExecutiveAgent)
    assert isinstance(agent, CAOAgent)
    assert agent.role == "CAO-ChatGPT"
    assert agent.assigned_model == "gpt-4o"
    assert agent.instance == "gpt"
    assert "completeness" in agent.specialization.lower() or "edge" in agent.specialization.lower()


def test_cao_real_jd_parsing_and_token_budget(test_vault, test_router):
    """Verifies CAO agents parse real CAO-Chief-Audit-Officer.md within token budget."""
    claude_agent = CAOClaudeAgent(vault_manager=test_vault, model_router=test_router)
    gpt_agent = CAOGPTAgent(vault_manager=test_vault, model_router=test_router)

    assert claude_agent.jd_path is not None
    assert claude_agent.jd_path.exists()
    assert "Chief Audit Officer" in claude_agent.role_id or "alpha-agent-cao" in claude_agent.role_id

    tokens_c = estimate_tokens(claude_agent.system_prompt)
    tokens_g = estimate_tokens(gpt_agent.system_prompt)

    assert 50 < tokens_c < 1000, f"Claude system prompt tokens {tokens_c} out of expected range"
    assert 50 < tokens_g < 1000, f"GPT system prompt tokens {tokens_g} out of expected range"


def test_cao_claude_persona_specialization(test_vault, test_router):
    """Verifies Claude persona focuses on architectural rigor and contract invariants."""
    agent = CAOClaudeAgent(vault_manager=test_vault, model_router=test_router)
    spec_text = agent.specialization.lower() + " " + agent.system_prompt.lower()
    assert any(term in spec_text for term in ["architectural", "rigor", "contract", "defensive", "logic"])


def test_cao_chatgpt_persona_specialization(test_vault, test_router):
    """Verifies ChatGPT persona focuses on edge cases, completeness, and alternatives."""
    agent = CAOGPTAgent(vault_manager=test_vault, model_router=test_router)
    spec_text = agent.specialization.lower() + " " + agent.system_prompt.lower()
    assert any(term in spec_text for term in ["completeness", "edge", "alternative", "ergonomics", "omission"])


# ============================================================================
# Category 2: 5-Axis Rubric Tests (4 tests)
# ============================================================================

def test_five_axis_rubric_weights_sum_to_one():
    """Verifies Addy Osmani review rubric axis weights sum to exactly 1.00 (100%)."""
    weights = CAOAgent.AXIS_WEIGHTS
    assert weights["correctness"] == 0.25
    assert weights["completeness"] == 0.20
    assert weights["security_safety"] == 0.20
    assert weights["performance_scalability"] == 0.15
    assert weights["maintainability_architecture"] == 0.20
    assert round(sum(weights.values()), 4) == 1.0000


def test_five_axis_score_calculation():
    """Verifies weighted score calculation matches Addy Osmani formula."""
    scores = FiveAxisScores(
        correctness=90.0,
        completeness=85.0,
        security=90.0,
        performance=80.0,
        maintainability=90.0,
    )
    # Expected: (90*0.25) + (85*0.20) + (90*0.20) + (80*0.15) + (90*0.20)
    # = 22.5 + 17.0 + 18.0 + 12.0 + 18.0 = 87.5%
    assert scores.weighted_total() == 87.5


def test_five_axis_boundary_at_85_threshold():
    """Verifies exact 85.0% threshold boundary behavior."""
    pass_score = FiveAxisScores(correctness=85.0, completeness=85.0, security=85.0, performance=85.0, maintainability=85.0)
    assert pass_score.weighted_total() == 85.0
    assert pass_score.weighted_total() >= CAOAgent.PASSING_THRESHOLD

    fail_score = FiveAxisScores(correctness=84.9, completeness=84.9, security=84.9, performance=84.9, maintainability=84.9)
    assert fail_score.weighted_total() == 84.9
    assert fail_score.weighted_total() < CAOAgent.PASSING_THRESHOLD

    perfect_score = FiveAxisScores(correctness=100.0, completeness=100.0, security=100.0, performance=100.0, maintainability=100.0)
    assert perfect_score.weighted_total() == 100.0

    zero_score = FiveAxisScores(correctness=0.0, completeness=0.0, security=0.0, performance=0.0, maintainability=0.0)
    assert zero_score.weighted_total() == 0.0


def test_five_axis_score_validation_bounds():
    """Verifies Pydantic score field validation rejects out-of-bound scores."""
    with pytest.raises(ValidationError):
        FiveAxisScores(correctness=105.0)

    with pytest.raises(ValidationError):
        FiveAxisScores(security=-10.0)


# ============================================================================
# Category 3: Critical Veto Tests (4 tests)
# ============================================================================

def test_critical_veto_security_breach_forces_failure(dual_cao):
    """Verifies hardcoded credential triggers immediate P0 veto and fails audit."""
    deliverables = {
        "title": "Auth Service",
        "code": "API_KEY = 'insecure plain token' # Hardcoded secret",
        "description": "Bypass authentication for testing",
    }
    result = dual_cao.audit(deliverables, "proj_veto_sec", round_num=1)
    assert result.passed is False
    assert len(result.p0_defects) >= 1
    assert any("security" in d.lower() or "credentials" in d.lower() or "token" in d.lower() for d in result.p0_defects)


def test_critical_veto_fatal_crash_exception_forces_failure(dual_cao):
    """Verifies unhandled fatal crash hazard triggers stability veto."""
    deliverables = {
        "title": "Data Pipeline",
        "code": "def process(): raise Unhandled Exception crash on null",
    }
    result = dual_cao.audit(deliverables, "proj_veto_crash", round_num=1)
    assert result.passed is False
    assert len(result.p0_defects) >= 1
    assert any("stability" in d.lower() or "crash" in d.lower() or "exception" in d.lower() for d in result.p0_defects)


def test_critical_veto_copyleft_gpl_contamination_forces_failure(dual_cao):
    """Verifies GPL/AGPL dependency triggers legal copyleft contamination veto."""
    deliverables = {
        "title": "Core Library",
        "dependencies": "Licensed under GPL-3.0 copyleft contamination terms",
    }
    result = dual_cao.audit(deliverables, "proj_veto_gpl", round_num=1)
    assert result.passed is False
    assert len(result.p0_defects) >= 1
    assert any("gpl" in d.lower() or "copyleft" in d.lower() or "legal" in d.lower() for d in result.p0_defects)


def test_multiple_critical_vetoes_aggregated(dual_cao):
    """Verifies multiple veto conditions are aggregated simultaneously."""
    deliverables = {
        "title": "Vulnerable Component",
        "secret": "password = hardcoded_secret",
        "dependency": "GNU General Public License v3 (AGPL)",
    }
    result = dual_cao.audit(deliverables, "proj_multi_veto", round_num=1)
    assert result.passed is False
    assert len(result.p0_defects) >= 2


# ============================================================================
# Category 4: Consensus Engine Tests (5 tests)
# ============================================================================

def test_consensus_engine_consolidates_duplicate_findings(dual_cao):
    """Verifies consensus consolidation merges near-duplicate defect descriptions."""
    items = [
        "Unauthenticated endpoint /api/goals allows unrestricted access.",
        "Unauthenticated endpoint /api/goals allows unrestricted access.",
        "Missing Bearer token validation on /api/goals endpoint.",
    ]
    deduped = dual_cao._deduplicate_strings(items)
    assert len(deduped) <= 2


def test_consensus_engine_separates_p0_p1_p2(dual_cao):
    """Verifies defects are properly segregated into P0, P1, and non-blocking P2 suggestions."""
    c_p0 = ["P0 Security leak detected in auth handler"]
    g_p0 = []
    c_p1 = ["P1 Missing retry backoff on network failure"]
    g_p1 = ["P2 Consider cleaner style using pattern matching"]

    p0, p1, p2, alt = dual_cao._reconcile_defects(c_p0, g_p0, c_p1, g_p1, [], [])
    assert len(p0) == 1
    assert "Security" in p0[0]
    assert len(p1) == 1
    assert "retry" in p1[0]
    assert len(p2) == 1
    assert "style" in p2[0].lower()


def test_consensus_engine_divergence_handling(dual_cao):
    """Verifies divergent perspectives are preserved under alternative views without failing audit."""
    c_report = {"score": 92.0, "perspective": "Claude architectural purity recommendation"}
    g_report = {"score": 90.0, "perspective": "GPT broad edge-case handling recommendation"}
    consensus = dual_cao.compare_audits(c_report, g_report)

    assert consensus["consensus_score"] == 91.0
    assert len(consensus["agreements"]) > 0
    assert len(consensus["disagreements"]) > 0
    assert "Claude perspective" in consensus["disagreements"][0]


def test_consensus_report_markdown_formatting(dual_cao, clean_deliverables):
    """Verifies generated markdown report matches standardized schema in CAO JD Section 6."""
    result = dual_cao.audit(clean_deliverables, "proj_md_check", round_num=1)
    md = result.consolidated_report

    assert "# 🔍 Alpha Consolidated Audit Report" in md
    assert "### 1. Executive Verdict" in md
    assert "### 2. Five-Axis Scorecard Summary" in md
    assert "### 3. Critical Findings (Must Fix)" in md
    assert "### 5. Consensus & Alternative Perspectives" in md
    assert "### 6. Sign-Off" in md
    assert "CAO-Claude" in md
    assert "CAO-ChatGPT" in md


def test_consensus_engine_compare_audits_contract(dual_cao):
    """Verifies compare_audits conforms to expected dictionary contract."""
    res = dual_cao.compare_audits({"score": 94.0}, {"score": 86.0})
    assert res["consensus_score"] == 90.0
    assert isinstance(res["agreements"], list)
    assert isinstance(res["disagreements"], list)


# ============================================================================
# Category 5: Strict 2-Round Escalation Cap Tests (5 tests)
# ============================================================================

def test_round1_failure_requests_revision_no_escalation(dual_cao):
    """Verifies Round 1 failure does not escalate to human founder, allowing revision."""
    deliverables = {"code": "Insecure plain token in auth header"}
    res = dual_cao.audit(deliverables, "proj_esc_r1", round_num=1)

    assert res.passed is False
    assert res.escalation_required is False
    assert res.round_num == 1
    assert res.verdict == "REVISE_REQUESTED"


def test_round2_pass_approves_deliverables(dual_cao, clean_deliverables):
    """Verifies Round 2 approval passes without escalation."""
    res = dual_cao.audit(clean_deliverables, "proj_esc_r2_pass", round_num=2)

    assert res.passed is True
    assert res.escalation_required is False
    assert res.round_num == 2
    assert res.verdict == "APPROVED"


def test_round2_failure_strictly_enforces_mandatory_escalation(dual_cao):
    """Verifies Round 2 failure strictly triggers mandatory human Founder escalation."""
    deliverables = {"code": "Insecure plain token in auth header"}
    res = dual_cao.audit(deliverables, "proj_esc_r2_fail", round_num=2)

    assert res.passed is False
    assert res.escalation_required is True
    assert res.round_num == 2
    assert res.verdict == "ESCALATED_TO_FOUNDER"
    assert res.escalation_ticket_path is not None
    assert "escalation_r2.json" in res.escalation_ticket_path


def test_zero_loop_runaway_prevention(dual_cao, clean_deliverables):
    """Verifies round_num >= 3 triggers immediate escalation guard and halts loop."""
    res = dual_cao.audit(clean_deliverables, "proj_loop_guard", round_num=3)

    assert res.escalation_required is True
    assert res.passed is False
    assert res.round_num == 3
    assert any("loop" in d.lower() for d in res.p0_defects)


def test_vault_escalation_ticket_payload_structure(test_vault, test_router):
    """Verifies escalation ticket and MCP user_escalate payloads have complete schemas."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    res = cao.audit({"code": "Insecure plain token"}, "proj_ticket_check", round_num=2)

    assert res.escalation_required is True
    assert res.user_escalate_payload is not None
    mcp_payload = res.user_escalate_payload
    assert mcp_payload["project_id"] == "proj_ticket_check"
    assert mcp_payload["from_agent"] == "CAO"
    assert "question" in mcp_payload
    assert "options" in mcp_payload
    assert mcp_payload["urgency"] == "high"

    # Verify Vault file ticket was written
    ticket_file = test_vault.vault_root / "projects" / "proj_ticket_check" / "audit" / "escalation_r2.json"
    assert ticket_file.exists()
    ticket_content = json.loads(ticket_file.read_text(encoding="utf-8"))
    assert ticket_content["project_id"] == "proj_ticket_check"
    assert ticket_content["verdict"] == "ESCALATED_TO_FOUNDER"


# ============================================================================
# Category 6: Fault Tolerance & MockLLM Resilience Tests (4 tests)
# ============================================================================

def test_dual_cao_headless_fallback_without_model_router(test_vault, clean_deliverables):
    """Verifies DualCAO operates reliably in headless mode when model_router is None."""
    cao = DualCAO(vault_manager=test_vault, model_router=None)
    res = cao.audit(clean_deliverables, "proj_headless_mr", round_num=1)
    assert res.passed is True
    assert res.claude_score >= 85.0
    assert res.gpt_score >= 85.0


def test_dual_cao_headless_fallback_without_vault_manager(test_router, clean_deliverables):
    """Verifies DualCAO operates in-memory when vault_manager is None."""
    cao = DualCAO(vault_manager=None, model_router=test_router)
    res = cao.audit(clean_deliverables, "proj_headless_vm", round_num=1)
    assert res.passed is True
    assert res.escalation_ticket_path is None


def test_dual_cao_mock_llm_json_parsing_resilience():
    """Verifies robust JSON extraction handles markdown fences, raw text, and malformed strings."""
    agent = CAOClaudeAgent()

    # 1. Markdown code block
    fenced = "```json\n{\"axes\": {\"correctness\": {\"score\": 95.0}}}\n```"
    parsed = agent._extract_json(fenced)
    assert parsed is not None
    assert parsed["axes"]["correctness"]["score"] == 95.0

    # 2. Text with embedded JSON
    embedded = "Analysis complete: {\"axes\": {\"security_safety\": {\"score\": 92.0}}} - Verified."
    parsed = agent._extract_json(embedded)
    assert parsed is not None
    assert parsed["axes"]["security_safety"]["score"] == 92.0

    # 3. Plain text from MockLLM without JSON
    mock_str = "[claude-3-5-sonnet] Output for CAO-Claude: Verified response for task 'audit'."
    parsed = agent._extract_json(mock_str)
    assert parsed is None  # Handled safely without raising JSONDecodeError


def test_dual_cao_empty_deliverables_handling(dual_cao):
    """Verifies empty deliverables dictionary {} is handled safely without crashing."""
    res = dual_cao.audit({}, "proj_empty_safe", round_num=1)
    assert res is not None
    assert res.passed is True  # Handled safely per boundary test contract
    assert res.claude_score >= 85.0
    assert res.gpt_score >= 85.0


# ============================================================================
# Category 7: Multi-Agent Integration Tests (4 tests)
# ============================================================================

def test_dual_cao_audits_cto_architecture_spec(dual_cao, test_vault, test_router):
    """Verifies Dual CAO audits real deliverables produced by CTOAgent."""
    cto = CTOAgent(vault_manager=test_vault, model_router=test_router)
    spec_result = cto.generate_architecture_spec(
        project_id="proj_cto_test",
        title="Payment Gateway Integration",
        requirements=["Zero exposed credentials", "Idempotent payment capture", "Pydantic validation"],
    )
    audit_res = dual_cao.audit(spec_result, "proj_cto_test", round_num=1)
    assert audit_res.passed is True
    assert len(audit_res.p0_defects) == 0


def test_dual_cao_audits_cfo_token_budget(dual_cao, test_vault, test_router):
    """Verifies Dual CAO audits financial token model produced by CFOAgent."""
    cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
    budget = cfo.model_unit_economics(
        project_id="proj_cfo_test",
        expected_queries_monthly=50000,
        user_count=500,
    )
    audit_res = dual_cao.audit({"token_budget": budget}, "proj_cfo_test", round_num=1)
    assert audit_res.passed is True
    assert len(audit_res.p0_defects) == 0


def test_dual_cao_audits_clo_permissive_license(dual_cao, test_vault, test_router):
    """Verifies Dual CAO audits licensing review produced by CLOAgent."""
    clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
    license_review = clo.audit_license_compliance(
        dependencies=[
            {"name": "fastapi", "license": "MIT"},
            {"name": "pydantic", "license": "MIT"},
            {"name": "chromadb", "license": "Apache-2.0"},
            {"name": "sqlite3", "license": "Public Domain"},
        ],
        project_id="proj_clo_test",
    )
    audit_res = dual_cao.audit({"license_review": license_review}, "proj_clo_test", round_num=1)
    assert audit_res.passed is True
    assert len(audit_res.p0_defects) == 0


def test_dual_cao_audits_cpo_product_requirements(dual_cao, test_vault, test_router):
    """Verifies Dual CAO audits PRD produced by CPOAgent."""
    cpo = CPOAgent(vault_manager=test_vault, model_router=test_router)
    prd = cpo.generate_prd(
        project_id="proj_cpo_test",
        title="Mobile Dashboard",
        description="Executive dashboard featuring live progress bars and Archify living canvas.",
    )
    audit_res = dual_cao.audit({"prd": prd}, "proj_cpo_test", round_num=1)
    assert audit_res.passed is True
    assert len(audit_res.p0_defects) == 0



# ============================================================================
# Category 8: Registry Factory Wiring & Subsystem Integration Tests (6 tests)
# ============================================================================

def test_registry_registers_cao_factories(test_registry):
    """Verifies CAO factories are registered in AgentRegistry."""
    factories = test_registry._factories
    assert "CAO" in factories
    assert "CAO-CLAUDE" in factories
    assert "CAO-CHATGPT" in factories
    assert "DUALCAO" in factories
    assert "CAO-AUDIT-GATE" in factories


def test_registry_load_all_instantiates_cao_claude_specialized_subclass(test_registry):
    """Verifies registry instantiates CAO-Claude as specialized CAOClaudeAgent."""
    test_registry.load_all()
    agent = test_registry.get("CAO-Claude")
    assert agent is not None
    assert isinstance(agent, CAOClaudeAgent)
    assert isinstance(agent, CAOAgent)
    assert isinstance(agent, BaseExecutiveAgent)


def test_registry_load_all_instantiates_cao_chatgpt_specialized_subclass(test_registry):
    """Verifies registry instantiates CAO-ChatGPT as specialized CAOGPTAgent."""
    test_registry.load_all()
    agent = test_registry.get("CAO-ChatGPT")
    assert agent is not None
    assert isinstance(agent, CAOGPTAgent)
    assert isinstance(agent, CAOAgent)
    assert isinstance(agent, BaseExecutiveAgent)


def test_registry_cao_alias_resolution_matrix(test_registry):
    """Verifies all CAO aliases resolve to the appropriate specialized instances."""
    test_registry.load_all()

    claude_inst = test_registry.get("CAO-Claude")
    gpt_inst = test_registry.get("CAO-ChatGPT")

    assert test_registry.get("CAO") is claude_inst
    assert test_registry.get("CAO-C") is claude_inst
    assert test_registry.get("CAO-G") is gpt_inst
    assert test_registry.get_by_role("Chief Audit Officer") is claude_inst
    assert test_registry.get_by_role("Chief Audit Officer Claude") is claude_inst
    assert test_registry.get_by_role("Chief Audit Officer GPT") is gpt_inst


def test_registry_get_dual_cao_or_audit_gate(test_registry):
    """Verifies DualCAO is instantiated in registry with convenience accessor."""
    test_registry.load_all()

    dual_cao = test_registry.get_dual_cao()
    assert dual_cao is not None
    assert isinstance(dual_cao, DualCAO)
    assert test_registry.get("DualCAO") is dual_cao
    assert test_registry.get("CAOAuditGate") is dual_cao
    assert dual_cao.claude_agent is test_registry.get("CAO-Claude")
    assert dual_cao.gpt_agent is test_registry.get("CAO-ChatGPT")


def test_clean_exports_in_backend_agents_init():
    """Verifies clean subsystem exports in backend.agents.__all__."""
    import backend.agents as ba

    expected_symbols = [
        "CAOAgent",
        "CAOClaudeAgent",
        "CAOGPTAgent",
        "DualCAO",
        "CAOAuditGate",
        "CAOAuditResult",
        "FiveAxisScores",
        "FiveAxisScorecard",
        "AuditFinding",
        "SingleAuditReport",
        "AuditReport",
        "ConsolidatedFindings",
        "ConsolidatedAuditReport",
        "ConsolidatedDefect",
    ]
    for sym in expected_symbols:
        assert hasattr(ba, sym), f"Missing symbol {sym} in backend.agents"
        assert sym in ba.__all__, f"Symbol {sym} missing from backend.agents.__all__"
