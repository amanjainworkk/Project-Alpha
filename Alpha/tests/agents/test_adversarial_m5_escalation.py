"""tests/agents/test_adversarial_m5_escalation.py - Adversarial Stress & Concurrency Suite for Milestone 5.

Authored by: challenger_m5_2 (Empirical Challenger)
Target: Alpha/backend/agents/cao.py (Dual CAO Escalation Cap, Loop Prevention, Concurrency, Consensus Conflict)

Adversarial Stress Matrix:
1. Strict 2-Round Escalation Cap State Machine:
   - Round 1 failure: passed=False, escalation_required=False, audit persisted
   - Round 2 revision pass: passed=True, escalation_required=False
   - Round 2 revision failure: passed=False, escalation_required=True, Vault SQLite ticket, founder brief, MCP payload
   - Round 3, 4, 10, 100 loop runaway prevention: immediate termination with escalation_required=True
   - String and boundary round inputs: "1", "2", "3", "100", float rounds
2. Concurrency & Thread-Safety:
   - Simultaneous audits of 30 distinct projects
   - Concurrent audits on the identical project_id
   - Concurrent Round 2 failures competing for SQLite vault_decisions writes
   - Concurrent mixed calls to audit() and compare_audits()
   - Deadlock absence and clean transaction isolation
3. Consensus Engine Conflict Stress:
   - Diametric opposition: Claude 100% vs GPT 0% with fatal P0 veto
   - Reverse diametric opposition: GPT 100% vs Claude 0% with fatal P0 veto
   - Score threshold conflict: Claude 95% vs GPT 84.9% (no P0 veto)
   - P2 stylistic segregation: naming conventions and code formatting NEVER block release
   - Defect deduplication across models
   - Boundary condition at 85.0% exact threshold
4. Vault Confinement & Integrity:
   - Strict confinement inside projects/{project_id}/audit/
   - Brief and ticket contents validated
"""

import concurrent.futures
import gc
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.agents.agent_registry import reset_agent_registry
from backend.agents.cao import (
    AxisScore,
    CAOAgent,
    CAOAuditResult,
    CAOClaudeAgent,
    CAOGPTAgent,
    DualCAO,
    FiveAxisScorecard,
    SingleAuditReport,
)
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import AccessDeniedError, VaultManager


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
    """Create isolated test VaultManager with clean teardown."""
    vm = VaultManager(
        vault_root=tmp_path / "vault",
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
    )
    yield vm
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
def dual_cao(test_vault: VaultManager, test_router: ModelRouter) -> DualCAO:
    """Create a standard DualCAO instance."""
    return DualCAO(vault_manager=test_vault, model_router=test_router)


@pytest.fixture
def clean_deliverables() -> Dict[str, Any]:
    """Flawless deliverables that pass 5-axis audit."""
    return {
        "project_id": "proj_clean_adv",
        "tech_spec": "Modular architecture following KISS and decoupled SOLID interfaces.",
        "prd": "Complete requirements specification with MoSCoW prioritization.",
        "code": "def process_data(item: str) -> bool:\n    return bool(item)\n",
        "tests": "def test_process():\n    assert process_data('valid') is True\n",
        "security": "Enforces strict token auth. Zero plaintext secrets.",
        "licensing": "Licensed under permissive MIT license.",
    }


# ============================================================================
# Helpers for Mock CAO Personas
# ============================================================================

def make_mock_scorecard(score: float, p0_reasons: List[str] = None) -> FiveAxisScorecard:
    """Construct a synthetic FiveAxisScorecard with specified score and vetoes."""
    p0_reasons = p0_reasons or []
    has_veto = len(p0_reasons) > 0
    raw = score
    axes = {}
    for name, weight in CAOAgent.AXIS_WEIGHTS.items():
        axes[name] = AxisScore(
            axis_name=name,
            weight=weight,
            raw_score=raw,
            weighted_score=round(raw * weight, 2),
            status="FAIL" if (raw < 85.0 or has_veto) else "PASS",
            findings=p0_reasons if has_veto else [],
        )
    return FiveAxisScorecard(
        correctness=axes["correctness"],
        completeness=axes["completeness"],
        security_safety=axes["security_safety"],
        performance_scalability=axes["performance_scalability"],
        maintainability_architecture=axes["maintainability_architecture"],
        total_score=score,
        passed=(score >= 85.0 and not has_veto),
        veto_triggered=has_veto,
        veto_reasons=p0_reasons,
    )


class SyntheticCAOAgent(CAOAgent):
    """Custom CAO instance with fixed score, defects, and opinions."""

    def __init__(
        self,
        instance: str = "claude",
        score: float = 90.0,
        p0_defects: List[str] = None,
        p1_defects: List[str] = None,
        p2_opinions: List[str] = None,
        alternatives: List[str] = None,
    ):
        role = "CAO-Claude" if instance == "claude" else "CAO-ChatGPT"
        super().__init__(agent_id=role, role=role, instance=instance)
        self._score = score
        self._p0 = p0_defects or []
        self._p1 = p1_defects or []
        self._p2 = p2_opinions or []
        self._alt = alternatives or []

    def evaluate_deliverable(self, deliverables: Dict[str, Any], project_id: str, round_num: int = 1) -> SingleAuditReport:
        card = make_mock_scorecard(self._score, self._p0)
        p1_list = list(self._p1)
        if self._p2:
            p1_list.extend(self._p2)
        return SingleAuditReport(
            audit_id=f"synth_{self.instance}_{round_num}",
            instance=self.role,
            assigned_model=self.assigned_model,
            scorecard=card,
            p0_defects=list(self._p0),
            p1_defects=p1_list,
            alternative_perspectives=list(self._alt),
            verdict="APPROVED" if card.passed else "REJECTED",
        )


# ============================================================================
# 1. Strict 2-Round Escalation Cap State Machine Tests
# ============================================================================

def test_state_machine_round1_failure_allows_revision(test_vault, test_router):
    """Round 1 failure MUST NOT escalate, verdict REVISE_REQUESTED, files written."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    flawed = {"code": "API_KEY = 'insecure plain token' # Hardcoded secret"}

    res = cao.audit(flawed, "proj_sm_r1", round_num=1)

    assert res.passed is False
    assert res.escalation_required is False
    assert res.round_num == 1
    assert res.verdict == "REVISE_REQUESTED"

    # Verify Round 1 audit artifacts persisted under projects/{id}/audit/
    r1_json_path = test_vault.vault_root / "projects" / "proj_sm_r1" / "audit" / "round_1_audit.json"
    r1_md_path = test_vault.vault_root / "projects" / "proj_sm_r1" / "audit" / "round_1_audit.md"
    assert r1_json_path.exists()
    assert r1_md_path.exists()

    content = json.loads(r1_json_path.read_text(encoding="utf-8"))
    assert content["project_id"] == "proj_sm_r1"
    assert content["round_num"] == 1
    assert content["passed"] is False
    assert content["escalation_required"] is False

    # Escalation ticket MUST NOT exist for Round 1
    esc_file = test_vault.vault_root / "projects" / "proj_sm_r1" / "audit" / "escalation_r2.json"
    assert not esc_file.exists()


def test_state_machine_round2_revision_pass(test_vault, test_router, clean_deliverables):
    """Round 2 pass MUST approve release and NOT escalate."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    res = cao.audit(clean_deliverables, "proj_sm_r2_pass", round_num=2)

    assert res.passed is True
    assert res.escalation_required is False
    assert res.round_num == 2
    assert res.verdict == "APPROVED"
    assert len(res.p0_defects) == 0

    r2_json_path = test_vault.vault_root / "projects" / "proj_sm_r2_pass" / "audit" / "round_2_audit.json"
    assert r2_json_path.exists()
    content = json.loads(r2_json_path.read_text(encoding="utf-8"))
    assert content["passed"] is True
    assert content["escalation_required"] is False


def test_state_machine_round2_failure_escalates_and_persists_all_artifacts(test_vault, test_router):
    """Round 2 failure MUST trigger mandatory escalation, ticket, brief, MCP payload, SQLite record."""
    # Seed thread and agent in SQLite store to ensure FK satisfaction
    test_vault.sqlite.upsert_thread({
        "thread_id": "thread_proj_sm_r2_fail_main",
        "project_id": "proj_sm_r2_fail",
        "project_name": "Project Escalation Test",
        "owner_agent": "CEO",
    })

    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    flawed = {"code": "def run(): crash on null unhandled exception"}

    res = cao.audit(flawed, "proj_sm_r2_fail", round_num=2)

    assert res.passed is False
    assert res.escalation_required is True
    assert res.round_num == 2
    assert res.verdict == "ESCALATED_TO_FOUNDER"
    assert len(res.p0_defects) >= 1

    # 1. Check escalation ticket file
    ticket_file = test_vault.vault_root / "projects" / "proj_sm_r2_fail" / "audit" / "escalation_r2.json"
    assert ticket_file.exists()
    ticket_data = json.loads(ticket_file.read_text(encoding="utf-8"))
    assert ticket_data["project_id"] == "proj_sm_r2_fail"
    assert ticket_data["verdict"] == "ESCALATED_TO_FOUNDER"
    assert "decision_options" in ticket_data

    # 2. Check founder escalation brief markdown
    brief_file = test_vault.vault_root / "projects" / "proj_sm_r2_fail" / "audit" / "founder_escalation_brief.md"
    assert brief_file.exists()
    brief_content = brief_file.read_text(encoding="utf-8")
    assert "HARD STOP: Dual CAO Audit Escalation" in brief_content
    assert "Options for Founder (Aman Jain)" in brief_content

    # 3. Check MCP user_escalate payload
    assert res.user_escalate_payload is not None
    mcp = res.user_escalate_payload
    assert mcp["project_id"] == "proj_sm_r2_fail"
    assert mcp["from_agent"] == "CAO"
    assert mcp["urgency"] == "high"
    assert len(mcp["options"]) == 3

    # 4. Check Vault SQLite decision ticket inserted
    with test_vault.sqlite._lock:
        cur = test_vault.sqlite._conn.cursor()
        cur.execute("SELECT * FROM vault_decisions WHERE project_id = ?", ("proj_sm_r2_fail",))
        row = cur.fetchone()
        assert row is not None
        rec = dict(row)
        assert rec["decision_id"] == "dec_esc_proj_sm_r2_fail_r2"
        assert rec["decision_type"] == "FOUNDER_ESCALATION"
        assert rec["risk_level"] == "critical"
        assert rec["cao_approved"] in (0, False)
        assert "FOUNDER" in rec["decision_summary"].upper() or "HALT" in rec["decision_summary"].upper()


@pytest.mark.parametrize("runaway_round", [3, 4, 10, 100])
def test_state_machine_round3_plus_loop_runaway_prevention(test_vault, test_router, clean_deliverables, runaway_round):
    """Any round_num >= 3 MUST immediately halt with escalation_required=True and zero infinite loop."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    res = cao.audit(clean_deliverables, f"proj_runaway_{runaway_round}", round_num=runaway_round)

    assert res.passed is False
    assert res.escalation_required is True
    assert res.round_num == runaway_round
    assert res.verdict == "ESCALATED_TO_FOUNDER"
    assert any("loop" in d.lower() for d in res.p0_defects)
    assert res.claude_score == 60.0
    assert res.gpt_score == 60.0

    # Verify escalation ticket created
    esc_file = test_vault.vault_root / "projects" / f"proj_runaway_{runaway_round}" / "audit" / "escalation_r2.json"
    assert esc_file.exists()


@pytest.mark.parametrize("round_input,expected_effective", [("1", 1), ("2", 2), ("3", 3), ("100", 100), (2.0, 2)])
def test_state_machine_string_and_float_round_conversion(test_vault, test_router, clean_deliverables, round_input, expected_effective):
    """String and float round numbers are safely coerced to integer without crashing."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    res = cao.audit(clean_deliverables, f"proj_round_conv_{expected_effective}", round_num=round_input)
    assert res.round_num == expected_effective
    if expected_effective >= 3:
        assert res.escalation_required is True
        assert res.passed is False


# ============================================================================
# 2. Concurrency & Thread-Safety Tests
# ============================================================================

def test_concurrency_simultaneous_audits_across_multiple_projects(test_vault, test_router, clean_deliverables):
    """Simultaneous audits of 30 distinct projects across 8 threads execute cleanly without errors."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    def audit_task(idx: int) -> CAOAuditResult:
        is_failing = (idx % 2 == 1)
        payload = {"code": "insecure plain token"} if is_failing else clean_deliverables
        r_num = 2 if is_failing else 1
        return cao.audit(payload, f"proj_conc_multi_{idx}", round_num=r_num)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(audit_task, i) for i in range(30)]
        results = [f.result(timeout=15.0) for f in futures]

    assert len(results) == 30
    for idx, r in enumerate(results):
        if idx % 2 == 1:
            assert r.passed is False
            assert r.escalation_required is True
            assert r.verdict == "ESCALATED_TO_FOUNDER"
        else:
            assert r.passed is True
            assert r.escalation_required is False
            assert r.verdict == "APPROVED"


def test_concurrency_simultaneous_audits_on_identical_project(test_vault, test_router, clean_deliverables):
    """20 threads auditing the EXACT SAME project_id concurrently do not deadlock or corrupt state."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    def single_proj_task(idx: int) -> CAOAuditResult:
        # Alternating passes and revisions
        round_val = 1 if (idx % 2 == 0) else 2
        payload = clean_deliverables if (idx % 2 == 0) else {"code": "insecure plain token"}
        return cao.audit(payload, "proj_single_contested", round_num=round_val)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(single_proj_task, i) for i in range(20)]
        results = [f.result(timeout=15.0) for f in futures]

    assert len(results) == 20
    # Audit history captured all 20 calls
    assert len(cao.audit_history) == 20


def test_concurrency_simultaneous_round2_failures_sqlite_transactions(test_vault, test_router):
    """20 concurrent Round 2 failures competing for SQLite vault_decisions writes execute atomically."""
    # Pre-seed 20 project threads so foreign keys succeed
    for i in range(20):
        test_vault.sqlite.upsert_thread({
            "thread_id": f"thread_proj_conc_sq_{i}_main",
            "project_id": f"proj_conc_sq_{i}",
            "project_name": f"Concurrent Project {i}",
            "owner_agent": "CEO",
        })

    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    def failing_round2_task(i: int) -> CAOAuditResult:
        return cao.audit({"code": "insecure plain token"}, f"proj_conc_sq_{i}", round_num=2)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(failing_round2_task, i) for i in range(20)]
        results = [f.result(timeout=15.0) for f in futures]

    assert len(results) == 20
    for r in results:
        assert r.escalation_required is True
        assert r.passed is False

    # Verify all 20 records exist in SQLite vault_decisions table
    with test_vault.sqlite._lock:
        cur = test_vault.sqlite._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vault_decisions WHERE decision_type = 'FOUNDER_ESCALATION'")
        count = cur.fetchone()[0]
        assert count == 20, f"Expected 20 SQLite decision records, found {count}"


def test_concurrency_mixed_audit_and_compare_audits_calls(test_vault, test_router, clean_deliverables):
    """Interleaved concurrent calls to audit() and compare_audits() operate safely in parallel."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    def mixed_task(i: int) -> Any:
        if i % 2 == 0:
            return cao.audit(clean_deliverables, f"proj_mixed_{i}", round_num=1)
        else:
            return cao.compare_audits(
                {"score": 92.0, "perspective": f"Claude view {i}"},
                {"score": 88.0, "perspective": f"GPT view {i}"},
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(mixed_task, i) for i in range(30)]
        results = [f.result(timeout=15.0) for f in futures]

    assert len(results) == 30
    for i, res in enumerate(results):
        if i % 2 == 0:
            assert isinstance(res, CAOAuditResult)
            assert res.passed is True
        else:
            assert isinstance(res, dict)
            assert res["consensus_score"] == 90.0
            assert "agreements" in res


# ============================================================================
# 3. Consensus Engine Conflict Stress Tests
# ============================================================================

def test_consensus_diametrically_opposed_claude_100_gpt_0_p0_veto():
    """Claude gives 100%, GPT gives 0% with fatal P0 flaw: P0 veto MUST win and block release."""
    c_agent = SyntheticCAOAgent(instance="claude", score=100.0)
    g_agent = SyntheticCAOAgent(
        instance="gpt",
        score=0.0,
        p0_defects=["P0 Remote Code Execution: unauthenticated debug shell open on port 8080"],
    )

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_diametric_1", round_num=1)

    assert res.passed is False
    assert res.claude_score == 100.0
    assert res.gpt_score == 0.0
    assert len(res.p0_defects) == 1
    assert "Remote Code Execution" in res.p0_defects[0]
    assert res.verdict == "REVISE_REQUESTED"
    assert res.escalation_required is False


def test_consensus_reverse_diametrically_opposed_gpt_100_claude_0_p0_veto():
    """GPT gives 100%, Claude gives 0% with fatal P0 flaw: Claude P0 veto MUST win and block release."""
    c_agent = SyntheticCAOAgent(
        instance="claude",
        score=0.0,
        p0_defects=["P0 Security Veto: Hardcoded production secret in auth middleware"],
    )
    g_agent = SyntheticCAOAgent(instance="gpt", score=100.0)

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_diametric_2", round_num=1)

    assert res.passed is False
    assert res.claude_score == 0.0
    assert res.gpt_score == 100.0
    assert len(res.p0_defects) == 1
    assert "Hardcoded production secret" in res.p0_defects[0]


def test_consensus_score_divergence_below_85_threshold_fails_without_veto():
    """Claude gives 95.0%, GPT gives 84.9% (no P0 veto): failure to meet 85% bar MUST block release."""
    c_agent = SyntheticCAOAgent(instance="claude", score=95.0)
    g_agent = SyntheticCAOAgent(instance="gpt", score=84.9)

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_score_div", round_num=1)

    assert res.passed is False
    assert res.claude_score == 95.0
    assert res.gpt_score == 84.9
    assert len(res.p0_defects) == 0
    assert res.verdict == "REVISE_REQUESTED"


def test_consensus_exact_85_threshold_boundary():
    """Both models give exactly 85.0% with zero P0: release MUST pass."""
    c_agent = SyntheticCAOAgent(instance="claude", score=85.0)
    g_agent = SyntheticCAOAgent(instance="gpt", score=85.0)

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_boundary_85", round_num=1)

    assert res.passed is True
    assert res.claude_score == 85.0
    assert res.gpt_score == 85.0
    assert res.verdict == "APPROVED"


def test_consensus_p2_stylistic_opinions_segregated_and_never_block():
    """Stylistic naming conventions and formatting suggestions are segregated to P2 and NEVER block release."""
    c_agent = SyntheticCAOAgent(
        instance="claude",
        score=92.0,
        p2_opinions=[
            "Consider cleaner style using pattern matching",
            "Formatting suggestion: adhere to black 88-char line limits",
        ],
        alternatives=["Claude favors functional decomposition"],
    )
    g_agent = SyntheticCAOAgent(
        instance="gpt",
        score=94.0,
        p2_opinions=[
            "Naming convention: prefer snake_case over camelCase for internal variables",
            "Style issue: simplify list comprehension",
        ],
        alternatives=["GPT favors explicit procedural iteration"],
    )

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_p2_non_blocking", round_num=1)

    # MUST pass because scores are >= 85.0 and no P0 defects exist
    assert res.passed is True
    assert res.escalation_required is False
    assert res.verdict == "APPROVED"
    assert len(res.p0_defects) == 0
    assert len(res.p1_defects) == 0

    # All 4 stylistic suggestions segregated into p2_suggestions
    assert len(res.p2_suggestions) == 4
    for sug in res.p2_suggestions:
        assert any(term in sug.lower() for term in ["style", "naming", "formatting", "consider"])

    # Markdown report contains Section 4
    assert "### 4. Stylistic Opinions & Minor Suggestions (P2 - Non-blocking)" in res.consolidated_report


def test_consensus_deduplicates_identical_and_near_identical_defects():
    """Concurring defects reported with identical or high token overlap are deduplicated."""
    c_agent = SyntheticCAOAgent(
        instance="claude",
        score=70.0,
        p0_defects=["Critical vulnerability: unauthenticated endpoint /api/v1/admin exposes admin console"],
        p1_defects=["Missing rate limiting on authentication endpoint"],
    )
    g_agent = SyntheticCAOAgent(
        instance="gpt",
        score=72.0,
        p0_defects=["Critical vulnerability: unauthenticated endpoint /api/v1/admin exposes admin console"],
        p1_defects=["Missing rate limit on authentication endpoint"],
    )

    cao = DualCAO(claude_agent=c_agent, gpt_agent=g_agent)
    res = cao.audit({}, "proj_dedup_test", round_num=1)

    # Both P0 and P1 should be deduplicated to 1 each
    assert len(res.p0_defects) == 1
    assert "unauthenticated endpoint" in res.p0_defects[0]
    assert len(res.p1_defects) == 1
    assert "rate limit" in res.p1_defects[0].lower()


# ============================================================================
# 4. Vault Confinement & Audit Artifact Integrity Tests
# ============================================================================

def test_vault_confinement_cao_cannot_write_outside_projects_audit(test_vault):
    """CAO is restricted by Vault RBAC and cannot write to root, agents/, or company/ paths."""
    with pytest.raises(AccessDeniedError):
        test_vault.write("company/identity.json", {"name": "Hacked"}, agent_id="CAO")

    with pytest.raises(AccessDeniedError):
        test_vault.write("agents/CEO/memory.json", {"compromised": True}, agent_id="CAO")

    with pytest.raises(AccessDeniedError):
        test_vault.write("projects/proj_x/deliverables/code.py", {"bad": True}, agent_id="CAO")

    # But writing to projects/{id}/audit/ is strictly permitted
    permitted = test_vault.write(
        "projects/proj_x/audit/valid_audit.json",
        {"audit_passed": True},
        agent_id="CAO",
    )
    assert permitted is True
