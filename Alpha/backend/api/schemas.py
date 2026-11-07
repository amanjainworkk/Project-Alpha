"""backend/api/schemas.py - Pydantic V2 Schemas for Alpha REST API & WebSocket Telemetry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Generic Error Envelope
# ============================================================================

class ErrorEnvelope(BaseModel):
    """Standardized error envelope returned for all API failures."""
    model_config = ConfigDict(extra="ignore")

    error: str = Field(description="High-level error classification")
    code: int = Field(description="HTTP status code")
    detail: Any = Field(description="Granular error message or validation trace")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================================
# Goals API Schemas
# ============================================================================

class GoalSubmissionRequest(BaseModel):
    """Request schema for POST /api/goals."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=1, max_length=255, description="High-level goal title")
    description: str = Field(default="", description="Detailed founder goal directive")
    complexity: Optional[int] = Field(default=None, ge=1, le=5, description="Complexity tier 1-5")
    priority: str = Field(default="medium", description="'low', 'medium', 'high', or 'critical'")

    @field_validator("title")
    @classmethod
    def validate_non_empty_title(cls, v: str) -> str:
        if "\x00" in v or "\0" in v:
            raise ValueError("title cannot contain null bytes.")
        s = v.strip()
        if not s:
            raise ValueError("title cannot be empty or whitespace.")
        return s

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if "\x00" in v or "\0" in v:
            raise ValueError("description cannot contain null bytes.")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Priority must be one of {sorted(list(allowed))}")
        return s


class GoalSubmissionResponse(BaseModel):
    """Response schema for POST /api/goals."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    status: str = "planning"
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GoalStatusResponse(BaseModel):
    """Response schema for GET /api/goals/{id}."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    status: str
    goal: str
    executive_summary: Optional[str] = None
    deliverables: Dict[str, Any] = Field(default_factory=dict)
    audit_result: Optional[Dict[str, Any]] = None
    founder_escalation: Optional[Dict[str, Any]] = None
    archify_diagram_html: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    passed_audit: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================================
# Projects API Schemas
# ============================================================================

class ProjectCreateRequest(BaseModel):
    """Request schema for manual project creation via POST /api/projects."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable project title")
    user_goal: str = Field(..., min_length=1, description="Verbatim founder goal")
    priority: str = Field(default="medium", description="Priority level")
    assigned_agents: Optional[List[str]] = Field(default=None, description="Assigned executive agents")
    tags: Optional[List[str]] = Field(default=None, description="Strategic domain tags")

    @field_validator("name", "user_goal")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if "\x00" in v or "\0" in v:
            raise ValueError("Field cannot contain null bytes.")
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


class ProjectSummary(BaseModel):
    """Summary item for GET /api/projects."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    id: Optional[str] = None
    title: str
    description: str
    status: str
    priority: str = "medium"
    progress: float = 0.0
    created_at: Optional[str] = None
    lead_agent: Optional[str] = "CEO"

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.project_id


class ProjectDetail(BaseModel):
    """Comprehensive detail schema for GET /api/projects/{id}."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    id: Optional[str] = None
    name: str
    title: str
    user_goal: str
    description: str
    status: str
    priority: str = "medium"
    progress: float = 0.0
    assigned_agents: List[str] = Field(default_factory=list)
    lead_agent: str = "CEO"
    created_at: str
    updated_at: str
    deliverables_expected: List[str] = Field(default_factory=list)
    deliverables_completed: List[str] = Field(default_factory=list)
    deliverables: Dict[str, Any] = Field(default_factory=dict)
    audit_status: str = "pending"
    audit_scorecard: Optional[Dict[str, Any]] = None
    archify_graph: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.project_id


class ThreadMessageResponse(BaseModel):
    """Thread message representation for GET /api/projects/{id}/threads."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: str
    thread_id: str
    project_id: Optional[str] = None
    timestamp: str
    from_agent: str = Field(alias="from")
    to_agents: List[str] = Field(default_factory=list)
    type: str
    subject: Optional[str] = None
    content: str
    attachments: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    tokens_used: int = 0
    status: str = "sent"


class ProjectThreadsResponse(BaseModel):
    """Response schema for GET /api/projects/{id}/threads."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    threads: List[ThreadMessageResponse]
    count: int


# ============================================================================
# Agents API Schemas
# ============================================================================

class AgentCard(BaseModel):
    """Executive card representation for GET /api/agents (exactly 13 agents)."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str
    role: str
    full_title: str
    status: str = "active"
    current_task: str = "Idle or awaiting delegation"
    model: str = "llama3.2"
    loaded_model: str = "llama3.2"
    cost_today: float = 0.0
    tokens_used: int = 0


class AgentDetail(BaseModel):
    """Detailed profile schema for GET /api/agents/{id}."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str
    role: str
    full_title: str
    status: str
    jd_summary: str = ""
    assigned_model: Any = "llama3.2"
    skills: List[str] = Field(default_factory=list)
    communication_style: str = "executive"
    vault_read_access: List[str] = Field(default_factory=list)
    vault_write_access: List[str] = Field(default_factory=list)
    peers: List[str] = Field(default_factory=list)
    reports_to: Optional[str] = None
    total_projects_completed: int = 0
    recent_memories_count: int = 0
    cost_today: float = 0.0
    tokens_used: int = 0


class AgentDirectMessageRequest(BaseModel):
    """Request schema for POST /api/agents/{id}/message."""
    model_config = ConfigDict(extra="ignore")

    message: str = Field(..., min_length=1, description="Instruction or query text")
    project_id: Optional[str] = Field(default=None, description="Optional target project ID")
    from_sender: str = Field(default="Founder", description="Sender identity")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if "\x00" in v or "\0" in v:
            raise ValueError("message cannot contain null bytes.")
        s = v.strip()
        if not s:
            raise ValueError("message cannot be empty.")
        return s


class AgentDirectMessageResponse(BaseModel):
    """Response schema for POST /api/agents/{id}/message."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str
    status: str = "delivered"
    response: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================================
# Vault API Schemas
# ============================================================================

class VaultWriteRequest(BaseModel):
    """Request schema for POST /api/vault/write."""
    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., min_length=1, description="Vault document path (e.g. 'company/identity')")
    data: Dict[str, Any] = Field(..., description="JSON document data payload")
    agent_id: Optional[str] = Field(default="ADMIN", description="Calling agent ID for RBAC validation")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("path cannot be empty.")
        return s


class VaultWriteResponse(BaseModel):
    """Response schema for POST /api/vault/write."""
    model_config = ConfigDict(extra="ignore")

    path: str
    success: bool
    message: str = "Document saved successfully."


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Response schema for GET /health and GET /api/health."""
    model_config = ConfigDict(extra="ignore")

    status: str = "healthy"
    version: str = "1.0.0"
    uptime_seconds: float
    subsystems: Dict[str, str] = Field(default_factory=dict)
    system: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# WebSocket Envelope & Event Payload Models
# ============================================================================

class WebSocketEnvelope(BaseModel):
    """Universal WebSocket message envelope."""
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskProgressData(BaseModel):
    """Payload for event: 'task_progress_update'."""
    task_id: str
    task_name: Optional[str] = ""
    progress_percent: int = Field(ge=0, le=100)
    current_step: str
    assigned_agent: str
    status: str = "running"


class AgentStatusData(BaseModel):
    """Payload for event: 'agent_status_change'."""
    agent_id: str
    old_status: Optional[str] = None
    new_status: str
    current_task: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class NodeFlowPulseData(BaseModel):
    """Payload for event: 'node_flow_pulse'."""
    source_agent: str
    target_agent: str
    message_type: str = "DELIBERATION"
    project_id: Optional[str] = None
    preview: str = ""
    pulse_color: str = "#06B6D4"


class AuditStatusData(BaseModel):
    """Payload for event: 'audit_status_update'."""
    project_id: str
    round: int
    status: str
    passed: bool
    claude_score: float
    gpt_score: float
    composite_score: Optional[float] = None
    p0_defects_count: int = 0
    p1_defects_count: int = 0
    escalation_required: bool = False


class ProjectStateChangeData(BaseModel):
    """Payload for event: 'project_state_change'."""
    project_id: str
    old_state: Optional[str] = None
    new_state: str
    status: str
    progress: Optional[float] = None
    title: Optional[str] = None


class TelemetryHeartbeatData(BaseModel):
    """Payload for event: 'telemetry_heartbeat'."""
    status: str = "alive"
    server_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    uptime_seconds: float = 0.0
    active_agents: int = 13
    active_tasks: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
