"""backend/vault/schemas.py - Project Alpha Pydantic V2 Vault Schemas.

Canonical schemas for institutional memory, agent profiles, project manifests,
episodic memories, thread messages, and founder user profile.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class MemoryType(str, Enum):
    """Types of episodic memory stored for agents."""
    DECISION = "decision"
    OBSERVATION = "observation"
    FEEDBACK = "feedback"
    LESSON = "lesson"
    FACT = "fact"
    PREFERENCE = "preference"
    SKILL = "skill"
    RELATIONSHIP = "relationship"


class ThreadMessageType(str, Enum):
    """Protocol message types exchanged between agents and systems."""
    DELEGATION = "DELEGATION"
    DELIVERABLE = "DELIVERABLE"
    QUESTION = "QUESTION"
    RESPONSE = "RESPONSE"
    REVIEW_REQUEST = "REVIEW_REQUEST"
    SYNTHESIS = "SYNTHESIS"
    AUDIT_REQUEST = "AUDIT_REQUEST"
    AUDIT_REPORT = "AUDIT_REPORT"
    USER_ESCALATION = "USER_ESCALATION"
    INPUT = "input"
    OUTPUT = "output"


class ProjectStatus(str, Enum):
    """Lifecycle status of a project."""
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    IN_AUDIT = "in_audit"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class ProjectPriority(str, Enum):
    """Priority level for project scheduling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditStatus(str, Enum):
    """Audit gate review status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class AgentStatus(str, Enum):
    """Operational status of an agent."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_TASK = "on_task"


# ============================================================================
# Submodels & Supporting Structures
# ============================================================================

class AssignedModel(BaseModel):
    """Model configuration assigned to an executive agent."""
    model_config = ConfigDict(extra="ignore")

    default: str
    simple_tasks: Optional[str] = None
    complex_tasks: Optional[str] = None


class OutputPreferences(BaseModel):
    """Output formatting preferences for founder deliverables."""
    model_config = ConfigDict(extra="ignore")

    length: str = "concise"  # "concise" | "detailed" | "both"
    format: str = "bullet"   # "bullet" | "prose" | "mixed"
    include_reasoning: bool = True


# ============================================================================
# Core Canonical Models
# ============================================================================

class CompanyIdentity(BaseModel):
    """Canonical model for company/identity.json."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    company_name: str
    founder: str
    founded_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    vision: str
    mission: str
    core_values: List[str] = Field(default_factory=list)
    industry: str
    current_stage: str = "early-stage"
    primary_goals: List[str] = Field(default_factory=list)
    working_style: str = "autonomous, high-velocity"
    preferred_communication: str = "direct, bulleted"
    timezone: str = "UTC"
    language: str = "en"
    alpha_version: str = "1.0.0"


class AgentProfile(BaseModel):
    """Canonical model for agents/{ROLE}/profile.json."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_id: str
    role: str
    full_title: str
    version: str = "1.0.0"
    created_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    jd_file: str = ""
    assigned_model: Union[AssignedModel, Dict[str, Any], str]
    skills: List[str] = Field(default_factory=list)
    communication_style: str = "professional"
    vault_read_access: List[str] = Field(default_factory=list)
    vault_write_access: List[str] = Field(default_factory=list)
    peers: List[str] = Field(default_factory=list)
    reports_to: Optional[str] = None
    status: Union[AgentStatus, str] = AgentStatus.ACTIVE
    total_projects_completed: int = 0
    specializations: List[str] = Field(default_factory=list)

    @field_validator("assigned_model", mode="before")
    @classmethod
    def parse_assigned_model(cls, v: Any) -> Any:
        if isinstance(v, str):
            return AssignedModel(default=v, simple_tasks=v, complex_tasks=v)
        if isinstance(v, dict):
            if "default" not in v:
                v["default"] = "ollama/llama3.2"
            return AssignedModel(**v)
        return v


class ProjectManifest(BaseModel):
    """Canonical model for projects/{id}/manifest.json."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    project_id: str
    name: str
    user_goal: str
    created_at: Union[datetime, str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Union[datetime, str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: Union[ProjectStatus, str] = ProjectStatus.PLANNING
    assigned_agents: List[str] = Field(default_factory=lambda: ["CEO"])
    lead_agent: str = "CEO"
    priority: Union[ProjectPriority, str] = ProjectPriority.MEDIUM
    deadline: Optional[Union[datetime, str]] = None
    deliverables_expected: List[str] = Field(default_factory=list)
    deliverables_completed: List[str] = Field(default_factory=list)
    audit_status: Union[AuditStatus, str] = AuditStatus.PENDING
    user_approved: Optional[bool] = None
    parent_project: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EpisodicMemory(BaseModel):
    """Canonical model for agents/{ROLE}/episodic_memory.jsonl."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    memory_id: str
    agent_id: Optional[str] = None
    timestamp: Union[datetime, str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    project_id: Optional[str] = None
    type: Union[MemoryType, str] = MemoryType.DECISION
    content: str
    context: Optional[str] = None
    importance: int = Field(default=3, ge=1, le=10)
    referenced_agents: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


# Alias for backward and cross-specification compatibility
MemoryEntry = EpisodicMemory


class ThreadMessage(BaseModel):
    """Canonical model for projects/{id}/threads/main.jsonl."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: str
    thread_id: str
    project_id: Optional[str] = None
    timestamp: Union[datetime, str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    from_agent: str = Field(alias="from")
    to_agents: List[str] = Field(default_factory=list)
    type: Union[ThreadMessageType, str] = ThreadMessageType.QUESTION
    subject: Optional[str] = None
    content: str
    attachments: List[str] = Field(default_factory=list)
    in_reply_to: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: int = 0
    status: str = "sent"


class UserProfile(BaseModel):
    """Canonical model for user/profile.json."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = "Aman Jain"
    role: str
    communication_style: str = "direct, high-signal"
    decision_making: str = "autonomous with review"
    working_hours: str = "flexible"
    output_preferences: OutputPreferences = Field(default_factory=OutputPreferences)
    auto_approve_routine: bool = True
    escalation_threshold: str = "critical_only"
    current_focus_areas: List[str] = Field(default_factory=list)
    long_term_goals: List[str] = Field(default_factory=list)
    projects_completed: int = 0
    total_goals_given: int = 0
