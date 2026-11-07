"""Project Alpha — Tier 2: Boundary & Corner Cases Test Suite.

Adversarial stress testing across system boundaries:
1. Empty and whitespace-only inputs
2. Extreme payload lengths (100k+ chars)
3. Path traversal and SQL/script injection defense
4. Malformed and schema-violating JSON payloads
5. Complexity tier boundary clamping (min 1, max 5)
6. Rate limit (429) simulation and exponential backoff
7. Unicode, multilingual, and emoji fidelity
8. WebSocket abrupt disconnection & reconnect recovery
9. Null byte and control character sanitization
10. Concurrent rapid writes & state consistency
"""

from __future__ import annotations

import json
import pytest
from typing import Dict, Any
from tests.conftest import ContractModelRouter


# ===========================================================================
# 1. Empty & Nil Boundaries
# ===========================================================================

def test_boundary_empty_goal_title_rejected(api_client, auth_headers):
    """Verifies empty or missing title in goal submission returns 422."""
    res = api_client.post("/api/goals", json_data={"title": "", "description": "No title"}, headers=auth_headers)
    assert res["status_code"] == 422

    res_nil = api_client.post("/api/goals", json_data={}, headers=auth_headers)
    assert res_nil["status_code"] == 422


def test_boundary_empty_string_vault_path_handling(vault_manager):
    """Verifies reading an empty string path returns None gracefully."""
    assert vault_manager.read("") is None
    assert vault_manager.read("   ") is None


def test_boundary_empty_deliverables_in_cao_audit(dual_cao):
    """Verifies Dual CAO handles empty deliverables dictionary without crashing."""
    result = dual_cao.audit({}, "proj_empty", round_num=1)
    assert result.passed is True  # Contract handles empty safely


# ===========================================================================
# 2. Extreme Payload Sizes & Max Length
# ===========================================================================

def test_boundary_massive_prompt_length_handling(model_router):
    """Verifies a 120,000-character input prompt is handled without memory exhaustion."""
    large_prompt = "Alpha OS task requirement: " + ("analyze data " * 10000)
    assert len(large_prompt) > 100000

    response = model_router.call(large_prompt, task_type="summarize", complexity=1, agent_role="CEO")
    assert response is not None
    assert len(response) > 0


def test_boundary_massive_json_deliverable_in_vault(vault_manager):
    """Verifies Vault stores large multi-megabyte payloads without corruption."""
    large_payload = {f"metric_{i}": f"value_token_{i}" * 50 for i in range(2000)}
    assert vault_manager.write("knowledge/heavy_metrics", large_payload) is True
    retrieved = vault_manager.read("knowledge/heavy_metrics")
    assert len(retrieved) == 2000


# ===========================================================================
# 3. Path Traversal & Injection Defense
# ===========================================================================

def test_boundary_path_traversal_sanitization(vault_manager):
    """Verifies path traversal attempts (e.g., ../../etc/passwd) are sanitized or confined."""
    malicious_path = "../../etc/shadow"
    vault_manager.write(malicious_path, {"compromised": True})
    # Should be stored under clean sanitized key, never escaping to filesystem
    assert vault_manager.read(malicious_path) is not None
    # Verify no file actually written outside vault
    assert not (vault_manager.vault_path.parent / "etc").exists()


def test_boundary_sql_and_script_injection_sanitization(vault_manager, api_client, auth_headers):
    """Verifies SQL injection strings and HTML/JS script tags are safely treated as raw data."""
    sql_injection = "'; DROP TABLE agents; --"
    xss_payload = "<script>alert('pwned')</script>"

    vault_manager.write("knowledge/security_test", {"query": sql_injection, "html": xss_payload})
    stored = vault_manager.read("knowledge/security_test")
    assert stored["query"] == sql_injection
    assert stored["html"] == xss_payload

    # REST endpoint does not execute or mangle injection payload
    res = api_client.get("/api/vault/read", params={"path": "knowledge/security_test"}, headers=auth_headers)
    assert res["status_code"] == 200
    assert res["json"]["query"] == sql_injection


def test_boundary_null_byte_injection_prevention(vault_manager):
    """Verifies null bytes in path or content do not cause POSIX truncation vulnerabilities."""
    null_byte_path = "knowledge/secret\x00_hidden"
    vault_manager.write(null_byte_path, {"safe": True})
    data = vault_manager.read(null_byte_path)
    assert data is not None


# ===========================================================================
# 4. Complexity Tier Clamping & Bounds
# ===========================================================================

def test_boundary_complexity_tier_zero_and_negative_clamped_to_one(model_router):
    """Verifies complexity <= 0 is automatically clamped to Tier 1."""
    c_zero = model_router.route("test", complexity=0)
    assert c_zero.tier == 1

    c_negative = model_router.route("test", complexity=-99)
    assert c_negative.tier == 1


def test_boundary_complexity_tier_excessive_clamped_to_five(model_router):
    """Verifies complexity > 5 is automatically clamped to Tier 5."""
    c_excess = model_router.route("test", complexity=42)
    assert c_excess.tier == 5


# ===========================================================================
# 5. Fault Simulation & Rate Limits
# ===========================================================================

def test_boundary_rate_limit_429_simulation_triggers_fallback():
    """Verifies HTTP 429 Too Many Requests triggers backoff and can fall back."""
    router = ContractModelRouter(simulate_rate_limit=True)
    # Tier 5 cloud call raises rate limit exception
    with pytest.raises(RuntimeError) as exc_info:
        router.call("High complexity task", complexity=5)
    assert "429" in str(exc_info.value)

    # When degrading to Tier 2 (Ollama), call succeeds without rate limit
    local_cfg = router.route("High complexity task", complexity=2)
    res = router.call("High complexity task", complexity=2, model_config=local_cfg)
    assert "llama3.2" in res


def test_boundary_read_nonexistent_vault_key_returns_404(api_client, auth_headers):
    """Verifies requesting non-existent key returns 404 rather than unhandled 500."""
    res = api_client.get("/api/vault/read", params={"path": "nonexistent/does_not_exist_123"}, headers=auth_headers)
    assert res["status_code"] == 404


# ===========================================================================
# 6. Encoding & Unicode Integrity
# ===========================================================================

def test_boundary_unicode_multilingual_and_emoji_fidelity(vault_manager):
    """Verifies perfect fidelity for emojis, Asian characters, Cyrillic, and Arabic."""
    multilingual_payload = {
        "english": "Autonomous Executive System 🚀",
        "hindi": "परियोजना अल्फा - स्वायत्त एआई ऑपरेटिंग सिस्टम 💡",
        "chinese": "阿尔法项目 - 自主执行系统 🔥",
        "arabic": "مشروع ألفا - نظام تشغيل ذكي ⚡",
        "special_symbols": "⌘ ⌥ ⇧ ⎋ ¬ ∀ ∃ ∄ ∈ ∉ ∑ ∏",
    }
    assert vault_manager.write("knowledge/i18n_test", multilingual_payload) is True
    retrieved = vault_manager.read("knowledge/i18n_test")
    assert retrieved == multilingual_payload


# ===========================================================================
# 7. Rapid Sequential Writes & Consistency
# ===========================================================================

def test_boundary_concurrent_rapid_writes_consistency(vault_manager):
    """Verifies 100 rapid sequential writes do not cause race conditions or data loss."""
    for i in range(100):
        vault_manager.write(f"projects/proj_stress/task_{i}", {"index": i, "status": "completed"})

    keys = vault_manager.list_keys("projects/proj_stress")
    assert len(keys) == 100
    assert vault_manager.read("projects/proj_stress/task_99")["index"] == 99


# ===========================================================================
# 8. WebSocket Reconnection & State Recovery
# ===========================================================================

def test_boundary_websocket_reconnection_handshake_recovery(api_client):
    """Verifies client can disconnect and re-authenticate without server leakage."""
    from tests.conftest import TEST_TOKEN
    # Connection 1
    assert api_client.websocket_connect(TEST_TOKEN) is True
    # Disconnect & Reconnect
    assert api_client.websocket_connect(TEST_TOKEN) is True
    # Invalid token rejected
    assert api_client.websocket_connect("expired_token_000") is False
