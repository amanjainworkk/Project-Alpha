"""backend/api/websocket.py - Project Alpha Real-Time WebSocket Telemetry Engine.

Architected for Milestone 8 (Feature 61).
Provides:
1. Universal typed message envelope: { "event": str, "data": dict, "timestamp": str }
2. ConnectionManager with thread-safe client lifecycle (connect, auth, disconnect, reap).
3. Bi-directional WebSocket endpoint (/ws and /ws/telemetry) with query/header authentication.
4. Support for all 6 required telemetry events:
   - task_progress_update (task progress bar)
   - agent_status_change (executive boardroom card)
   - node_flow_pulse (Archify canvas pulsing data packet)
   - audit_status_update (Dual CAO audit scorecard & escalation)
   - project_state_change (project lifecycle transition)
   - telemetry_heartbeat (system metrics & keepalive)
5. Project subscription filtering and client ping/pong keepalive.
6. Seamless orchestrator and thread manager telemetry integration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Union

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

logger = logging.getLogger("alpha.api.websocket")

router = APIRouter(tags=["telemetry"])


# ============================================================================
# 1. Universal Envelope & Event Data Models
# ============================================================================

class WebSocketEnvelope(BaseModel):
    """Universal typed envelope conforming to PROJECT.md & Mobile Dart models."""
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskProgressPayload(BaseModel):
    """Payload for event: 'task_progress_update'."""
    task_id: str
    task_name: Optional[str] = ""
    progress_percent: int = Field(ge=0, le=100)
    current_step: str
    assigned_agent: str
    status: str = "running"  # 'running', 'auditing', 'blocked', 'done', 'failed'


class AgentStatusPayload(BaseModel):
    """Payload for event: 'agent_status_change'."""
    agent_id: str
    old_status: Optional[str] = None
    new_status: str
    current_task: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class NodeFlowPulsePayload(BaseModel):
    """Payload for event: 'node_flow_pulse' (Archify animated spline pulse)."""
    source_agent: str
    target_agent: str
    message_type: str = "DELIBERATION"
    project_id: Optional[str] = None
    preview: str = ""
    pulse_color: str = "#06B6D4"  # Neon cyan default


class AuditStatusPayload(BaseModel):
    """Payload for event: 'audit_status_update'."""
    project_id: str
    round: int
    status: str  # 'in_progress', 'passed', 'rejected', 'escalated_to_founder'
    passed: bool
    claude_score: float
    gpt_score: float
    composite_score: Optional[float] = None
    p0_defects_count: int = 0
    p1_defects_count: int = 0
    escalation_required: bool = False


class ProjectStateChangePayload(BaseModel):
    """Payload for event: 'project_state_change'."""
    project_id: str
    old_state: Optional[str] = None
    new_state: str
    status: str
    progress: Optional[float] = None
    title: Optional[str] = None


class TelemetryHeartbeatPayload(BaseModel):
    """Payload for event: 'telemetry_heartbeat'."""
    status: str = "alive"
    server_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    uptime_seconds: float = 0.0
    active_agents: int = 13
    active_tasks: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0


# ============================================================================
# 2. Client Session Representation
# ============================================================================

@dataclass
class ClientSession:
    """Represents an active client WebSocket connection state."""
    websocket: WebSocket
    client_id: str
    authenticated: bool = True
    subscribed_projects: Set[str] = field(default_factory=lambda: {"*"})
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


# ============================================================================
# 3. ConnectionManager Core Engine
# ============================================================================

class ConnectionManager:
    """Thread-safe WebSocket connection lifecycle, event broadcast, and subscription manager."""

    def __init__(self, auth_token: Optional[str] = None) -> None:
        self.auth_token = auth_token or os.environ.get("ALPHA_TOKEN", "test_alpha_bearer_token_secret_xyz789")
        self._active_sessions: Dict[WebSocket, ClientSession] = {}
        self._lock = asyncio.Lock()
        self._orchestrator_hook_registered = False
        self._background_tasks: set[asyncio.Task] = set()

    @property
    def active_count(self) -> int:
        """Return the number of connected active WebSocket sessions."""
        return len(self._active_sessions)

    def verify_token(self, candidate_token: Optional[str]) -> bool:
        """Verify token in constant time."""
        if not self.auth_token:
            return True
        if not candidate_token:
            return False
        clean_candidate = candidate_token.strip()
        expected = self.auth_token.strip()
        return secrets.compare_digest(clean_candidate, expected)

    async def connect(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> bool:
        """Authenticate and register a newly incoming client connection."""
        # 1. Dual-mode authentication (query parameter or Authorization header)
        if not token:
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]

        if not self.verify_token(token):
            logger.warning("Rejecting unauthenticated WebSocket connection from %s", websocket.client)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        # 2. Accept WebSocket handshake
        await websocket.accept()
        cid = client_id or f"client_{uuid.uuid4().hex[:8]}"
        session = ClientSession(websocket=websocket, client_id=cid, authenticated=True)

        async with self._lock:
            self._active_sessions[websocket] = session

        logger.info("Client '%s' connected via WebSocket. Active sessions: %d", cid, self.active_count)

        # 3. Emit initial connected confirmation envelope
        welcome_envelope = {
            "event": "connected",
            "data": {
                "client_id": cid,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "subscribed_projects": list(session.subscribed_projects),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await websocket.send_text(json.dumps(welcome_envelope))
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """Safely prune a client connection on close or network drop."""
        session = self._active_sessions.pop(websocket, None)
        if session:
            logger.info("Client '%s' disconnected. Remaining sessions: %d", session.client_id, self.active_count)

    def subscribe(self, websocket: WebSocket, project_id: str) -> bool:
        """Subscribe connection to a specific project stream."""
        if not project_id:
            return False
        session = self._active_sessions.get(websocket)
        if session:
            clean_pid = project_id.strip()
            if clean_pid != "*":
                session.subscribed_projects.discard("*")
            else:
                session.subscribed_projects.clear()
            session.subscribed_projects.add(clean_pid)
            session.last_activity = time.time()
            return True
        return False

    def unsubscribe(self, websocket: WebSocket, project_id: str) -> bool:
        """Unsubscribe connection from a specific project stream."""
        session = self._active_sessions.get(websocket)
        if session:
            session.subscribed_projects.discard(project_id.strip())
            if not session.subscribed_projects:
                session.subscribed_projects.add("*")
            session.last_activity = time.time()
            return True
        return False

    def reap_stale(self, max_idle_seconds: float = 120.0) -> int:
        """Reap and remove stale client sessions whose last activity exceeds max_idle_seconds."""
        now = time.time()
        stale_sockets = [
            ws for ws, sess in list(self._active_sessions.items())
            if (now - sess.last_activity) > max_idle_seconds
        ]
        for ws in stale_sockets:
            try:
                self.disconnect(ws)
            except Exception:
                pass
        return len(stale_sockets)

    # Method alias for caller consistency and backwards-compatibility
    reap_stale_connections = reap_stale

    # ------------------------------------------------------------------------
    # Broadcast Pipeline (Async Core + Sync Thread Bridge)
    # ------------------------------------------------------------------------

    async def broadcast_async(
        self,
        event: str,
        data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> int:
        """Core asynchronous broadcast dispatcher emitting typed envelopes."""
        envelope = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload_str = json.dumps(envelope)
        sent_count = 0
        dead_sockets: List[WebSocket] = []

        # Iterate over snapshot of active sessions
        for ws, session in list(self._active_sessions.items()):
            subs = session.subscribed_projects
            # Apply project subscription filter
            if project_id is not None and len(subs) > 0 and "*" not in subs and project_id not in subs:
                continue

            try:
                await ws.send_text(payload_str)
                sent_count += 1
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug("Failed sending to client %s (%s). Flagged for cleanup.", session.client_id, exc)
                dead_sockets.append(ws)

        for dead in dead_sockets:
            self.disconnect(dead)

        return sent_count

    def broadcast(
        self,
        event: str,
        data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> int:
        """Thread-safe synchronous bridge for broadcasting telemetry from any thread or coroutine."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            task = loop.create_task(self.broadcast_async(event, data, project_id))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return 1
        else:
            return asyncio.run(self.broadcast_async(event, data, project_id))

    # ------------------------------------------------------------------------
    # Client Inbound Message Dispatcher (Ping/Pong, Subscribe)
    # ------------------------------------------------------------------------

    async def handle_client_message(self, websocket: WebSocket, raw_text: str) -> None:
        """Process inbound JSON directive from Flutter client."""
        session = self._active_sessions.get(websocket)
        if session:
            session.last_activity = time.time()

        stripped = raw_text.strip()
        if stripped.lower() in ("ping", '"ping"'):
            reply = {
                "event": "pong",
                "data": {
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "client_echo": "ping",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(reply))
            return

        try:
            msg = json.loads(raw_text)
        except Exception:
            return

        if not isinstance(msg, dict):
            return

        action = str(msg.get("action") or "").lower()

        if action == "ping":
            reply = {
                "event": "pong",
                "data": {
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "client_echo": msg.get("data") if isinstance(msg, dict) else {},
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(reply))

        elif action == "subscribe":
            pid = msg.get("project_id")
            if pid:
                self.subscribe(websocket, pid)
                reply = {
                    "event": "subscribed",
                    "data": {"project_id": pid},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await websocket.send_text(json.dumps(reply))

        elif action == "unsubscribe":
            pid = msg.get("project_id")
            if pid:
                self.unsubscribe(websocket, pid)
                reply = {
                    "event": "unsubscribed",
                    "data": {"project_id": pid},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await websocket.send_text(json.dumps(reply))

    # ------------------------------------------------------------------------
    # Typed Emitters for Core Telemetry Events
    # ------------------------------------------------------------------------

    def emit_task_progress(
        self,
        task_id: str,
        progress_percent: int,
        current_step: str,
        assigned_agent: str,
        status: str = "running",
        task_name: str = "",
        project_id: Optional[str] = None,
    ) -> int:
        """Emit 'task_progress_update' for Flutter Tasks Screen progress bar."""
        payload = TaskProgressPayload(
            task_id=task_id,
            task_name=task_name or task_id,
            progress_percent=max(0, min(100, progress_percent)),
            current_step=current_step,
            assigned_agent=assigned_agent,
            status=status,
        ).model_dump()
        return self.broadcast("task_progress_update", payload, project_id=project_id)

    def emit_agent_status(
        self,
        agent_id: str,
        new_status: str,
        old_status: Optional[str] = None,
        current_task: Optional[str] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> int:
        """Emit 'agent_status_change' for Flutter Boardroom Screen executive cards."""
        payload = AgentStatusPayload(
            agent_id=agent_id,
            old_status=old_status,
            new_status=new_status,
            current_task=current_task,
            model_used=model_used,
            tokens_used=tokens_used,
        ).model_dump()
        return self.broadcast("agent_status_change", payload)

    def emit_node_flow_pulse(
        self,
        source_agent: str,
        target_agent: str,
        message_type: str = "DELIBERATION",
        project_id: Optional[str] = None,
        preview: str = "",
        pulse_color: str = "#06B6D4",
    ) -> int:
        """Emit 'node_flow_pulse' for Archify+ animated canvas spline particles."""
        payload = NodeFlowPulsePayload(
            source_agent=source_agent,
            target_agent=target_agent,
            message_type=message_type,
            project_id=project_id,
            preview=preview[:80],
            pulse_color=pulse_color,
        ).model_dump()
        return self.broadcast("node_flow_pulse", payload, project_id=project_id)

    def emit_audit_status(
        self,
        project_id: str,
        round_num: int,
        status: str,
        passed: bool,
        claude_score: float,
        gpt_score: float,
        composite_score: Optional[float] = None,
        p0_defects_count: int = 0,
        p1_defects_count: int = 0,
        escalation_required: bool = False,
    ) -> int:
        """Emit 'audit_status_update' for Dual CAO audit updates and Founder escalation."""
        payload = AuditStatusPayload(
            project_id=project_id,
            round=round_num,
            status=status,
            passed=passed,
            claude_score=claude_score,
            gpt_score=gpt_score,
            composite_score=composite_score or ((claude_score + gpt_score) / 2.0),
            p0_defects_count=p0_defects_count,
            p1_defects_count=p1_defects_count,
            escalation_required=escalation_required,
        ).model_dump()
        return self.broadcast("audit_status_update", payload, project_id=project_id)

    def emit_project_state(
        self,
        project_id: str,
        new_state: str,
        old_state: Optional[str] = None,
        status: str = "planning",
        progress: Optional[float] = None,
        title: Optional[str] = None,
    ) -> int:
        """Emit 'project_state_change' for project lifecycle state changes."""
        payload = ProjectStateChangePayload(
            project_id=project_id,
            old_state=old_state,
            new_state=new_state,
            status=status,
            progress=progress,
            title=title,
        ).model_dump()
        return self.broadcast("project_state_change", payload, project_id=project_id)

    def emit_heartbeat(
        self,
        uptime_seconds: float = 0.0,
        active_agents: int = 13,
        active_tasks: int = 0,
        memory_mb: float = 0.0,
        cpu_percent: float = 0.0,
    ) -> int:
        """Emit 'telemetry_heartbeat' for client connection keepalive."""
        payload = TelemetryHeartbeatPayload(
            status="alive",
            uptime_seconds=uptime_seconds,
            active_agents=active_agents,
            active_tasks=active_tasks,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
        ).model_dump()
        return self.broadcast("telemetry_heartbeat", payload)

    # ------------------------------------------------------------------------
    # Subsystem Telemetry Hooks (Orchestrator, ThreadManager)
    # ------------------------------------------------------------------------

    def attach_orchestrator(self, orchestrator: Any) -> None:
        """Wire real-time broadcast hooks into AlphaOrchestrator and ThreadManager."""
        if orchestrator is not None:
            if hasattr(orchestrator, "attach_telemetry") and callable(orchestrator.attach_telemetry):
                orchestrator.attach_telemetry(self)
            else:
                setattr(orchestrator, "telemetry_manager", self)

        if self._orchestrator_hook_registered:
            return

        tm = getattr(orchestrator, "thread_manager", None)
        if tm is not None and hasattr(tm, "subscribe_all"):
            def on_thread_message(msg: Any) -> None:
                try:
                    sender = getattr(msg, "from_agent", "AGENT")
                    to_list = getattr(msg, "to_agents", ["*"])
                    target = to_list[0] if (to_list and to_list[0] != "*") else "BOARDROOM"
                    mtype = getattr(msg, "type", "MESSAGE")
                    pid = getattr(msg, "project_id", None)
                    content = getattr(msg, "content", "")

                    # 1. Emit animated Archify data pulse
                    self.emit_node_flow_pulse(
                        source_agent=sender,
                        target_agent=target,
                        message_type=str(mtype),
                        project_id=pid,
                        preview=content[:60],
                    )

                    # 2. Update agent status to active
                    self.emit_agent_status(
                        agent_id=sender,
                        new_status="active",
                        current_task=f"Deliberating with {target}",
                    )
                except Exception as e:
                    logger.debug("Orchestrator thread message hook notice: %s", e)

            try:
                tm.subscribe_all(on_thread_message)
                self._orchestrator_hook_registered = True
                logger.info("Attached WebSocket telemetry hook to ThreadManager.")
            except Exception as e:
                logger.warning("Could not attach thread manager telemetry hook: %s", e)


# ============================================================================
# 4. WebSocket Route Endpoints
# ============================================================================

@router.websocket("/ws")
@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
) -> None:
    """Bi-directional real-time telemetry stream for Flutter APK & Archify Canvas."""
    # Obtain manager from application state or create default
    manager: ConnectionManager = getattr(websocket.app.state, "connection_manager", None)
    if manager is None:
        token_env = getattr(websocket.app.state, "auth_token", None) or os.environ.get("ALPHA_TOKEN")
        manager = ConnectionManager(auth_token=token_env)
        websocket.app.state.connection_manager = manager

    # Connect and authenticate
    connected = await manager.connect(websocket, token=token)
    if not connected:
        return

    try:
        while True:
            raw_text = await websocket.receive_text()
            await manager.handle_client_message(websocket, raw_text)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.debug("WebSocket connection closed with: %s", exc)
        manager.disconnect(websocket)
