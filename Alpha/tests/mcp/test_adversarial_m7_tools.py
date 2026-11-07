"""Alpha/tests/mcp/test_adversarial_m7_tools.py - MCP Tools Adversarial Test Suite.

Milestone 7 Adversarial Challenge & Stress-Testing Harness covering:
1. Path Traversal & File System Infiltration Resistance (vault_read, vault_write)
2. Deep RBAC & CAO Confinement Stress Tests (12+ unauthorized paths across CAO variants)
3. Out-of-Bounds Parameter Validation (top_k, importance, complexity, limit, enums)
4. Empty & Malformed Input Fuzzing across all 15 tools
5. Entity Robustness & Error Recovery (non-existent agents, non-existent projects)
6. CAO Audit Gate Model Override Verification
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.mcp.server import (
    ALPHA_TOOLS,
    AlphaMCPServer,
    create_mcp_server,
)
from backend.mcp.tools import dispatch_tool
from backend.vault.vault_manager import AccessDeniedError, VaultManager
from tests.conftest import ContractModelRouter, ContractVaultManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_vault(tmp_path: Path) -> ContractVaultManager:
    """Isolated ContractVaultManager fixture."""
    vault_dir = tmp_path / "mock_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return ContractVaultManager(str(vault_dir))


@pytest.fixture
def mock_router() -> ContractModelRouter:
    """ContractModelRouter fixture."""
    return ContractModelRouter()


@pytest.fixture
def mcp_server(mock_vault: ContractVaultManager, mock_router: ContractModelRouter) -> AlphaMCPServer:
    """Default AlphaMCPServer initialized with ContractVaultManager."""
    return create_mcp_server(
        vault_manager=mock_vault,
        model_router=mock_router,
    )


@pytest.fixture
def real_vault_server(tmp_path: Path, mock_router: ContractModelRouter):
    """AlphaMCPServer backed by real production VaultManager for path traversal & RBAC defense."""
    vault_dir = tmp_path / "real_vault_root"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vm = VaultManager(vault_root=vault_dir)
    server = create_mcp_server(vault_manager=vm, model_router=mock_router)
    return server, vm


# ============================================================================
# 1. Path Traversal & File System Infiltration Resistance
# ============================================================================

class TestPathTraversalAttacks:
    """Adversarial attacks attempting directory traversal, null-byte injection, and sandbox escape."""

    @pytest.mark.parametrize("traversal_path", [
        "../../etc/passwd",
        "../../../etc/shadow",
        "../secrets/keys.json",
        "..\\..\\windows\\system32\\cmd.exe",
        "..\\..\\boot.ini",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "C:/Windows/System32/drivers/etc/hosts",
        "\\\\server\\share\\secret.json",
        "./../../company/identity.json",
        "projects/../../company/identity.json",
    ])
    def test_vault_read_rejects_path_traversal(self, real_vault_server, traversal_path: str):
        """Verify real VaultManager detects and rejects traversal attacks on vault_read."""
        server, _ = real_vault_server
        req = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "vault_read",
                "arguments": {
                    "path": traversal_path,
                    "agent_id": "CEO",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Traversal path '{traversal_path}' was not blocked: {resp}"
        assert resp["error"]["code"] == -32003
        assert "Access Denied" in resp["error"]["message"] or "Path traversal detected" in resp["error"]["message"]

    def test_vault_read_posix_slash_path_safe_handling(self, real_vault_server):
        """Verify reading /etc/passwd does not leak host file data even if stripped on Windows."""
        server, _ = real_vault_server
        req = {
            "jsonrpc": "2.0",
            "id": 102,
            "method": "tools/call",
            "params": {
                "name": "vault_read",
                "arguments": {
                    "path": "/etc/passwd",
                    "agent_id": "CEO",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        # Either denied by RBAC or not found inside vault root - never leak external files
        if "error" in resp:
            assert resp["error"]["code"] == -32003
        else:
            text = resp["result"]["content"][0]["text"]
            data = json.loads(text)
            assert data["found"] is False
            assert data["data"] is None

    @pytest.mark.parametrize("null_byte_path", [
        "company/identity\x00.json",
        "projects/proj_001/audit\x00/exploit.json",
        "knowledge\x00/base.md",
    ])
    def test_vault_read_rejects_null_bytes(self, real_vault_server, null_byte_path: str):
        """Verify real VaultManager detects and rejects null bytes in paths on vault_read."""
        server, _ = real_vault_server
        req = {
            "jsonrpc": "2.0",
            "id": 103,
            "method": "tools/call",
            "params": {
                "name": "vault_read",
                "arguments": {
                    "path": null_byte_path,
                    "agent_id": "CEO",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Null byte path '{repr(null_byte_path)}' was not blocked"
        assert resp["error"]["code"] == -32003
        assert "Null byte detected" in resp["error"]["message"] or "Access Denied" in resp["error"]["message"]

    @pytest.mark.parametrize("traversal_path", [
        "../../outside_vault.json",
        "../../../escape.json",
        "..\\..\\outside_vault.json",
        "/etc/cron.d/malicious",
        "C:\\Windows\\Temp\\malicious.json",
    ])
    def test_vault_write_rejects_path_traversal(self, real_vault_server, traversal_path: str):
        """Verify vault_write forbids path traversal outside vault root."""
        server, vm = real_vault_server
        req = {
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": traversal_path,
                    "data": {"payload": "arbitrary_write_exploit"},
                    "agent_id": "CEO",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Traversal write to '{traversal_path}' succeeded unexpectedly"
        assert resp["error"]["code"] == -32003

    def test_vault_read_mock_vault_safe_degradation(self, mcp_server: AlphaMCPServer):
        """Verify that when using mock vault, path traversal safely degrades to not found without crashes."""
        req = {
            "jsonrpc": "2.0",
            "id": 105,
            "method": "tools/call",
            "params": {
                "name": "vault_read",
                "arguments": {
                    "path": "../../etc/passwd",
                    "agent_id": "CEO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["found"] is False
        assert data["data"] is None


# ============================================================================
# 2. Deep RBAC & CAO Confinement Stress Tests
# ============================================================================

class TestDeepRBACAndConfinement:
    """Stress tests verifying CAO isolation outside projects/{id}/audit/* and CEO delegation monopoly."""

    UNAUTHORIZED_CAO_PATHS = [
        "company/identity.json",
        "company/vision.md",
        "knowledge/base.md",
        "knowledge/tech_decisions.md",
        "projects/proj_001/deliverables/code.py",
        "projects/proj_001/deliverables/architecture.md",
        "projects/proj_001/manifest.json",
        "projects/proj_001/goal.md",
        "agents/CEO/profile.json",
        "agents/CTO/JD.md",
        "user/profile.json",
        "backups/vault_backup.tar.gz",
        "vault.db",
        "chroma/index.bin",
    ]

    CAO_AGENT_VARIANTS = [
        "CAO",
        "CAO-Claude",
        "CAO-ChatGPT",
        "CAO-C",
        "CAO-G",
    ]

    @pytest.mark.parametrize("cao_agent", CAO_AGENT_VARIANTS)
    @pytest.mark.parametrize("unauth_path", UNAUTHORIZED_CAO_PATHS)
    def test_cao_write_denied_across_unauthorized_paths(
        self,
        mcp_server: AlphaMCPServer,
        cao_agent: str,
        unauth_path: str,
    ):
        """Verify all CAO agent variants are denied write access across 12+ unauthorized vault paths."""
        req = {
            "jsonrpc": "2.0",
            "id": 201,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": unauth_path,
                    "data": {"audit_tamper": True},
                    "agent_id": cao_agent,
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"CAO agent '{cao_agent}' was permitted to write to unauthorized path '{unauth_path}'"
        assert resp["error"]["code"] == -32003
        assert "RBAC Permission Denied" in resp["error"]["message"]

    @pytest.mark.parametrize("sneaky_path", [
        "company/audit_plan.json",
        "knowledge/audit_checklist.md",
        "agents/audit/log.json",
        "projects/proj_001/audit_bypass/findings.json",
        "projects/proj_001/not_audit/report.json",
    ])
    def test_cao_cannot_bypass_confinement_via_substring_matching_real_vault(
        self,
        real_vault_server,
        sneaky_path: str,
    ):
        """Verify CAO cannot bypass confinement using paths containing 'audit' outside projects/{id}/audit/*."""
        server, _ = real_vault_server
        req = {
            "jsonrpc": "2.0",
            "id": 202,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": sneaky_path,
                    "data": {"bypass": True},
                    "agent_id": "CAO-Claude",
                },
            },
        }
        resp = server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"CAO bypassed confinement on sneaky path '{sneaky_path}'"
        assert resp["error"]["code"] == -32003

    def test_cao_gateway_check_forbids_audit_substring_bypass(self, mcp_server: AlphaMCPServer):
        """Adversarial check: Verify MCP server gateway strictly rejects company/audit_plan.json for CAO.
        
        Exposes DEFECT 1: If server.py line 563 only checks `not ('audit' in path)`,
        paths like company/audit_plan.json slip past the gateway into mock vaults!
        """
        req = {
            "jsonrpc": "2.0",
            "id": 203,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": "company/audit_plan.json",
                    "data": {"tamper": True},
                    "agent_id": "CAO-Claude",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, "Server gateway allowed CAO to write to 'company/audit_plan.json' because 'audit' was in path"
        assert resp["error"]["code"] == -32003

    def test_cao_authorized_write_in_audit_directory_succeeds(self, mcp_server: AlphaMCPServer):
        """Verify CAO write to authorized path projects/{project_id}/audit/* succeeds."""
        req = {
            "jsonrpc": "2.0",
            "id": 204,
            "method": "tools/call",
            "params": {
                "name": "vault_write",
                "arguments": {
                    "path": "projects/proj_001/audit/findings.json",
                    "data": {"audit_passed": True, "score": 9.5},
                    "agent_id": "CAO-Claude",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp, f"CAO authorized audit write failed: {resp}"
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["success"] is True

    @pytest.mark.parametrize("unauthorized_agent", [
        "CTO",
        "CMO",
        "CAO",
        "COO",
        "CFO",
        "CHRO",
        "CIO",
        "CLO",
        "CSO",
        "CDO",
        "CPO",
        "CAO-Claude",
    ])
    def test_non_ceo_agent_delegate_denied(self, mcp_server: AlphaMCPServer, unauthorized_agent: str):
        """Verify non-CEO agents cannot invoke agent_delegate (exclusive CEO authority)."""
        req = {
            "jsonrpc": "2.0",
            "id": 205,
            "method": "tools/call",
            "params": {
                "name": "agent_delegate",
                "arguments": {
                    "project_id": "proj_001",
                    "from_agent": unauthorized_agent,
                    "to_agents": ["CMO"],
                    "task": "Unauthorized delegation attempt",
                    "expected_deliverable": "Brief",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Agent '{unauthorized_agent}' was permitted to delegate tasks"
        assert resp["error"]["code"] == -32003
        assert "Authority Denied" in resp["error"]["message"]


# ============================================================================
# 3. Out-of-Bounds Parameter Validation
# ============================================================================

class TestOutOfBoundsParameterValidation:
    """Stress tests verifying boundary checks: top_k (1-20), importance (1-10), complexity (1-5), etc."""

    @pytest.mark.parametrize("invalid_top_k", [0, -1, -50, 21, 50, 100])
    def test_vault_search_top_k_bounds_in_dispatch_tool(self, invalid_top_k: int):
        """Verify dispatch_tool enforces top_k bounds (1 <= top_k <= 20)."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(
                "vault_search",
                {"query": "architecture", "agent_id": "CEO", "top_k": invalid_top_k},
            )
        assert "top_k" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_top_k", [0, -1, 21, 50])
    def test_vault_search_top_k_bounds_via_jsonrpc(self, mcp_server: AlphaMCPServer, invalid_top_k: int):
        """Adversarial check: Verify vault_search rejects out-of-bounds top_k when called via JSON-RPC.
        
        Exposes DEFECT 2: If server.py line 596 swallows ValueError, server falls back to
        _handle_vault_search which silently clamps top_k instead of returning code -32602!
        """
        req = {
            "jsonrpc": "2.0",
            "id": 310,
            "method": "tools/call",
            "params": {
                "name": "vault_search",
                "arguments": {
                    "query": "architecture",
                    "agent_id": "CEO",
                    "top_k": invalid_top_k,
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"JSON-RPC allowed out-of-bounds top_k={invalid_top_k} without returning -32602 error"
        assert resp["error"]["code"] == -32602

    @pytest.mark.parametrize("invalid_scope", ["invalid_scope", "hacked_scope", "root", "system"])
    def test_vault_search_scope_enum_in_dispatch_tool(self, invalid_scope: str):
        """Verify dispatch_tool rejects invalid search scopes."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(
                "vault_search",
                {"query": "context", "agent_id": "CEO", "scope": invalid_scope},
            )
        assert "scope" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_importance", [0, -1, -10, 11, 20, 100])
    def test_vault_save_memory_importance_bounds(self, mcp_server: AlphaMCPServer, invalid_importance: int):
        """Verify vault_save_memory enforces importance bounds (1 <= importance <= 10)."""
        req = {
            "jsonrpc": "2.0",
            "id": 301,
            "method": "tools/call",
            "params": {
                "name": "vault_save_memory",
                "arguments": {
                    "agent_id": "CTO",
                    "memory": {
                        "type": "observation",
                        "content": "Database latency spike observed",
                        "importance": invalid_importance,
                    },
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Out-of-bounds importance {invalid_importance} accepted"
        assert resp["error"]["code"] == -32602
        assert "importance" in resp["error"]["message"].lower()

    @pytest.mark.parametrize("invalid_complexity", [0, -1, -10, 6, 10, 100])
    def test_model_route_complexity_bounds(self, mcp_server: AlphaMCPServer, invalid_complexity: int):
        """Verify model_route enforces complexity bounds (1 <= complexity <= 5)."""
        req = {
            "jsonrpc": "2.0",
            "id": 302,
            "method": "tools/call",
            "params": {
                "name": "model_route",
                "arguments": {
                    "task_type": "architecture_review",
                    "complexity": invalid_complexity,
                    "agent_id": "CTO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Out-of-bounds complexity {invalid_complexity} accepted"
        assert resp["error"]["code"] == -32602
        assert "complexity" in resp["error"]["message"].lower()

    @pytest.mark.parametrize("invalid_priority", ["extreme", "super_high", "none", "urgent"])
    def test_project_create_invalid_priority_enum(self, invalid_priority: str):
        """Verify project_create rejects invalid priority enums in dispatch_tool."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(
                "project_create",
                {"name": "Alpha Project", "user_goal": "Goal", "priority": invalid_priority},
            )
        assert "priority" in str(exc_info.value).lower()

    @pytest.mark.parametrize("invalid_status", ["deleted", "reverted", "paused", "abandoned"])
    def test_project_update_status_invalid_status_enum(self, mcp_server: AlphaMCPServer, invalid_status: str):
        """Verify project_update_status rejects invalid lifecycle statuses."""
        req = {
            "jsonrpc": "2.0",
            "id": 303,
            "method": "tools/call",
            "params": {
                "name": "project_update_status",
                "arguments": {
                    "project_id": "proj_001",
                    "status": invalid_status,
                    "agent_id": "CEO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Invalid status '{invalid_status}' accepted"
        assert resp["error"]["code"] == -32602
        assert "status" in resp["error"]["message"].lower()

    @pytest.mark.parametrize("invalid_type", ["INVALID_TYPE", "PING", "GOSSIP", "RANDOM"])
    def test_thread_post_invalid_type_enum(self, invalid_type: str):
        """Verify thread_post rejects invalid message types in dispatch_tool."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(
                "thread_post",
                {
                    "project_id": "proj_001",
                    "from_agent": "CEO",
                    "to_agents": ["CTO"],
                    "type": invalid_type,
                    "content": "Ping message",
                },
            )
        assert "type" in str(exc_info.value).lower()

    @pytest.mark.parametrize("invalid_urgency", ["immediate", "catastrophic", "none", "urgent"])
    def test_user_escalate_invalid_urgency_enum(self, mcp_server: AlphaMCPServer, invalid_urgency: str):
        """Verify user_escalate rejects invalid urgency ratings."""
        req = {
            "jsonrpc": "2.0",
            "id": 304,
            "method": "tools/call",
            "params": {
                "name": "user_escalate",
                "arguments": {
                    "project_id": "proj_001",
                    "from_agent": "CLO",
                    "question": "Critical legal inquiry",
                    "context": "Context",
                    "urgency": invalid_urgency,
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "error" in resp, f"Invalid urgency '{invalid_urgency}' accepted"
        assert resp["error"]["code"] == -32602
        assert "urgency" in resp["error"]["message"].lower()


# ============================================================================
# 4. Empty and Malformed Input Fuzzing
# ============================================================================

class TestEmptyAndMalformedInputs:
    """Fuzzing tests verifying schema resistance against empty strings, empty lists, and type mismatches."""

    @pytest.mark.parametrize("tool_def", ALPHA_TOOLS)
    def test_missing_all_required_arguments_returns_32602(self, mcp_server: AlphaMCPServer, tool_def: Dict[str, Any]):
        """Verify every tool rejects calls with completely missing required arguments with code -32602."""
        tool_name = tool_def["name"]
        req = {
            "jsonrpc": "2.0",
            "id": 401,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {},
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        required = tool_def.get("inputSchema", {}).get("required", [])
        if required:
            assert "error" in resp, f"Tool '{tool_name}' accepted empty arguments when required fields exist"
            assert resp["error"]["code"] == -32602

    @pytest.mark.parametrize("tool_name,empty_args", [
        ("vault_read", {"path": "", "agent_id": "CEO"}),
        ("vault_read", {"path": "   ", "agent_id": "CEO"}),
        ("vault_write", {"path": "", "data": {"a": 1}, "agent_id": "CEO"}),
        ("agent_status", {"agent_id": ""}),
        ("agent_hire", {"role": "", "full_title": "Title", "jd_content": "JD", "skills": ["AI"], "assigned_model": "llama3.2"}),
        ("project_create", {"name": "", "user_goal": "Goal", "priority": "medium"}),
        ("project_create", {"name": "Name", "user_goal": "", "priority": "medium"}),
        ("project_update_status", {"project_id": "", "status": "planning", "agent_id": "CEO"}),
        ("thread_post", {"project_id": "", "from_agent": "CEO", "to_agents": ["CTO"], "type": "DELIVERABLE", "content": "text"}),
        ("thread_read", {"project_id": "", "agent_id": "CEO"}),
        ("model_route", {"task_type": "", "complexity": 3, "agent_id": "CEO"}),
        ("user_profile_read", {"agent_id": ""}),
        ("user_escalate", {"project_id": "", "from_agent": "CEO", "question": "Q", "context": "C", "urgency": "high"}),
    ])
    def test_empty_string_fields_rejected_by_dispatch_tool(self, tool_name: str, empty_args: Dict[str, Any]):
        """Verify Pydantic input schemas strictly reject empty strings and whitespace across all tools."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(tool_name, empty_args)
        err_msg = str(exc_info.value).lower()
        assert "empty" in err_msg or "whitespace" in err_msg or "validation error" in err_msg

    def test_vault_search_empty_query_rejected(self):
        """Adversarial check: Verify vault_search rejects empty query string.
        
        Exposes DEFECT 3: VaultSearchInput lacks validate_non_empty on 'query' and 'agent_id'.
        """
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool("vault_search", {"query": "", "agent_id": "CEO"})
        assert "empty" in str(exc_info.value).lower() or "validation error" in str(exc_info.value).lower()

    def test_vault_save_memory_empty_agent_id_rejected(self):
        """Adversarial check: Verify vault_save_memory rejects empty agent_id.
        
        Exposes DEFECT 3: VaultSaveMemoryInput lacks validate_non_empty on 'agent_id',
        causing invalid Chroma collection names 'agent_memory_' to crash vector indexing.
        """
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(
                "vault_save_memory",
                {"agent_id": "", "memory": {"type": "observation", "content": "test", "importance": 3}},
            )
        assert "empty" in str(exc_info.value).lower() or "validation error" in str(exc_info.value).lower()

    @pytest.mark.parametrize("tool_name,empty_list_args", [
        ("agent_delegate", {"project_id": "p1", "from_agent": "CEO", "to_agents": [], "task": "Task", "expected_deliverable": "D"}),
        ("agent_hire", {"role": "VP", "full_title": "VP", "jd_content": "JD", "skills": [], "assigned_model": "m"}),
        ("thread_post", {"project_id": "p1", "from_agent": "CEO", "to_agents": [], "type": "DELIVERABLE", "content": "C"}),
    ])
    def test_empty_lists_rejected_for_min_length_fields(self, tool_name: str, empty_list_args: Dict[str, Any]):
        """Verify tools requiring at least one list item reject empty lists ([])."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(tool_name, empty_list_args)
        assert "at least 1 item" in str(exc_info.value).lower() or "too_short" in str(exc_info.value).lower()

    @pytest.mark.parametrize("tool_name,malformed_args", [
        ("vault_write", {"path": "p", "data": "not_a_dict", "agent_id": "CEO"}),
        ("model_route", {"task_type": "task", "complexity": "very_complex", "agent_id": "CEO"}),
        ("agent_delegate", {"project_id": "p1", "from_agent": "CEO", "to_agents": "not_a_list", "task": "t", "expected_deliverable": "d"}),
        ("vault_save_memory", {"agent_id": "CTO", "memory": "not_a_dict"}),
    ])
    def test_malformed_type_arguments_rejected_by_dispatch_tool(self, tool_name: str, malformed_args: Dict[str, Any]):
        """Verify type mismatches (e.g. string for dict or string for list) trigger validation errors."""
        with pytest.raises(ValueError) as exc_info:
            dispatch_tool(tool_name, malformed_args)
        assert "validation error" in str(exc_info.value).lower()


# ============================================================================
# 5. Entity Robustness & Error Recovery
# ============================================================================

class TestEntityRobustness:
    """Verify system resiliency when querying non-existent agents, projects, threads, and files."""

    def test_agent_status_non_existent_agent_graceful_handling(self, mcp_server: AlphaMCPServer):
        """Verify agent_status for non-existent agent returns graceful response without unhandled crash."""
        req = {
            "jsonrpc": "2.0",
            "id": 501,
            "method": "tools/call",
            "params": {
                "name": "agent_status",
                "arguments": {
                    "agent_id": "NON_EXISTENT_GHOST_BOT_404",
                    "include_memory_summary": True,
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp, f"Querying non-existent agent crashed: {resp}"
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["agent_id"] == "NON_EXISTENT_GHOST_BOT_404"
        assert "status" in data

    def test_project_update_status_non_existent_project_fails_cleanly(self, mcp_server: AlphaMCPServer):
        """Verify project_update_status for non-existent project returns updated=False without crashing."""
        req = {
            "jsonrpc": "2.0",
            "id": 502,
            "method": "tools/call",
            "params": {
                "name": "project_update_status",
                "arguments": {
                    "project_id": "proj_ghost_non_existent_99999",
                    "status": "complete",
                    "agent_id": "CEO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["updated"] is False
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_thread_read_non_existent_project_returns_empty_cleanly(self, mcp_server: AlphaMCPServer):
        """Verify thread_read for non-existent project returns empty message list without crashing."""
        req = {
            "jsonrpc": "2.0",
            "id": 503,
            "method": "tools/call",
            "params": {
                "name": "thread_read",
                "arguments": {
                    "project_id": "proj_unseen_999",
                    "agent_id": "CEO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["count"] == 0
        assert data["messages"] == []

    def test_vault_read_non_existent_path_returns_not_found(self, mcp_server: AlphaMCPServer):
        """Verify vault_read for non-existent document returns found=False without crashing."""
        req = {
            "jsonrpc": "2.0",
            "id": 504,
            "method": "tools/call",
            "params": {
                "name": "vault_read",
                "arguments": {
                    "path": "knowledge/does_not_exist_at_all.md",
                    "agent_id": "CEO",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["found"] is False
        assert data["data"] is None

    def test_thread_post_auto_scaffolds_non_existent_project(self, mcp_server: AlphaMCPServer):
        """Verify thread_post safely auto-scaffolds thread if project was not explicitly pre-created."""
        req = {
            "jsonrpc": "2.0",
            "id": 505,
            "method": "tools/call",
            "params": {
                "name": "thread_post",
                "arguments": {
                    "project_id": "proj_auto_scaffold_999",
                    "from_agent": "CEO",
                    "to_agents": ["CTO"],
                    "type": "DELIVERABLE",
                    "content": "Autonomous deliverable post",
                    "subject": "Initial Deliverable",
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp, f"Auto-scaffolding thread_post failed: {resp}"
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["success"] is True
        assert data["posted"] is True
        assert data["project_id"] == "proj_auto_scaffold_999"


# ============================================================================
# 6. CAO Audit Gate Model Override Verification
# ============================================================================

class TestCAORoutingOverrides:
    """Verify Tier 5 inviolable override for CAO independent audit gates."""

    @pytest.mark.parametrize("agent_id,expected_model,expected_provider", [
        ("CAO", "claude-3-5-sonnet", "anthropic"),
        ("CAO-Claude", "claude-3-5-sonnet", "anthropic"),
        ("CAO-C", "claude-3-5-sonnet", "anthropic"),
        ("CAO-ChatGPT", "gpt-4o", "openai"),
        ("CAO-G", "gpt-4o", "openai"),
    ])
    def test_model_route_cao_tier5_overrides(
        self,
        mcp_server: AlphaMCPServer,
        agent_id: str,
        expected_model: str,
        expected_provider: str,
    ):
        """Verify CAO agents always receive Tier 5 premium models even at minimum complexity 1."""
        req = {
            "jsonrpc": "2.0",
            "id": 601,
            "method": "tools/call",
            "params": {
                "name": "model_route",
                "arguments": {
                    "task_type": "audit_review",
                    "complexity": 1,  # Minimum complexity, but CAO must get Tier 5
                    "agent_id": agent_id,
                },
            },
        }
        resp = mcp_server.handle_jsonrpc_sync(req)
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["tier"] == 5
        assert data["recommended_model"] == expected_model
        assert data["provider"] == expected_provider
