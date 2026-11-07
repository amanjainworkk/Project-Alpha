"""tests/agents/test_adversarial_m4_governance.py

Adversarial Stress Test Suite for Project Alpha Milestone 4:
Finance, Governance, People, Legal, and Multi-Breach Subsystems.

Target Classes:
1. CFOAgent (Alpha/backend/agents/cfo.py)
2. CLOAgent (Alpha/backend/agents/clo.py)
3. CEOAgent (Alpha/backend/agents/ceo.py) - Multi-Breach Tribunal (VULN-M3-01)
4. CHROAgent (Alpha/backend/agents/chro.py)
5. CSOAgent (Alpha/backend/agents/cso.py)

Empirical verification suite executing adversarial vectors, boundary conditions,
and edge-case stress harnesses against concrete agent implementations.
"""

from pathlib import Path
from typing import Any, Dict, List
import pytest

from backend.agents.agent_registry import AgentRegistry, reset_agent_registry
from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.ceo import CEOAgent
from backend.agents.cfo import CFOAgent
from backend.agents.chro import CHROAgent
from backend.agents.clo import CLOAgent
from backend.agents.cso import CSOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


# ============================================================================
# Shared Fixtures
# ============================================================================

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
def registry(test_vault: VaultManager, test_router: ModelRouter) -> AgentRegistry:
    reset_agent_registry()
    reg = AgentRegistry(vault_manager=test_vault, model_router=test_router)
    reg.load_all()
    return reg


# ============================================================================
# Vector 1: CFO Budget Breach Escalation Contract
# ============================================================================

class TestCFOBudgetBreachEscalation:
    """Stress-test audit_spending across negative spend, 0 spend, 79%, 80%,

    exact cap (100%), boundary overruns, and massive overruns ($1,000 on $500 cap).
    Verify strict contract matching CEOAgent.synthesize ingestion requirements.
    """

    @pytest.mark.parametrize(
        "spend_value,expected_status,expected_breach,expected_escalation",
        [
            (-150.0, "within_budget", False, False),
            (0.0, "within_budget", False, False),
            (395.0, "within_budget", False, False),       # 79% of $500 ceiling
            (400.0, "warning_80_percent", False, False),  # Exact 80% boundary
            (450.0, "warning_80_percent", False, False),  # 90%
            (500.0, "warning_80_percent", False, False),  # Exact 100% ceiling (not yet over)
            (500.01, "over_budget", True, True),          # Minimal fractional overrun
            (501.0, "over_budget", True, True),           # $1 overrun
            (1000.0, "over_budget", True, True),          # Massive overrun ($1,000 on $500 cap)
            (15000.0, "over_budget", True, True),         # 30x overrun
        ],
    )
    def test_cfo_audit_spending_boundary_matrix(
        self,
        spend_value: float,
        expected_status: str,
        expected_breach: bool,
        expected_escalation: bool,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        res = cfo.audit_spending(
            project_id="proj_budget_stress",
            actual_spend_data={"total_spend": spend_value},
            budget_ceiling=500.0,
        )

        assert res["status"] == expected_status
        assert res["budget_breach"] is expected_breach
        assert res["founder_escalation_required"] is expected_escalation
        assert res["total_spend"] == spend_value
        assert res["budget_ceiling"] == 500.0
        assert isinstance(res["breach_details"], str)
        assert len(res["breach_details"]) > 0
        assert isinstance(res["recommendations"], list)
        assert len(res["recommendations"]) >= 1

    def test_cfo_audit_spending_alternate_key_name(self, test_vault: VaultManager, test_router: ModelRouter):
        """Verify fallback to 'spend' key when 'total_spend' is absent."""
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        res = cfo.audit_spending(
            project_id="proj_alt_key",
            actual_spend_data={"spend": 1200.0},
            budget_ceiling=500.0,
        )
        assert res["budget_breach"] is True
        assert res["status"] == "over_budget"
        assert res["total_spend"] == 1200.0

    def test_cfo_audit_spending_zero_ceiling_safeguard(self, test_vault: VaultManager, test_router: ModelRouter):
        """Verify zero budget ceiling does not trigger ZeroDivisionError."""
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        res_zero = cfo.audit_spending(
            project_id="proj_zero_ceiling",
            actual_spend_data={"total_spend": 0.0},
            budget_ceiling=0.0,
        )
        assert res_zero["status"] == "within_budget"

        res_over = cfo.audit_spending(
            project_id="proj_zero_ceiling",
            actual_spend_data={"total_spend": 10.0},
            budget_ceiling=0.0,
        )
        assert res_over["budget_breach"] is True
        assert res_over["status"] == "over_budget"

    def test_cfo_breach_persists_to_vault_and_memory(self, test_vault: VaultManager, test_router: ModelRouter):
        """Verify audit report and decision memory are written to vault upon breach."""
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        pid = "proj_cfo_vault"
        res = cfo.audit_spending(
            project_id=pid,
            actual_spend_data={"total_spend": 800.0},
            budget_ceiling=500.0,
        )
        assert res["budget_breach"] is True

        # Read back from vault
        saved = test_vault.read(f"projects/{pid}/deliverables/budget_audit.json")
        assert saved is not None
        assert saved["budget_breach"] is True
        assert saved["total_spend"] == 800.0

        # Verify episodic memory recorded in agent
        assert len(cfo.working_memory) > 0
        latest_mem = cfo.working_memory[-1]
        assert "BUDGET BREACH" in latest_mem["content"]


# ============================================================================
# Vector 2: CLO Copyleft / GPL Contamination Defense
# ============================================================================

class TestCLOCopyleftGPLDefense:
    """Stress-test audit_license_compliance against permutations of license strings:

    "GPLv3", "AGPL-3.0", "GPL-2.0", "LGPL", "MIT", "Apache 2.0", "Proprietary",
    mixed case, whitespace, etc.
    Verify that ANY copyleft/GPL package triggers risk="critical", license_violation=True,
    veto_issued=True, status="escalation_required", and clear remediation advice.
    """

    @pytest.mark.parametrize(
        "bad_license",
        [
            "GPLv3",
            "gplv3",
            "GPLV3",
            "  GPLv3  ",
            "AGPL-3.0",
            "agpl-3.0",
            "  Agpl-3.0 ",
            "GPL-2.0",
            "gpl-2.0",
            "GPL",
            "gpl",
            "AGPL",
            "agpl",
            "LGPL",
            "lgpl",
            "LGPLv3",
            "lgpl-3.0",
            "SSPL",
            "sspl",
            "non-commercial",
            "GPL-3.0-only",
            "GNU General Public License v3 (GPLv3)",
        ],
    )
    def test_clo_copyleft_permutations_trigger_critical_veto(
        self,
        bad_license: str,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
        res = clo.audit_license_compliance(
            dependencies=[
                {"name": "clean-fastapi", "license": "MIT"},
                {"name": "tainted-dep", "license": bad_license},
            ],
            project_id="proj_clo_stress",
        )

        assert res["risk"] == "critical"
        assert res["license_violation"] is True
        assert res["veto_issued"] is True
        assert res["status"] == "escalation_required"
        assert "tainted-dep" in res["risk_details"]
        assert "remediation" in res
        assert "Replace tainted-dep" in res["remediation"]
        assert len(res["violations_detected"]) >= 1

    @pytest.mark.parametrize(
        "clean_license",
        [
            "MIT",
            "mit",
            "  mit  ",
            "Apache 2.0",
            "Apache-2.0",
            "apache",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "bsd",
            "ISC",
            "isc",
            "Unlicense",
            "0BSD",
        ],
    )
    def test_clo_permissive_licenses_approved(
        self,
        clean_license: str,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
        res = clo.audit_license_compliance(
            dependencies=[{"name": "pure-dep", "license": clean_license}],
            project_id="proj_clo_clean",
        )

        assert res["risk"] == "low"
        assert res["license_violation"] is False
        assert res["veto_issued"] is False
        assert res["status"] == "approved"
        assert res["approved_count"] == 1
        assert len(res["violations_detected"]) == 0

    @pytest.mark.parametrize(
        "yellow_license",
        [
            "MPL-2.0",
            "mpl 2.0",
            "CC-BY",
            "CC-BY-SA",
            "Proprietary",
            "Commercial-Custom",
            "Unknown",
        ],
    )
    def test_clo_yellow_or_unknown_licenses_trigger_conditional_review(
        self,
        yellow_license: str,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
        res = clo.audit_license_compliance(
            dependencies=[{"name": "conditional-dep", "license": yellow_license}],
            project_id="proj_clo_yellow",
        )

        assert res["risk"] == "moderate"
        assert res["license_violation"] is False
        assert res["veto_issued"] is False
        assert res["status"] == "conditional_approval"
        assert len(res["yellow_warnings"]) == 1
        assert len(res["violations_detected"]) == 0

    def test_clo_empty_dependencies_list(self, test_vault: VaultManager, test_router: ModelRouter):
        """Verify empty dependencies list gracefully returns approved status."""
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
        res = clo.audit_license_compliance(dependencies=[], project_id="proj_clo_empty")
        assert res["risk"] == "low"
        assert res["license_violation"] is False
        assert res["status"] == "approved"
        assert res["packages_audited"] == 0

    def test_clo_license_audit_persists_to_vault_and_memory(self, test_vault: VaultManager, test_router: ModelRouter):
        """Verify audit record and decision memory are written to vault upon violation."""
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)
        pid = "proj_clo_vault"
        res = clo.audit_license_compliance(
            dependencies=[{"name": "bad-lib", "license": "AGPL-3.0"}],
            project_id=pid,
        )
        assert res["license_violation"] is True

        saved = test_vault.read(f"projects/{pid}/deliverables/license_audit.json")
        assert saved is not None
        assert saved["license_violation"] is True
        assert saved["veto_issued"] is True

        assert len(clo.working_memory) > 0
        latest_mem = clo.working_memory[-1]
        assert "LEGAL BLOCKER" in latest_mem["content"]


# ============================================================================
# Vector 3: CEO Multi-Breach Simultaneous Adjudication with Real CFO & CLO
# ============================================================================

class TestCEOMultiBreachAdjudication:
    """Stress-test CEOAgent.synthesize multi-breach escalation tribunal (VULN-M3-01).

    Construct end-to-end multi-agent scenario where CFOAgent emits a real budget
    breach deliverable AND CLOAgent emits a real GPL copyleft blocker deliverable
    simultaneously.
    Verify:
    1. Neither breach overwrites the other.
    2. briefing_record["founder_escalations"] contains BOTH escalations.
    3. briefing_record["unified_briefing_md"] displays both blockers clearly to Founder Aman Jain.
    """

    def test_ceo_multi_breach_simultaneous_cfo_and_clo(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        ceo = CEOAgent(vault_manager=test_vault, model_router=test_router)
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)

        pid = "proj_multi_breach_emp"

        # 1. CFO audits spending with severe overrun ($1,000 on $500 ceiling)
        cfo_report = cfo.audit_spending(
            project_id=pid,
            actual_spend_data={"total_spend": 1000.0},
            budget_ceiling=500.0,
        )
        assert cfo_report["budget_breach"] is True
        assert cfo_report["status"] == "over_budget"

        # 2. CLO audits dependencies with critical GPL contamination
        clo_report = clo.audit_license_compliance(
            dependencies=[
                {"name": "safe-starlette", "license": "BSD-3-Clause"},
                {"name": "tainted-engine", "license": "GPL-3.0"},
            ],
            project_id=pid,
        )
        assert clo_report["license_violation"] is True
        assert clo_report["veto_issued"] is True

        # 3. Formulate synthesized executive deliverables package
        reports = [
            {"role": "CTO", "summary": "Core autonomous execution pipeline scaffolded."},
            {"role": "CFO", **cfo_report},
            {"role": "CLO", **clo_report},
        ]

        briefing = ceo.synthesize(reports, project_id=pid)

        # Assertion Set 1: Executive Status & Conflict Count
        assert briefing["status"] == "escalation_required"
        assert len(briefing["conflicts_detected"]) == 2

        # Assertion Set 2: VULN-M3-01 Regression Defense - Both Breaches Preserved
        assert briefing["founder_escalation"] is not None
        assert "founder_escalations" in briefing
        assert len(briefing["founder_escalations"]) == 2

        escalations = briefing["founder_escalations"]
        depts = [e["department"] for e in escalations]
        assert "CFO" in depts
        assert "CLO" in depts

        # Verify CFO escalation details
        cfo_esc = next(e for e in escalations if e["department"] == "CFO")
        assert cfo_esc["severity"] == "P0_CRITICAL"
        assert "$1,000.00" in cfo_esc["issue"] or "budget overrun" in cfo_esc["issue"].lower()
        assert len(cfo_esc["decision_options"]) >= 2

        # Verify CLO escalation details
        clo_esc = next(e for e in escalations if e["department"] == "CLO")
        assert clo_esc["severity"] == "P0_CRITICAL"
        assert "tainted-engine" in clo_esc["issue"] or "GPL" in clo_esc["issue"]
        assert len(clo_esc["decision_options"]) >= 2

        # Assertion Set 3: Composite Escalation Structure Integrity
        composite = briefing["founder_escalation"]
        assert composite["severity"] == "P0_CRITICAL"
        assert "CFO" in composite["departments"]
        assert "CLO" in composite["departments"]
        assert len(composite["decision_options"]) >= 4  # Both pairs of options aggregated

        # Assertion Set 4: Unified Briefing Markdown for Founder Aman Jain
        briefing_md = briefing["unified_briefing_md"]
        assert "⚠️ Founder Escalation Required (Tier 3 Decision)" in briefing_md
        assert "**Total Critical Breaches Detected:** 2" in briefing_md
        assert "Critical Blocker 1: [CFO]" in briefing_md or "[CFO]" in briefing_md
        assert "Critical Blocker 2: [CLO]" in briefing_md or "[CLO]" in briefing_md
        assert "Aman Jain" in briefing_md
        assert "[CFO-" in briefing_md
        assert "[CLO-" in briefing_md

        # Assertion Set 5: Vault Persistence
        saved = test_vault.read(f"projects/{pid}/deliverables/executive_briefing.json")
        assert saved is not None
        assert saved["status"] == "escalation_required"
        assert len(saved["founder_escalations"]) == 2

    def test_ceo_three_way_simultaneous_critical_breach(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        """Stress-test with 3 simultaneous blockers: CFO breach, CLO veto, and explicit CTO blocker."""
        ceo = CEOAgent(vault_manager=test_vault, model_router=test_router)
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)

        pid = "proj_3way_breach"

        cfo_report = cfo.audit_spending(
            project_id=pid,
            actual_spend_data={"total_spend": 2500.0},
            budget_ceiling=500.0,
        )
        clo_report = clo.audit_license_compliance(
            dependencies=[{"name": "copyleft-pkg", "license": "AGPL-3.0"}],
            project_id=pid,
        )

        reports = [
            {"role": "CFO", **cfo_report},
            {"role": "CLO", **clo_report},
            {
                "role": "CLO",
                "risk": "critical",
                "license_violation": True,
                "risk_details": "Second independent legal violation: Trademark infringement detected.",
            },
        ]

        briefing = ceo.synthesize(reports, project_id=pid)
        assert briefing["status"] == "escalation_required"
        assert len(briefing["conflicts_detected"]) == 3
        assert len(briefing["founder_escalations"]) == 3
        assert "**Total Critical Breaches Detected:** 3" in briefing["unified_briefing_md"]

    def test_ceo_synthesize_raw_agent_deliverables_without_role_tag_dropped(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        """VULNERABILITY PROBE:

        When real deliverables from CFOAgent (audit_spending) and CLOAgent (audit_license_compliance)
        are passed directly to CEOAgent.synthesize without manually injected 'role' or 'agent_id' tags,
        CEOAgent fails to detect the budget overrun and legal copyleft blocker because:
        1. Deliverables do not contain 'role' or 'agent_id' keys.
        2. CEOAgent._detect_conflicts checks 'budget' in r and 'legal' in r, but CFO uses 'budget_ceiling'/'budget_breach'
           and CLO uses 'license_violation'/'risk'.
        """
        ceo = CEOAgent(vault_manager=test_vault, model_router=test_router)
        cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
        clo = CLOAgent(vault_manager=test_vault, model_router=test_router)

        cfo_report = cfo.audit_spending("p_raw", {"total_spend": 1000.0}, budget_ceiling=500.0)
        clo_report = clo.audit_license_compliance([{"name": "bad", "license": "GPL-3.0"}], "p_raw")

        # Passing raw deliverables without manual 'role' tag:
        briefing = ceo.synthesize([cfo_report, clo_report], project_id="p_raw")
        # Documents vulnerability: conflicts are 0 and status is completed rather than escalation_required
        assert len(briefing["conflicts_detected"]) == 0
        assert briefing["status"] == "completed"


# ============================================================================
# Vector 4: CHRO Dynamic Hiring & JD Validation
# ============================================================================

class TestCHRODynamicHiringAndValidation:
    """Stress-test hire_agent with malformed specs:
    missing responsibilities, <3 responsibilities, 0 boundaries, invalid agent_id.
    Verify invalid specs raise ValueError and do NOT corrupt AgentRegistry or Vault.
    Verify valid dynamic hiring registers in AgentRegistry and can be retrieved.
    """

    def test_chro_hire_agent_empty_spec_raises_value_error(self, registry: AgentRegistry):
        chro = registry.get("CHRO")
        with pytest.raises(ValueError, match="agent_spec cannot be empty"):
            chro.hire_agent(agent_spec={})

    @pytest.mark.parametrize("invalid_id", ["", "   "])
    def test_chro_hire_agent_invalid_agent_id_raises_value_error(self, invalid_id: Any, registry: AgentRegistry):
        chro = registry.get("CHRO")
        spec = {
            "agent_id": invalid_id,
            "role": "Specialist",
            "role_title": "Test Specialist",
            "mission": "Execute testing.",
            "responsibilities": ["Task 1", "Task 2", "Task 3"],
            "boundaries": ["No production write"],
        }
        with pytest.raises(ValueError, match="agent_id"):
            chro.hire_agent(agent_spec=spec)

    def test_chro_hire_agent_none_agent_id_vulnerability(self, registry: AgentRegistry):
        """VULNERABILITY PROBE:

        Verify that agent_spec with agent_id=None currently bypasses validation,
        converts None to string 'NONE', and incorrectly creates an agent named 'NONE'.
        """
        chro = registry.get("CHRO")
        spec = {
            "agent_id": None,
            "role": "Ghost",
            "role_title": "Ghost Specialist",
            "mission": "Execute ghost actions.",
            "responsibilities": ["Task 1", "Task 2", "Task 3"],
            "boundaries": ["No production write"],
        }
        # Documents the vulnerability: hire_agent converts None -> 'NONE' instead of raising ValueError
        res = chro.hire_agent(agent_spec=spec, registry=registry)
        assert res["agent_id"] == "NONE"
        assert registry.get("NONE") is not None

    def test_chro_empty_registry_truthiness_fallthrough_vulnerability(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        """VULNERABILITY PROBE:

        AgentRegistry defines __len__ returning number of registered agents.
        When registry has 0 agents, bool(registry) evaluates to False.
        Therefore, `reg = registry or self.registry or get_agent_registry()`
        evaluates empty `registry` as falsy and silently falls back to the
        global singleton `get_agent_registry()`.
        """
        empty_reg = AgentRegistry(vault_manager=test_vault, model_router=test_router)
        assert len(empty_reg) == 0
        assert bool(empty_reg) is False  # Falsy object

        chro = CHROAgent(vault_manager=test_vault, model_router=test_router)
        spec = {
            "agent_id": "ISOLATED_TEST_AGENT",
            "role": "Isolation Specialist",
            "role_title": "Isolation Specialist",
            "mission": "Test registry isolation.",
            "responsibilities": ["Task 1", "Task 2", "Task 3"],
            "boundaries": ["No escape"],
        }
        res = chro.hire_agent(agent_spec=spec, registry=empty_reg)
        assert res["status"] == "hired"

        # Documents vulnerability: empty_reg does NOT receive the agent!
        assert empty_reg.get("ISOLATED_TEST_AGENT") is None
        # Instead, it leaked into the global singleton:
        from backend.agents.agent_registry import get_agent_registry
        assert get_agent_registry().get("ISOLATED_TEST_AGENT") is not None

    def test_chro_hire_agent_missing_responsibilities_raises_value_error(self, registry: AgentRegistry):
        chro = registry.get("CHRO")
        spec = {
            "agent_id": "TEST_AGENT_FAIL",
            "role": "Specialist",
            "mission": "Execute tasks.",
            "boundaries": ["Strict limit"],
        }
        with pytest.raises(ValueError, match="failed schema validation"):
            chro.hire_agent(agent_spec=spec)

        # Verify registry was NOT corrupted
        assert registry.get("TEST_AGENT_FAIL") is None

    @pytest.mark.parametrize("resps", [[], ["Solo Task"], ["Task 1", "Task 2"]])
    def test_chro_hire_agent_fewer_than_3_responsibilities_raises_value_error(
        self,
        resps: List[str],
        registry: AgentRegistry,
    ):
        chro = registry.get("CHRO")
        spec = {
            "agent_id": "UNDER_QUALIFIED",
            "role": "Intern",
            "mission": "Assist team.",
            "responsibilities": resps,
            "boundaries": ["Read only"],
        }
        with pytest.raises(ValueError, match="responsibilities"):
            chro.hire_agent(agent_spec=spec)

        assert registry.get("UNDER_QUALIFIED") is None

    @pytest.mark.parametrize("bounds", [[], None, "invalid_non_list"])
    def test_chro_hire_agent_zero_or_invalid_boundaries_raises_value_error(
        self,
        bounds: Any,
        registry: AgentRegistry,
    ):
        chro = registry.get("CHRO")
        spec = {
            "agent_id": "UNBOUNDED_ROGUE",
            "role": "Rogue",
            "mission": "Unconstrained agent.",
            "responsibilities": ["Task 1", "Task 2", "Task 3"],
            "boundaries": bounds,
        }
        with pytest.raises(ValueError, match="boundaries"):
            chro.hire_agent(agent_spec=spec)

        assert registry.get("UNBOUNDED_ROGUE") is None

    def test_chro_hire_agent_valid_spec_registers_and_executes(
        self,
        registry: AgentRegistry,
        test_vault: VaultManager,
    ):
        chro = registry.get("CHRO")
        spec = {
            "agent_id": "SECURITY_OFFICER",
            "role": "Security Specialist",
            "role_title": "Chief Information Security Officer",
            "mission": "Enforce zero-trust architecture and cryptographic audits.",
            "responsibilities": [
                "Audit cryptographic primitives across local vault",
                "Scan dependencies for CVEs",
                "Review network ingress rules",
            ],
            "boundaries": [
                "Never disable authentication safeguards",
                "Never export raw keys outside local keychain",
            ],
        }

        hire_res = chro.hire_agent(agent_spec=spec, registry=registry)

        assert hire_res["status"] == "hired"
        assert hire_res["success"] is True
        assert hire_res["agent_id"] == "SECURITY_OFFICER"

        # Verify retrieval from registry
        sec_agent = registry.get("SECURITY_OFFICER")
        assert sec_agent is not None
        assert isinstance(sec_agent, BaseExecutiveAgent)
        assert sec_agent.role == "Security Specialist"

        # Verify Vault profile created
        profile = test_vault.read("agents/SECURITY_OFFICER/profile.json")
        assert profile is not None
        assert profile["agent_id"] == "SECURITY_OFFICER"
        assert profile["status"] == "active"

        # Verify new agent can act
        act_res = sec_agent.act("record_thought", {"content": "Security audit initiated.", "importance": 8})
        assert act_res["status"] == "success"

        # Clean retirement
        ret_res = chro.retire_agent("SECURITY_OFFICER", reason="Audit sprint concluded", registry=registry)
        assert ret_res["status"] == "retired"
        assert registry.get("SECURITY_OFFICER") is None


# ============================================================================
# Vector 5: CSO Strategic Alignment Scorer
# ============================================================================

class TestCSOStrategicAlignmentScorer:
    """Stress-test check_alignment with initiatives conflicting with Local-First

    Privacy or Financial Sustainability. Verify that misaligned initiatives
    receive scores < 70 and recommendation "REJECT".
    """

    def test_cso_alignment_clean_initiative_proceed(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        cso = CSOAgent(vault_manager=test_vault, model_router=test_router)
        res = cso.check_alignment(
            initiative_title="Local-First Vector Indexing",
            initiative_description="Implement on-device HNSW indexing with ChromaDB and SQLite.",
            project_id="proj_cso_clean",
        )

        assert res["aligned"] is True
        assert res["alignment_score"] >= 85.0
        assert res["strategic_recommendation"] == "PROCEED"
        assert len(res["misalignments"]) == 0

    @pytest.mark.parametrize(
        "title,desc,expected_violation_term",
        [
            ("Cloud Telemetry Ingestion", "Upload user prompts and system logs to external telemetry cloud", "sovereignty"),
            ("Cloud-Only Architecture", "Deprecate local SQLite and force mandatory cloud_only synchronization", "sovereignty"),
            ("Proprietary Vendor Lock-in", "Migrate core modules to closed_source proprietary cloud vendor", "sovereignty"),
            ("Unbounded Paid LLM Burn", "Default all queries to paid_only frontier models with unbounded_tokens burn", "burn"),
            ("Expensive Cloud Inference", "Run expensive cloud multi-agent swarms with zero token throttling", "burn"),
        ],
    )
    def test_cso_alignment_misaligned_initiatives_strictly_rejected(
        self,
        title: str,
        desc: str,
        expected_violation_term: str,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        cso = CSOAgent(vault_manager=test_vault, model_router=test_router)
        res = cso.check_alignment(
            initiative_title=title,
            initiative_description=desc,
            project_id="proj_cso_reject",
        )

        assert res["aligned"] is False
        assert res["alignment_score"] < 70.0
        assert res["alignment_score"] <= 45.0  # Critical failure cap
        assert res["strategic_recommendation"] == "REJECT"
        assert len(res["misalignments"]) >= 1
        assert any(expected_violation_term in m.lower() for m in res["misalignments"])

    def test_cso_alignment_empty_title_raises_value_error(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        cso = CSOAgent(vault_manager=test_vault, model_router=test_router)
        with pytest.raises(ValueError, match="initiative_title cannot be empty"):
            cso.check_alignment(initiative_title="", initiative_description="Valid desc")

    def test_cso_alignment_persists_to_vault_and_memory(
        self,
        test_vault: VaultManager,
        test_router: ModelRouter,
    ):
        cso = CSOAgent(vault_manager=test_vault, model_router=test_router)
        pid = "proj_cso_vault"
        res = cso.check_alignment(
            initiative_title="Cloud Telemetry Stream",
            initiative_description="Mandatory telemetry upload",
            project_id=pid,
        )
        assert res["strategic_recommendation"] == "REJECT"

        saved = test_vault.read(f"projects/{pid}/deliverables/strategic_alignment.json")
        assert saved is not None
        assert saved["strategic_recommendation"] == "REJECT"
        assert saved["alignment_score"] <= 45.0
