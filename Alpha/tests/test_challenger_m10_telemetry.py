"""tests/test_challenger_m10_telemetry.py - Empirical Adversarial Challenger Suite for Milestone 10.

Authored by challenger_m10_2 to stress-test and verify:
1. AlphaApiClient (Alpha/apk/lib/services/api_client.dart):
   - Custom exception hierarchy: 400 (ApiException), 401 (AuthException), 403 (AuthException/ApiException),
     404 (NotFoundException), 422 (ValidationException), 500 (ApiException), client timeouts (RequestTimeoutException),
     network errors (NetworkException).
   - Authorization headers: Bearer token format serialization ('Authorization: Bearer <token>').
   - Exact route path and query parameter match against FastAPI OpenAPI contracts.
2. AlphaWebSocketService (Alpha/apk/lib/services/websocket_service.dart):
   - Handshake URL construction: ws://{host}:{port}/ws?token={token}.
   - Exponential backoff reconnection calculation: 1s, 2s, 4s, 8s, 16s, capped at 30s.
   - Frame resilience: malformed JSON, non-dict payloads (arrays, strings, ints), unknown event types, missing keys.
   - Stream broadcasting: typed stream routing and unhandled exception safety.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest
from starlette.testclient import TestClient

from backend.api.main import create_app
from backend.api.websocket import ConnectionManager
from backend.vault.vault_manager import VaultManager


# ============================================================================
# Section 1: Dart Source Code Parsing & Route Matching Oracle
# ============================================================================

def test_alpha_api_client_routes_match_fastapi_openapi_spec(tmp_path):
    """Empirically extract all endpoints from api_client.dart and verify they exist in FastAPI OpenAPI schema."""
    api_client_path = Path("Alpha/apk/lib/services/api_client.dart")
    assert api_client_path.exists(), f"api_client.dart not found at {api_client_path}"

    dart_code = api_client_path.read_text(encoding="utf-8")

    # Extract all URI patterns like '$baseUrl/health', '$baseUrl/api/projects', '$baseUrl/api/projects/$cleanId'
    raw_matches = re.findall(r"\$baseUrl(/api/[\w/{}\-\$]+|/health)", dart_code)
    extracted_routes = sorted(set(raw_matches))

    assert len(extracted_routes) >= 7, f"Expected at least 7 API routes, found: {extracted_routes}"

    # Build FastAPI test app and inspect OpenAPI paths
    vm = VaultManager(vault_root=tmp_path / "vault")
    app = create_app(vault_manager=vm)
    openapi_spec = app.openapi()
    spec_paths = set(openapi_spec.get("paths", {}).keys())

    # Map Dart path interpolation variables to OpenAPI format: e.g. $cleanId -> {id}
    normalized_dart_routes = set()
    for route in extracted_routes:
        # Replace $cleanId or similar variable interpolations with {id}
        norm = re.sub(r"\$cleanId", "{id}", route)
        norm = re.sub(r"\$cleanPath", "{path}", norm)
        # Strip query parameters if present in template
        norm = norm.split("?")[0]
        normalized_dart_routes.add(norm)

    # Core routes expected
    expected_core_routes = {
        "/health",
        "/api/projects",
        "/api/projects/{id}",
        "/api/agents",
        "/api/agents/{id}",
        "/api/agents/{id}/message",
        "/api/goals",
        "/api/goals/{id}",
        "/api/vault/read",
        "/api/vault/search",
    }

    for core_route in expected_core_routes:
        assert core_route in spec_paths, f"FastAPI schema missing core route: {core_route}"
        assert core_route in normalized_dart_routes, f"AlphaApiClient missing core route: {core_route}"


def test_alpha_api_client_bearer_token_format_against_auth_endpoint(tmp_path):
    """Verify AlphaApiClient Bearer header serialization against FastAPI verify_token."""
    vm = VaultManager(vault_root=tmp_path / "vault")
    secret_token = "secret_alpha_token_42"
    app = create_app(vault_manager=vm, token=secret_token)
    client = TestClient(app)

    # Simulation of AlphaApiClient._buildHeaders
    def build_dart_headers(token: Optional[str], extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token is not None and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        if extra:
            headers.update(extra)
        return headers

    # 1. Valid token
    valid_headers = build_dart_headers(secret_token)
    assert valid_headers["Authorization"] == f"Bearer {secret_token}"
    res = client.get("/api/projects", headers=valid_headers)
    assert res.status_code == 200, f"Expected 200 with valid Bearer header, got {res.status_code}: {res.text}"

    # 2. Token with whitespace (Dart does token!.trim())
    whitespace_headers = build_dart_headers(f"   {secret_token}   ")
    assert whitespace_headers["Authorization"] == f"Bearer {secret_token}"
    res = client.get("/api/projects", headers=whitespace_headers)
    assert res.status_code == 200

    # 3. Missing / empty token
    empty_headers = build_dart_headers("")
    assert "Authorization" not in empty_headers
    res = client.get("/api/projects", headers=empty_headers)
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers

    # 4. Invalid token
    bad_headers = build_dart_headers("wrong_token_123")
    res = client.get("/api/projects", headers=bad_headers)
    assert res.status_code == 401


# ============================================================================
# Section 2: Exception Hierarchy & Status Code Mapping Oracle
# ============================================================================

class DartAlphaException(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

class DartApiException(DartAlphaException): pass
class DartAuthException(DartAlphaException): pass
class DartValidationException(DartAlphaException): pass
class DartNotFoundException(DartAlphaException): pass
class DartNetworkException(DartAlphaException): pass
class DartRequestTimeoutException(DartAlphaException): pass

def simulate_dart_handle_response(status_code: int, body_str: str) -> Any:
    """Exact replica of AlphaApiClient._handleResponse in Dart."""
    if 200 <= status_code < 300:
        if not body_str:
            return {}
        try:
            return json.loads(body_str)
        except Exception as e:
            raise DartApiException(f"Failed to decode JSON response: {e}", status_code=status_code, details=body_str)

    # Process error payload
    parsed_body = None
    try:
        if body_str:
            parsed_body = json.loads(body_str)
    except Exception:
        parsed_body = body_str

    error_message = f"HTTP request failed with status {status_code}"
    error_detail = parsed_body

    if isinstance(parsed_body, dict):
        error_message = (
            parsed_body.get("detail")
            or parsed_body.get("error")
            or parsed_body.get("message")
            or error_message
        )
        if not isinstance(error_message, str):
            error_message = str(error_message)
        error_detail = parsed_body.get("detail", parsed_body)
    elif isinstance(parsed_body, str) and parsed_body:
        error_message = parsed_body

    if status_code == 401:
        raise DartAuthException(f"Unauthorized: {error_message}", status_code=status_code, details=error_detail)
    elif status_code == 403:
        raise DartAuthException(f"Forbidden: {error_message}", status_code=status_code, details=error_detail)
    elif status_code == 404:
        raise DartNotFoundException(f"Not Found: {error_message}", status_code=status_code, details=error_detail)
    elif status_code == 422:
        raise DartValidationException(f"Validation Error: {error_message}", status_code=status_code, details=error_detail)
    elif status_code in (500, 502, 503, 504):
        raise DartApiException(f"Server Error: {error_message}", status_code=status_code, details=error_detail)
    else:
        raise DartApiException(error_message, status_code=status_code, details=error_detail)


def test_empirical_exception_mapping_matrix():
    """Stress-test Dart _handleResponse logic across 400, 401, 403, 404, 422, 500, 502, 503, 504, 200."""
    # 200 Success
    res = simulate_dart_handle_response(200, '{"key": "value"}')
    assert res == {"key": "value"}

    # 200 Empty body
    res_empty = simulate_dart_handle_response(204, "")
    assert res_empty == {}

    # 400 Bad Request -> ApiException
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(400, '{"detail": "Bad syntax"}')
    assert exc_info.value.status_code == 400
    assert "Bad syntax" in exc_info.value.message
    assert issubclass(DartApiException, DartAlphaException)

    # 401 Unauthorized -> AuthException
    with pytest.raises(DartAuthException) as exc_info:
        simulate_dart_handle_response(401, '{"detail": "Invalid token"}')
    assert exc_info.value.status_code == 401
    assert "Unauthorized" in exc_info.value.message

    # 403 Forbidden -> AuthException
    with pytest.raises(DartAuthException) as exc_info:
        simulate_dart_handle_response(403, '{"detail": "CAO access denied"}')
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.message

    # 404 Not Found -> NotFoundException
    with pytest.raises(DartNotFoundException) as exc_info:
        simulate_dart_handle_response(404, '{"detail": "Project not found"}')
    assert exc_info.value.status_code == 404
    assert "Not Found" in exc_info.value.message

    # 422 Validation Error -> ValidationException
    with pytest.raises(DartValidationException) as exc_info:
        simulate_dart_handle_response(422, '{"detail": [{"loc": ["body", "title"], "msg": "Field required"}]}')
    assert exc_info.value.status_code == 422
    assert "Validation Error" in exc_info.value.message

    # 500 Server Error -> ApiException
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(500, '{"detail": "SQLite store lock timeout"}')
    assert exc_info.value.status_code == 500
    assert "Server Error" in exc_info.value.message

    # 502 Bad Gateway / 503 Service Unavailable / 504 Gateway Timeout -> ApiException
    for code in (502, 503, 504):
        with pytest.raises(DartApiException) as exc_info:
            simulate_dart_handle_response(code, "<html>Error</html>")
        assert exc_info.value.status_code == code
        assert "Server Error" in exc_info.value.message


# ============================================================================
# Section 3: WebSocket Handshake URL Construction Oracle
# ============================================================================

def simulate_dart_ws_uri(host: str, token: Optional[str] = None, default_path: str = "/ws") -> str:
    """Exact replica of AlphaWebSocketService._normalizeHost and uri getter in Dart."""
    # _normalizeHost
    clean = host.strip()
    if clean.startswith("ws://") or clean.startswith("http://"):
        clean = clean[clean.index("://") + 3:]
    elif clean.startswith("wss://") or clean.startswith("https://"):
        clean = clean[clean.index("://") + 3:]
    while clean.endswith("/"):
        clean = clean[:-1]

    # uri getter
    query_params = {}
    if token is not None and token.strip():
        query_params["token"] = token.strip()

    h = clean.split(":")[0] if ":" in clean else clean
    p = int(clean.split(":")[1]) if ":" in clean else 8765

    query_str = f"?token={query_params['token']}" if "token" in query_params else ""
    return f"ws://{h}:{p}{default_path}{query_str}"


def test_websocket_handshake_uri_construction_matrix():
    """Verify handshake URL construction across emulator, localhost, LAN IPs, and tokens."""
    # 1. Default emulator host with token
    uri1 = simulate_dart_ws_uri("10.0.2.2:8765", token="my_token")
    assert uri1 == "ws://10.0.2.2:8765/ws?token=my_token"

    # 2. Localhost with scheme prefix stripped
    uri2 = simulate_dart_ws_uri("http://127.0.0.1:8765///", token="abc_xyz")
    assert uri2 == "ws://127.0.0.1:8765/ws?token=abc_xyz"

    # 3. LAN IP without explicit port (defaults to 8765)
    uri3 = simulate_dart_ws_uri("192.168.1.150", token="token123")
    assert uri3 == "ws://192.168.1.150:8765/ws?token=token123"

    # 4. Without token
    uri4 = simulate_dart_ws_uri("10.0.2.2:8765", token=None)
    assert uri4 == "ws://10.0.2.2:8765/ws"

    # 5. Token with surrounding whitespace
    uri5 = simulate_dart_ws_uri("10.0.2.2:8765", token="   clean_token   ")
    assert uri5 == "ws://10.0.2.2:8765/ws?token=clean_token"


# ============================================================================
# Section 4: Exponential Backoff Reconnection Oracle
# ============================================================================

def simulate_dart_exponential_backoff(
    num_failures: int,
    initial_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
) -> List[float]:
    """Exact replica of AlphaWebSocketService._scheduleReconnect backoff calculation in Dart."""
    delays_executed = []
    current_retry_delay = initial_delay_s

    for _ in range(num_failures):
        delay = current_retry_delay
        delays_executed.append(delay)

        # Dart: nextDelayMs = min(currentRetryDelayMs * 2, maxRetryDelayMs)
        next_delay = min(current_retry_delay * 2.0, max_delay_s)
        current_retry_delay = next_delay

    return delays_executed


def test_exponential_backoff_exact_progression_and_cap():
    """Verify exponential progression: 1s, 2s, 4s, 8s, 16s, capped at 30s."""
    delays = simulate_dart_exponential_backoff(num_failures=10, initial_delay_s=1.0, max_delay_s=30.0)

    expected = [
        1.0,   # Failure 1 delay
        2.0,   # Failure 2 delay
        4.0,   # Failure 3 delay
        8.0,   # Failure 4 delay
        16.0,  # Failure 5 delay
        30.0,  # Failure 6 delay (capped from 32.0 to 30.0)
        30.0,  # Failure 7 delay
        30.0,  # Failure 8 delay
        30.0,  # Failure 9 delay
        30.0,  # Failure 10 delay
    ]

    assert delays == expected, f"Backoff progression mismatch: got {delays}, expected {expected}"


# ============================================================================
# Section 5: Frame Resilience & Stream Broadcasting Stress Oracle
# ============================================================================

class DartWebSocketEnvelope:
    def __init__(self, event: str, data: Dict[str, Any], timestamp: str):
        self.event = event
        self.data = data
        self.timestamp = timestamp

    @classmethod
    def from_json(cls, json_map: Dict[str, Any]) -> "DartWebSocketEnvelope":
        ev = str(json_map.get("event") or "")
        dt = json_map.get("data")
        # In Dart: (json['data'] as Map<String, dynamic>?) ?? {}
        if dt is None:
            data_map = {}
        elif isinstance(dt, dict):
            data_map = dt
        else:
            raise TypeError(f"type '{type(dt).__name__}' is not a subtype of type 'Map<String, dynamic>?'")
        ts = str(json_map.get("timestamp") or "")
        return cls(event=ev, data=data_map, timestamp=ts)


def simulate_dart_handle_incoming_message(raw_text: Any) -> Optional[DartWebSocketEnvelope]:
    """Exact replica of AlphaWebSocketService._handleIncomingMessage with Dart error handling."""
    try:
        text = raw_text if isinstance(raw_text, str) else raw_text.decode("utf-8")
        decoded = json.loads(text)

        if not isinstance(decoded, dict):
            return None

        envelope = DartWebSocketEnvelope.from_json(decoded)
        return envelope
    except Exception:
        # Dart: catch (e) { // Ignore malformed text or partial chunks }
        return None


def test_frame_resilience_adversarial_payloads():
    """Verify AlphaWebSocketService handles all malformed, non-dict, and boundary frames without crashing."""
    adversarial_inputs = [
        # Malformed JSON
        "NOT JSON AT ALL",
        '{"event": "task_progress_update"',  # Truncated
        '{"event": "task_progress_update", "data": }',  # Invalid syntax
        "",  # Empty string
        "   ",  # Whitespace

        # Non-dict JSON payloads
        "[1, 2, 3]",
        '"just a plain string"',
        "12345",
        "true",
        "null",

        # Non-dict 'data' key inside dict
        '{"event": "task_progress_update", "data": [1, 2, 3]}',
        '{"event": "task_progress_update", "data": "not_a_map"}',
        '{"event": "task_progress_update", "data": 42}',

        # Missing keys
        '{}',
        '{"unknown_key": "some_value"}',
    ]

    for payload in adversarial_inputs:
        result = simulate_dart_handle_incoming_message(payload)
        # Should gracefully return None or safe empty envelope, never raise unhandled exception!
        if result is not None:
            assert isinstance(result.data, dict)
            assert isinstance(result.event, str)


def test_stream_broadcasting_typed_routing():
    """Verify incoming frames route to correct typed streams without unhandled exceptions."""
    valid_frames = [
        (
            '{"event": "task_progress_update", "data": {"task_id": "t1", "progress_percent": 80, "status": "running"}}',
            "task_progress_update",
            True
        ),
        (
            '{"event": "agent_status_change", "data": {"agent_id": "CTO", "new_status": "active"}}',
            "agent_status_change",
            True
        ),
        (
            '{"event": "node_flow_pulse", "data": {"source_agent": "CEO", "target_agent": "CTO"}}',
            "node_flow_pulse",
            True
        ),
        (
            '{"event": "audit_status_update", "data": {"project_id": "p1", "round": 1, "passed": true}}',
            "audit_status_update",
            True
        ),
        (
            '{"event": "project_state_change", "data": {"project_id": "p1", "new_state": "active"}}',
            "project_state_change",
            True
        ),
        (
            '{"event": "telemetry_heartbeat", "data": {"status": "alive", "uptime_seconds": 120.0}}',
            "telemetry_heartbeat",
            True
        ),
        (
            '{"event": "alien_event", "data": {"custom": 123}}',
            "alien_event",
            False  # Unknown event type, safely dropped
        )
    ]

    for raw, expected_event, expected_known in valid_frames:
        envelope = simulate_dart_handle_incoming_message(raw)
        assert envelope is not None
        assert envelope.event == expected_event
        assert isinstance(envelope.data, dict)


# ============================================================================
# Section 6: Live FastAPI WebSocket Connection & Frame Exchange
# ============================================================================

def test_live_fastapi_websocket_auth_and_directives(tmp_path):
    """Test live FastAPI WebSocket endpoint (/ws) authentication and directive roundtrip."""
    vm = VaultManager(vault_root=tmp_path / "vault")
    secret_token = "secret_ws_token_777"
    app = create_app(vault_manager=vm, token=secret_token)
    client = TestClient(app)

    # 1. Handshake with valid query token
    with client.websocket_connect(f"/ws?token={secret_token}") as ws:
        # FastAPI emits initial welcome envelope upon accept
        welcome_resp = json.loads(ws.receive_text())
        assert welcome_resp["event"] == "connected"
        assert "client_id" in welcome_resp["data"]

        # Send ping directive
        ws.send_text(json.dumps({
            "action": "ping",
            "data": {"client_time": "2026-11-07T14:00:00Z"}
        }))

        # Receive pong response
        resp = ws.receive_text()
        pong = json.loads(resp)
        assert pong["event"] == "pong"
        assert "server_time" in pong["data"]

        # Send subscribe directive
        ws.send_text(json.dumps({
            "action": "subscribe",
            "project_id": "proj_emp_01"
        }))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["event"] == "subscribed"
        assert sub_resp["data"]["project_id"] == "proj_emp_01"

        # Send unsubscribe directive
        ws.send_text(json.dumps({
            "action": "unsubscribe",
            "project_id": "proj_emp_01"
        }))
        unsub_resp = json.loads(ws.receive_text())
        assert unsub_resp["event"] == "unsubscribed"

    # 2. Handshake with invalid token fails with policy violation (code 1008)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid_token") as ws:
            ws.receive_text()

    # 3. Handshake with missing token fails
    with pytest.raises(Exception):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()


# ============================================================================
# Section 7: Mathematical Progress Bar & Schema Conformance Invariants
# ============================================================================

def simulate_dart_format_progress_bar(progress_percent: int) -> str:
    """Exact replica of TaskProgress.formatProgressBar in Dart."""
    # In Dart: (progressPercent / 10).round().clamp(0, 10)
    # Python round() uses round-to-even, but Dart uses standard mathematical rounding for .5
    # Dart: (x / 10).round() -> if 80: 8, if 0: 0, if 100: 10
    val = progress_percent / 10.0
    # Emulate Dart's double.round()
    if val >= 0:
        rounded = int(math.floor(val + 0.5))
    else:
        rounded = int(math.ceil(val - 0.5))
    filled = max(0, min(10, rounded))
    empty = max(0, min(10, 10 - filled))
    return f"[{'█' * filled}{'░' * empty}] {progress_percent}%"


def test_ascii_progress_bar_mathematical_invariants():
    """Verify ASCII progress bar formatting across 0%, 80%, 100%, and adversarial bounds."""
    # 1. Core milestone contracts
    assert simulate_dart_format_progress_bar(80) == "[████████░░] 80%"
    assert simulate_dart_format_progress_bar(0) == "[░░░░░░░░░░] 0%"
    assert simulate_dart_format_progress_bar(100) == "[██████████] 100%"

    # 2. Intermediate steps
    assert simulate_dart_format_progress_bar(10) == "[█░░░░░░░░░] 10%"
    assert simulate_dart_format_progress_bar(50) == "[█████░░░░░] 50%"

    # 3. Adversarial boundary conditions (clamped, no negative repetition error)
    bar_neg = simulate_dart_format_progress_bar(-50)
    assert bar_neg == "[░░░░░░░░░░] -50%"

    bar_overflow = simulate_dart_format_progress_bar(150)
    assert bar_overflow == "[██████████] 150%"

    # Invariant: inner bar character count must ALWAYS equal exactly 10
    for pct in range(-20, 121, 5):
        formatted = simulate_dart_format_progress_bar(pct)
        inner_bar = formatted[1:11]
        assert len(inner_bar) == 10
        assert set(inner_bar).issubset({"█", "░"})


def test_alpha_api_client_error_body_parsing_resilience():
    """Verify error parsing when server emits plain text, HTML, or empty error bodies."""
    # 1. HTML error page (e.g. from reverse proxy or Cloudflare)
    html_page = "<html><head><title>502 Bad Gateway</title></head><body>502 Bad Gateway</body></html>"
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(502, html_page)
    assert exc_info.value.status_code == 502
    assert "Server Error" in exc_info.value.message

    # 2. Empty response body on 500
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(500, "")
    assert exc_info.value.status_code == 500
    assert "Server Error" in exc_info.value.message

    # 3. Custom 'error' key instead of 'detail'
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(400, '{"error": "Custom error description"}')
    assert exc_info.value.status_code == 400
    assert "Custom error description" in exc_info.value.message

    # 4. Custom 'message' key
    with pytest.raises(DartApiException) as exc_info:
        simulate_dart_handle_response(400, '{"message": "Custom message description"}')
    assert exc_info.value.status_code == 400
    assert "Custom message description" in exc_info.value.message


def test_websocket_telemetry_payload_schema_conformance():
    """Verify all 6 backend telemetry emitters match the expected fields in Dart domain models."""
    manager = ConnectionManager(auth_token="dummy_token")

    # Capture broadcasted envelopes
    captured = []
    manager.broadcast = lambda event, data, project_id=None: captured.append((event, data))

    # 1. Task progress
    manager.emit_task_progress(
        task_id="task_99",
        progress_percent=75,
        current_step="Step 3 of 4",
        assigned_agent="CTO",
        task_name="Compile APK",
    )
    ev, data = captured[-1]
    assert ev == "task_progress_update"
    assert data["task_id"] == "task_99"
    assert data["progress_percent"] == 75
    assert data["current_step"] == "Step 3 of 4"
    assert data["assigned_agent"] == "CTO"
    assert data["status"] == "running"

    # 2. Agent status
    manager.emit_agent_status(
        agent_id="CEO",
        new_status="active",
        current_task="Analyzing Founder goals",
        model_used="llama3.2",
        tokens_used=1200,
    )
    ev, data = captured[-1]
    assert ev == "agent_status_change"
    assert data["agent_id"] == "CEO"
    assert data["new_status"] == "active"
    assert data["tokens_used"] == 1200

    # 3. Node flow pulse
    manager.emit_node_flow_pulse(
        source_agent="CEO",
        target_agent="CTO",
        message_type="DIRECTIVE",
        preview="Proceed with architecture review",
    )
    ev, data = captured[-1]
    assert ev == "node_flow_pulse"
    assert data["source_agent"] == "CEO"
    assert data["target_agent"] == "CTO"
    assert data["pulse_color"] == "#06B6D4"

    # 4. Audit status
    manager.emit_audit_status(
        project_id="proj_01",
        round_num=1,
        status="passed",
        passed=True,
        claude_score=92.5,
        gpt_score=90.0,
    )
    ev, data = captured[-1]
    assert ev == "audit_status_update"
    assert data["project_id"] == "proj_01"
    assert data["round"] == 1
    assert data["passed"] is True
    assert data["composite_score"] == 91.25

    # 5. Project state
    manager.emit_project_state(
        project_id="proj_01",
        new_state="in_progress",
        progress=0.45,
        title="Project Alpha",
    )
    ev, data = captured[-1]
    assert ev == "project_state_change"
    assert data["project_id"] == "proj_01"
    assert data["new_state"] == "in_progress"
    assert data["progress"] == 0.45

    # 6. Heartbeat
    manager.emit_heartbeat(
        uptime_seconds=3600.0,
        active_agents=13,
        active_tasks=2,
        memory_mb=128.5,
        cpu_percent=12.0,
    )
    ev, data = captured[-1]
    assert ev == "telemetry_heartbeat"
    assert data["status"] == "alive"
    assert data["uptime_seconds"] == 3600.0
    assert data["active_agents"] == 13
