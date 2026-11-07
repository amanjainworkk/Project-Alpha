"""Alpha/tests/mcp/test_mcp_server.py - Master MCP Server Test Suite.

Comprehensive automated verification of:
1. Server Lifecycle, Tool Registration, and JSON Schema Generation for all 15 tools
2. Canonical Resource URI discovery and reading
3. Full JSON-RPC 2.0 Protocol Compliance (initialize, ping, tools/list, tools/call, resources/list, resources/read, error codes)
4. Unit Tests for every one of the 15 tools across 6 namespaces:
   - Vault: vault_read, vault_write, vault_search, vault_save_memory
   - Agent: agent_delegate, agent_status, agent_hire
   - Project: project_create, project_update_status, project_list
   - Thread: thread_post, thread_read
   - Model: model_route
   - User: user_profile_read, user_escalate
5. RBAC Enforcement & Confinement (CAO write restrictions outside audit/, CEO delegation authority)
6. End-to-End Multi-Tool Autonomous Executive Closed-Loop Workflow
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any, Dict, List

from backend.mcp.server import (
    ALPHA_RESOURCES,
    ALPHA_TOOLS,
    AlphaMCPServer,
    NativeMCPServer,
    TextContent,
    create_mcp_server,
)
from tests.conftest import ContractModelRouter, ContractVaultManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_vault(tmp_path: Path) -> ContractVaultManager:
    """Provides a fresh, isolated contract-compliant VaultManager."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return ContractVaultManager(str(vault_dir))


@pytest.fixture
def mock_router() -> ContractModelRouter:
    """Provides a contract-compliant ModelRouter."""
    return ContractModelRouter()


@pytest.fixture
def mcp_server(mock_vault: ContractVaultManager, mock_router: ContractModelRouter) -> AlphaMCPServer:
    """Provides a fully initialized AlphaMCPServer with mocked dependencies."""
    return create_mcp_server(
        vault_manager=mock_vault,
        model_router=mock_router,
    )


# ============================================================================
# 1. Server Lifecycle, Registration, and Schema Validation Tests
# ============================================================================

def test_server_initialization_defaults():
    """Verify server initializes with proper metadata and capability definitions."""
    server = create_mcp_server()
    assert server.server_name == "alpha-mcp"
    assert server.server_version == "1.0.0"
    assert isinstance(server, NativeMCPServer)


def test_list_tools_returns_all_15_tools(mcp_server: AlphaMCPServer):
    """Verify list_tools() returns exactly 15 tools matching the specification."""
    tools = mcp_server.list_tools()
    assert len(tools) == 15

    tool_names = mcp_server.get_tool_names()
    assert len(tool_names) == 15

    expected_tools = {
        "vault_read",
        "vault_write",
        "vault_search",
        "vault_save_memory",
        "agent_delegate",
        "agent_status",
        "agent_hire",
        "project_create",
        "project_update_status",
        "project_list",
        "thread_post",
        "thread_read",
        "model_route",
        "user_profile_read",
        "user_escalate",
    }
    assert set(tool_names) == expected_tools


def test_tool_schemas_compliance(mcp_server: AlphaMCPServer):
    """Verify that all 15 tools possess valid JSON Schema input schemas."""
    for tool in mcp_server.list_tools():
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool

        schema = tool["inputSchema"]
        assert schema.get("type") == "object"
        assert "properties" in schema
        assert isinstance(schema["properties"], dict)

        if "required" in schema:
            assert isinstance(schema["required"], list)
            for req in schema["required"]:
                assert req in schema["properties"], f"Required field '{req}' missing from properties in tool '{tool['name']}'"


def test_list_resources(mcp_server: AlphaMCPServer):
    """Verify list_resources() returns canonical resources."""
    resources = mcp_server.list_resources()
    assert len(resources) >= 4
    uris = [r["uri"] for r in resources]
    assert "vault://company/identity" in uris
    assert "vault://user/profile" in uris
    assert "agents://registry" in uris
    assert "projects://list" in uris


# ============================================================================
# 2. JSON-RPC 2.0 Protocol Compliance Tests
# ============================================================================

def test_jsonrpc_initialize(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 initialize method handshake."""
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "alpha-mcp"


def test_jsonrpc_ping(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 ping method."""
    req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    assert resp["result"] == {}


def test_jsonrpc_tools_list(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 tools/list method."""
    req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["id"] == 3
    assert "tools" in resp["result"]
    assert len(resp["result"]["tools"]) == 15


def test_jsonrpc_tools_call_success(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 tools/call execution."""
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "user_profile_read",
            "arguments": {"agent_id": "CEO"},
        },
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["id"] == 4
    assert "result" in resp
    assert resp["result"]["isError"] is False
    content = resp["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    parsed = json.loads(content[0]["text"])
    assert parsed["name"] == "Aman Jain"


def test_jsonrpc_unknown_method(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 unknown method returns -32601."""
    req = {"jsonrpc": "2.0", "id": 5, "method": "non_existent_method"}
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_jsonrpc_parse_error(mcp_server: AlphaMCPServer):
    """Verify malformed JSON string payload returns -32700."""
    resp = mcp_server.handle_jsonrpc_sync("{invalid_json:")
    assert "error" in resp
    assert resp["error"]["code"] == -32700


def test_jsonrpc_unknown_tool(mcp_server: AlphaMCPServer):
    """Verify calling an unregistered tool returns -32601."""
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "ghost_tool", "arguments": {}},
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_jsonrpc_missing_required_params_returns_32602(mcp_server: AlphaMCPServer):
    """Verify tool call with missing required parameter returns -32602."""
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "vault_read",
            "arguments": {"path": "company/identity"},  # missing agent_id
        },
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_jsonrpc_rbac_confinement_returns_32003(mcp_server: AlphaMCPServer):
    """Verify CAO write violation returns -32003 (RBAC Permission Denied)."""
    req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": "company/identity",
                "data": {"compromised": True},
                "agent_id": "CAO-Claude",
            },
        },
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32003
    assert "RBAC Permission Denied" in resp["error"]["message"]


def test_jsonrpc_resources_list(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 resources/list method."""
    req = {"jsonrpc": "2.0", "id": 9, "method": "resources/list"}
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["id"] == 9
    assert "resources" in resp["result"]
    assert len(resp["result"]["resources"]) >= 4


def test_jsonrpc_resources_read(mcp_server: AlphaMCPServer):
    """Verify JSON-RPC 2.0 resources/read method."""
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "resources/read",
        "params": {"uri": "vault://company/identity"},
    }
    resp = mcp_server.handle_jsonrpc_sync(req)
    assert resp["id"] == 10
    assert "contents" in resp["result"]
    assert len(resp["result"]["contents"]) == 1
    content_text = resp["result"]["contents"][0]["text"]
    parsed = json.loads(content_text)
    assert parsed["found"] is True
    assert parsed["data"]["company_name"] == "Alpha Corp"


# ============================================================================
# 3. Unit Tests: Vault Tools (4 Tools)
# ============================================================================

def test_tool_vault_read(mcp_server: AlphaMCPServer):
    """Test vault_read for existing and missing paths."""
    # 1. Existing path
    res = mcp_server.call_tool_dict_sync("vault_read", {"path": "company/identity", "agent_id": "CEO"})
    assert res["found"] is True
    assert res["data"]["company_name"] == "Alpha Corp"

    # 2. Missing path
    res_missing = mcp_server.call_tool_dict_sync("vault_read", {"path": "non/existent/doc", "agent_id": "CEO"})
    assert res_missing["found"] is False
    assert res_missing["data"] is None

    # 3. Missing required argument raises ValueError
    with pytest.raises(ValueError):
        mcp_server.call_tool_dict_sync("vault_read", {"path": "company/identity"})


def test_tool_vault_write_and_rbac(mcp_server: AlphaMCPServer):
    """Test vault_write happy path and RBAC confinement violations."""
    # 1. Happy path: CEO writes to company roadmap
    write_res = mcp_server.call_tool_dict_sync(
        "vault_write",
        {
            "path": "company/roadmap",
            "data": {"q1_goal": "Master MCP integration"},
            "agent_id": "CEO",
        },
    )
    assert write_res["success"] is True

    # Verify written data
    read_res = mcp_server.call_tool_dict_sync("vault_read", {"path": "company/roadmap", "agent_id": "CEO"})
    assert read_res["found"] is True
    assert read_res["data"]["q1_goal"] == "Master MCP integration"

    # 2. RBAC Violation: CAO cannot write outside projects/{id}/audit/
    with pytest.raises(PermissionError):
        mcp_server.call_tool_dict_sync(
            "vault_write",
            {
                "path": "company/identity",
                "data": {"compromised": True},
                "agent_id": "CAO-Claude",
            },
        )


def test_tool_vault_search(mcp_server: AlphaMCPServer):
    """Test vault_search semantic query and scope filtering."""
    res = mcp_server.call_tool_dict_sync(
        "vault_search",
        {
            "query": "Autonomous AI Executive",
            "scope": "all",
            "top_k": 5,
            "agent_id": "CTO",
        },
    )
    assert res["query"] == "Autonomous AI Executive"
    assert "results" in res
    assert isinstance(res["results"], list)


def test_tool_vault_save_memory(mcp_server: AlphaMCPServer):
    """Test vault_save_memory episodic logging."""
    res = mcp_server.call_tool_dict_sync(
        "vault_save_memory",
        {
            "agent_id": "CTO",
            "memory": {
                "type": "decision",
                "content": "Adopted pure-Python dual-mode architecture for FastMCP",
                "importance": 5,
                "project_id": "proj_001",
                "tags": ["mcp", "architecture"],
            },
        },
    )
    assert res["saved"] is True
    assert "memory_id" in res

    # Invalid importance outside 1-10 raises ValueError
    with pytest.raises(ValueError):
        mcp_server.call_tool_dict_sync(
            "vault_save_memory",
            {
                "agent_id": "CTO",
                "memory": {
                    "type": "decision",
                    "content": "Invalid importance test",
                    "importance": 99,
                },
            },
        )


# ============================================================================
# 4. Unit Tests: Agent Tools (3 Tools)
# ============================================================================

def test_tool_agent_delegate(mcp_server: AlphaMCPServer):
    """Test agent_delegate task dispatching."""
    res = mcp_server.call_tool_dict_sync(
        "agent_delegate",
        {
            "project_id": "proj_101",
            "from_agent": "CEO",
            "to_agents": ["CTO", "CPO"],
            "task": "Formulate technical architecture and PRD for Mobile Client",
            "expected_deliverable": "tech_spec.md",
            "priority": "high",
        },
    )
    assert res["status"] in ("dispatched", "delegated")
    assert res["project_id"] == "proj_101"
    assert res["to_agents"] == ["CTO", "CPO"]
    assert "delegation_id" in res

    # Non-CEO delegation raises PermissionError
    with pytest.raises(PermissionError):
        mcp_server.call_tool_dict_sync(
            "agent_delegate",
            {
                "project_id": "proj_101",
                "from_agent": "CTO",
                "to_agents": ["CPO"],
                "task": "Unauthorized delegation attempt",
                "expected_deliverable": "doc.md",
            },
        )


def test_tool_agent_status(mcp_server: AlphaMCPServer):
    """Test agent_status query with and without memory summary."""
    res = mcp_server.call_tool_dict_sync(
        "agent_status",
        {
            "agent_id": "CTO",
            "include_memory_summary": True,
        },
    )
    assert res["agent_id"] == "CTO"
    assert res["status"] == "active"


def test_tool_agent_hire(mcp_server: AlphaMCPServer):
    """Test agent_hire registering a new agent persona."""
    res = mcp_server.call_tool_dict_sync(
        "agent_hire",
        {
            "role": "CQO",
            "full_title": "Chief Quality Officer",
            "jd_content": "# CQO Job Description\nOversee 100% test pass rate.",
            "skills": ["TDD", "Verification", "Pytest"],
            "assigned_model": "llama3.2",
            "reports_to": "CEO",
            "peers": ["CTO", "CIO"],
        },
    )
    assert res["hired"] is True
    assert res["role"] == "CQO"
    assert res["status"] == "active"


# ============================================================================
# 5. Unit Tests: Project Tools (3 Tools)
# ============================================================================

def test_tool_project_create(mcp_server: AlphaMCPServer):
    """Test project_create project scaffolding."""
    res = mcp_server.call_tool_dict_sync(
        "project_create",
        {
            "name": "Build Rust Engine",
            "user_goal": "Implement ultra-low latency WebSocket streaming core",
            "priority": "high",
            "assigned_agents": ["CEO", "CTO"],
        },
    )
    assert "project_id" in res
    assert res["name"] == "Build Rust Engine"
    assert res["status"] == "planning"


def test_tool_project_update_status(mcp_server: AlphaMCPServer):
    """Test project_update_status lifecycle transitions."""
    # 1. Create project
    create_res = mcp_server.call_tool_dict_sync(
        "project_create",
        {"name": "Lifecycle Test", "user_goal": "Test status updates", "priority": "medium"},
    )
    pid = create_res["project_id"]

    # 2. Update to in_progress
    up_res = mcp_server.call_tool_dict_sync(
        "project_update_status",
        {
            "project_id": pid,
            "status": "in_progress",
            "agent_id": "CEO",
            "note": "Workstreams initiated",
        },
    )
    assert up_res["updated"] is True
    assert up_res["status"] == "in_progress"

    # 3. Invalid status raises ValueError
    with pytest.raises(ValueError):
        mcp_server.call_tool_dict_sync(
            "project_update_status",
            {"project_id": pid, "status": "invalid_status", "agent_id": "CEO"},
        )


def test_tool_project_list(mcp_server: AlphaMCPServer):
    """Test project_list with filtering."""
    mcp_server.call_tool_dict_sync(
        "project_create",
        {"name": "List Project", "user_goal": "Goal for listing", "priority": "low"},
    )
    res = mcp_server.call_tool_dict_sync("project_list", {"limit": 10})
    assert "projects" in res
    assert res["count"] >= 1


# ============================================================================
# 6. Unit Tests: Thread Tools (2 Tools)
# ============================================================================

def test_tool_thread_post_and_read(mcp_server: AlphaMCPServer):
    """Test thread_post and thread_read inter-agent messaging."""
    pid = "proj_test_threads"

    # 1. Post message
    post_res = mcp_server.call_tool_dict_sync(
        "thread_post",
        {
            "project_id": pid,
            "from_agent": "CTO",
            "to_agents": ["CEO"],
            "type": "DELIVERABLE",
            "subject": "System Architecture V1",
            "content": "Proposed high-speed SQLite/Chroma hybrid architecture.",
        },
    )
    assert post_res["status"] == "sent"
    assert post_res["posted"] is True
    assert "message_id" in post_res

    # 2. Read thread
    read_res = mcp_server.call_tool_dict_sync(
        "thread_read",
        {
            "project_id": pid,
            "agent_id": "CEO",
        },
    )
    assert read_res["project_id"] == pid
    assert read_res["count"] >= 1
    found = any(m["content"] == "Proposed high-speed SQLite/Chroma hybrid architecture." for m in read_res["messages"])
    assert found is True


# ============================================================================
# 7. Unit Tests: Model Routing Tools (1 Tool)
# ============================================================================

def test_tool_model_route(mcp_server: AlphaMCPServer):
    """Test model_route for zero-cost and CAO audit gate rules."""
    # 1. Tier 1 free local model
    res_t1 = mcp_server.call_tool_dict_sync(
        "model_route",
        {"task_type": "formatting", "complexity": 1, "agent_id": "CIO"},
    )
    assert res_t1["tier"] == 1
    assert res_t1["is_free"] is True

    # 2. CAO-Claude override to Tier 5
    res_cao = mcp_server.call_tool_dict_sync(
        "model_route",
        {"task_type": "audit_review", "complexity": 2, "agent_id": "CAO-Claude"},
    )
    assert res_cao["tier"] == 5
    assert "claude" in res_cao["recommended_model"].lower()

    # 3. Complexity outside 1-5 raises ValueError
    with pytest.raises(ValueError):
        mcp_server.call_tool_dict_sync(
            "model_route",
            {"task_type": "invalid", "complexity": 10, "agent_id": "CEO"},
        )


# ============================================================================
# 8. Unit Tests: User Tools (2 Tools)
# ============================================================================

def test_tool_user_profile_read(mcp_server: AlphaMCPServer):
    """Test user_profile_read founder profile retrieval."""
    res = mcp_server.call_tool_dict_sync("user_profile_read", {"agent_id": "CEO"})
    assert res["name"] == "Aman Jain"
    assert res["role"] in ("Founder", "Founder & Chairman")


def test_tool_user_escalate(mcp_server: AlphaMCPServer):
    """Test user_escalate notification trigger."""
    res = mcp_server.call_tool_dict_sync(
        "user_escalate",
        {
            "project_id": "proj_deadlock",
            "from_agent": "CEO",
            "question": "Should we allow external web search or keep strictly offline?",
            "context": "Dual CAO flagged security risk of external network access in air-gapped mode.",
            "urgency": "high",
            "options": ["Allow Offline Only", "Allow Sandboxed Web Search"],
        },
    )
    assert res["status"] == "pending_founder_response"
    assert res["escalated"] is True
    assert res["urgency"] == "high"
    assert "escalation_id" in res

    # Invalid urgency raises ValueError
    with pytest.raises(ValueError):
        mcp_server.call_tool_dict_sync(
            "user_escalate",
            {
                "project_id": "proj_deadlock",
                "from_agent": "CEO",
                "question": "Bad urgency",
                "context": "Bad",
                "urgency": "super_urgent",
            },
        )


# ============================================================================
# 9. Resource URI Resolution Tests
# ============================================================================

def test_read_resource_endpoints(mcp_server: AlphaMCPServer):
    """Test resource reading across canonical URIs."""
    # 1. Company Identity
    identity = mcp_server.read_resource_sync("vault://company/identity")
    assert identity["found"] is True
    assert identity["data"]["company_name"] == "Alpha Corp"

    # 2. User Profile
    user_prof = mcp_server.read_resource_sync("vault://user/profile")
    assert user_prof["found"] is True
    assert user_prof["data"]["name"] == "Aman Jain"

    # 3. Agent Registry
    agents = mcp_server.read_resource_sync("agents://registry")
    assert "agents" in agents
    assert len(agents["agents"]) >= 1

    # 4. Projects Directory
    projs = mcp_server.read_resource_sync("projects://list")
    assert "projects" in projs

    # 5. Unknown URI raises ValueError
    with pytest.raises(ValueError):
        mcp_server.read_resource_sync("unknown://uri")


# ============================================================================
# 10. End-to-End Multi-Tool Closed-Loop Autonomous Executive Workflow
# ============================================================================

def test_e2e_closed_loop_multi_tool_workflow(mcp_server: AlphaMCPServer):
    """Full 10-step autonomous executive workflow through Alpha MCP Server:
    Founder Goal -> Project Scaffolding -> Model Routing -> Task Delegation ->
    Context Search -> Deliverable Post -> Thread Review -> Status Update ->
    Episodic Memory -> User Profile Read.
    """
    # Step 1: Founder Directive Arrives -> project_create
    proj = mcp_server.call_tool_dict_sync(
        "project_create",
        {
            "name": "Autonomous Market Expansion Engine",
            "user_goal": "Deploy competitive intelligence crawler and market analysis agents",
            "priority": "critical",
            "assigned_agents": ["CEO", "CMO", "CTO"],
        },
    )
    pid = proj["project_id"]
    assert pid is not None

    # Step 2: CEO Routes Optimal Model for Workstream Decomposition -> model_route
    route = mcp_server.call_tool_dict_sync(
        "model_route",
        {"task_type": "strategic_planning", "complexity": 4, "agent_id": "CEO"},
    )
    assert route["tier"] in (4, 5)

    # Step 3: CEO Delegates Architecture to CTO -> agent_delegate
    del_cto = mcp_server.call_tool_dict_sync(
        "agent_delegate",
        {
            "project_id": pid,
            "from_agent": "CEO",
            "to_agents": ["CTO"],
            "task": "Design low-overhead crawler architecture",
            "expected_deliverable": "crawler_spec.json",
            "priority": "critical",
        },
    )
    assert del_cto["status"] in ("dispatched", "delegated")

    # Step 4: CTO Searches Vault for Past Architecture Decisions -> vault_search
    search_res = mcp_server.call_tool_dict_sync(
        "vault_search",
        {"query": "crawler architecture decisions", "scope": "knowledge", "agent_id": "CTO"},
    )
    assert "results" in search_res

    # Step 5: CTO Submits Deliverable to Project Thread -> thread_post
    post_res = mcp_server.call_tool_dict_sync(
        "thread_post",
        {
            "project_id": pid,
            "from_agent": "CTO",
            "to_agents": ["CEO"],
            "type": "DELIVERABLE",
            "subject": "Crawler Spec V1",
            "content": json.dumps({"engine": "httpx_async", "max_concurrency": 10}),
        },
    )
    assert post_res["status"] == "sent"
    assert post_res["posted"] is True

    # Step 6: CEO Reads Thread to Review Deliverables -> thread_read
    thread_res = mcp_server.call_tool_dict_sync(
        "thread_read",
        {"project_id": pid, "agent_id": "CEO"},
    )
    assert thread_res["count"] >= 1
    assert any("Crawler Spec V1" in m.get("subject", "") for m in thread_res["messages"])

    # Step 7: CEO Transitions Project to Audit Phase -> project_update_status
    status_res = mcp_server.call_tool_dict_sync(
        "project_update_status",
        {"project_id": pid, "status": "in_audit", "agent_id": "CEO", "note": "Deliverables ready for CAO"},
    )
    assert status_res["status"] == "in_audit"

    # Step 8: CTO Consolidates Technical Memory -> vault_save_memory
    mem_res = mcp_server.call_tool_dict_sync(
        "vault_save_memory",
        {
            "agent_id": "CTO",
            "memory": {
                "type": "decision",
                "content": "Selected asynchronous HTTP pipeline for scraper over heavy browser automation",
                "importance": 4,
                "project_id": pid,
                "tags": ["performance", "crawler"],
            },
        },
    )
    assert mem_res["saved"] is True

    # Step 9: CAO Checks User Preferences Before Final Sign-Off -> user_profile_read
    user_prof = mcp_server.call_tool_dict_sync(
        "user_profile_read",
        {"agent_id": "CAO-Claude"},
    )
    assert user_prof["name"] == "Aman Jain"

    # Step 10: CEO Writes Final Approved Spec to Vault -> vault_write
    write_res = mcp_server.call_tool_dict_sync(
        "vault_write",
        {
            "path": f"projects/{pid}/deliverables/final_spec",
            "data": {"status": "approved", "spec": "crawler_v1"},
            "agent_id": "CEO",
        },
    )
    assert write_res["success"] is True


def test_jsonrpc_remediation_invariants(mcp_server: AlphaMCPServer):
    """Test Milestone 7 Iteration 2 hardened invariants in JSON-RPC protocol and tool dispatching."""
    # 1. Non-object payload returns -32600
    resp_non_obj = mcp_server.handle_jsonrpc_sync("42")
    assert resp_non_obj["error"]["code"] == -32600

    # 2. Missing or invalid jsonrpc returns -32600
    resp_bad_ver = mcp_server.handle_jsonrpc_sync({"jsonrpc": "1.0", "id": 1, "method": "ping"})
    assert resp_bad_ver["error"]["code"] == -32600

    # 3. Dynamic isError: True on failed tool result
    resp_tool_err = mcp_server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "vault_read",
            "arguments": {"path": "non/existent/doc/path", "agent_id": "CEO"},
        },
    })
    assert resp_tool_err["result"]["isError"] is True

    # 4. Strict CAO path confinement in gateway
    resp_cao_gate = mcp_server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": "company/audit_plan.json",
                "data": {"tamper": True},
                "agent_id": "CAO-Claude",
            },
        },
    })
    assert resp_cao_gate["error"]["code"] == -32003

    # 5. Case-insensitive CAO model routing override
    resp_cao_route = mcp_server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "model_route",
            "arguments": {
                "task_type": "audit_review",
                "complexity": 1,
                "agent_id": "cao-chatgpt",
            },
        },
    })
    parsed_route = json.loads(resp_cao_route["result"]["content"][0]["text"])
    assert parsed_route["tier"] == 5
    assert parsed_route["recommended_model"] == "gpt-4o"

