"""tests/api/test_websocket.py - WebSocket Telemetry Engine Test Suite.

Verifies:
1. WebSocket Handshake & Authentication (query param & header)
2. Unauthenticated Connection Rejection (WS_1008_POLICY_VIOLATION)
3. Event Broadcast Across Multiple Connected Clients
4. Client Disconnect Resilience Without Server Exception Leakage
5. Project-Specific Subscription Filtering
6. Inbound Client Ping/Pong Protocol
7. All 6 Core Telemetry Event Types & Envelope Structure:
   - task_progress_update
   - agent_status_change
   - node_flow_pulse
   - audit_status_update
   - project_state_change
   - telemetry_heartbeat
8. Orchestrator ThreadManager Telemetry Hook Propagation
9. Stale Connection Reaping
"""

from __future__ import annotations

import json
import time
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import TEST_TOKEN


# ============================================================================
# 1. Connection & Handshake Tests
# ============================================================================

def test_websocket_connect_authenticated_success(client: TestClient, test_token: str):
    """Verifies that an authenticated client receives the initial 'connected' envelope."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "connected"
        assert "client_id" in msg["data"]
        assert "server_time" in msg["data"]


def test_websocket_connect_unauthenticated_rejected(client: TestClient):
    """Verifies that unauthenticated WebSocket connections are rejected with code 1008."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


# ============================================================================
# 2. Multi-Client Event Broadcasting Tests
# ============================================================================

def test_websocket_broadcast_across_multiple_clients(client: TestClient, connection_manager, test_token: str):
    """Verifies that broadcast events reach all active, listening client connections."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws1:
        # Consume welcome messages
        ws1.receive_json()

        with client.websocket_connect(f"/ws?token={test_token}") as ws2:
            ws2.receive_json()

            # Trigger broadcast from manager
            connection_manager.emit_agent_status(
                agent_id="CTO",
                new_status="auditing",
                old_status="active",
                current_task="Dual CAO 5-axis review",
            )

            # Both clients must receive the identical event envelope
            m1 = ws1.receive_json()
            m2 = ws2.receive_json()

            assert m1["event"] == "agent_status_change"
            assert m2["event"] == "agent_status_change"
            assert m1["data"]["agent_id"] == "CTO"
            assert m2["data"]["agent_id"] == "CTO"
            assert m1["data"]["new_status"] == "auditing"
            assert "timestamp" in m1


def test_websocket_client_disconnect_resilience(client: TestClient, connection_manager, test_token: str):
    """Verifies server cleans up disconnected clients and continues broadcasting to surviving clients."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws_surviving:
        ws_surviving.receive_json()

        with client.websocket_connect(f"/ws?token={test_token}") as ws_dropping:
            ws_dropping.receive_json()
            assert connection_manager.active_count == 2

        # ws_dropping has cleanly closed; active count should decrement
        assert connection_manager.active_count == 1

        # Subsequent broadcast succeeds without exception
        connection_manager.emit_heartbeat(active_agents=13, active_tasks=2)

        m = ws_surviving.receive_json()
        assert m["event"] == "telemetry_heartbeat"
        assert m["data"]["active_agents"] == 13


# ============================================================================
# 3. Project Subscription Filtering Tests
# ============================================================================

def test_websocket_project_subscription_filtering(client: TestClient, connection_manager, test_token: str):
    """Verifies that clients subscribed to a project only receive matching project events or globals."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws_alpha:
        ws_alpha.receive_json()

        # Subscribe ws_alpha explicitly to proj_alpha
        ws_alpha.send_text(json.dumps({"action": "subscribe", "project_id": "proj_alpha"}))
        sub_ack = ws_alpha.receive_json()
        assert sub_ack["event"] == "subscribed"

        with client.websocket_connect(f"/ws?token={test_token}") as ws_beta:
            ws_beta.receive_json()

            # Subscribe ws_beta explicitly to proj_beta
            ws_beta.send_text(json.dumps({"action": "subscribe", "project_id": "proj_beta"}))
            ws_beta.receive_json()

            # Broadcast event targeting proj_alpha
            connection_manager.emit_task_progress(
                task_id="T-01",
                progress_percent=85,
                current_step="Generating Archify SVG",
                assigned_agent="CTO",
                status="running",
                project_id="proj_alpha",
            )

            # ws_alpha receives matching event
            m_alpha = ws_alpha.receive_json()
            assert m_alpha["event"] == "task_progress_update"
            assert m_alpha["data"]["task_id"] == "T-01"

            # Global event broadcasts to both
            connection_manager.emit_heartbeat(active_agents=13)
            m_alpha_global = ws_alpha.receive_json()
            m_beta_global = ws_beta.receive_json()
            assert m_alpha_global["event"] == "telemetry_heartbeat"
            assert m_beta_global["event"] == "telemetry_heartbeat"


# ============================================================================
# 4. Inbound Client Protocol (Ping/Pong)
# ============================================================================

def test_websocket_client_ping_pong_protocol(client: TestClient, test_token: str):
    """Verifies client ping produces server pong keepalive reply."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws:
        ws.receive_json()  # Connected welcome

        # Inbound JSON ping
        ws.send_text(json.dumps({"action": "ping", "data": {"seq": 1}}))
        pong = ws.receive_json()
        assert pong["event"] == "pong"
        assert "server_time" in pong["data"]

        # Inbound raw string ping
        ws.send_text("ping")
        pong_raw = ws.receive_json()
        assert pong_raw["event"] == "pong"


# ============================================================================
# 5. Envelope Structure for All 6 Required Event Types
# ============================================================================

def test_websocket_all_6_event_envelopes_compliance(client: TestClient, connection_manager, test_token: str):
    """Verifies envelope format and data payloads for all 6 core telemetry events."""
    with client.websocket_connect(f"/ws?token={test_token}") as ws:
        ws.receive_json()

        # 1. task_progress_update
        connection_manager.emit_task_progress(
            task_id="task_001",
            progress_percent=80,
            current_step="Step 4: CAO Audit",
            assigned_agent="CTO",
            status="auditing",
        )
        e1 = ws.receive_json()
        assert e1["event"] == "task_progress_update"
        assert e1["data"]["task_id"] == "task_001"
        assert e1["data"]["progress_percent"] == 80
        assert "timestamp" in e1

        # 2. agent_status_change
        connection_manager.emit_agent_status(
            agent_id="CEO",
            new_status="active",
            current_task="Intake Goal Decomposition",
        )
        e2 = ws.receive_json()
        assert e2["event"] == "agent_status_change"
        assert e2["data"]["agent_id"] == "CEO"

        # 3. node_flow_pulse
        connection_manager.emit_node_flow_pulse(
            source_agent="CEO",
            target_agent="CTO",
            message_type="DELEGATION",
            preview="Architectural Design Directive",
            pulse_color="#06B6D4",
        )
        e3 = ws.receive_json()
        assert e3["event"] == "node_flow_pulse"
        assert e3["data"]["source_agent"] == "CEO"
        assert e3["data"]["target_agent"] == "CTO"
        assert e3["data"]["pulse_color"] == "#06B6D4"

        # 4. audit_status_update
        connection_manager.emit_audit_status(
            project_id="proj_001",
            round_num=1,
            status="passed",
            passed=True,
            claude_score=92.5,
            gpt_score=91.0,
            escalation_required=False,
        )
        e4 = ws.receive_json()
        assert e4["event"] == "audit_status_update"
        assert e4["data"]["passed"] is True
        assert e4["data"]["claude_score"] == 92.5

        # 5. project_state_change
        connection_manager.emit_project_state(
            project_id="proj_001",
            new_state="review",
            old_state="planning",
            status="review",
            progress=0.75,
        )
        e5 = ws.receive_json()
        assert e5["event"] == "project_state_change"
        assert e5["data"]["new_state"] == "review"
        assert e5["data"]["progress"] == 0.75

        # 6. telemetry_heartbeat
        connection_manager.emit_heartbeat(
            uptime_seconds=3600.0,
            active_agents=13,
            memory_mb=128.5,
        )
        e6 = ws.receive_json()
        assert e6["event"] == "telemetry_heartbeat"
        assert e6["data"]["active_agents"] == 13
        assert e6["data"]["status"] == "alive"


# ============================================================================
# 6. Orchestrator Hook Propagation & Stale Reaping
# ============================================================================

def test_websocket_orchestrator_hook_thread_message_propagation(client: TestClient, connection_manager, test_token: str):
    """Verifies that messages posted in ThreadManager trigger live node_flow_pulse over WebSocket."""
    class MockThreadMessage:
        from_agent = "CEO"
        to_agents = ["CTO"]
        type = "DELEGATION"
        project_id = "proj_orch_001"
        content = "Execute technical specification."
        subject = "Architecture Task"

    class MockThreadManager:
        def __init__(self):
            self.subscriber = None
        def subscribe_all(self, callback):
            self.subscriber = callback

    class MockOrchestrator:
        thread_manager = MockThreadManager()

    orch = MockOrchestrator()
    connection_manager.attach_orchestrator(orch)

    with client.websocket_connect(f"/ws?token={test_token}") as ws:
        ws.receive_json()  # Connected

        # Trigger message via hooked callback
        orch.thread_manager.subscriber(MockThreadMessage())

        # ws must receive node_flow_pulse and agent_status_change
        pulse = ws.receive_json()
        assert pulse["event"] == "node_flow_pulse"
        assert pulse["data"]["source_agent"] == "CEO"
        assert pulse["data"]["target_agent"] == "CTO"

        status_msg = ws.receive_json()
        assert status_msg["event"] == "agent_status_change"
        assert status_msg["data"]["agent_id"] == "CEO"


def test_websocket_stale_connection_reaping(connection_manager):
    """Verifies that reap_stale removes inactive sessions exceeding idle threshold."""
    class MockWS:
        pass
    ws_dummy = MockWS()
    connection_manager._active_sessions[ws_dummy] = type("Session", (), {
        "client_id": "stale_client",
        "last_activity": time.time() - 300.0,
    })()

    assert connection_manager.active_count >= 1
    reaped = connection_manager.reap_stale(max_idle_seconds=60.0)
    assert reaped >= 1
