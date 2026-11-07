"""tests/api/test_routes.py - Comprehensive REST Route Test Suite.

Verifies:
1. Goals API (/api/goals): intake, validation (422), retrieval, status (404)
2. Projects API (/api/projects): list, detail, threads, manual project creation
3. Agents API (/api/agents): all 13 C-suite agents present, detail lookup, message dispatch
4. Vault API (/api/vault): read, write, RBAC CAO confinement (403), path traversal (400), hybrid search
5. Health Probe (/health and /api/health): uptime and subsystem health statuses
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


# ============================================================================
# 1. Goals REST Endpoints (/api/goals)
# ============================================================================

def test_goals_post_valid_payload_creates_project(client: TestClient, auth_headers: dict):
    """Verifies POST /api/goals accepts valid goal and initiates planning."""
    payload = {
        "title": "Build Autonomous Mobile Command Center",
        "description": "Flutter app with Archify canvas and pulsing telemetry flows",
        "complexity": 4,
        "priority": "high",
    }
    res = client.post("/api/goals", json=payload, headers=auth_headers)
    assert res.status_code in (200, 201)
    data = res.json()
    assert "project_id" in data
    assert data["project_id"].startswith("proj_")
    assert data["status"] == "planning"


def test_goals_post_empty_or_whitespace_title_returns_422(client: TestClient, auth_headers: dict):
    """Verifies POST /api/goals rejects empty or whitespace title with 422."""
    # Empty string
    res_empty = client.post("/api/goals", json={"title": ""}, headers=auth_headers)
    assert res_empty.status_code == 422

    # Whitespace only
    res_ws = client.post("/api/goals", json={"title": "   "}, headers=auth_headers)
    assert res_ws.status_code == 422

    # Missing title field
    res_missing = client.post("/api/goals", json={"description": "No title provided"}, headers=auth_headers)
    assert res_missing.status_code == 422


def test_goals_get_status_existing_and_nonexistent(client: TestClient, auth_headers: dict):
    """Verifies GET /api/goals/{id} returns goal execution state or 404."""
    create = client.post("/api/goals", json={"title": "Goal Status Check"}, headers=auth_headers)
    pid = create.json()["project_id"]

    res = client.get(f"/api/goals/{pid}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid

    res_missing = client.get("/api/goals/proj_nonexistent_99999", headers=auth_headers)
    assert res_missing.status_code == 404


# ============================================================================
# 2. Projects REST Endpoints (/api/projects)
# ============================================================================

def test_projects_get_list(client: TestClient, auth_headers: dict):
    """Verifies GET /api/projects returns list of project summaries."""
    res = client.get("/api/projects", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_projects_get_detail_and_not_found(client: TestClient, auth_headers: dict):
    """Verifies GET /api/projects/{id} returns detailed manifest or 404."""
    create = client.post("/api/goals", json={"title": "Project Detail Test"}, headers=auth_headers)
    pid = create.json()["project_id"]

    detail = client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["project_id"] == pid

    not_found = client.get("/api/projects/proj_fake_000000", headers=auth_headers)
    assert not_found.status_code == 404


def test_projects_get_threads_endpoint(client: TestClient, auth_headers: dict):
    """Verifies GET /api/projects/{id}/threads returns thread history or 404."""
    create = client.post("/api/goals", json={"title": "Thread Project"}, headers=auth_headers)
    pid = create.json()["project_id"]

    threads_res = client.get(f"/api/projects/{pid}/threads", headers=auth_headers)
    assert threads_res.status_code == 200
    data = threads_res.json()
    assert "threads" in data
    assert data["project_id"] == pid


def test_projects_post_manual_creation(client: TestClient, auth_headers: dict):
    """Verifies POST /api/projects creates project manifest without immediate pipeline start."""
    payload = {
        "name": "Manual Scaffold Project",
        "user_goal": "Establish baseline repository structure",
        "priority": "medium",
        "tags": ["infrastructure", "scaffolding"],
    }
    res = client.post("/api/projects", json=payload, headers=auth_headers)
    assert res.status_code in (200, 201)
    data = res.json()
    assert "project_id" in data
    assert data["status"] == "planning"


# ============================================================================
# 3. Agents REST Endpoints (/api/agents)
# ============================================================================

def test_agents_get_roster_contains_all_13_csuite_agents(client: TestClient, auth_headers: dict):
    """Verifies GET /api/agents returns exactly 13 C-Suite executive cards."""
    res = client.get("/api/agents", headers=auth_headers)
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) == 13

    expected_roles = {
        "CEO", "CTO", "CMO", "CPO", "CDO", "CFO",
        "COO", "CHRO", "CIO", "CSO", "CLO",
    }
    for r in expected_roles:
        assert any(r == a.get("agent_id") or r in a.get("role", "") for a in agents), f"Role {r} missing from roster"


def test_agents_get_detail_and_not_found(client: TestClient, auth_headers: dict):
    """Verifies GET /api/agents/{id} returns full profile or 404."""
    res_cto = client.get("/api/agents/CTO", headers=auth_headers)
    assert res_cto.status_code == 200
    data = res_cto.json()
    assert data["agent_id"] == "CTO" or data.get("role") == "CTO"

    res_missing = client.get("/api/agents/NONEXISTENT_BOT", headers=auth_headers)
    assert res_missing.status_code == 404


def test_agents_post_message_dispatch(client: TestClient, auth_headers: dict):
    """Verifies POST /api/agents/{id}/message delivers directive to executive."""
    payload = {"message": "Generate preliminary architecture blueprint."}
    res = client.post("/api/agents/CTO/message", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "delivered"

    # Empty message rejection
    res_empty = client.post("/api/agents/CTO/message", json={"message": ""}, headers=auth_headers)
    assert res_empty.status_code == 422


# ============================================================================
# 4. Vault REST Endpoints (/api/vault)
# ============================================================================

def test_vault_read_existing_and_nonexistent_key(client: TestClient, auth_headers: dict):
    """Verifies GET /api/vault/read returns document JSON or 404."""
    # Existing company identity
    res = client.get("/api/vault/read", params={"path": "company/identity"}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "company_name" in data or "name" in data

    # Nonexistent path returns 404
    res_missing = client.get("/api/vault/read", params={"path": "nonexistent/key_xyz"}, headers=auth_headers)
    assert res_missing.status_code == 404


def test_vault_read_path_traversal_and_null_byte_blocked(client: TestClient, auth_headers: dict):
    """Verifies GET /api/vault/read blocks path traversal and null bytes with 400."""
    res_traversal = client.get("/api/vault/read", params={"path": "../../etc/passwd"}, headers=auth_headers)
    assert res_traversal.status_code == 400

    res_null = client.get("/api/vault/read", params={"path": "company/identity\x00secret"}, headers=auth_headers)
    assert res_null.status_code == 400

    res_empty = client.get("/api/vault/read", params={"path": "   "}, headers=auth_headers)
    assert res_empty.status_code == 400


def test_vault_write_and_cao_confinement_rbac(client: TestClient, auth_headers: dict):
    """Verifies POST /api/vault/write enforces strict CAO audit gate confinement (403 Forbidden)."""
    # Authorized write under CEO
    valid_payload = {
        "path": "company/mission_statement",
        "data": {"statement": "Autonomous AI Executive Operating System"},
        "agent_id": "CEO",
    }
    res_ok = client.post("/api/vault/write", json=valid_payload, headers=auth_headers)
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True

    # Unauthorized CAO write outside projects/{id}/audit/ must be rejected with 403 Forbidden
    cao_violation = {
        "path": "company/mission_statement",
        "data": {"statement": "Corrupted by unauthorized audit agent"},
        "agent_id": "CAO",
    }
    res_forbidden = client.post("/api/vault/write", json=cao_violation, headers=auth_headers)
    assert res_forbidden.status_code == 403
    err_body = str(res_forbidden.json())
    assert "Forbidden" in err_body or "AccessDenied" in err_body or "detail" in res_forbidden.json()


def test_vault_search_semantic_and_keyword(client: TestClient, auth_headers: dict):
    """Verifies GET /api/vault/search returns ranked search matches."""
    res = client.get("/api/vault/search", params={"query": "Autonomous", "top_k": 5}, headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_empty = client.get("/api/vault/search", params={"query": ""}, headers=auth_headers)
    assert res_empty.status_code == 400


# ============================================================================
# 5. System Health Check Endpoints
# ============================================================================

def test_health_endpoints_return_healthy(client: TestClient):
    """Verifies GET /health and GET /api/health report system uptime and subsystem health."""
    for path in ("/health", "/api/health"):
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "subsystems" in data
