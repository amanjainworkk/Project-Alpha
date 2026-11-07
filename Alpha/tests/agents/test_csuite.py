"""tests/agents/test_csuite.py - Master Comprehensive Test Suite for Project Alpha C-Suite.

Covers all 10 specialized C-Suite executive agents:
- CTOAgent (Feature 17)
- CMOAgent (Feature 18)
- CPOAgent (Feature 19)
- CDOAgent (Feature 20)
- CFOAgent (Feature 21)
- COOAgent (Feature 22)
- CHROAgent (Feature 23)
- CIOAgent (Feature 24)
- CSOAgent (Feature 25)
- CLOAgent (Feature 26)

Test Categories:
1. Parameterized Direct Instantiation Matrix (10 Agents)
2. AgentRegistry Loading & Factory Instantiation (10 Specialized Classes)
3. Real Markdown JD Parsing & Token Budget Verification (<1000 tokens)
4. Dedicated Specialized Method Suites (10 Roles)
5. Parameterized run(task, project_id) Execution Harness (10 Agents)
6. Parameterized Headless & Fallback Resilience (10 Agents)
7. Parameterized Input Sanitization & Fault Tolerance (10 Agents)
8. CEO Cross-Functional Delegation & Multi-Breach Escalation Tribunal
9. CHRO Dynamic Hiring & Lifecycle Integration via Registry
"""

from pathlib import Path
from typing import Any, Dict, List, Type
import pytest

from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.agent_registry import AgentRegistry, reset_agent_registry
from backend.agents.ceo import CEOAgent
from backend.agents.cto import CTOAgent
from backend.agents.cmo import CMOAgent
from backend.agents.cpo import CPOAgent
from backend.agents.cdo import CDOAgent
from backend.agents.cfo import CFOAgent
from backend.agents.coo import COOAgent
from backend.agents.chro import CHROAgent
from backend.agents.cio import CIOAgent
from backend.agents.cso import CSOAgent
from backend.agents.clo import CLOAgent
from backend.model_router.base_client import estimate_tokens
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
def registry(test_vault, test_router) -> AgentRegistry:
    reset_agent_registry()
    reg = AgentRegistry(vault_manager=test_vault, model_router=test_router)
    reg.load_all()
    return reg


ALL_CSUITE_CLASSES = [
    (CTOAgent, "CTO", "Alpha CTO"),
    (CMOAgent, "CMO", "Alpha CMO"),
    (CPOAgent, "CPO", "Alpha CPO"),
    (CDOAgent, "CDO", "Alpha CDO"),
    (CFOAgent, "CFO", "Alpha CFO"),
    (COOAgent, "COO", "Alpha COO"),
    (CHROAgent, "CHRO", "Alpha CHRO"),
    (CIOAgent, "CIO", "Alpha CIO"),
    (CSOAgent, "CSO", "Alpha CSO"),
    (CLOAgent, "CLO", "Alpha CLO"),
]


# ============================================================================
# Category 1: Parameterized Direct Instantiation Matrix
# ============================================================================

@pytest.mark.parametrize("agent_cls,role,expected_name", ALL_CSUITE_CLASSES)
def test_csuite_instantiation_matrix(agent_cls: Type[BaseExecutiveAgent], role: str, expected_name: str, test_vault, test_router):
    agent = agent_cls(vault_manager=test_vault, model_router=test_router)
    assert isinstance(agent, BaseExecutiveAgent)
    assert isinstance(agent, agent_cls)
    assert agent.role == role
    assert agent.name == expected_name
    assert agent.status == "active"
    assert len(agent.working_memory) == 0


# ============================================================================
# Category 2: AgentRegistry Loading & Factory Instantiation
# ============================================================================

def test_agent_registry_instantiates_all_10_specialized_classes(registry):
    agents = registry.load_all()
    assert len(agents) >= 13

    expected_types = {
        "CEO": CEOAgent,
        "CTO": CTOAgent,
        "CMO": CMOAgent,
        "CPO": CPOAgent,
        "CDO": CDOAgent,
        "CFO": CFOAgent,
        "COO": COOAgent,
        "CHRO": CHROAgent,
        "CIO": CIOAgent,
        "CSO": CSOAgent,
        "CLO": CLOAgent,
    }

    for role_id, expected_cls in expected_types.items():
        ag = registry.get(role_id)
        assert ag is not None, f"Registry missing agent {role_id}"
        assert isinstance(ag, expected_cls), f"Agent {role_id} expected {expected_cls.__name__}, got {type(ag).__name__}"
        assert isinstance(ag, BaseExecutiveAgent)


# ============================================================================
# Category 3: Real Markdown JD Parsing & Token Budget Verification (<1000 tokens)
# ============================================================================

@pytest.mark.parametrize("agent_cls,role,expected_name", ALL_CSUITE_CLASSES)
def test_csuite_real_jd_parsing_and_token_budget(agent_cls: Type[BaseExecutiveAgent], role: str, expected_name: str, test_vault, test_router):
    agent = agent_cls(vault_manager=test_vault, model_router=test_router)
    assert agent.jd_path is not None
    assert agent.jd_path.exists(), f"JD path for {role} not found: {agent.jd_path}"

    assert len(agent.jd_data.responsibilities) >= 3, f"{role} must have >=3 responsibilities"
    assert len(agent.jd_data.constraints) >= 1, f"{role} must have >=1 boundaries/constraints"

    token_count = estimate_tokens(agent.system_prompt)
    assert token_count < 1000, f"{role} system prompt exceeded 1000 tokens: {token_count}"
    assert token_count > 100, f"{role} system prompt suspiciously short: {token_count}"


# ============================================================================
# Category 4: Dedicated Specialized Method Suites (10 Roles)
# ============================================================================

def test_cto_specialized_methods(test_vault, test_router):
    cto = CTOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. generate_architecture_spec
    spec = cto.generate_architecture_spec(requirements="Build distributed event engine", project_id="proj_cto")
    assert spec["project_id"] == "proj_cto"
    assert "components" in spec
    assert "tech_stack" in spec
    assert test_vault.read("projects/proj_cto/deliverables/technical_spec.json") is not None

    # 2. review_tech_stack - approved
    approved_stack = {
        "backend": {"name": "FastAPI", "scores": {"security_track_record": 4.5, "open_source_licensing": 5.0}},
        "db": {"name": "SQLite", "scores": {"security_track_record": 4.0, "total_cost_of_ownership": 5.0}},
    }
    review_ok = cto.review_tech_stack(approved_stack, project_id="proj_cto")
    assert review_ok["stack_status"] in ("APPROVED", "CONDITIONAL")
    assert review_ok["disqualified"] is False

    # 2b. review_tech_stack - security disqualification (dimension 4 <= 1.0)
    insecure_stack = {
        "db": {"name": "InsecureDB", "scores": {"security_track_record": 1.0}},
    }
    review_bad = cto.review_tech_stack(insecure_stack, project_id="proj_cto")
    assert review_bad["disqualified"] is True
    assert review_bad["stack_status"] == "REJECTED"
    assert "SECURITY DISQUALIFIED" in review_bad["evaluations"]["db"]["decision"]

    # 3. generate_archify_graph
    graph = cto.generate_archify_graph(project_id="proj_cto")
    assert graph["project_id"] == "proj_cto"
    assert len(graph["graph_data"]["nodes"]) >= 2
    assert "html" in graph
    assert "#0A0A0F" in graph["html"]
    assert "#06B6D4" in graph["html"]

    # 4. review_code_standards
    long_func = "def long_function():\n" + "    x = 1\n" * 55
    res_code = cto.review_code_standards(long_func)
    assert res_code["passed"] is False
    assert any(v["rule"] == "max_function_length" for v in res_code["violations"])

    # 5. generate_tdd_test_plan
    plan = cto.generate_tdd_test_plan("VaultSync", ["Read document", "Write document"], project_id="proj_cto")
    assert plan["component"] == "VaultSync"
    assert len(plan["tests"]) == 2
    assert plan["tests"][0]["phase"] == "RED (Failing Assertion)"


def test_coo_specialized_methods(test_vault, test_router):
    coo = COOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. create_pep
    pep = coo.create_pep(project_id="proj_coo", founder_goal="Ship MVP in 2 weeks")
    assert pep["project_id"] == "proj_coo"
    assert "critical_path" in pep
    assert len(pep["critical_path"]) >= 1
    assert test_vault.read("projects/proj_coo/deliverables/execution_plan.json") is not None

    # 2. track_critical_path
    cpm = coo.track_critical_path(coo.DEFAULT_WORKSTREAM_SEQUENCE, project_id="proj_coo")
    assert cpm["total_duration"] > 0
    assert len(cpm["critical_path"]) >= 1
    assert cpm["has_cycles"] is False

    # 3. detect_bottlenecks
    events = [{"agent_id": "CTO", "status": "stalled", "idle_seconds": 500, "task_id": "T-05"}]
    bottlenecks = coo.detect_bottlenecks(events, timeout_seconds=300.0)
    assert len(bottlenecks) == 1
    assert "step_1_inspect_vault" in bottlenecks[0]["remediation"]
    assert "step_2_escalate_ping" in bottlenecks[0]["remediation"]

    # 4. update_milestone_matrix and enforce_quality_gate
    gate_res = coo.update_milestone_matrix(
        project_id="proj_coo",
        task_id="T-01",
        new_status="completed",
        verification_proof={"tests_passed": True, "archify_linked": True, "prd_validated": True, "cao_passed": True, "release_notes": True},
    )
    assert gate_res["gate_passed"] is True
    assert gate_res["status"] == "completed"

    # 5. generate_status_report
    report = coo.generate_status_report(project_id="proj_coo")
    assert report["project_id"] == "proj_coo"
    assert report["overall_health"] == "ON_TRACK"


def test_cio_specialized_methods(test_vault, test_router):
    cio = CIOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. enforce_vault_schema
    schema_res = cio.enforce_vault_schema(
        path="company/identity",
        data={
            "company_name": "Project Alpha",
            "founder": "Aman Jain",
            "vision": "Autonomous Executive Operating System",
            "mission": "Empower builders with sovereign AI intelligence",
            "industry": "Autonomous AI Software",
            "core_values": ["sovereign", "rigor"],
        },
    )
    assert schema_res["valid"] is True
    assert schema_res["data_tier"] in ("T1", "T2", "T3")

    # 2. maintain_relational_tables & audit_vault_integrity
    integrity = cio.maintain_relational_tables(check_integrity=True)
    assert integrity["integrity_ok"] is True
    assert "table_counts" in integrity

    # 3. manage_chroma_collections
    col_res = cio.manage_chroma_collections(action="inspect", collection_name="vault_knowledge")
    assert col_res["status"] in ("success", "simulated")

    # 4. compress_episodic_memory
    cio.record_thought("High importance milestone completed", importance=9, project_id="proj_cio")
    cio.record_thought("Low background ping", importance=2, project_id="proj_cio")
    comp_res = cio.compress_episodic_memory(agent_id="CIO")
    assert comp_res["status"] in ("compressed",)
    assert "summary" in comp_res

    # 5. run_ecc_integrity_check
    ecc_res = cio.run_ecc_integrity_check()
    assert "healthy" in ecc_res


def test_cpo_specialized_methods(test_vault, test_router):
    cpo = CPOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. generate_prd
    prd = cpo.generate_prd(project_id="proj_cpo", title="Autonomous Engine", description="Complete autonomous executor")
    assert prd["project_id"] == "proj_cpo"
    assert len(prd["functional_requirements"]) >= 1
    assert test_vault.read("projects/proj_cpo/deliverables/product_prd.json") is not None
    assert test_vault.read("projects/proj_cpo/deliverables/product_prd.md") is not None

    # 2. prioritize_backlog (RICE & MoSCoW)
    features = [
        {"name": "Core Task Dispatcher", "reach": 10.0, "impact": 3.0, "confidence": 1.0, "effort": 2.0},
        {"name": "Fancy Rainbow Theme", "reach": 1.0, "impact": 0.5, "confidence": 0.5, "effort": 5.0},
    ]
    backlog = cpo.prioritize_backlog(features, project_id="proj_cpo")
    assert len(backlog) == 2
    assert backlog[0]["priority"] == "P0"
    assert backlog[0]["rice_score"] > backlog[1]["rice_score"]

    # 3. create_user_stories
    stories = cpo.create_user_stories(feature_name="Dynamic Memory", feature_description="Save thoughts to vault", count=3)
    assert len(stories) == 3
    assert any("Given" in ac for ac in stories[0]["acceptance_criteria"])

    # 4. audit_anti_gold_plating
    audit = cpo.audit_anti_gold_plating(prd, project_id="proj_cpo")
    assert "score" in audit
    assert "checklist" in audit

    # 5. scope_mvp
    mvp = cpo.scope_mvp(backlog, target_days=14, project_id="proj_cpo")
    assert mvp["v1_must_have_count"] >= 1


def test_cmo_specialized_methods(test_vault, test_router):
    cmo = CMOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. build_gtm_strategy
    gtm = cmo.build_gtm_strategy(
        project_id="proj_cmo",
        product_name="Project Alpha",
        value_prop="Personal autonomous AI executive OS",
        target_audience="Developers and AI Founders",
    )
    assert gtm["project_id"] == "proj_cmo"
    assert len(gtm["checklist_status"]) == 10
    assert test_vault.read("projects/proj_cmo/deliverables/marketing_brief.json") is not None
    assert test_vault.read("projects/proj_cmo/deliverables/marketing_brief.md") is not None

    # 2. create_buyer_persona
    persona = cmo.create_buyer_persona("Indie Hacker", "AI Builders", project_id="proj_cmo")
    assert "demographics" in persona
    assert "psychographics" in persona
    assert len(persona["pain_points"]) >= 1

    # 3. create_messaging_framework
    msg = cmo.create_messaging_framework(
        project_name="Alpha",
        problem="High token costs",
        solution="Free-first routing",
        target_audience="Developers",
        project_id="proj_cmo",
    )
    assert "one_line_hook" in msg
    assert len(msg["value_pillars"]) == 3
    assert len(msg["objection_shields"]) >= 1

    # 4. generate_content_calendar
    cal = cmo.generate_content_calendar("proj_cmo", "Alpha Launch", duration_weeks=4)
    assert len(cal["schedule"]) == 4

    # 5. conduct_market_discovery
    disc = cmo.conduct_market_discovery("Autonomous Executive System", project_id="proj_cmo")
    assert "step_4_defensible_wedge" in disc


def test_cdo_specialized_methods(test_vault, test_router):
    cdo = CDOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. get_oled_design_tokens
    tokens = cdo.get_oled_design_tokens()
    assert tokens["palette"]["background"] == "#090A0F"
    assert tokens["palette"]["primary"] == "#3B82F6"
    assert tokens["palette"]["accent"] == "#06B6D4"

    # 2. generate_canvas_node_style
    active_style = cdo.generate_canvas_node_style("agent", status="active")
    assert active_style["border_color"] == "#06B6D4"
    assert active_style["pulse_animation"] is True

    # 3. generate_mobile_layout_spec
    for screen in ["canvas_screen", "tasks_screen", "chat_screen", "boardroom_screen", "vault_screen"]:
        spec = cdo.generate_mobile_layout_spec(screen, project_id="proj_cdo")
        assert spec["screen_name"] == screen
        assert len(spec["widgets"]) >= 1
        assert "wireframe" in spec["ascii_wireframe"].lower() or len(spec["ascii_wireframe"]) > 20

    # 4. review_ui_spec
    review = cdo.review_ui_spec({"touch_target_min_dp": 48, "contrast_ratio": 7.0}, project_id="proj_cdo")
    assert review["passed"] is True
    assert review["score"] == 100.0

    # 5. export_archify_diagram_spec
    diag = cdo.export_archify_diagram_spec(
        system_nodes=[{"id": "n1", "type": "agent", "status": "active"}],
        system_edges=[{"from": "n1", "to": "n2"}],
        project_id="proj_cdo",
    )
    assert diag["total_nodes"] == 1
    assert diag["canvas_background"] == "#090A0F"


def test_cfo_specialized_methods(test_vault, test_router):
    cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. model_unit_economics
    econ = cfo.model_unit_economics(project_id="proj_cfo", expected_queries_monthly=100000, user_count=1000, target_price_monthly=9.0)
    assert econ["blended_cpq"] > 0
    assert econ["cost_to_serve_per_user"] > 0
    assert econ["gross_margin_pct"] >= 85.0
    assert econ["target_margin_achieved"] is True
    assert test_vault.read("projects/proj_cfo/deliverables/unit_economics.json") is not None

    # 2. forecast_budget
    forecast = cfo.forecast_budget(project_id="proj_cfo", tasks=[{"task_id": "T1"}, {"task_id": "T2"}])
    assert forecast["capex_build_cost"] >= 0
    assert forecast["free_first_savings_realized"] > 0

    # 3. audit_spending - within budget
    audit_ok = cfo.audit_spending(project_id="proj_cfo", actual_spend_data={"total_spend": 200.0}, budget_ceiling=500.0)
    assert audit_ok["status"] == "within_budget"
    assert audit_ok["budget_breach"] is False
    assert audit_ok["founder_escalation_required"] is False

    # 3b. audit_spending - over budget (CEO escalation contract)
    audit_bad = cfo.audit_spending(project_id="proj_cfo", actual_spend_data={"total_spend": 15000.0}, budget_ceiling=10000.0)
    assert audit_bad["status"] == "over_budget"
    assert audit_bad["budget_breach"] is True
    assert audit_bad["founder_escalation_required"] is True
    assert "15,000" in audit_bad["breach_details"]

    # 4. evaluate_roi
    roi = cfo.evaluate_roi("proj_cfo", build_cost=100.0, pricing_model={"monthly_price": 9.0}, user_growth_projections=[10, 50, 100])
    assert roi["break_even_users"] > 0
    assert roi["payback_period_months"] >= 1

    # 5. generate_financial_report
    rep = cfo.generate_financial_report("proj_cfo")
    assert "report_id" in rep
    assert test_vault.read("projects/proj_cfo/deliverables/financial_report.json") is not None
    assert test_vault.read("projects/proj_cfo/deliverables/financial_report.md") is not None


def test_chro_specialized_methods(test_vault, test_router):
    chro = CHROAgent(vault_manager=test_vault, model_router=test_router)

    # 1. validate_jd_schema
    good_spec = {
        "role_title": "Security Specialist",
        "mission": "Defend system boundaries",
        "responsibilities": ["Monitor access logs", "Audit crypto keys", "Perform vulnerability scans"],
        "boundaries": ["Never disable vault encryption"],
    }
    v_ok = chro.validate_jd_schema(good_spec)
    assert v_ok["is_valid"] is True

    bad_spec = {"role_title": "Invalid Agent"}
    v_bad = chro.validate_jd_schema(bad_spec)
    assert v_bad["is_valid"] is False

    # 2. hire_agent
    hired = chro.hire_agent(agent_spec={
        "agent_id": "SEC_ENG",
        "role": "Security Engineer",
        "role_title": "Chief Security Engineer",
        "mission": "Maintain zero-trust security perimeter",
        "responsibilities": ["Audit tokens", "Verify encryption", "Enforce RBAC"],
        "boundaries": ["Never expose private keys"],
    })
    assert hired["status"] == "hired"
    assert hired["success"] is True

    # 3. audit_agent_performance
    audit = chro.audit_agent_performance("CTO")
    assert audit["health_score"] >= 0.0
    assert "action" in audit

    # 4. conduct_skill_gap_analysis
    gap = chro.conduct_skill_gap_analysis(["Build embedded firmware for microchip"])
    assert gap["has_critical_gaps"] is True
    assert len(gap["recommended_hires"]) >= 1

    # 5. enforce_culture_and_tone
    fluff_out = chro.enforce_culture_and_tone("Certainly! I would be happy to help you with that! Feel free to ask!")
    assert fluff_out["compliant"] is False
    assert len(fluff_out["violations"]) >= 1

    clean_out = chro.enforce_culture_and_tone("### Architecture Verification\n- All 10 suites passing 100%.\n- Zero exceptions.")
    assert clean_out["compliant"] is True

    # 6. retire_agent
    ret = chro.retire_agent("SEC_ENG", reason="Project completed")
    assert ret["status"] == "retired"


def test_cso_specialized_methods(test_vault, test_router):
    cso = CSOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. check_alignment - aligned
    align_ok = cso.check_alignment(
        initiative_title="Local-first offline vector storage",
        initiative_description="Enhance privacy and speed by storing embeddings locally.",
        project_id="proj_cso",
    )
    assert align_ok["aligned"] is True
    assert align_ok["recommendation"] in ("PROCEED", "CONDITIONAL_APPROVAL")

    # 1b. check_alignment - misaligned
    align_bad = cso.check_alignment(
        initiative_title="Send telemetry to closed-source cloud proprietary server",
        initiative_description="Upload all user prompts and code to external server.",
        project_id="proj_cso",
    )
    assert align_bad["aligned"] is False
    assert align_bad["recommendation"] == "REJECT"

    # 2. define_okrs
    okrs = cso.define_okrs("Q1 2026", "Autonomous Production Readiness", project_id="proj_cso")
    assert len(okrs["objectives"]) >= 2
    assert test_vault.read("projects/proj_cso/deliverables/okrs.json") is not None

    # 3. track_okrs
    track = cso.track_okrs("Q1 2026", {"overall_progress_pct": 85.0}, project_id="proj_cso")
    assert track["status"] == "on_track"

    # 4. analyze_competitors
    moat = cso.analyze_competitors("Autonomous Dev Systems", ["Devin", "AutoGPT"], project_id="proj_cso")
    assert "strategic_moat" in moat
    assert len(moat["teardowns"]) == 2

    # 5. generate_strategic_brief
    brief = cso.generate_strategic_brief("proj_cso")
    assert "north_star" in brief
    assert test_vault.read("projects/proj_cso/deliverables/strategic_brief.json") is not None
    assert test_vault.read("projects/proj_cso/deliverables/strategic_brief.md") is not None


def test_clo_specialized_methods(test_vault, test_router):
    clo = CLOAgent(vault_manager=test_vault, model_router=test_router)

    # 1. audit_license_compliance - approved
    clean_deps = [{"name": "fastapi", "license": "MIT"}, {"name": "pydantic", "license": "MIT"}, {"name": "uvicorn", "license": "BSD"}]
    lic_ok = clo.audit_license_compliance(clean_deps, project_id="proj_clo")
    assert lic_ok["risk"] == "low"
    assert lic_ok["license_violation"] is False
    assert lic_ok["veto_issued"] is False
    assert lic_ok["status"] == "approved"

    # 1b. audit_license_compliance - GPL copyleft violation (CEO escalation contract)
    gpl_deps = [{"name": "copyleft_lib", "license": "GPL-3.0"}]
    lic_bad = clo.audit_license_compliance(gpl_deps, project_id="proj_clo")
    assert lic_bad["risk"] == "critical"
    assert lic_bad["license_violation"] is True
    assert lic_bad["veto_issued"] is True
    assert lic_bad["status"] == "escalation_required"
    assert "GPL" in lic_bad["risk_details"]

    # 2. audit_data_privacy
    priv = clo.audit_data_privacy({"telemetry_enabled": False, "storage_type": "local_sqlite_chroma"}, project_id="proj_clo")
    assert priv["compliant"] is True
    assert priv["dpdp_compliance"] is True

    # 3. generate_terms_and_disclaimers
    terms = clo.generate_terms_and_disclaimers("Project Alpha", project_id="proj_clo")
    assert "MIT License" in terms["license_text"]
    assert "Aman Jain" in terms["license_text"]
    assert "AS IS" in terms["as_is_disclaimer"]

    # 4. conduct_ip_risk_assessment
    ip_res = clo.conduct_ip_risk_assessment({"models": ["llama3.2"]}, project_id="proj_clo")
    assert ip_res["commercial_use_permitted"] is True
    assert ip_res["risk_level"] == "LOW"

    # 5. generate_legal_review
    review = clo.generate_legal_review("proj_clo")
    assert review["status"] == "APPROVED"
    assert review["all_gates_passed"] is True
    assert test_vault.read("projects/proj_clo/deliverables/legal_review.json") is not None
    assert test_vault.read("projects/proj_clo/deliverables/legal_review.md") is not None


# ============================================================================
# Category 5: Parameterized run(task, project_id) Execution Harness
# ============================================================================

@pytest.mark.parametrize("agent_cls,role,expected_name", ALL_CSUITE_CLASSES)
def test_all_10_agents_run_execution(agent_cls: Type[BaseExecutiveAgent], role: str, expected_name: str, test_vault, test_router):
    agent = agent_cls(vault_manager=test_vault, model_router=test_router)
    task_desc = f"Execute standard baseline analysis for {role} department"
    res = agent.run(task=task_desc, project_id="proj_run_matrix")

    assert res["status"] == "completed"
    assert res["agent_id"] == role
    assert res["role"] == role
    assert res["project_id"] == "proj_run_matrix"
    assert "output" in res

    # Verify episodic thought memory was recorded
    recent = agent.get_recent_memories(n=5)
    assert len(recent) >= 1
    assert any(role in m.get("content", m.get("memory_content", "")) for m in recent)


# ============================================================================
# Category 6: Parameterized Headless & Fallback Resilience (None Vault/Router)
# ============================================================================

@pytest.mark.parametrize("agent_cls,role,expected_name", ALL_CSUITE_CLASSES)
def test_all_10_agents_headless_fallback_resilience(agent_cls: Type[BaseExecutiveAgent], role: str, expected_name: str):
    agent = agent_cls(vault_manager=None, model_router=None)
    assert agent.vault_manager is None
    assert agent.model_router is None

    # Think fallback
    thought = agent.think("Evaluate operational readiness")
    assert thought is not None
    assert len(thought) > 0

    # Run fallback
    res = agent.run("Perform headless verification check")
    assert res["status"] == "completed"
    assert len(agent.working_memory) >= 1


# ============================================================================
# Category 7: Parameterized Input Sanitization & Fault Tolerance
# ============================================================================

@pytest.mark.parametrize("agent_cls,role,expected_name", ALL_CSUITE_CLASSES)
def test_all_10_agents_input_sanitization_and_error_handling(agent_cls: Type[BaseExecutiveAgent], role: str, expected_name: str, test_vault, test_router):
    agent = agent_cls(vault_manager=test_vault, model_router=test_router)

    # Empty task input raises ValueError
    with pytest.raises(ValueError):
        agent.run("")

    with pytest.raises(ValueError):
        agent.run("   ")

    # Invalid custom action returns error envelope without crashing
    bad_act = agent.act("completely_unknown_action_xyz", {})
    assert bad_act["status"] == "error"
    assert bad_act["success"] is False


# ============================================================================
# Category 8: CEO Delegation & Multi-Breach Escalation Tribunal
# ============================================================================

def test_ceo_delegation_and_multi_breach_escalation_tribunal(test_vault, test_router):
    ceo = CEOAgent(vault_manager=test_vault, model_router=test_router)
    cfo = CFOAgent(vault_manager=test_vault, model_router=test_router)
    clo = CLOAgent(vault_manager=test_vault, model_router=test_router)

    # Generate real reports from CFO and CLO that trigger critical breaches
    cfo_spend_report = cfo.audit_spending(
        project_id="proj_tribunal",
        actual_spend_data={"total_spend": 15000.0},
        budget_ceiling=10000.0,
    )
    assert cfo_spend_report["budget_breach"] is True

    clo_license_report = clo.audit_license_compliance(
        dependencies=[{"name": "tainted_package", "license": "GPL-3.0"}],
        project_id="proj_tribunal",
    )
    assert clo_license_report["license_violation"] is True

    # Submit reports to CEO synthesize
    reports = [
        {"role": "CTO", "summary": "Core engine deployed."},
        {"role": "CFO", **cfo_spend_report},
        {"role": "CLO", **clo_license_report},
    ]

    briefing = ceo.synthesize(reports, project_id="proj_tribunal")
    assert briefing["status"] == "escalation_required"
    assert briefing["founder_escalation"] is not None

    esc = briefing["founder_escalation"]
    assert esc["severity"] == "P0_CRITICAL"
    assert len(esc["decision_options"]) >= 2
    assert "Founder Escalation Required" in briefing["unified_briefing_md"]
    assert len(briefing["conflicts_detected"]) == 2


# ============================================================================
# Category 9: CHRO Dynamic Hiring & Lifecycle Integration via Registry
# ============================================================================

def test_chro_dynamic_hiring_and_lifecycle_integration(registry, test_vault, test_router):
    chro = registry.get("CHRO")
    assert isinstance(chro, CHROAgent)

    # Hire new specialist
    hire_result = chro.hire_agent(agent_spec={
        "agent_id": "DEVOPS_LEAD",
        "role": "DevOps Engineer",
        "role_title": "Chief DevOps Engineer",
        "mission": "Automate local CI/CD and Flutter APK compilation",
        "responsibilities": ["Configure build scripts", "Verify APK artifacts", "Monitor runner health"],
        "boundaries": ["Never alter core vault schema without CIO approval"],
    })
    assert hire_result["status"] == "hired"

    # Verify agent is active in registry
    devops = registry.get("DEVOPS_LEAD")
    assert devops is not None
    assert devops.agent_id == "DEVOPS_LEAD"

    # Execute task with newly hired agent
    res = devops.act("record_thought", {"content": "DevOps initialized", "importance": 7})
    assert res["status"] == "success"

    # Retire agent
    ret_res = chro.retire_agent("DEVOPS_LEAD", reason="Build pipeline operational")
    assert ret_res["status"] == "retired"
    assert registry.get("DEVOPS_LEAD") is None
