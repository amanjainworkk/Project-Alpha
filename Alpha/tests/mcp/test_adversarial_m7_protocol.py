"""Alpha/tests/mcp/test_adversarial_m7_protocol.py - Adversarial Protocol & Workflow Test Suite.

Milestone 7 Adversarial Verification:
1. Malformed JSON-RPC wire attacks:
   - Non-JSON strings, non-object JSON payloads, missing/invalid jsonrpc version,
     missing/non-string method, non-existent methods, non-existent tools, missing/invalid parameters.
   - Strict verification of standard JSON-RPC 2.0 error codes:
     * -32700: Parse error
     * -32600: Invalid Request
     * -32601: Method not found / Tool not found
     * -32602: Invalid params
     * -32003: RBAC Permission Denied
2. RBAC Confinement & Authority Stress:
   - CAO write confinement outside audit/ rejected with -32003
   - Non-CEO delegation rejected with -32003
3. Canonical & Malicious Resource URI Stress:
   - Canonical URIs resolution
   - Path traversal rejection (vault://../../evil)
   - Malicious URI schemes rejection (ftp://, file://, http://)
4. Multi-threaded Concurrency:
   - 25+ concurrent threads making simultaneous tool calls and resource reads without deadlocks
5. Complex Closed-Loop Multi-Tool Autonomous Workflow:
   - Chaining 10+ sequential tool operations across all 6 namespaces
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.mcp.server import (
    ALPHA_RESOURCES,
    ALPHA_TOOLS,
    AlphaMCPServer,
    create_mcp_server,
)
from tests.conftest import ContractModelRouter, ContractVaultManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_vault(tmp_path: Path) -> ContractVaultManager:
    """Isolated, contract-compliant VaultManager instance."""
    vault_dir = tmp_path / "adversarial_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return ContractVaultManager(str(vault_dir))


@pytest.fixture
def mock_router() -> ContractModelRouter:
    """Contract-compliant ModelRouter instance."""
    return ContractModelRouter()


@pytest.fixture
def server(mock_vault: ContractVaultManager, mock_router: ContractModelRouter) -> AlphaMCPServer:
    """Fully initialized AlphaMCPServer instance for adversarial testing."""
    return create_mcp_server(
        vault_manager=mock_vault,
        model_router=mock_router,
    )


# ============================================================================
# 1. Malformed JSON-RPC Wire Attacks & Protocol Compliance
# ============================================================================

def test_malformed_json_syntax_returns_32700(server: AlphaMCPServer):
    """Wire Attack: Non-JSON raw strings must return error code -32700 (Parse error)."""
    malformed_payloads = [
        "{invalid_json:",
        '{"jsonrpc": "2.0", "method": "ping", broken}',
        "Just a plain text message",
        "",
        "   ",
        "{{}}",
    ]
    for payload in malformed_payloads:
        resp = server.handle_jsonrpc_sync(payload)
        assert resp.get("jsonrpc") == "2.0", f"Response missing jsonrpc header for: {payload}"
        assert resp.get("id") is None, f"Response id should be None for parse error: {payload}"
        assert "error" in resp, f"Expected error block for: {payload}"
        assert resp["error"]["code"] == -32700, f"Expected -32700, got: {resp['error']}"


def test_non_object_json_payloads_must_return_32600(server: AlphaMCPServer):
    """Wire Attack: Valid JSON primitives or arrays that are NOT JSON objects must return -32600 (Invalid Request)

    According to JSON-RPC 2.0 Section 5, a Request MUST be an object.
    Servers must not crash with uncaught AttributeError or TypeError.
    """
    non_object_payloads = [
        "123",
        "[1, 2, 3]",
        '"just_a_string"',
        "true",
        "null",
        123,
        [1, 2, 3],
    ]
    for payload in non_object_payloads:
        try:
            resp = server.handle_jsonrpc_sync(payload)
            assert "error" in resp, f"Expected error response for non-object payload: {payload}"
            assert resp["error"]["code"] in (-32600, -32700), (
                f"Expected -32600 (Invalid Request) or -32700 (Parse error), got: {resp['error']}"
            )
        except AttributeError as ae:
            pytest.fail(f"Vulnerability confirmed: Server crashed with uncaught AttributeError on payload '{payload}': {ae}")
        except Exception as e:
            pytest.fail(f"Vulnerability confirmed: Server crashed with uncaught {type(e).__name__} on payload '{payload}': {e}")


def test_missing_jsonrpc_version_must_return_32600(server: AlphaMCPServer):
    """Wire Attack: JSON-RPC requests omitting 'jsonrpc: 2.0' must return -32600 (Invalid Request).

    JSON-RPC 2.0 Section 4 explicitly requires 'jsonrpc': '2.0'.
    """
    req = {
        "id": 101,
        "method": "ping",
        # missing "jsonrpc": "2.0"
    }
    resp = server.handle_jsonrpc_sync(req)
    assert "error" in resp, f"Server accepted request without 'jsonrpc': '2.0': {resp}"
    assert resp["error"]["code"] == -32600, f"Expected -32600, got: {resp.get('error')}"


def test_invalid_jsonrpc_version_must_return_32600(server: AlphaMCPServer):
    """Wire Attack: Requests specifying invalid jsonrpc versions (e.g. '1.0', '3.0') must return -32600."""
    invalid_versions = ["1.0", "3.0", 2.0, "", None]
    for ver in invalid_versions:
        req = {
            "jsonrpc": ver,
            "id": 102,
            "method": "ping",
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Server accepted invalid jsonrpc version '{ver}': {resp}"
        assert resp["error"]["code"] == -32600, f"Expected -32600 for version '{ver}', got: {resp.get('error')}"


def test_missing_method_returns_32600(server: AlphaMCPServer):
    """Wire Attack: Requests with missing or empty 'method' must return -32600 (Invalid Request)."""
    payloads = [
        {"jsonrpc": "2.0", "id": 103},
        {"jsonrpc": "2.0", "id": 104, "method": ""},
        {"jsonrpc": "2.0", "id": 105, "method": None},
    ]
    for req in payloads:
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp
        assert resp["error"]["code"] == -32600


def test_non_string_method_returns_32600(server: AlphaMCPServer):
    """Wire Attack: Requests with non-string 'method' must return -32600 (Invalid Request)."""
    payloads = [
        {"jsonrpc": "2.0", "id": 106, "method": 99999},
        {"jsonrpc": "2.0", "id": 107, "method": ["ping"]},
        {"jsonrpc": "2.0", "id": 108, "method": {"name": "ping"}},
    ]
    for req in payloads:
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp
        assert resp["error"]["code"] == -32600


def test_unknown_method_returns_32601(server: AlphaMCPServer):
    """Wire Attack: Requesting a non-existent method must return -32601 (Method not found)."""
    unknown_methods = [
        "admin/shutdown",
        "system/reboot",
        "tools/execute_raw_code",
        "non_existent_rpc_call",
    ]
    for method in unknown_methods:
        req = {"jsonrpc": "2.0", "id": 109, "method": method}
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp
        assert resp["error"]["code"] == -32601


def test_unknown_tool_returns_32601(server: AlphaMCPServer):
    """Wire Attack: tools/call specifying an unregistered tool must return -32601."""
    req = {
        "jsonrpc": "2.0",
        "id": 110,
        "method": "tools/call",
        "params": {"name": "unregistered_destructive_tool", "arguments": {}},
    }
    resp = server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_missing_tool_call_params_returns_32602(server: AlphaMCPServer):
    """Wire Attack: tools/call missing 'params' or 'name' must return -32602 (Invalid params)."""
    payloads = [
        {"jsonrpc": "2.0", "id": 111, "method": "tools/call"},
        {"jsonrpc": "2.0", "id": 112, "method": "tools/call", "params": {}},
        {"jsonrpc": "2.0", "id": 113, "method": "tools/call", "params": {"name": ""}},
    ]
    for req in payloads:
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp
        assert resp["error"]["code"] == -32602


def test_missing_required_tool_arguments_returns_32602(server: AlphaMCPServer):
    """Wire Attack: tools/call missing required arguments defined in tool inputSchema must return -32602."""
    missing_arg_cases = [
        # vault_read requires 'path' and 'agent_id'
        ("vault_read", {}),
        ("vault_read", {"path": "company/identity"}),  # missing agent_id
        # vault_write requires 'path', 'data', and 'agent_id'
        ("vault_write", {"path": "projects/1/data"}),
        ("vault_write", {"path": "projects/1/data", "agent_id": "CEO"}),  # missing data
        # agent_delegate requires 'project_id', 'from_agent', 'to_agents', 'task', 'expected_deliverable'
        ("agent_delegate", {"from_agent": "CEO"}),
        # model_route requires 'task_type', 'complexity', 'agent_id'
        ("model_route", {"task_type": "coding", "agent_id": "CEO"}),  # missing complexity
        # user_escalate requires 'agent_id', 'decision_required'
        ("user_escalate", {"agent_id": "CEO"}),  # missing decision_required
    ]
    for i, (tool_name, arguments) in enumerate(missing_arg_cases):
        req = {
            "jsonrpc": "2.0",
            "id": 200 + i,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Expected -32602 for tool '{tool_name}' with args {arguments}, got: {resp}"
        assert resp["error"]["code"] == -32602, f"Expected code -32602, got: {resp['error']}"


def test_invalid_tool_argument_types_returns_32602(server: AlphaMCPServer):
    """Wire Attack: Passing invalid parameter types (e.g. string where object is required)

    Pydantic schema validation must enforce types and reject violations with -32602,
    rather than silently bypassing validation and returning success.
    """
    invalid_type_cases = [
        # vault_write expects 'data' to be an object (dict), not a string
        (
            "vault_write",
            {"path": "projects/1/audit/log", "agent_id": "CAO-1", "data": "raw_string_not_dict"},
        ),
        # agent_hire expects 'skills' to be an array of strings, not a string
        (
            "agent_hire",
            {
                "agent_id": "CHRO",
                "new_agent_id": "Dev-1",
                "role": "Developer",
                "full_title": "Fullstack Engineer",
                "jd_content": "Build apps",
                "skills": "not_a_list_string",
                "assigned_model": "gpt-4o",
            },
        ),
    ]
    for i, (tool_name, arguments) in enumerate(invalid_type_cases):
        req = {
            "jsonrpc": "2.0",
            "id": 300 + i,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, (
            f"Vulnerability confirmed: Tool '{tool_name}' silently accepted invalid argument types without returning an error: {resp}"
        )
        assert resp["error"]["code"] == -32602, (
            f"Expected error code -32602 (Invalid params), got: {resp['error']}"
        )


def test_out_of_bounds_parameters_returns_32602(server: AlphaMCPServer):
    """Wire Attack: Out of bounds parameter values must return -32602 (Invalid params)."""
    boundary_cases = [
        # complexity must be between 1 and 5
        ("model_route", {"task_type": "coding", "complexity": 0, "agent_id": "CEO"}),
        ("model_route", {"task_type": "coding", "complexity": 6, "agent_id": "CEO"}),
        ("model_route", {"task_type": "coding", "complexity": 999, "agent_id": "CEO"}),
        ("model_route", {"task_type": "coding", "complexity": -1, "agent_id": "CEO"}),
    ]
    for i, (tool_name, arguments) in enumerate(boundary_cases):
        req = {
            "jsonrpc": "2.0",
            "id": 400 + i,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Expected error for {arguments}"
        assert resp["error"]["code"] == -32602, f"Expected -32602, got: {resp['error']}"


def test_invalid_project_status_returns_32602(server: AlphaMCPServer):
    """Wire Attack: project_update_status with invalid enum status must return -32602."""
    req = {
        "jsonrpc": "2.0",
        "id": 410,
        "method": "tools/call",
        "params": {
            "name": "project_update_status",
            "arguments": {
                "project_id": "proj_001",
                "status": "unauthorized_exploding_state",
                "agent_id": "CEO",
            },
        },
    }
    resp = server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32602


# ============================================================================
# 2. RBAC Confinement & Authority Stress
# ============================================================================

def test_rbac_cao_write_outside_audit_denied_32003(server: AlphaMCPServer):
    """Security Attack: CAO agents attempting to write outside projects/{id}/audit/*

    Must be rejected with -32003 (RBAC Permission Denied) across multiple unauthorized paths.
    """
    forbidden_paths = [
        "company/identity",
        "vault/system_config",
        "agents/profiles/CEO",
        "projects/proj_001/manifest.json",
        "projects/proj_001/src/main.py",
        "user/profile",
    ]
    for i, path in enumerate(forbidden_paths):
        req = {
            "jsonrpc": "2.0",
            "id": 500 + i,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": path,
                    "data": {"tampered": True},
                    "agent_id": "CAO-Claude",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"CAO unauthorized write to '{path}' was not blocked!"
        assert resp["error"]["code"] == -32003, f"Expected -32003 for '{path}', got: {resp['error']}"
        assert "Access Denied" in resp["error"]["message"]


def test_rbac_cao_write_inside_audit_allowed(server: AlphaMCPServer):
    """RBAC Verification: CAO write within projects/{id}/audit/* is permitted."""
    req = {
        "jsonrpc": "2.0",
        "id": 520,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": "projects/proj_001/audit/gate_review.json",
                "data": {"passed": True, "auditor": "CAO-Claude"},
                "agent_id": "CAO-Claude",
            },
        },
    }
    resp = server.handle_jsonrpc_sync(req)
    assert resp.get("id") == 520
    assert "result" in resp
    assert resp["result"]["isError"] is False


def test_rbac_non_ceo_delegation_denied_32003(server: AlphaMCPServer):
    """Authority Attack: Non-CEO agents attempting agent_delegate must be denied with -32003."""
    unauthorized_agents = ["CTO", "CPO", "CFO", "CHRO", "CAO", "SWE-1"]
    for i, agent in enumerate(unauthorized_agents):
        req = {
            "jsonrpc": "2.0",
            "id": 530 + i,
            "method": "tools/call",
            "params": {
                "name": "agent_delegate",
                "arguments": {
                    "project_id": "proj_001",
                    "from_agent": agent,
                    "to_agents": ["SWE-1"],
                    "task": "Build feature X",
                    "expected_deliverable": "feature_spec.json",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Non-CEO agent '{agent}' was permitted to delegate!"
        assert resp["error"]["code"] == -32003, f"Expected -32003 for '{agent}', got: {resp['error']}"
        assert "Authority Denied" in resp["error"]["message"]


def test_rbac_ceo_delegation_allowed(server: AlphaMCPServer):
    """Authority Verification: CEO agent delegation succeeds."""
    req = {
        "jsonrpc": "2.0",
        "id": 540,
        "method": "tools/call",
        "params": {
            "name": "agent_delegate",
            "arguments": {
                "project_id": "proj_001",
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "task": "Architect system infrastructure",
                "expected_deliverable": "architecture_blueprint.json",
            },
        },
    }
    resp = server.handle_jsonrpc_sync(req)
    assert resp.get("id") == 540
    assert "result" in resp
    assert resp["result"]["isError"] is False


# ============================================================================
# 3. Canonical & Malicious Resource URI Stress
# ============================================================================

def test_canonical_resource_uris_resolution(server: AlphaMCPServer):
    """Verify all 4 canonical resources resolve and return valid contents."""
    canonical_uris = [
        "vault://company/identity",
        "vault://user/profile",
        "agents://registry",
        "projects://list",
    ]
    for i, uri in enumerate(canonical_uris):
        req = {
            "jsonrpc": "2.0",
            "id": 600 + i,
            "method": "resources/read",
            "params": {"uri": uri},
        }
        resp = server.handle_jsonrpc_sync(req)
        assert resp.get("id") == 600 + i
        assert "result" in resp, f"Failed to read canonical resource: {uri}"
        contents = resp["result"].get("contents", [])
        assert len(contents) == 1
        assert contents[0]["uri"] == uri
        assert contents[0]["mimeType"] == "application/json"
        assert len(contents[0]["text"]) > 0


def test_dynamic_vault_resource_resolution(server: AlphaMCPServer):
    """Verify dynamic vault resource URI 'vault://{path}' resolves correctly."""
    # Write a test document first
    server.call_tool_dict_sync(
        "vault_write",
        {
            "path": "projects/p_dyn/manifest.json",
            "data": {"project": "Dynamic Test", "version": "1.0"},
            "agent_id": "CEO",
        },
    )
    req = {
        "jsonrpc": "2.0",
        "id": 610,
        "method": "resources/read",
        "params": {"uri": "vault://projects/p_dyn/manifest.json"},
    }
    resp = server.handle_jsonrpc_sync(req)
    assert "result" in resp
    contents = resp["result"]["contents"]
    parsed = json.loads(contents[0]["text"])
    assert parsed.get("found") is True
    assert parsed["data"]["project"] == "Dynamic Test"


def test_malicious_path_traversal_resource_rejected(server: AlphaMCPServer):
    """Security Attack: Malicious path traversal URIs must be blocked and not disclose external files."""
    traversal_uris = [
        "vault://../../etc/passwd",
        "vault://..\\..\\secret.key",
        "vault://projects/../../../root",
    ]
    for i, uri in enumerate(traversal_uris):
        req = {
            "jsonrpc": "2.0",
            "id": 620 + i,
            "method": "resources/read",
            "params": {"uri": uri},
        }
        resp = server.handle_jsonrpc_sync(req)
        # Must either return error envelope or contents indicating not found/failure without data
        if "error" in resp:
            assert "Path traversal" in resp["error"]["message"] or "Access Denied" in resp["error"]["message"] or -32000 == resp["error"]["code"]
        else:
            contents = resp["result"]["contents"]
            parsed = json.loads(contents[0]["text"])
            assert parsed.get("found") is False or parsed.get("success") is False
            assert parsed.get("data") is None


def test_malicious_uri_schemes_rejected(server: AlphaMCPServer):
    """Security Attack: Non-canonical URI schemes must be rejected."""
    unsupported_schemes = [
        "ftp://malicious.example.com/exploit.sh",
        "file:///etc/shadow",
        "http://insecure.internal.service/api",
        "ldap://ad.company.local",
    ]
    for i, uri in enumerate(unsupported_schemes):
        req = {
            "jsonrpc": "2.0",
            "id": 630 + i,
            "method": "resources/read",
            "params": {"uri": uri},
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Unsupported URI scheme '{uri}' was not rejected!"
        assert "Unknown resource URI" in resp["error"]["message"]


def test_missing_resource_uri_param_returns_32602(server: AlphaMCPServer):
    """Wire Attack: resources/read without 'uri' param returns -32602."""
    req = {
        "jsonrpc": "2.0",
        "id": 640,
        "method": "resources/read",
        "params": {},
    }
    resp = server.handle_jsonrpc_sync(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32602


# ============================================================================
# 4. Multi-Threaded Concurrency (25+ Threads)
# ============================================================================

def test_concurrent_multi_threaded_invocations_no_deadlock(server: AlphaMCPServer):
    """Stress Test: 25+ concurrent threads making simultaneous tool calls and resource reads.

    Must complete cleanly without deadlocks, race conditions, or unhandled exceptions.
    """
    num_threads = 28
    results: Dict[int, Any] = {}
    thread_exceptions: List[Exception] = []

    def worker_task(thread_id: int):
        try:
            # Alternate between writes, reads, model routing, and resource accesses
            idx = thread_id % 4
            if idx == 0:
                resp = server.handle_jsonrpc_sync({
                    "jsonrpc": "2.0",
                    "id": thread_id,
                    "method": "tools/call",
                    "params": {
                        "name": "vault_write",
                        "arguments": {
                            "path": f"projects/proj_concur/data_{thread_id}.json",
                            "data": {"thread": thread_id, "timestamp": time.time()},
                            "agent_id": "CEO",
                        },
                    },
                })
            elif idx == 1:
                resp = server.handle_jsonrpc_sync({
                    "jsonrpc": "2.0",
                    "id": thread_id,
                    "method": "tools/call",
                    "params": {
                        "name": "model_route",
                        "arguments": {
                            "task_type": "coding",
                            "complexity": 3,
                            "agent_id": f"Agent_{thread_id}",
                        },
                    },
                })
            elif idx == 2:
                resp = server.handle_jsonrpc_sync({
                    "jsonrpc": "2.0",
                    "id": thread_id,
                    "method": "resources/read",
                    "params": {"uri": "vault://company/identity"},
                })
            else:
                resp = server.handle_jsonrpc_sync({
                    "jsonrpc": "2.0",
                    "id": thread_id,
                    "method": "tools/call",
                    "params": {
                        "name": "agent_status",
                        "arguments": {"agent_id": "CEO"},
                    },
                })
            results[thread_id] = resp
        except Exception as e:
            thread_exceptions.append(e)

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(num_threads)]

    start_time = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    duration = time.time() - start_time

    assert len(thread_exceptions) == 0, f"Exceptions occurred in worker threads: {thread_exceptions}"
    assert len(results) == num_threads, f"Expected {num_threads} completed calls, got {len(results)}"
    assert duration < 8.0, f"Concurrent operations took too long ({duration:.2f}s) — possible contention/deadlock"

    # Verify ID correlation across all responses
    for thread_id, resp in results.items():
        assert resp.get("id") == thread_id, f"ID mismatch in thread {thread_id}: {resp}"
        assert resp.get("jsonrpc") == "2.0"
        assert "error" not in resp, f"Unexpected error in thread {thread_id}: {resp['error']}"


# ============================================================================
# 5. Closed-Loop Multi-Tool Autonomous Workflow (17 Chained Operations)
# ============================================================================

def test_closed_loop_autonomous_executive_workflow(server: AlphaMCPServer):
    """End-to-End Stress Test: 17 sequential chained operations simulating full autonomous executive operation.

    Chains operations across all 6 namespaces:
    1. user_profile_read (Verify Founder Aman Jain)
    2. vault_read (Verify Company identity)
    3. agent_status (Inspect CEO status)
    4. agent_hire (CHRO onboards MLOps-Lead)
    5. model_route (Route architecture model for CEO)
    6. project_create (Scaffold proj_autonomous_infra)
    7. thread_post (CEO posts mission kickoff)
    8. agent_delegate (CEO delegates architecture to CTO)
    9. thread_post (CTO confirms spec completion)
    10. vault_write (CTO writes spec.json)
    11. model_route (CAO Tier 5 audit override to Claude 3.5 Sonnet)
    12. vault_write (CAO writes audit review)
    13. project_update_status (CEO transitions project to in_progress)
    14. vault_save_memory (CEO records episodic decision)
    15. thread_read (Verify thread history)
    16. resources/read (Verify project listed in projects://list)
    17. user_escalate (Notify Founder Aman Jain of Phase 1 sign-off)
    """
    # Step 1: user_profile_read
    r1 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "user_profile_read", "arguments": {"agent_id": "CEO"}},
    })
    assert r1["result"]["isError"] is False
    profile = json.loads(r1["result"]["content"][0]["text"])
    assert profile["name"] == "Aman Jain"

    # Step 2: vault_read company/identity
    r2 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "vault_read", "arguments": {"path": "company/identity", "agent_id": "CEO"}},
    })
    assert r2["result"]["isError"] is False

    # Step 3: agent_status
    r3 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "agent_status", "arguments": {"agent_id": "CEO"}},
    })
    assert r3["result"]["isError"] is False

    # Step 4: agent_hire
    r4 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "agent_hire",
            "arguments": {
                "agent_id": "CHRO",
                "new_agent_id": "MLOps-Lead",
                "role": "MLOps Lead",
                "full_title": "Lead MLOps Engineer",
                "jd_content": "Orchestrates automated evaluation harnesses.",
                "skills": ["docker", "kubernetes", "python", "mcp"],
                "assigned_model": "claude-3-5-sonnet",
            },
        },
    })
    assert r4["result"]["isError"] is False

    # Step 5: model_route for architecture
    r5 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "model_route",
            "arguments": {"task_type": "strategic_planning", "complexity": 4, "agent_id": "CEO"},
        },
    })
    assert r5["result"]["isError"] is False

    # Step 6: project_create
    r6 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "project_create",
            "arguments": {
                "name": "Autonomous Infrastructure",
                "user_goal": "Build robust autonomous execution engine",
                "priority": "critical",
                "assigned_agents": ["CEO", "CTO"],
            },
        },
    })
    assert r6["result"]["isError"] is False
    proj_info = json.loads(r6["result"]["content"][0]["text"])
    proj_id = proj_info["project_id"]
    assert proj_id is not None

    # Step 7: thread_post (CEO kickoff)
    r7 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": proj_id,
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "type": "DELEGATION",
                "subject": "Project Kickoff",
                "content": "Please start architectural drafting.",
            },
        },
    })
    assert r7["result"]["isError"] is False

    # Step 8: agent_delegate (CEO delegates to CTO)
    r8 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "agent_delegate",
            "arguments": {
                "project_id": proj_id,
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "task": "Design modular microservices",
                "expected_deliverable": "architecture_spec.json",
                "priority": "critical",
            },
        },
    })
    assert r8["result"]["isError"] is False

    # Step 9: thread_post (CTO response)
    r9 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": proj_id,
                "from_agent": "CTO",
                "to_agents": ["CEO"],
                "type": "DELIVERABLE",
                "subject": "Design Complete",
                "content": "Specification drafted and written to vault.",
            },
        },
    })
    assert r9["result"]["isError"] is False

    # Step 10: vault_write (CTO writes spec)
    r10 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": f"projects/{proj_id}/spec.json",
                "data": {"architecture": "event-driven", "consensus": "raft"},
                "agent_id": "CTO",
            },
        },
    })
    assert r10["result"]["isError"] is False

    # Step 11: model_route (CAO Audit gate - Tier 5 override)
    r11 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "model_route",
            "arguments": {"task_type": "audit", "complexity": 5, "agent_id": "CAO-Claude"},
        },
    })
    assert r11["result"]["isError"] is False
    route_info = json.loads(r11["result"]["content"][0]["text"])
    assert route_info["model"] == "claude-3-5-sonnet"
    assert route_info["tier"] == 5

    # Step 12: vault_write (CAO audit report within audit/)
    r12 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": f"projects/{proj_id}/audit/gate_review.json",
                "data": {"compliance": "100%", "verdict": "APPROVED"},
                "agent_id": "CAO-Claude",
            },
        },
    })
    assert r12["result"]["isError"] is False

    # Step 13: project_update_status
    r13 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "project_update_status",
            "arguments": {
                "project_id": proj_id,
                "status": "in_progress",
                "agent_id": "CEO",
                "note": "Architecture approved by CAO.",
            },
        },
    })
    assert r13["result"]["isError"] is False

    # Step 14: vault_save_memory
    r14 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 14,
        "method": "tools/call",
        "params": {
            "name": "vault_save_memory",
            "arguments": {
                "agent_id": "CEO",
                "memory": {
                    "type": "decision",
                    "content": "Transitioned autonomous infra project to in_progress following audit approval.",
                    "importance": 5,
                    "project_id": proj_id,
                },
            },
        },
    })
    assert r14["result"]["isError"] is False

    # Step 15: thread_read
    r15 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 15,
        "method": "tools/call",
        "params": {"name": "thread_read", "arguments": {"project_id": proj_id, "agent_id": "CEO"}},
    })
    assert r15["result"]["isError"] is False
    thread_data = json.loads(r15["result"]["content"][0]["text"])
    assert thread_data["count"] >= 2

    # Step 16: resources/read projects://list
    r16 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 16,
        "method": "resources/read",
        "params": {"uri": "projects://list"},
    })
    assert "result" in r16
    resource_data = json.loads(r16["result"]["contents"][0]["text"])
    assert resource_data.get("success") is True

    # Step 17: user_escalate
    r17 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {
            "name": "user_escalate",
            "arguments": {
                "project_id": proj_id,
                "from_agent": "CEO",
                "question": "Confirm Phase 1 deployment to production cluster.",
                "context": f"Project '{proj_id}' successfully initiated and verified.",
                "urgency": "high",
            },
        },
    })
    assert r17["result"]["isError"] is False
    esc_data = json.loads(r17["result"]["content"][0]["text"])
    assert esc_data["escalated"] is True
