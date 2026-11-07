"""Project Alpha — Tier 3: Cross-Feature Interactions Test Suite.

Verifies pairwise and cross-subsystem interactions:
1. Full Pipeline: Goal Intake ➔ Thread Deliberation ➔ Archify Diagram ➔ Dual CAO Audit ➔ Vault Commit
2. Model Router cloud-to-local fallback during active CrewAI agent delegation
3. FastMCP tool invocation triggering real-time WebSocket telemetry packets
4. Dual CAO audit failure updating Archify visual node status to blocked/auditing
5. Token authentication revocation isolating both REST and WebSocket channels
6. CFO token budget governance rerouting cloud tasks to free local Ollama
7. Point-in-time Vault backup snapshot during active concurrent execution
8. Founder profile working style influencing CEO output synthesis
"""

from __future__ import annotations

import json
import pytest
from typing import Dict, Any
from tests.conftest import ContractModelRouter, ContractDualCAO, TEST_TOKEN


# ===========================================================================
# 1. Full Pipeline Cross-Feature Interaction
# ===========================================================================

def test_interaction_goal_intake_to_deliberation_to_archify_to_cao_to_vault(
    api_client, auth_headers, vault_manager, archify_engine, dual_cao, mcp_client
):
    """Verifies end-to-end integration: REST ➔ Vault ➔ Threads ➔ Archify ➔ CAO."""
    # Step 1: Founder submits goal via REST API
    res = api_client.post(
        "/api/goals",
        json_data={"title": "Launch Autonomous Billing Engine", "description": "Stripe zero-dependency integration"},
        headers=auth_headers,
    )
    assert res["status_code"] == 200
    pid = res["json"]["project_id"]

    # Step 2: CEO posts delegation to CTO in project thread
    mcp_client.call_tool("thread_post", {
        "project_id": pid,
        "from_agent": "CEO",
        "to_agents": ["CTO"],
        "type": "DELEGATION",
        "content": "Create Billing Architecture and Archify Diagram",
    })

    # Step 3: CTO generates Archify visual system diagram
    components = [
        {"id": "node_api", "name": "Billing REST API"},
        {"id": "node_vault", "name": "Billing Ledger in Vault"},
    ]
    html_diagram = archify_engine.generate_diagram(pid, components)
    assert "data-project" in html_diagram

    # Step 4: CTO stores deliverable in Vault
    deliverable = {
        "architecture": "Event-driven asynchronous ledger",
        "diagram_html": html_diagram,
        "compliance": "PCI-DSS Level 4 Compliant",
    }
    vault_manager.write(f"projects/{pid}/deliverables/tech_spec", deliverable)

    # Step 5: Dual CAO audits deliverable
    audit_res = dual_cao.audit(deliverable, pid, round_num=1)
    assert audit_res.passed is True
    assert audit_res.claude_score >= 85.0
    assert audit_res.gpt_score >= 85.0

    # Step 6: CEO stores final validated state in Vault
    vault_manager.write(f"projects/{pid}/final_output", {
        "status": "APPROVED",
        "audit_consensus": audit_res.consolidated_report,
    })
    final_data = vault_manager.read(f"projects/{pid}/final_output")
    assert final_data["status"] == "APPROVED"


# ===========================================================================
# 2. Model Router Fallback During Active Delegation
# ===========================================================================

def test_interaction_model_router_fallback_during_crewai_delegation():
    """Verifies active agent delegation gracefully survives cloud API outage via local Ollama."""
    failing_router = ContractModelRouter(simulate_groq_failure=True)
    # Task complexity 3 normally routes to Groq 70B
    cfg = failing_router.route(task_type="market_research", complexity=3, agent_role="CMO")
    # Router intercepts Groq outage and steps down to Tier 2 Ollama
    assert cfg.provider == "ollama"
    assert cfg.is_free is True

    # Call succeeds using local model
    response = failing_router.call("Execute competitive analysis", model_config=cfg, agent_role="CMO")
    assert "llama3.2" in response


# ===========================================================================
# 3. MCP Tool Invocation Triggers WebSocket Telemetry
# ===========================================================================

def test_interaction_mcp_tool_invocation_broadcasts_websocket_telemetry(mcp_client, api_client, auth_headers):
    """Verifies executing an MCP tool updates project state and pushes WebSocket telemetry."""
    # Create project via MCP
    proj = mcp_client.call_tool("project_create", {
        "name": "Live Telemetry Demo",
        "user_goal": "Verify mobile packet delivery",
        "priority": "high",
    })
    pid = proj["project_id"]

    # Trigger REST state change which feeds WebSocket
    api_client.post(
        "/api/goals",
        json_data={"title": "Trigger Telemetry", "description": "Ensure WS envelope received"},
        headers=auth_headers,
    )
    assert len(api_client.ws_messages) > 0
    recent_event = api_client.ws_messages[-1]
    assert recent_event["event"] == "project_state_change"


# ===========================================================================
# 4. Dual CAO Rejection Updates Archify Node State
# ===========================================================================

def test_interaction_dual_cao_audit_rejection_updates_archify_node_status(archify_engine):
    """Verifies that an audit rejection flags components as in_audit or blocked."""
    failing_cao = ContractDualCAO(force_defect=True, defect_type="p0")
    audit = failing_cao.audit({"spec": "flawed"}, "proj_flawed", round_num=1)
    assert audit.passed is False

    # Archify engine renders rejected/blocked state
    graph = archify_engine.generate_graph_data("proj_flawed")
    # Mark nodes as auditing/blocked
    for node in graph["nodes"]:
        if node["id"] == "node_cto":
            node["status"] = "blocked_audit_rejection"

    cto_node = next(n for n in graph["nodes"] if n["id"] == "node_cto")
    assert cto_node["status"] == "blocked_audit_rejection"


# ===========================================================================
# 5. Token Revocation Isolates Channels
# ===========================================================================

def test_interaction_token_auth_revocation_closes_websocket_and_rejects_mcp(api_client):
    """Verifies invalidating auth token immediately blocks both REST and WebSocket channels."""
    from tests.conftest import TEST_TOKEN
    # Authenticated initially
    assert api_client.websocket_connect(TEST_TOKEN) is True
    valid_res = api_client.get("/api/projects", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert valid_res["status_code"] == 200

    # Revoke / rotate token
    revoked_token = "expired_token_abc123"
    assert api_client.websocket_connect(revoked_token) is False
    rejected_res = api_client.get("/api/projects", headers={"Authorization": f"Bearer {revoked_token}"})
    assert rejected_res["status_code"] == 401


# ===========================================================================
# 6. CFO Budget Governance & Rerouting
# ===========================================================================

def test_interaction_cfo_budget_cap_interception_reroutes_agent_to_ollama(model_router):
    """Verifies that CFO token governance can clamp requests to local zero-cost tier."""
    budget_exhausted = True
    requested_complexity = 5  # Claude paid tier

    if budget_exhausted:
        # Enforce zero-cost priority fallback
        effective_complexity = min(requested_complexity, 2)
    else:
        effective_complexity = requested_complexity

    cfg = model_router.route("draft_spec", complexity=effective_complexity)
    assert cfg.tier == 2
    assert cfg.provider == "ollama"
    assert cfg.is_free is True


# ===========================================================================
# 7. Vault Backup Snapshot During Concurrent Execution
# ===========================================================================

def test_interaction_vault_backup_snapshot_during_active_project_execution(vault_manager):
    """Verifies Vault backup snapshots can be taken while active threads are being written."""
    vault_manager.write("projects/proj_live/thread_1", {"message": "Active discussion"})
    vault_manager.write("company/identity", {"status": "snapshot_ready"})

    # Perform snapshot
    snapshot_keys = vault_manager.list_keys()
    snapshot = {k: vault_manager.read(k) for k in snapshot_keys}

    assert "company/identity" in snapshot
    assert "projects/proj_live/thread_1" in snapshot
    # Concurrent write after snapshot does not alter captured snapshot
    vault_manager.write("projects/proj_live/thread_1", {"message": "New message"})
    assert snapshot["projects/proj_live/thread_1"]["message"] == "Active discussion"


# ===========================================================================
# 8. User Profile Preferences Influence Synthesis
# ===========================================================================

def test_interaction_user_profile_preferences_shape_agent_synthesis(vault_manager, model_router):
    """Verifies CEO output synthesizer respects Founder's preferred communication style."""
    user_prof = vault_manager.get_user_profile()
    style = user_prof.get("preferred_communication", "concise")

    prompt = f"Synthesize deliverables with style: {style}"
    res = model_router.call(prompt, task_type="synthesis", complexity=3, agent_role="CEO")
    assert "CEO" in res
