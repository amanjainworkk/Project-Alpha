"""backend/mcp/tools/agent_tools.py - Alpha MCP Agent Tool Handlers.

Implements MCP tools for managing executive agents:
- agent_delegate: CEO delegates specific tasks to C-Suite agents with formal briefs.
- agent_status: Query health, active workstream, token telemetry, and episodic memory summary.
- agent_hire: CHRO dynamically registers and onboards a new agent persona with JD and profile.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.agents.agent_registry import AgentRegistry, get_agent_registry
from backend.agents.base_agent import BaseExecutiveAgent
from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.schemas import AgentProfile, AgentStatus
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.mcp.tools.agents")


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class AgentDelegateInput(BaseModel):
    """Input schema for agent_delegate MCP tool."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Target project ID")
    from_agent: str = Field(default="CEO", description="Must be 'CEO' (only CEO holds delegation authority)")
    to_agents: List[str] = Field(..., min_length=1, description="List of target C-suite agent IDs (e.g. ['CTO', 'CMO'])")
    task: str = Field(..., description="Core task description")
    expected_deliverable: str = Field(..., description="Specification of the required artifact")
    context: str = Field(default="", description="Strategic background and operational context")
    deadline_minutes: Optional[int] = Field(default=None, description="Completion timeline in minutes")
    priority: str = Field(
        default="medium",
        description="Priority level: 'low', 'medium', 'high', or 'critical'",
    )

    @field_validator("from_agent")
    @classmethod
    def validate_from_agent(cls, v: str) -> str:
        s = v.strip().upper()
        if s != "CEO":
            raise ValueError(f"Only the CEO can delegate tasks. '{v}' is unauthorized.")
        return "CEO"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Priority must be one of {sorted(list(allowed))}")
        return s


class AgentStatusInput(BaseModel):
    """Input schema for agent_status MCP tool."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(..., description="Agent identifier, e.g. 'CTO' or 'CAO-Claude'")
    include_memory_summary: bool = Field(default=False, description="Whether to include recent episodic memory snippets")

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("agent_id cannot be empty.")
        return s


class AgentHireInput(BaseModel):
    """Input schema for agent_hire MCP tool."""
    model_config = ConfigDict(extra="ignore")

    role: str = Field(..., description="Unique role identifier, e.g. 'CSO-AI' or 'VP-SALES'")
    full_title: str = Field(..., description="Descriptive title, e.g. 'Vice President of Global Sales'")
    jd_content: str = Field(..., description="Full Job Description in markdown format")
    skills: List[str] = Field(..., min_length=1, description="Core technical or functional competencies")
    assigned_model: str = Field(..., description="Primary LLM identifier (e.g. 'llama3.2', 'groq/llama-3.1-70b')")
    reports_to: Optional[str] = Field(default="CEO", description="Manager agent role, defaults to 'CEO'")
    peers: Optional[List[str]] = Field(default=None, description="Peer agent IDs for collaboration matrix")

    @field_validator("role", "full_title", "jd_content", "assigned_model")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


# ============================================================================
# Tool Handlers
# ============================================================================

def agent_delegate(
    project_id: str,
    from_agent: str,
    to_agents: List[str],
    task: str,
    expected_deliverable: str,
    context: str = "",
    deadline_minutes: Optional[int] = None,
    priority: str = "medium",
    agent_registry: Optional[AgentRegistry] = None,
    vault_manager: Optional[VaultManager] = None,
    thread_manager: Optional[ThreadManager] = None,
) -> Dict[str, Any]:
    """CEO delegates a task to one or more executive C-Suite agents.

    Steps:
    1. Verify authority: from_agent must be CEO.
    2. Format executive delegation brief.
    3. Ensure project thread exists in SQLite.
    4. Post DELEGATION message to project thread with broadcast.
    5. Return structured delegation confirmation.

    Args:
        project_id: Associated project identifier.
        from_agent: Requesting agent (must be CEO).
        to_agents: List of recipient agent roles.
        task: Operational task directive.
        expected_deliverable: Required output deliverable.
        context: Strategic background context.
        deadline_minutes: Optional completion deadline in minutes.
        priority: Workstream priority.
        agent_registry: Optional AgentRegistry.
        vault_manager: Optional VaultManager.
        thread_manager: Optional ThreadManager.

    Returns:
        Structured response dictionary.
    """
    clean_from = from_agent.strip().upper()
    if clean_from != "CEO":
        return {
            "success": False,
            "project_id": project_id,
            "from_agent": from_agent,
            "error": f"Authority Denied: Only CEO holds delegation authority. Agent '{from_agent}' cannot delegate.",
        }

    clean_to = [a.strip().upper() for a in to_agents if a.strip()]
    if not clean_to:
        return {
            "success": False,
            "project_id": project_id,
            "error": "to_agents list cannot be empty.",
        }

    try:
        vm = vault_manager or VaultManager()
        tm = thread_manager or ThreadManager(vault_manager=vm)
        delegation_id = f"del_{uuid.uuid4().hex[:8]}"

        # Format delegation brief
        deadline_str = f"{deadline_minutes} minutes" if deadline_minutes else "Standard milestone review"
        brief_body = (
            f"# Executive Task Delegation Brief\n"
            f"**From:** CEO\n"
            f"**To:** {', '.join(clean_to)}\n"
            f"**Priority:** {priority.upper()}\n"
            f"**Deadline:** {deadline_str}\n\n"
            f"## Task Objective\n{task}\n\n"
            f"## Expected Deliverable\n{expected_deliverable}\n\n"
            f"## Strategic Context\n{context or 'Align with Project Alpha standards.'}\n"
        )

        # Ensure project thread exists before posting message (FK compliance)
        thread_id = f"thread_{project_id}_main"
        try:
            tm.create_thread(
                project_id=project_id,
                thread_id=thread_id,
                topic=f"Executive Discussion: {project_id}",
                stakeholders=["CEO"] + clean_to,
                owner_agent="CEO",
            )
        except Exception as te:
            logger.debug("Thread creation notice (may already exist): %s", te)

        # Post DELEGATION message to project thread
        msg = tm.post_message(
            thread_id=thread_id,
            sender_agent="CEO",
            to_agents=clean_to,
            message_type="DELEGATION",
            subject=f"[DELEGATION] {task[:60]}",
            content=brief_body,
            project_id=project_id,
        )

        return {
            "success": True,
            "delegation_id": delegation_id,
            "message_id": msg.message_id,
            "project_id": project_id,
            "thread_id": thread_id,
            "from_agent": "CEO",
            "to_agents": clean_to,
            "task": task,
            "expected_deliverable": expected_deliverable,
            "priority": priority,
            "status": "dispatched",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Unexpected error in agent_delegate: %s", e, exc_info=True)
        return {
            "success": False,
            "project_id": project_id,
            "error": f"Internal error during agent_delegate: {str(e)}",
        }


def agent_status(
    agent_id: str,
    include_memory_summary: bool = False,
    agent_registry: Optional[AgentRegistry] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Query current status, telemetry, model allocation, and episodic memory of an agent.

    Args:
        agent_id: Target agent ID (e.g. 'CTO', 'CAO-Claude').
        include_memory_summary: If True, fetches recent episodic memories.
        agent_registry: Optional AgentRegistry instance.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    try:
        vm = vault_manager or VaultManager()
        clean_id = agent_id.strip()
        reg = agent_registry or (get_agent_registry(vault_manager=vm) if hasattr(vm, "sqlite") else None)
        agent_obj = reg.get(clean_id) if (reg and hasattr(reg, "get")) else None
        db_agent = vm.sqlite.get_agent(clean_id) if (hasattr(vm, "sqlite") and hasattr(vm.sqlite, "get_agent")) else None

        # Resolve agent telemetry
        role = getattr(agent_obj, "role", None) or (db_agent.get("agent_role") if db_agent else clean_id)
        name = getattr(agent_obj, "name", None) or role
        assigned_model = (
            getattr(agent_obj, "assigned_model", None)
            or (db_agent.get("agent_model") if db_agent else "llama3.2")
        )
        status = getattr(agent_obj, "status", None) or ("active" if (db_agent and db_agent.get("is_active")) else "active")
        tokens_used = getattr(agent_obj, "total_tokens_used", 0)
        cost_usd = getattr(agent_obj, "total_cost_usd", 0.0)

        response: Dict[str, Any] = {
            "success": True,
            "agent_id": clean_id,
            "name": name,
            "role": role,
            "status": status,
            "assigned_model": assigned_model,
            "telemetry": {
                "total_tokens_used": tokens_used,
                "total_cost_usd": cost_usd,
            },
        }

        if include_memory_summary:
            try:
                memories = vm.sqlite.query_memories(clean_id, limit=5) if hasattr(vm, "sqlite") else []
                response["memory_summary"] = {
                    "recent_count": len(memories),
                    "recent_memories": [
                        {
                            "memory_id": m.get("memory_id"),
                            "type": m.get("memory_type"),
                            "importance": m.get("importance"),
                            "snippet": (m.get("memory_content") or "")[:120],
                            "created_at": m.get("created_at"),
                        }
                        for m in memories
                    ],
                }
            except Exception as me:
                logger.debug("Could not query memory summary for %s: %s", clean_id, me)
                response["memory_summary"] = {"recent_count": 0, "recent_memories": []}

        return response
    except Exception as e:
        logger.error("Unexpected error in agent_status: %s", e, exc_info=True)
        return {
            "success": False,
            "agent_id": agent_id,
            "error": f"Internal error during agent_status: {str(e)}",
        }


def agent_hire(
    role: str,
    full_title: str,
    jd_content: str,
    skills: List[str],
    assigned_model: str,
    reports_to: Optional[str] = "CEO",
    peers: Optional[List[str]] = None,
    agent_registry: Optional[AgentRegistry] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """CHRO onboards and registers a new executive agent persona in Alpha.

    Steps:
    1. Save Job Description to Vault at `agents/{role}/JD.md`.
    2. Write agent profile to `agents/{role}/profile.json`.
    3. Upsert record into SQLite table `vault_agents`.
    4. Instantiate BaseExecutiveAgent and register in AgentRegistry.
    5. Update `agents/registry.json`.

    Args:
        role: Role abbreviation or identifier (e.g. 'CSO', 'VP-SALES').
        full_title: Full descriptive title.
        jd_content: Markdown text of the complete Job Description.
        skills: List of specialized capabilities.
        assigned_model: Default LLM identifier.
        reports_to: Manager agent role (defaults to 'CEO').
        peers: Collaborating peer roles.
        agent_registry: Optional AgentRegistry instance.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    try:
        vm = vault_manager or VaultManager()
        reg = agent_registry or get_agent_registry(vault_manager=vm)

        clean_role = role.strip().upper()
        clean_title = full_title.strip()

        vault_root = getattr(vm, "vault_root", getattr(vm, "vault_path", None))
        if vault_root:
            jd_dir = Path(vault_root) / "agents" / clean_role
            jd_dir.mkdir(parents=True, exist_ok=True)
            jd_path = jd_dir / "JD.md"
            with open(jd_path, "w", encoding="utf-8") as f:
                f.write(jd_content)
        else:
            jd_path = Path(f"agents/{clean_role}/JD.md")

        # 2. Persist AgentProfile model
        profile = AgentProfile(
            agent_id=clean_role,
            role=clean_role,
            full_title=clean_title,
            version="1.0.0",
            jd_file=f"agents/{clean_role}/JD.md",
            assigned_model=assigned_model,
            skills=skills,
            communication_style="executive",
            reports_to=reports_to or "CEO",
            peers=peers or [],
            status=AgentStatus.ACTIVE,
        )
        if hasattr(vm, "write"):
            vm.write(f"agents/{clean_role}/profile.json", profile.model_dump(mode="json"))

        # 3. Upsert into SQLite vault_agents table
        if hasattr(vm, "sqlite") and hasattr(vm.sqlite, "upsert_agent"):
            vm.sqlite.upsert_agent({
                "agent_id": clean_role,
                "agent_role": clean_title,
                "agent_model": assigned_model,
                "agent_version": "1.0.0",
                "is_active": True,
                "personality": f"Autonomous C-Suite Executive: {clean_title}",
                "jd_version": "1.0",
            })

        # 4. Instantiate and register in AgentRegistry if available
        try:
            reg = agent_registry or (get_agent_registry(vault_manager=vm) if hasattr(vm, "sqlite") else None)
            if reg and hasattr(reg, "register"):
                agent_instance = BaseExecutiveAgent(
                    agent_id=clean_role,
                    name=clean_title,
                    role=clean_role,
                    jd_path=jd_path,
                    vault_manager=vm if hasattr(vm, "sqlite") else None,
                    model_router=getattr(reg, "model_router", None),
                )
                reg.register(agent_instance, sync_vault=True)
        except Exception as reg_err:
            logger.debug("Registry onboarding notice: %s", reg_err)

        return {
            "success": True,
            "hired": True,
            "agent_id": clean_role,
            "role": clean_role,
            "full_title": clean_title,
            "assigned_model": assigned_model,
            "skills": skills,
            "reports_to": reports_to or "CEO",
            "status": "active",
            "message": f"Successfully hired and registered agent '{clean_role}' ({clean_title}).",
        }
    except Exception as e:
        logger.error("Unexpected error in agent_hire: %s", e, exc_info=True)
        return {
            "success": False,
            "role": role,
            "error": f"Internal error during agent_hire: {str(e)}",
        }
