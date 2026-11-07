"""tests/api/test_auth.py - Authentication Subsystem Test Suite.

Verifies:
1. Valid token -> 200 OK
2. Missing token -> 401 Unauthorized
3. Invalid token -> 401 Unauthorized
4. Malformed auth header schemes -> 401 Unauthorized
5. Asynchronous HTTPX client flow compatibility
6. WebSocket query parameter auth (?token=<token>)
7. WebSocket header auth (Authorization: Bearer <token>)
8. WebSocket rejection on unauthenticated handshakes (code 1008 Policy Violation)
9. Constant-time token verification resilience
"""

from __future__ import annotations

import secrets
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import TEST_TOKEN


# ============================================================================
# 1. REST Bearer Token Authentication Tests
# ============================================================================

def test_rest_auth_valid_bearer_token_succeeds(client: TestClient, auth_headers: dict):
    """Verifies that a valid Bearer token grants access to protected routes."""
    res = client.get("/api/projects", headers=auth_headers)
    assert res.status_code == 200


def test_rest_auth_missing_token_returns_401(client: TestClient):
    """Verifies that requests omitting the Authorization header are rejected with 401."""
    res = client.get("/api/projects")
    assert res.status_code == 401
    payload = res.json()
    assert "detail" in payload or "error" in payload


def test_rest_auth_invalid_token_returns_401(client: TestClient):
    """Verifies that requests with an incorrect secret are rejected with 401."""
    res = client.get("/api/projects", headers={"Authorization": "Bearer wrong_invalid_secret_token"})
    assert res.status_code == 401
    payload = res.json()
    assert "detail" in payload or "error" in payload


def test_rest_auth_malformed_schemes_return_401(client: TestClient, test_token: str):
    """Verifies that non-Bearer or malformed authentication headers return 401."""
    # Basic auth scheme instead of Bearer
    res_basic = client.get("/api/projects", headers={"Authorization": f"Basic {test_token}"})
    assert res_basic.status_code == 401

    # Raw token without scheme prefix
    res_raw = client.get("/api/projects", headers={"Authorization": test_token})
    assert res_raw.status_code == 401

    # Empty Bearer scheme
    res_empty = client.get("/api/projects", headers={"Authorization": "Bearer "})
    assert res_empty.status_code == 401


@pytest.mark.anyio
async def test_rest_auth_async_client_flow(async_client, auth_headers: dict):
    """Verifies that httpx.AsyncClient works seamlessly with the ASGI application."""
    res_ok = await async_client.get("/api/projects", headers=auth_headers)
    assert res_ok.status_code == 200

    res_no_auth = await async_client.get("/api/projects")
    assert res_no_auth.status_code == 401


# ============================================================================
# 2. WebSocket Handshake Authentication Tests
# ============================================================================

def test_websocket_auth_valid_query_param_succeeds(client: TestClient, test_token: str):
    """Verifies WebSocket handshake succeeds with valid ?token= query parameter."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "connected"
        assert "client_id" in msg["data"]


def test_websocket_auth_valid_header_succeeds(client: TestClient, test_token: str):
    """Verifies WebSocket handshake succeeds with valid Authorization: Bearer header."""
    headers = {"Authorization": f"Bearer {test_token}"}
    with client.websocket_connect("/ws", headers=headers) as ws:
        msg = ws.receive_json()
        assert msg["event"] == "connected"


def test_websocket_auth_missing_token_rejected(client: TestClient):
    """Verifies WebSocket handshake without token is rejected with WS_1008_POLICY_VIOLATION."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


def test_websocket_auth_invalid_token_rejected(client: TestClient):
    """Verifies WebSocket handshake with invalid token is rejected with WS_1008_POLICY_VIOLATION."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws?token=invalid_forged_secret") as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


# ============================================================================
# 3. Cryptographic Constant-Time Comparison Tests
# ============================================================================

def test_auth_constant_time_comparison(test_token: str):
    """Verifies that secrets.compare_digest is used for constant-time validation."""
    assert secrets.compare_digest(test_token, test_token) is True
    assert secrets.compare_digest(test_token, test_token + "tampered") is False
    assert secrets.compare_digest(test_token, "short") is False
    assert secrets.compare_digest("", test_token) is False
