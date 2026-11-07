"""Alpha/tests/mcp/test_challenger_m7_wire_stress.py - Empirical Challenger Stress Test Suite.

Adversarial Wire-Level & Protocol Stress Harness by challenger_m7_r2_2:
1. Non-JSON string payloads & syntax corruption
2. Non-object JSON string payloads (int, float, bool, null, list, empty array)
3. Direct non-dict Python objects passed to handle_jsonrpc / handle_jsonrpc_sync
4. Strict JSON-RPC version enforcement ('2.0' exactness)
5. Method format & routing edge cases
6. ID preservation across all valid & error cases
7. Tools/call param and arguments robustness
8. Dynamic isError behavior under tool successes, data errors, and exceptions
9. RBAC permission denied mapping to -32003
10. Massive payloads, Unicode, and boundary stress
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.mcp.server import (
    AlphaMCPServer,
    create_mcp_server,
)
from tests.conftest import ContractModelRouter, ContractVaultManager


@pytest.fixture
def mock_vault(tmp_path: Path) -> ContractVaultManager:
    vault_dir = tmp_path / "wire_stress_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return ContractVaultManager(str(vault_dir))


@pytest.fixture
def mock_router() -> ContractModelRouter:
    return ContractModelRouter()


@pytest.fixture
def server(mock_vault: ContractVaultManager, mock_router: ContractModelRouter) -> AlphaMCPServer:
    return create_mcp_server(
        vault_manager=mock_vault,
        model_router=mock_router,
    )


# ============================================================================
# 1. Non-JSON String Payloads & Syntax Corruption (-32700)
# ============================================================================

@pytest.mark.parametrize("payload", [
    "{invalid_json:",
    '{"jsonrpc": "2.0", "method": "ping", broken}',
    '{"jsonrpc": "2.0", "method": "ping",}',  # trailing comma
    '{"jsonrpc": "2.0", "method": "ping"',   # unclosed brace
    "Just plain text",
    "",
    "    ",
    "\t\n",
    "{{}}",
    "<xml>not json</xml>",
    "// single line comment\n{}",
])
def test_malformed_raw_strings_must_return_32700(server: AlphaMCPServer, payload: str):
    res = server.handle_jsonrpc_sync(payload)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") is None
    assert "error" in res
    assert res["error"]["code"] == -32700
    assert "Parse error" in res["error"]["message"]


# ============================================================================
# 2. Non-Object JSON String Payloads (-32600)
# ============================================================================

@pytest.mark.parametrize("payload", [
    "123",
    "-456",
    "3.14159",
    '"just_a_string"',
    '""',
    "true",
    "false",
    "null",
    "[1, 2, 3]",
    "[]",
    '["a", "b", "c"]',
    '[[1, 2], [3, 4]]',
])
def test_non_object_json_strings_must_return_32600(server: AlphaMCPServer, payload: str):
    res = server.handle_jsonrpc_sync(payload)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") is None
    assert "error" in res
    assert res["error"]["code"] == -32600
    assert "Invalid Request" in res["error"]["message"]


# ============================================================================
# 3. Direct Non-Dict Python Objects (-32600)
# ============================================================================

@pytest.mark.parametrize("payload", [
    123,
    -999,
    3.14,
    True,
    False,
    None,
    [1, 2, 3],
    [],
    ("tuple", "items"),
    {"not": "a", "jsonrpc": "2.0"},  # this has jsonrpc 2.0 but missing method -> handled below
])
def test_non_dict_python_objects_must_return_32600(server: AlphaMCPServer, payload: Any):
    if isinstance(payload, dict):
        return  # tested separately
    res = server.handle_jsonrpc_sync(payload)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") is None
    assert "error" in res
    assert res["error"]["code"] == -32600
    assert "Invalid Request" in res["error"]["message"]


# ============================================================================
# 4. Strict JSON-RPC Version Enforcement ('2.0' exact string)
# ============================================================================

@pytest.mark.parametrize("ver", [
    "1.0",
    "2.1",
    "3.0",
    "2.00",
    " 2.0",
    "2.0 ",
    2.0,
    2,
    "",
    None,
    True,
    False,
    [],
    {},
])
def test_invalid_jsonrpc_version_must_return_32600(server: AlphaMCPServer, ver: Any):
    req = {"jsonrpc": ver, "id": 555, "method": "ping"}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") == 555
    assert "error" in res
    assert res["error"]["code"] == -32600
    assert "jsonrpc" in res["error"]["message"]


def test_missing_jsonrpc_key_must_return_32600(server: AlphaMCPServer):
    req = {"id": 777, "method": "ping"}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") == 777
    assert "error" in res
    assert res["error"]["code"] == -32600


# ============================================================================
# 5. Method Format & Validation (-32600 and -32601)
# ============================================================================

@pytest.mark.parametrize("bad_method", [
    "",
    None,
    123,
    3.14,
    True,
    False,
    [],
    ["ping"],
    {},
    {"name": "ping"},
])
def test_invalid_method_format_must_return_32600(server: AlphaMCPServer, bad_method: Any):
    req = {"jsonrpc": "2.0", "id": 888, "method": bad_method}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") == 888
    assert "error" in res
    assert res["error"]["code"] == -32600


@pytest.mark.parametrize("unknown_method", [
    "   ",
    "unknown/method",
    "admin/shutdown",
    "eval",
    "exec",
    "__init__",
    "tools/destroy_everything",
    "resources/delete_all",
])
def test_unknown_methods_must_return_32601(server: AlphaMCPServer, unknown_method: str):
    req = {"jsonrpc": "2.0", "id": 999, "method": unknown_method}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("jsonrpc") == "2.0"
    assert res.get("id") == 999
    assert "error" in res
    assert res["error"]["code"] == -32601


# ============================================================================
# 6. ID Preservation Across Success and Error Envelopes
# ============================================================================

@pytest.mark.parametrize("sample_id", [
    "string-id-alpha",
    "uuid-1234-5678-90ab",
    0,
    1,
    -1,
    99999999,
    3.14159,
    None,
])
def test_id_preservation_on_success(server: AlphaMCPServer, sample_id: Any):
    req = {"jsonrpc": "2.0", "id": sample_id, "method": "ping"}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("id") == sample_id
    assert "result" in res


@pytest.mark.parametrize("sample_id", [
    "string-id-err",
    42,
    None,
])
def test_id_preservation_on_error(server: AlphaMCPServer, sample_id: Any):
    # Method not found (-32601)
    req = {"jsonrpc": "2.0", "id": sample_id, "method": "no_such_method"}
    res = server.handle_jsonrpc_sync(req)
    assert res.get("id") == sample_id
    assert "error" in res
    assert res["error"]["code"] == -32601


# ============================================================================
# 7. tools/call Parameter & Arguments Robustness (-32601, -32602)
# ============================================================================

@pytest.mark.parametrize("bad_name", [
    "",
    None,
    123,
    True,
    [],
    {},
])
def test_tools_call_invalid_name_type_returns_32602(server: AlphaMCPServer, bad_name: Any):
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": bad_name, "arguments": {}},
    }
    res = server.handle_jsonrpc_sync(req)
    assert "error" in res
    assert res["error"]["code"] == -32602


@pytest.mark.parametrize("bad_arguments", [
    "not_a_dict",
    123,
    3.14,
    True,
    False,
    [1, 2, 3],
    [],
])
def test_tools_call_arguments_not_object_returns_32602(server: AlphaMCPServer, bad_arguments: Any):
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "vault_read", "arguments": bad_arguments},
    }
    res = server.handle_jsonrpc_sync(req)
    assert "error" in res
    assert res["error"]["code"] == -32602
    assert "arguments" in res["error"]["message"].lower()


def test_tools_call_unknown_tool_returns_32601(server: AlphaMCPServer):
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "non_existent_tool_xyz", "arguments": {}},
    }
    res = server.handle_jsonrpc_sync(req)
    assert "error" in res
    assert res["error"]["code"] == -32601
    assert "Unknown MCP tool" in res["error"]["message"]


# ============================================================================
# 8. Dynamic isError Behavior Under Protocol v1.0
# ============================================================================

def test_dynamic_is_error_flag_on_tool_success_and_failure(server: AlphaMCPServer):
    # Success: vault_read on existing document
    res_ok = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "vault_read", "arguments": {"path": "company/identity", "agent_id": "CEO"}},
    })
    assert "result" in res_ok
    assert res_ok["result"]["isError"] is False
    assert len(res_ok["result"]["content"]) > 0

    # Business failure: vault_read on non-existent document
    # Under MCP v1.0, business tool errors are encapsulated inside result with isError: True
    res_err = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "vault_read", "arguments": {"path": "completely/imaginary/file", "agent_id": "CEO"}},
    })
    assert "result" in res_err
    assert res_err["result"]["isError"] is True


def test_dynamic_is_error_flag_on_thread_post_validation(server: AlphaMCPServer):
    # thread_post with valid arguments
    res_ok = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": "p1",
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "type": "INPUT",
                "content": "Proceed with architecture review",
            },
        },
    })
    assert "result" in res_ok
    assert res_ok["result"]["isError"] is False

    # thread_post with invalid message type
    res_bad = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": "p1",
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "type": "MALFORMED_UNSUPPORTED_TYPE",
                "content": "Hello",
            },
        },
    })
    # Input schema validation should return -32602
    assert "error" in res_bad
    assert res_bad["error"]["code"] == -32602


# ============================================================================
# 9. RBAC Permission Denied Protocol Error (-32003)
# ============================================================================

def test_rbac_permission_denied_code_32003(server: AlphaMCPServer):
    # CAO write to root
    res1 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": "company/identity",
                "agent_id": "CAO-Claude",
                "data": {"compromised": True},
            },
        },
    })
    assert "error" in res1
    assert res1["error"]["code"] == -32003
    assert "RBAC Permission Denied" in res1["error"]["message"]

    # CAO write with audit substring bypass
    res2 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "vault_write",
            "arguments": {
                "path": "company/audit_plan.json",
                "agent_id": "CAO-ChatGPT",
                "data": {"compromised": True},
            },
        },
    })
    assert "error" in res2
    assert res2["error"]["code"] == -32003
    assert "RBAC Permission Denied" in res2["error"]["message"]

    # Non-CEO delegation
    res3 = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 22,
        "method": "tools/call",
        "params": {
            "name": "agent_delegate",
            "arguments": {
                "project_id": "p1",
                "from_agent": "CPO",
                "to_agents": ["CTO"],
                "task": "Build feature",
                "expected_deliverable": "Code",
            },
        },
    })
    assert "error" in res3
    assert res3["error"]["code"] == -32003
    assert "RBAC Permission Denied" in res3["error"]["message"]


# ============================================================================
# 10. Massive Payload and Unicode Stress
# ============================================================================

def test_large_payload_handling(server: AlphaMCPServer):
    large_text = "A" * 100_000
    res = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": "p1",
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "type": "INPUT",
                "content": large_text,
            },
        },
    })
    assert "result" in res
    assert res["result"]["isError"] is False


def test_unicode_and_special_character_payload(server: AlphaMCPServer):
    unicode_content = "🚀 Alpha AI 🌟 中文 日本語 한국어 \u0000 \u200b \t \n \r special"
    res = server.handle_jsonrpc_sync({
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {
            "name": "thread_post",
            "arguments": {
                "project_id": "p1",
                "from_agent": "CEO",
                "to_agents": ["CTO"],
                "type": "INPUT",
                "content": unicode_content,
            },
        },
    })
    assert "result" in res
    assert res["result"]["isError"] is False
