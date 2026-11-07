"""tests/api/test_adversarial_m8_rest.py - Adversarial Stress & Security Test Suite for Milestone 8 REST API.

Empirically challenges Milestone 8 REST API layer across 7 adversarial attack vectors:
1. Malformed Goal Submissions: Empty string, whitespace-only, null bytes, 100k chars, non-dict payloads, missing title -> 422.
2. Path Traversal & Injection Attacks in Vault Routes: ../.., encoded %2e%2e%2f, null bytes -> 400.
3. Vault RBAC & CAO Confinement: CAO writes outside projects/{id}/audit/ blocked with 403; legitimate audit writes succeed with 200.
4. Entity Not Found & Boundary Conditions: Nonexistent projects, goals, agents, and vault paths return 404.
5. Auth Attacks: Tampered tokens, lowercase bearer, missing prefix, basic auth, query param on REST -> 401.
6. Unicode & Multi-lingual Preservation: Emojis, CJK, Arabic RTL, math symbols preserved without corruption.
7. Concurrency Stress: 20 concurrent goal submissions and 20 concurrent vault reads/writes -> zero race conditions or crashes.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List
import pytest
from starlette.testclient import TestClient


# ============================================================================
# Scenario 1: Malformed Goal Submissions
# ============================================================================

def test_adversarial_goals_empty_string_returns_422(client: TestClient, auth_headers: dict):
    """Verify POST /api/goals rejects empty title with HTTP 422 Unprocessable Entity."""
    res = client.post("/api/goals", json={"title": ""}, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for empty string, got {res.status_code}: {res.text}"


def test_adversarial_goals_whitespace_only_returns_422(client: TestClient, auth_headers: dict):
    """Verify POST /api/goals rejects whitespace-only title with HTTP 422 Unprocessable Entity."""
    res = client.post("/api/goals", json={"title": "   \t\n   "}, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for whitespace title, got {res.status_code}: {res.text}"


def test_adversarial_goals_missing_title_returns_422(client: TestClient, auth_headers: dict):
    """Verify POST /api/goals rejects missing title field with HTTP 422 Unprocessable Entity."""
    res = client.post("/api/goals", json={"description": "No title specified"}, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for missing title, got {res.status_code}: {res.text}"


@pytest.mark.parametrize(
    "payload,desc",
    [
        (["item1", "item2"], "list payload"),
        (12345, "integer payload"),
        (True, "boolean payload"),
        ("raw string payload", "string payload"),
    ],
)
def test_adversarial_goals_non_dict_payloads_return_422(client: TestClient, auth_headers: dict, payload: Any, desc: str):
    """Verify POST /api/goals rejects non-dict JSON bodies with HTTP 422 Unprocessable Entity."""
    res = client.post("/api/goals", json=payload, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for {desc}, got {res.status_code}: {res.text}"


def test_adversarial_goals_excessively_long_text_returns_422(client: TestClient, auth_headers: dict):
    """Verify POST /api/goals rejects title exceeding maximum length (100k chars) with HTTP 422."""
    excessive_title = "A" * 100_000
    res = client.post("/api/goals", json={"title": excessive_title}, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for 100k char title, got {res.status_code}: {res.text}"


def test_adversarial_goals_null_bytes_in_title(client: TestClient, auth_headers: dict):
    """Probe POST /api/goals with null byte injection in title -> verify HTTP 422 Unprocessable Entity.

    Vulnerability check: verifies whether input validator catches embedded or solitary null bytes.
    """
    for bad_title in ["\x00", "Build Autonomous \x00 System", "\x00\x00\x00"]:
        res = client.post("/api/goals", json={"title": bad_title}, headers=auth_headers)
        assert res.status_code == 422, (
            f"VULNERABILITY: Goal submission accepted null byte title {repr(bad_title)} "
            f"with HTTP {res.status_code} instead of 422 Unprocessable Entity: {res.text}"
        )


# ============================================================================
# Scenario 2: Path Traversal & Injection Attacks in Vault Routes
# ============================================================================

@pytest.mark.parametrize(
    "traversal_path",
    [
        "../../company/identity.json",
        "../../../../etc/passwd",
        "../..",
        "company/../../../etc/shadow",
        "..\\..\\windows\\win.ini",
    ],
)
def test_adversarial_vault_dot_dot_traversal_blocked(client: TestClient, auth_headers: dict, traversal_path: str):
    """Verify GET /api/vault/read blocks ../.. traversal attempts with HTTP 400 Bad Request."""
    res = client.get(f"/api/vault/read?path={traversal_path}", headers=auth_headers)
    assert res.status_code == 400, f"Expected 400 for path '{traversal_path}', got {res.status_code}: {res.text}"


@pytest.mark.parametrize(
    "encoded_path",
    [
        "%2e%2e%2fcompany/identity.json",
        "%2e%2e/company/identity.json",
        "..%2fcompany/identity.json",
        "%2e%2e%2f%2e%2e%2fetc/passwd",
    ],
)
def test_adversarial_vault_encoded_traversal_blocked(client: TestClient, auth_headers: dict, encoded_path: str):
    """Verify GET /api/vault/read blocks URL-encoded path traversal with HTTP 400 Bad Request."""
    res = client.get(f"/api/vault/read?path={encoded_path}", headers=auth_headers)
    assert res.status_code == 400, f"Expected 400 for encoded path '{encoded_path}', got {res.status_code}: {res.text}"


@pytest.mark.parametrize(
    "null_path",
    [
        "company/identity.json%00.txt",
        "company%00/identity.json",
        "%00company/identity.json",
    ],
)
def test_adversarial_vault_null_byte_injection_blocked(client: TestClient, auth_headers: dict, null_path: str):
    """Verify GET /api/vault/read blocks null bytes in path query param with HTTP 400 Bad Request."""
    res = client.get(f"/api/vault/read?path={null_path}", headers=auth_headers)
    assert res.status_code == 400, f"Expected 400 for null byte path '{null_path}', got {res.status_code}: {res.text}"


def test_adversarial_vault_write_traversal_blocked(client: TestClient, auth_headers: dict):
    """Verify POST /api/vault/write blocks path traversal and null bytes with HTTP 400 Bad Request."""
    for bad_path in ["../../company/identity.json", "company/identity.json\x00.txt"]:
        payload = {"path": bad_path, "data": {"tamper": True}, "agent_id": "CEO"}
        res = client.post("/api/vault/write", json=payload, headers=auth_headers)
        assert res.status_code == 400, f"Expected 400 for bad write path '{bad_path}', got {res.status_code}: {res.text}"


# ============================================================================
# Scenario 3: Vault RBAC & CAO Confinement
# ============================================================================

@pytest.mark.parametrize("cao_agent", ["CAO", "CAO-Claude", "CAO-ChatGPT"])
@pytest.mark.parametrize(
    "forbidden_path",
    [
        "company/identity.json",
        "financials/budget.json",
        "projects/p1/deliverables/code.py",
        "knowledge/tech_decisions.json",
        "agents/CEO/memory.json",
    ],
)
def test_adversarial_cao_unauthorized_writes_forbidden(
    client: TestClient, auth_headers: dict, cao_agent: str, forbidden_path: str
):
    """Verify CAO caller attempting writes outside projects/{id}/audit/ returns HTTP 403 Forbidden."""
    payload = {
        "path": forbidden_path,
        "data": {"compromised": True},
        "agent_id": cao_agent,
    }
    res = client.post("/api/vault/write", json=payload, headers=auth_headers)
    assert res.status_code == 403, (
        f"VULNERABILITY: CAO agent '{cao_agent}' was permitted to write to '{forbidden_path}' "
        f"with status {res.status_code}: {res.text}"
    )


@pytest.mark.parametrize("cao_agent", ["CAO", "CAO-Claude", "CAO-ChatGPT"])
def test_adversarial_cao_legitimate_audit_write_succeeds(
    client: TestClient, auth_headers: dict, cao_agent: str
):
    """Verify legitimate CAO write to projects/{id}/audit/ returns HTTP 200 OK."""
    payload = {
        "path": f"projects/p1/audit/{cao_agent.lower()}_report.json",
        "data": {"passed": True, "score": 98.5, "reviewer": cao_agent},
        "agent_id": cao_agent,
    }
    res = client.post("/api/vault/write", json=payload, headers=auth_headers)
    assert res.status_code == 200, f"Legitimate CAO write failed with {res.status_code}: {res.text}"
    assert res.json().get("success") is True


# ============================================================================
# Scenario 4: Entity Not Found & Boundary Conditions
# ============================================================================

def test_adversarial_entity_not_found_projects(client: TestClient, auth_headers: dict):
    """Verify querying nonexistent project IDs returns HTTP 404 Not Found."""
    for pid in ["proj_nonexistent_99999", "invalid_id_format", "proj_000_fake"]:
        res_detail = client.get(f"/api/projects/{pid}", headers=auth_headers)
        assert res_detail.status_code == 404, f"Expected 404 for project {pid}, got {res_detail.status_code}"

        res_threads = client.get(f"/api/projects/{pid}/threads", headers=auth_headers)
        assert res_threads.status_code == 404, f"Expected 404 for threads {pid}, got {res_threads.status_code}"


def test_adversarial_entity_not_found_goals(client: TestClient, auth_headers: dict):
    """Verify querying nonexistent goal/project IDs returns HTTP 404 Not Found."""
    for gid in ["proj_missing_goal_123", "fake_goal_id"]:
        res = client.get(f"/api/goals/{gid}", headers=auth_headers)
        assert res.status_code == 404, f"Expected 404 for goal {gid}, got {res.status_code}"


def test_adversarial_entity_not_found_agents(client: TestClient, auth_headers: dict):
    """Verify querying nonexistent agent IDs returns HTTP 404 Not Found."""
    for aid in ["NONEXISTENT_BOT", "ROGUE_AI_AGENT", "UNKNOWN_ACTOR"]:
        res_profile = client.get(f"/api/agents/{aid}", headers=auth_headers)
        assert res_profile.status_code == 404, f"Expected 404 for agent {aid}, got {res_profile.status_code}"

        res_msg = client.post(f"/api/agents/{aid}/message", json={"message": "hello"}, headers=auth_headers)
        assert res_msg.status_code == 404, f"Expected 404 for message to {aid}, got {res_msg.status_code}"


def test_adversarial_entity_not_found_vault_paths(client: TestClient, auth_headers: dict):
    """Verify querying nonexistent vault paths returns HTTP 404 Not Found."""
    for vpath in ["company/nonexistent_strategy.json", "projects/missing_proj/manifest.json", "agents/nobody/data"]:
        res = client.get(f"/api/vault/read?path={vpath}", headers=auth_headers)
        assert res.status_code == 404, f"Expected 404 for vault path {vpath}, got {res.status_code}"


# ============================================================================
# Scenario 5: Auth Attacks
# ============================================================================

def test_adversarial_auth_tampered_token_returns_401(client: TestClient, test_token: str):
    """Verify requests with tampered or forged Bearer tokens return HTTP 401 Unauthorized."""
    for bad_token in [f"{test_token}_tampered", "forged_secret_token", "Bearer"]:
        headers = {"Authorization": f"Bearer {bad_token}"}
        res = client.get("/api/projects", headers=headers)
        assert res.status_code == 401, f"Expected 401 for tampered token, got {res.status_code}"


def test_adversarial_auth_missing_prefix_returns_401(client: TestClient, test_token: str):
    """Verify token provided without 'Bearer ' prefix returns HTTP 401 Unauthorized."""
    headers = {"Authorization": test_token}
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 401, f"Expected 401 for missing prefix, got {res.status_code}"


def test_adversarial_auth_basic_auth_returns_401(client: TestClient, test_token: str):
    """Verify Basic authentication scheme returns HTTP 401 Unauthorized."""
    headers = {"Authorization": f"Basic {test_token}"}
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 401, f"Expected 401 for Basic auth scheme, got {res.status_code}"


def test_adversarial_auth_missing_header_returns_401(client: TestClient):
    """Verify protected endpoints without Authorization header return HTTP 401 Unauthorized."""
    # GET endpoints
    for endpoint in ["/api/projects", "/api/agents", "/api/vault/read?path=company/identity"]:
        res = client.get(endpoint)
        assert res.status_code == 401, f"Expected 401 for unauthenticated GET to {endpoint}, got {res.status_code}"

    # POST endpoint
    res_post = client.post("/api/goals", json={"title": "unauthenticated goal"})
    assert res_post.status_code == 401, f"Expected 401 for unauthenticated POST to /api/goals, got {res_post.status_code}"


def test_adversarial_auth_lowercase_bearer_returns_401(client: TestClient, test_token: str):
    """Probe RFC 6750 case-sensitivity: lowercase 'bearer' scheme -> verify HTTP 401 Unauthorized."""
    headers = {"Authorization": f"bearer {test_token}"}
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 401, (
        f"RFC 6750 Case-Sensitivity Discrepancy: lowercase 'bearer' was accepted with {res.status_code} "
        f"instead of being rejected with 401 Unauthorized"
    )


def test_adversarial_auth_query_param_on_rest_returns_401(client: TestClient, test_token: str):
    """Probe REST endpoint token leakage: passing ?token= on REST without header -> verify HTTP 401.

    Query param tokens on REST endpoints leak secrets into server logs and browser history.
    They should only be accepted on WebSocket handshakes (/ws?token=), not REST endpoints.
    """
    for endpoint in [f"/api/projects?token={test_token}", f"/api/agents?token={test_token}"]:
        res = client.get(endpoint)
        assert res.status_code == 401, (
            f"SECURITY DISCREPANCY: REST endpoint '{endpoint}' accepted ?token= in query string "
            f"with {res.status_code} instead of requiring Authorization header (401 Unauthorized)"
        )


# ============================================================================
# Scenario 6: Unicode & Multi-lingual Preservation
# ============================================================================

@pytest.mark.parametrize(
    "category,text",
    [
        ("emojis", "🚀 Project Alpha Autonomous AI Executive OS 🤖✨🛡️"),
        ("CJK characters", "プロジェクト・アルファ 深度学习 自动化 架构设计 テスト"),
        ("Arabic RTL", "مشروع ألفا نظام التشغيل التنفيذي المستقل للذكاء الاصطناعي"),
        ("math symbols", "∀x ∈ ℝ: ∑_{i=1}^n x_i ≤ √n · ||x||_2 ∧ ∂f/∂x = ∇f(x) ⊗ λ"),
        ("mixed multi-lingual", "Alpha 🌟 [日本語] [العربية] ∑=100% 🎯"),
    ],
)
def test_adversarial_unicode_preservation_in_goals_and_vault(
    client: TestClient, auth_headers: dict, category: str, text: str
):
    """Verify unicode, emojis, CJK, Arabic RTL, and math symbols are preserved without corruption."""
    # 1. Goal submission and query
    r_goal = client.post("/api/goals", json={"title": text, "description": f"Directive: {text}"}, headers=auth_headers)
    assert r_goal.status_code == 200, f"Goal creation failed for {category}: {r_goal.text}"
    goal_data = r_goal.json()
    assert goal_data["title"] == text, f"Title corrupted for {category}: {goal_data['title']} != {text}"
    pid = goal_data["project_id"]

    r_status = client.get(f"/api/goals/{pid}", headers=auth_headers)
    assert r_status.status_code == 200
    st_data = r_status.json()
    assert text in st_data["goal"] or text in st_data.get("title", ""), f"Goal status text corrupted for {category}"

    # 2. Vault write and read
    vpath = f"projects/{pid}/deliverables/unicode_{category.replace(' ', '_')}.json"
    r_write = client.post(
        "/api/vault/write",
        json={"path": vpath, "data": {"category": category, "payload": text}, "agent_id": "CTO"},
        headers=auth_headers,
    )
    assert r_write.status_code == 200, f"Vault write failed for {category}: {r_write.text}"

    r_read = client.get(f"/api/vault/read?path={vpath}", headers=auth_headers)
    assert r_read.status_code == 200, f"Vault read failed for {category}: {r_read.text}"
    read_payload = r_read.json()
    assert read_payload.get("payload") == text, f"Vault payload corrupted for {category}: {read_payload}"


# ============================================================================
# Scenario 7: Concurrency Stress
# ============================================================================

def test_adversarial_concurrency_20_goal_submissions(client: TestClient, auth_headers: dict):
    """Verify 20 concurrent goal submissions produce 20 unique projects with zero race conditions."""
    def submit_goal(index: int) -> tuple[int, Dict[str, Any]]:
        payload = {
            "title": f"Concurrent Stress Goal #{index:03d}",
            "description": f"Testing thread safety under high concurrency index {index}",
            "priority": "high",
        }
        res = client.post("/api/goals", json=payload, headers=auth_headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(submit_goal, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    status_codes = [r[0] for r in results]
    assert all(code == 200 for code in status_codes), f"Not all submissions returned 200: {status_codes}"

    project_ids = [r[1].get("project_id") for r in results]
    assert len(project_ids) == 20
    assert len(set(project_ids)) == 20, f"Race condition: Duplicate project IDs detected: {project_ids}"


def test_adversarial_concurrency_20_vault_reads_writes(client: TestClient, auth_headers: dict):
    """Verify 20 concurrent vault writes followed by 20 concurrent reads without deadlocks or crashes."""
    def write_vault(index: int) -> tuple[int, str]:
        path = f"projects/p_concurrent_stress/deliverables/artifact_{index:03d}.json"
        data = {"index": index, "marker": f"stress_value_{index}"}
        res = client.post(
            "/api/vault/write",
            json={"path": path, "data": data, "agent_id": "CTO"},
            headers=auth_headers,
        )
        return res.status_code, path

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        write_futures = [executor.submit(write_vault, i) for i in range(20)]
        write_results = [f.result() for f in concurrent.futures.as_completed(write_futures)]

    write_statuses = [r[0] for r in write_results]
    assert all(code == 200 for code in write_statuses), f"Vault writes failed: {write_statuses}"

    paths = [r[1] for r in write_results]

    def read_vault(path: str) -> tuple[int, Dict[str, Any]]:
        res = client.get(f"/api/vault/read?path={path}", headers=auth_headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        read_futures = [executor.submit(read_vault, p) for p in paths]
        read_results = [f.result() for f in concurrent.futures.as_completed(read_futures)]

    read_statuses = [r[0] for r in read_results]
    assert all(code == 200 for code in read_statuses), f"Vault reads failed: {read_statuses}"

    for _, doc in read_results:
        assert "index" in doc and "marker" in doc
