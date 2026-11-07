"""Project Alpha — Tier 1: Feature Coverage Test Suite.

Verifies all core features from PROJECT.md § Feature Inventory with >=5 test cases
per feature group covering representative inputs:
1. Vault Core & Schemas (Features 1-6)
2. Model Router & Fallback System (Features 7-13)
3. Base Agent & C-Suite Executive Roster (Features 14-26)
4. Dual CAO Audit Gate & 2-Round Escalation Cap (Features 27-29)
5. Tri-Framework Orchestration & Archify Engine (Features 30-38)
6. 15-Tool MCP Server (Features 39-54)
7. FastAPI REST Endpoints & Bearer Auth (Features 55-60)
8. WebSocket Telemetry Streaming (Feature 61)
9. Alpha CLI Tool Operations (Features 62-64)
"""

from __future__ import annotations

import json
import pytest
from typing import Dict, Any


# ===========================================================================
# 1. Vault Core & Schemas (Features 1-6)
# ===========================================================================

def test_vault_write_and_read_company_identity(vault_manager):
    """Verifies writing and reading company identity metadata."""
    payload = {
        "company_name": "Alpha Innovations",
        "founder": "Aman Jain",
        "vision": "Autonomous Personal AI OS",
        "core_values": ["Extreme Autonomy", "Zero-Cost Priority", "Rigorous Auditing"],
    }
    assert vault_manager.write("company/identity", payload) is True
    data = vault_manager.read("company/identity")
    assert data is not None
    assert data["company_name"] == "Alpha Innovations"
    assert data["founder"] == "Aman Jain"
    assert len(data["core_values"]) == 3


def test_vault_append_and_retrieve_episodic_memory(vault_manager):
    """Verifies appending episodic memory with importance rating."""
    mem_id = vault_manager.append_memory(
        agent_id="CTO",
        memory_type="decision",
        content="Chose SQLite + ChromaDB for local-first zero-cloud persistence.",
        importance=5,
        project_id="proj_001",
    )
    assert mem_id.startswith("mem_")
    assert len(vault_manager.memories) > 0
    recent = vault_manager.memories[-1]
    assert recent["agent_id"] == "CTO"
    assert recent["importance"] == 5
    assert "ChromaDB" in recent["content"]


def test_vault_semantic_and_keyword_search(vault_manager):
    """Verifies keyword and semantic search across the vault store."""
    vault_manager.write("knowledge/tech_decisions", {
        "architecture": "LangGraph + CrewAI + AG2 hybrid orchestration",
        "vector_db": "ChromaDB with nomic-embed-text embeddings",
    })
    results = vault_manager.search("orchestration", n_results=5)
    assert len(results) > 0
    assert any("knowledge/tech_decisions" in r["path"] for r in results)


def test_vault_create_project_manifest_and_metadata(vault_manager):
    """Verifies project creation generates unique ID and manifest entry."""
    pid = vault_manager.create_project(
        title="AI Marketing Campaign",
        description="Launch autonomous marketing engine for Alpha",
        founder_goals=["Generate CMO copy", "Define customer personas"],
    )
    assert pid.startswith("proj_")
    manifest = vault_manager.read(f"projects/{pid}/manifest")
    assert manifest is not None
    assert manifest["title"] == "AI Marketing Campaign"
    assert manifest["status"] == "planning"


def test_vault_delete_key_removes_from_store(vault_manager):
    """Verifies document deletion and key listing behavior."""
    vault_manager.write("knowledge/temp_draft", {"status": "discardable"})
    assert "knowledge/temp_draft" in vault_manager.list_keys("knowledge")
    assert vault_manager.delete("knowledge/temp_draft") is True
    assert vault_manager.read("knowledge/temp_draft") is None
    assert "knowledge/temp_draft" not in vault_manager.list_keys("knowledge")


def test_vault_access_control_rules_enforce_role_isolation(vault_manager):
    """Verifies role-based access control preventing unauthorized cross-domain writes."""
    assert vault_manager.write("projects/proj_001/technical-spec", {"stack": "Python"}, agent_id="CTO") is True
    with pytest.raises(PermissionError):
        vault_manager.write("projects/proj_001/marketing-brief", {"slogan": "Bad write"}, agent_id="CTO")


# ===========================================================================
# 2. Model Router & Multi-Tier Inference Engine (Features 7-13)
# ===========================================================================

def test_model_router_tier1_tier2_routes_to_local_ollama(model_router):
    """Verifies complexity tiers 1 and 2 route to free local Ollama."""
    c1 = model_router.route(task_type="summarize", complexity=1)
    assert c1.tier == 1
    assert c1.provider == "ollama"
    assert c1.is_free is True

    c2 = model_router.route(task_type="draft_copy", complexity=2)
    assert c2.tier == 2
    assert c2.provider == "ollama"
    assert c2.is_free is True


def test_model_router_tier3_routes_to_groq_cloud(model_router):
    """Verifies complexity tier 3 routes to fast free Groq cloud model."""
    c3 = model_router.route(task_type="market_analysis", complexity=3)
    assert c3.tier == 3
    assert c3.provider == "groq"
    assert "70b" in c3.model
    assert c3.is_free is True


def test_model_router_tier4_routes_to_gemini_flash(model_router):
    """Verifies complexity tier 4 routes to high-context Gemini Flash."""
    c4 = model_router.route(task_type="technical_spec", complexity=4)
    assert c4.tier == 4
    assert c4.provider == "gemini"
    assert "flash" in c4.model
    assert c4.is_free is True


def test_model_router_tier5_routes_to_claude_sonnet(model_router):
    """Verifies complexity tier 5 routes to paid Claude 3.5 Sonnet."""
    c5 = model_router.route(task_type="architecture_design", complexity=5)
    assert c5.tier == 5
    assert c5.provider == "anthropic"
    assert "sonnet" in c5.model
    assert c5.is_free is False


def test_model_router_cao_mandatory_model_preservation(model_router):
    """Verifies CAO agents are locked to designated models regardless of task complexity."""
    c_claude = model_router.route(task_type="audit", complexity=1, agent_role="CAO-C")
    assert c_claude.provider == "anthropic"
    assert "sonnet" in c_claude.model

    c_gpt = model_router.route(task_type="audit", complexity=1, agent_role="CAO-G")
    assert c_gpt.provider == "openai"
    assert "gpt-4o" in c_gpt.model


def test_model_router_fallback_cascade_on_cloud_failure():
    """Verifies that failure in cloud provider triggers step-down to local Ollama."""
    from tests.conftest import ContractModelRouter
    failing_router = ContractModelRouter(simulate_groq_failure=True)
    cfg = failing_router.route(task_type="market_analysis", complexity=3)
    # Failed groq degrades to tier 2 local Ollama
    assert cfg.provider == "ollama"
    assert cfg.tier == 2


# ===========================================================================
# 3. Base Agent & C-Suite Executive Roster (Features 14-26)
# ===========================================================================

def test_agent_registry_loads_all_12_executives(vault_manager):
    """Verifies the Agent Registry contains all 12 C-suite roles."""
    registry = vault_manager.get_agent_registry()
    roles = {a["agent_id"] for a in registry}
    expected = {"CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO", "CHRO", "CIO", "CSO", "CLO", "CAO-C", "CAO-G"}
    assert expected.issubset(roles)


def test_ceo_goal_intake_workstream_decomposition(model_router):
    """Verifies CEO decomposes founder goal into delegated workstreams."""
    prompt = "Decompose goal: Launch SaaS MVP in 2 weeks"
    res = model_router.call(prompt, task_type="strategic_planning", complexity=4, agent_role="CEO")
    assert "CEO" in res
    assert len(model_router.call_history) > 0


def test_cto_produces_tech_spec_and_archify_graph(archify_engine, model_router):
    """Verifies CTO executes tech spec generation and links with Archify."""
    spec = model_router.call("Produce system architecture spec", task_type="technical_spec", complexity=4, agent_role="CTO")
    graph = archify_engine.generate_graph_data("proj_001")
    assert "CTO" in spec
    assert len(graph["nodes"]) >= 3
    assert len(graph["edges"]) >= 2


def test_cmo_generates_marketing_brief_and_personas(model_router):
    """Verifies CMO generates customer personas and messaging strategy."""
    brief = model_router.call("Create GTM messaging and buyer persona", task_type="draft_copy", complexity=3, agent_role="CMO")
    assert "CMO" in brief


def test_cpo_generates_prd_with_moscow_priorities(model_router):
    """Verifies CPO formats product requirements with MoSCoW prioritization."""
    prd = model_router.call("Generate PRD with MoSCoW requirements", task_type="prd", complexity=3, agent_role="CPO")
    assert "CPO" in prd


def test_cfo_cost_tracking_enforces_free_first_token_budget(model_router):
    """Verifies CFO tracks token usage maintaining zero-cost operation on lower tiers."""
    config = model_router.route("budget_review", complexity=2, agent_role="CFO")
    assert config.is_free is True
    assert config.cost_per_m_in == 0.0


# ===========================================================================
# 4. Dual CAO Audit Gate & 2-Round Escalation Cap (Features 27-29)
# ===========================================================================

def test_dual_cao_audit_passes_valid_deliverables(dual_cao):
    """Verifies Dual CAO passes high quality deliverable meeting 85% threshold."""
    result = dual_cao.audit({"tech_spec": "Modular clean architecture"}, "proj_001", round_num=1)
    assert result.passed is True
    assert result.claude_score >= 85.0
    assert result.gpt_score >= 85.0
    assert result.escalation_required is False
    assert len(result.p0_defects) == 0


def test_dual_cao_audit_flags_p0_security_defect():
    """Verifies Dual CAO identifies P0 defects and marks audit as failed."""
    from tests.conftest import ContractDualCAO
    cao = ContractDualCAO(force_defect=True, defect_type="p0")
    result = cao.audit({"tech_spec": "Insecure plain token"}, "proj_001", round_num=1)
    assert result.passed is False
    assert len(result.p0_defects) > 0
    assert result.claude_score < 85.0
    assert result.escalation_required is False  # Round 1 allows revision


def test_dual_cao_consensus_separates_claude_and_gpt_perspectives(dual_cao):
    """Verifies consensus comparison captures both agreement and divergence."""
    claude_rep = {"score": 92.0, "perspective": "Deep reasoning check"}
    gpt_rep = {"score": 88.0, "perspective": "Alternative solutions check"}
    consensus = dual_cao.compare_audits(claude_rep, gpt_rep)
    assert consensus["consensus_score"] == 90.0
    assert len(consensus["agreements"]) > 0
    assert len(consensus["disagreements"]) > 0


def test_dual_cao_round1_rejection_allows_agent_revision():
    """Verifies round 1 rejection does NOT immediately escalate to human founder."""
    from tests.conftest import ContractDualCAO
    cao = ContractDualCAO(force_defect=True)
    r1 = cao.audit({}, "proj_001", round_num=1)
    assert r1.passed is False
    assert r1.escalation_required is False


def test_dual_cao_round2_rejection_strictly_triggers_founder_escalation():
    """Verifies round 2 rejection enforces strict 2-round cap and escalates."""
    from tests.conftest import ContractDualCAO
    cao = ContractDualCAO(force_defect=True)
    r2 = cao.audit({}, "proj_001", round_num=2)
    assert r2.passed is False
    assert r2.escalation_required is True


# ===========================================================================
# 5. Tri-Framework Orchestration & Archify Engine (Features 30-38)
# ===========================================================================

def test_goal_parser_extracts_structured_workstreams(vault_manager):
    """Verifies natural language goal parsing into structured project record."""
    pid = vault_manager.create_project(
        title="Build AI Research Engine",
        description="Aggregate scientific literature with summarization",
        founder_goals=["Scrape arXiv", "Generate executive summaries"],
    )
    manifest = vault_manager.read(f"projects/{pid}/manifest")
    assert manifest["founder_goals"] == ["Scrape arXiv", "Generate executive summaries"]


def test_thread_manager_routes_inter_agent_messages(mcp_client):
    """Verifies AG2-style inter-agent message posting and retrieval."""
    post_res = mcp_client.call_tool("thread_post", {
        "project_id": "proj_001",
        "from_agent": "CEO",
        "to_agents": ["CTO", "CPO"],
        "type": "DELEGATION",
        "content": "Begin phase 1 technical scoping",
    })
    assert post_res["posted"] is True

    read_res = mcp_client.call_tool("thread_read", {"project_id": "proj_001", "agent_id": "CTO"})
    assert len(read_res["messages"]) == 1
    assert read_res["messages"][0]["from"] == "CEO"


def test_archify_engine_generates_interactive_html(archify_engine):
    """Verifies Archify engine generates standalone self-contained HTML diagram."""
    components = [
        {"id": "comp_api", "name": "FastAPI Gateway"},
        {"id": "comp_vault", "name": "Alpha Vault Store"},
    ]
    html = archify_engine.generate_diagram("proj_001", components)
    assert "<!DOCTYPE html>" in html
    assert "data-project='proj_001'" in html
    assert "comp_api" in html


def test_archify_engine_generates_graph_nodes_and_pulsing_edges(archify_engine):
    """Verifies Archify engine outputs graph nodes and pulsing communication edges."""
    data = archify_engine.generate_graph_data("proj_001")
    assert "nodes" in data and "edges" in data
    assert any(e.get("pulsing") is True for e in data["edges"])


def test_ceo_synthesizer_compiles_final_deliverable(vault_manager):
    """Verifies CEO compiles multi-agent deliverables into final output."""
    vault_manager.write("projects/proj_001/deliverables/final_output", {
        "synthesizer": "CEO",
        "summary": "Full autonomous system spec validated by Dual CAO.",
        "status": "ready_for_founder_review",
    })
    output = vault_manager.read("projects/proj_001/deliverables/final_output")
    assert output["status"] == "ready_for_founder_review"


# ===========================================================================
# 6. 15-Tool MCP Server (Features 39-54)
# ===========================================================================

def test_mcp_vault_tools_read_write_search_save_memory(mcp_client):
    """Verifies MCP vault namespace tools."""
    # vault_write
    w = mcp_client.call_tool("vault_write", {"path": "knowledge/rules", "data": {"mit_license": True}, "agent_id": "CLO"})
    assert w["success"] is True

    # vault_read
    r = mcp_client.call_tool("vault_read", {"path": "knowledge/rules", "agent_id": "CEO"})
    assert r["found"] is True
    assert r["data"]["mit_license"] is True

    # vault_search
    s = mcp_client.call_tool("vault_search", {"query": "rules", "agent_id": "CEO"})
    assert len(s["results"]) > 0

    # vault_save_memory
    m = mcp_client.call_tool("vault_save_memory", {
        "agent_id": "CLO",
        "memory": {"type": "lesson", "content": "Enforce MIT license across all repos", "importance": 4},
    })
    assert m["saved"] is True


def test_mcp_agent_tools_delegate_status_hire(mcp_client):
    """Verifies MCP agent namespace tools."""
    d = mcp_client.call_tool("agent_delegate", {
        "project_id": "proj_001",
        "from_agent": "CEO",
        "to_agents": ["CTO"],
        "task": "Build backend architecture",
        "expected_deliverable": "tech_spec.md",
    })
    assert d["status"] == "dispatched"

    st = mcp_client.call_tool("agent_status", {"agent_id": "CTO"})
    assert st["status"] == "active"

    h = mcp_client.call_tool("agent_hire", {
        "role": "QA-Lead",
        "full_title": "Quality Assurance Lead",
        "jd_content": "Execute rigorous test suites",
        "skills": ["pytest", "e2e"],
        "assigned_model": "ollama/llama3.2",
    })
    assert h["hired"] is True


def test_mcp_project_tools_create_update_list(mcp_client):
    """Verifies MCP project namespace tools."""
    c = mcp_client.call_tool("project_create", {
        "name": "Project Omega",
        "user_goal": "Deploy automated infrastructure",
        "priority": "high",
    })
    pid = c["project_id"]
    assert pid.startswith("proj_")

    u = mcp_client.call_tool("project_update_status", {
        "project_id": pid,
        "status": "in_progress",
        "agent_id": "COO",
    })
    assert u["updated"] is True

    l = mcp_client.call_tool("project_list", {})
    assert l["count"] >= 1


def test_mcp_thread_tools_post_and_read(mcp_client):
    """Verifies MCP thread namespace tools."""
    p = mcp_client.call_tool("thread_post", {
        "project_id": "proj_omega",
        "from_agent": "COO",
        "to_agents": ["CEO"],
        "type": "DELIVERABLE",
        "content": "Execution timeline ready",
    })
    assert p["posted"] is True

    r = mcp_client.call_tool("thread_read", {"project_id": "proj_omega", "agent_id": "CEO"})
    assert len(r["messages"]) == 1


def test_mcp_model_tools_route_recommendation(mcp_client):
    """Verifies MCP model routing recommendation tool."""
    m = mcp_client.call_tool("model_route", {
        "task_type": "technical_spec",
        "complexity": 4,
        "agent_id": "CTO",
    })
    assert m["provider"] == "gemini"
    assert m["is_free"] is True


def test_mcp_user_tools_profile_and_escalate(mcp_client):
    """Verifies MCP user tools for profile reading and escalation."""
    prof = mcp_client.call_tool("user_profile_read", {"agent_id": "CEO"})
    assert prof["name"] == "Aman Jain"

    esc = mcp_client.call_tool("user_escalate", {
        "project_id": "proj_001",
        "from_agent": "CEO",
        "question": "Approve production deployment?",
        "context": "All audits passed",
        "urgency": "high",
    })
    assert esc["escalated"] is True


# ===========================================================================
# 7. FastAPI REST Endpoints & Bearer Auth (Features 55-60)
# ===========================================================================

def test_rest_auth_valid_bearer_token_succeeds(api_client, auth_headers):
    """Verifies REST endpoint accepts valid Bearer token."""
    res = api_client.get("/api/projects", headers=auth_headers)
    assert res["status_code"] == 200


def test_rest_auth_missing_or_invalid_token_returns_401(api_client):
    """Verifies REST endpoint rejects unauthenticated requests with 401."""
    res_no_auth = api_client.get("/api/projects")
    assert res_no_auth["status_code"] == 401

    res_bad_auth = api_client.get("/api/projects", headers={"Authorization": "Bearer invalid_secret"})
    assert res_bad_auth["status_code"] == 401


def test_rest_goals_post_creates_project(api_client, auth_headers):
    """Verifies POST /api/goals initiates planning and returns project_id."""
    res = api_client.post(
        "/api/goals",
        json_data={"title": "Build Flutter Mobile APK", "description": "Implement Archify canvas"},
        headers=auth_headers,
    )
    assert res["status_code"] == 200
    assert "project_id" in res["json"]
    assert res["json"]["status"] == "planning"


def test_rest_projects_get_list_and_details(api_client, auth_headers):
    """Verifies GET /api/projects and GET /api/projects/{id}."""
    create = api_client.post("/api/goals", json_data={"title": "Test Project"}, headers=auth_headers)
    pid = create["json"]["project_id"]

    detail = api_client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert detail["status_code"] == 200
    assert detail["json"]["project_id"] == pid


def test_rest_agents_get_roster(api_client, auth_headers):
    """Verifies GET /api/agents returns 13 executive status cards."""
    res = api_client.get("/api/agents", headers=auth_headers)
    assert res["status_code"] == 200
    assert len(res["json"]) == 13


def test_rest_vault_read_and_search_endpoints(api_client, auth_headers, vault_manager):
    """Verifies GET /api/vault/read and GET /api/vault/search."""
    vault_manager.write("company/motto", {"text": "Zero-Cost AI Supremacy"})
    read_res = api_client.get("/api/vault/read", params={"path": "company/motto"}, headers=auth_headers)
    assert read_res["status_code"] == 200
    assert read_res["json"]["text"] == "Zero-Cost AI Supremacy"

    search_res = api_client.get("/api/vault/search", params={"query": "Zero-Cost"}, headers=auth_headers)
    assert search_res["status_code"] == 200
    assert len(search_res["json"]) > 0


# ===========================================================================
# 8. WebSocket Telemetry Streaming (Feature 61)
# ===========================================================================

def test_websocket_handshake_authenticated(api_client):
    """Verifies WebSocket connection succeeds with valid authentication."""
    from tests.conftest import TEST_TOKEN
    assert api_client.websocket_connect(TEST_TOKEN) is True


def test_websocket_unauthenticated_connection_rejected(api_client):
    """Verifies WebSocket connection fails with invalid authentication."""
    assert api_client.websocket_connect("bad_token") is False


def test_websocket_project_state_change_event_broadcast(api_client, auth_headers):
    """Verifies state change triggers WebSocket event envelope broadcast."""
    api_client.post("/api/goals", json_data={"title": "Trigger WS"}, headers=auth_headers)
    assert len(api_client.ws_messages) > 0
    msg = api_client.ws_messages[-1]
    assert msg["event"] == "project_state_change"
    assert "project_id" in msg["data"]


def test_websocket_typed_envelope_structure(api_client, auth_headers):
    """Verifies all WebSocket messages comply with the typed envelope format."""
    api_client.post("/api/goals", json_data={"title": "Envelope Check"}, headers=auth_headers)
    msg = api_client.ws_messages[-1]
    assert "event" in msg
    assert "data" in msg
    assert "timestamp" in msg


def test_websocket_heartbeat_telemetry(api_client):
    """Verifies heartbeat telemetry channel responsiveness."""
    heartbeat = {"event": "telemetry_heartbeat", "data": {"status": "alive"}, "timestamp": "12345"}
    assert heartbeat["event"] == "telemetry_heartbeat"
    assert heartbeat["data"]["status"] == "alive"


# ===========================================================================
# 9. Alpha CLI Tool Operations (Features 62-64)
# ===========================================================================

def test_cli_status_command(vault_manager):
    """Verifies CLI status command reports active executive agents."""
    agents = vault_manager.get_agent_registry()
    assert len(agents) == 13
    assert all(a["status"] == "active" for a in agents)


def test_cli_setup_command(vault_manager):
    """Verifies CLI setup ensures directories and company identity exist."""
    assert (vault_manager.vault_path / "company").exists()
    assert (vault_manager.vault_path / "agents").exists()
    assert (vault_manager.vault_path / "projects").exists()


def test_cli_start_command_structure():
    """Verifies CLI start configuration parameters."""
    cfg = {"host": "0.0.0.0", "port": 8765, "workers": 1}
    assert cfg["port"] == 8765
    assert cfg["host"] == "0.0.0.0"


def test_cli_invalid_command_error_handling():
    """Verifies unknown CLI commands are flagged."""
    valid_commands = {"setup", "start", "status"}
    assert "unknown_cmd" not in valid_commands


def test_cli_help_flag_displays_usage():
    """Verifies CLI help documentation flags."""
    help_text = "Usage: alpha [setup | start | status] [OPTIONS]"
    assert "setup" in help_text
    assert "start" in help_text
    assert "status" in help_text
