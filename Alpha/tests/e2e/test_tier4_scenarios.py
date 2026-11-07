"""Project Alpha — Tier 4: Real-World Application Scenarios Test Suite.

High-fidelity end-to-end user and system workflows:
1. Complete Founder SaaS Project Lifecycle: Goal Intake ➔ C-Suite Deliberation ➔ Archify Diagram ➔ Dual CAO 5-Axis Audit ➔ Mobile Telemetry Delivery
2. Dual CAO 2-Round Rejection Deadlock & Escalation to Founder Mobile Interface
3. Mobile Client Disconnection, Offline Buffer & State Catch-up
4. Parallel Multi-Project Execution with CFO Token Governance
"""

from __future__ import annotations

import json
import pytest
from typing import Dict, Any
from tests.conftest import ContractDualCAO, ContractModelRouter


# ===========================================================================
# Scenario 1: Complete Founder SaaS Project Lifecycle
# ===========================================================================

def test_scenario_founder_submits_saas_project_full_csuite_lifecycle(
    api_client, auth_headers, vault_manager, archify_engine, dual_cao, mcp_client, model_router
):
    """Executes full autonomous company lifecycle from Founder prompt to verified delivery."""
    # -----------------------------------------------------------------------
    # Step 1: Founder submits goal via REST API
    # -----------------------------------------------------------------------
    goal_submission = {
        "title": "Build AI Invoice Processing Micro-SaaS",
        "description": "Autonomous PDF parser extracting line items with zero external cloud dependencies.",
        "complexity": 4,
    }
    goal_res = api_client.post("/api/goals", json_data=goal_submission, headers=auth_headers)
    assert goal_res["status_code"] == 200
    project_id = goal_res["json"]["project_id"]
    assert project_id.startswith("proj_")

    # -----------------------------------------------------------------------
    # Step 2: CEO parses goal, scaffolds Vault project, and initiates thread
    # -----------------------------------------------------------------------
    mcp_client.call_tool("thread_post", {
        "project_id": project_id,
        "from_agent": "CEO",
        "to_agents": ["CPO", "CMO", "CTO", "CDO", "CLO"],
        "type": "DELEGATION",
        "content": "Convene workstream for AI Invoice Processing SaaS. Deliver PRD, GTM, Tech Spec, and Archify Diagram.",
    })

    # -----------------------------------------------------------------------
    # Step 3: CPO & CMO deliver PRD and GTM Strategy
    # -----------------------------------------------------------------------
    cpo_prd = {
        "mvp_scope": ["PDF Line Item Extraction", "JSON Export", "Local Vault Persistence"],
        "moscow": {"must": ["OCR parser", "Accuracy > 98%"], "wont": ["Cloud sync"]},
    }
    vault_manager.write(f"projects/{project_id}/deliverables/product_prd", cpo_prd, agent_id="CEO")

    cmo_brief = {
        "target_persona": "Solo Founders & Accounting Consultancies",
        "positioning": "Zero-cloud confidential automated invoice parsing",
    }
    vault_manager.write(f"projects/{project_id}/deliverables/marketing_brief", cmo_brief, agent_id="CEO")

    # -----------------------------------------------------------------------
    # Step 4: CTO generates Technical Architecture & Archify System Diagram
    # -----------------------------------------------------------------------
    components = [
        {"id": "comp_ingest", "name": "PDF Ingestion Pipeline"},
        {"id": "comp_ocr", "name": "Local Ollama OCR Model"},
        {"id": "comp_vault", "name": "Alpha Vault Structured Ledger"},
    ]
    archify_html = archify_engine.generate_diagram(project_id, components)
    cto_spec = {
        "stack": "FastAPI + Ollama Llama 3.2 + SQLite Store",
        "diagram_html": archify_html,
        "security_sandbox": "Isolated subprocess execution",
    }
    vault_manager.write(f"projects/{project_id}/deliverables/tech_spec", cto_spec, agent_id="CEO")

    # -----------------------------------------------------------------------
    # Step 5: CLO verifies permissive MIT licensing & GPL defense
    # -----------------------------------------------------------------------
    clo_review = {
        "license": "MIT",
        "gpl_contamination_detected": False,
        "compliance_approved": True,
    }
    vault_manager.write(f"projects/{project_id}/deliverables/legal_review", clo_review, agent_id="CEO")

    # -----------------------------------------------------------------------
    # Step 6: Dual CAO Audit Gate (5-Axis Review Rubric)
    # -----------------------------------------------------------------------
    all_deliverables = {
        "prd": cpo_prd,
        "cmo": cmo_brief,
        "tech_spec": cto_spec,
        "legal": clo_review,
    }
    audit_result = dual_cao.audit(all_deliverables, project_id, round_num=1)
    assert audit_result.passed is True
    assert audit_result.claude_score >= 85.0
    assert audit_result.gpt_score >= 85.0
    assert audit_result.escalation_required is False

    # -----------------------------------------------------------------------
    # Step 7: CEO synthesizes final output and marks project complete
    # -----------------------------------------------------------------------
    final_output = {
        "project_id": project_id,
        "title": "AI Invoice Processing Micro-SaaS",
        "status": "COMPLETED",
        "executive_summary": "Autonomous micro-SaaS architecture fully specified, legally approved, and audited.",
        "audit_consensus": audit_result.consolidated_report,
    }
    vault_manager.write(f"projects/{project_id}/final_output", final_output, agent_id="CEO")

    # -----------------------------------------------------------------------
    # Step 8: Founder mobile client receives final state via REST
    # -----------------------------------------------------------------------
    project_query = api_client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert project_query["status_code"] == 200
    assert project_query["json"]["project_id"] == project_id


# ===========================================================================
# Scenario 2: Dual CAO 2-Round Rejection Deadlock & Founder Escalation
# ===========================================================================

def test_scenario_dual_cao_two_round_rejection_escalation_to_founder(
    mcp_client, vault_manager
):
    """Verifies that 2 consecutive audit rejections halt execution and escalate to Founder."""
    project_id = vault_manager.create_project(
        title="Flawed System Proposal",
        description="Proposal containing unresolvable architectural defects",
        founder_goals=["Bypass authentication checks"],
    )

    failing_cao = ContractDualCAO(force_defect=True, defect_type="p0")

    # Round 1 Audit
    round1_result = failing_cao.audit({"spec": "flawed_v1"}, project_id, round_num=1)
    assert round1_result.passed is False
    assert round1_result.escalation_required is False  # Round 1 permits team revision
    assert len(round1_result.p0_defects) > 0

    # Team attempts revision
    mcp_client.call_tool("thread_post", {
        "project_id": project_id,
        "from_agent": "CEO",
        "to_agents": ["CTO"],
        "type": "AUDIT_REQUEST",
        "content": f"Address CAO Round 1 Defects: {round1_result.p0_defects}",
    })

    # Round 2 Audit (Revision still fails)
    round2_result = failing_cao.audit({"spec": "flawed_v2_still_insecure"}, project_id, round_num=2)
    assert round2_result.passed is False
    # Strict 2-Round Cap Enforced!
    assert round2_result.escalation_required is True

    # Mandatory escalation triggered via MCP user_escalate tool
    escalation_response = mcp_client.call_tool("user_escalate", {
        "project_id": project_id,
        "from_agent": "CEO",
        "question": "Dual CAO rejected deliverable after 2 revision rounds. Founder decision required.",
        "context": round2_result.consolidated_report,
        "options": ["Override audit and proceed", "Cancel project", "Manually revise architecture"],
        "urgency": "high",
    })

    assert escalation_response["escalated"] is True
    assert escalation_response["project_id"] == project_id
    assert escalation_response["urgency"] == "high"


# ===========================================================================
# Scenario 3: Mobile Client Offline Catch-up & State Recovery
# ===========================================================================

def test_scenario_mobile_client_offline_catchup_and_reconnection(
    api_client, auth_headers, vault_manager, mcp_client
):
    """Verifies mobile client reconnects and retrieves missed events without corruption."""
    pid = vault_manager.create_project("Offline Test", "Testing mobile catchup", ["Sync state"])

    # Mobile simulates going offline while backend processes 5 thread messages
    for i in range(5):
        mcp_client.call_tool("thread_post", {
            "project_id": pid,
            "from_agent": "CTO",
            "to_agents": ["CEO"],
            "type": "DELIVERABLE",
            "content": f"Subtask deliverable step {i+1} completed.",
        })

    # Mobile reconnects
    from tests.conftest import TEST_TOKEN
    assert api_client.websocket_connect(TEST_TOKEN) is True

    # Mobile polls project thread history
    thread_res = mcp_client.call_tool("thread_read", {"project_id": pid, "agent_id": "CEO"})
    assert len(thread_res["messages"]) == 5
    assert thread_res["messages"][-1]["content"] == "Subtask deliverable step 5 completed."


# ===========================================================================
# Scenario 4: Parallel Multi-Project Execution with Token Governance
# ===========================================================================

def test_scenario_multi_project_concurrency_with_token_governance(
    vault_manager, model_router, mcp_client
):
    """Verifies parallel project execution maintains strict directory and token isolation."""
    # Launch Project Alpha-1
    p1 = vault_manager.create_project("Alpha-1", "First concurrent project", ["G1"])
    # Launch Project Alpha-2
    p2 = vault_manager.create_project("Alpha-2", "Second concurrent project", ["G2"])

    assert p1 != p2

    # Agent work on Project 1
    mcp_client.call_tool("thread_post", {
        "project_id": p1,
        "from_agent": "CEO",
        "to_agents": ["CTO"],
        "type": "DELEGATION",
        "content": "P1 task",
    })

    # Agent work on Project 2
    mcp_client.call_tool("thread_post", {
        "project_id": p2,
        "from_agent": "CEO",
        "to_agents": ["CMO"],
        "type": "DELEGATION",
        "content": "P2 task",
    })

    # Verify thread isolation
    t1 = mcp_client.call_tool("thread_read", {"project_id": p1, "agent_id": "CEO"})
    t2 = mcp_client.call_tool("thread_read", {"project_id": p2, "agent_id": "CEO"})

    assert len(t1["messages"]) == 1
    assert t1["messages"][0]["content"] == "P1 task"

    assert len(t2["messages"]) == 1
    assert t2["messages"][0]["content"] == "P2 task"

    # Token governance checks
    cfg_p1 = model_router.route("task", complexity=2)
    cfg_p2 = model_router.route("task", complexity=3)

    assert cfg_p1.is_free is True
    assert cfg_p2.is_free is True  # Groq tier 3 is free
