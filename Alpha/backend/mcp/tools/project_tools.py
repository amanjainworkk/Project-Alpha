"""backend/mcp/tools/project_tools.py - Alpha MCP Project Tool Handlers.

Implements MCP tools for project lifecycle governance:
- project_create: Scaffold a new project workspace, manifest, goal document, and SQLite thread.
- project_update_status: Transition project lifecycle status with audit notes.
- project_list: Enumerate and filter projects across Vault and SQLite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.vault.schemas import ProjectManifest, ProjectPriority, ProjectStatus
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.mcp.tools.projects")


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class ProjectCreateInput(BaseModel):
    """Input schema for project_create MCP tool."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Human-readable project name")
    user_goal: str = Field(..., description="Verbatim founder directive or goal statement")
    priority: str = Field(
        default="medium",
        description="Scheduling priority: 'low', 'medium', 'high', or 'critical'",
    )
    assigned_agents: Optional[List[str]] = Field(
        default=None,
        description="Assigned executive agents (defaults to ['CEO'])",
    )
    deadline: Optional[str] = Field(default=None, description="Optional target completion ISO datetime")
    tags: Optional[List[str]] = Field(default=None, description="Domain tags or strategic classification keywords")

    @field_validator("name", "user_goal")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Priority must be one of {sorted(list(allowed))}")
        return s


class ProjectUpdateStatusInput(BaseModel):
    """Input schema for project_update_status MCP tool."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Unique project ID (e.g. 'proj-20261107-abc123')")
    status: str = Field(
        ...,
        description="Target status: 'planning', 'in_progress', 'in_audit', 'awaiting_approval', 'complete', or 'archived'",
    )
    agent_id: str = Field(..., description="Calling agent updating the status")
    note: str = Field(default="", description="Optional transition note or rationale")

    @field_validator("project_id", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"planning", "in_progress", "in_audit", "awaiting_approval", "complete", "archived"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Status must be one of {sorted(list(allowed))}")
        return s


class ProjectListInput(BaseModel):
    """Input schema for project_list MCP tool."""
    model_config = ConfigDict(extra="ignore")

    status: Optional[str] = Field(default=None, description="Filter projects by lifecycle status")
    agent_id: Optional[str] = Field(default=None, description="Filter projects by assigned executive agent")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of projects to return (1-100)")
    include_archived: bool = Field(default=False, description="Whether to include projects in 'archived' status")


# ============================================================================
# Tool Handlers
# ============================================================================

def project_create(
    name: str,
    user_goal: str,
    priority: str = "medium",
    assigned_agents: Optional[List[str]] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Create and scaffold a new project workspace in Alpha's Vault.

    Scaffolds:
    1. Subdirectories: projects/{project_id}/{threads, deliverables, audit}
    2. Manifest: projects/{project_id}/manifest.json
    3. Goal documentation: projects/{project_id}/goal.md
    4. SQLite thread: thread_{project_id}_main in vault_project_threads
    5. Semantic Chroma indexing

    Args:
        name: Project title.
        user_goal: Directive given by Founder.
        priority: 'low', 'medium', 'high', or 'critical'.
        assigned_agents: List of agent IDs assigned (defaults to ['CEO']).
        deadline: Optional ISO deadline.
        tags: Optional list of tags.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary with created project_id and thread_id.
    """
    try:
        vm = vault_manager or VaultManager()
        clean_name = name.strip()
        clean_goal = user_goal.strip()
        clean_tags = [t.strip() for t in tags if t.strip()] if tags else []
        clean_agents = [a.strip().upper() for a in assigned_agents if a.strip()] if assigned_agents else ["CEO"]

        # Call VaultManager scaffolding method
        proj_id = vm.create_project(
            title=clean_name,
            description=clean_goal,
            founder_goals=clean_tags,
        )

        # Update manifest with custom priority, agents, and deadline
        manifest_path = f"projects/{proj_id}/manifest.json"
        manifest_data = vm.read(manifest_path)
        if manifest_data:
            manifest_data["priority"] = priority.lower().strip()
            manifest_data["assigned_agents"] = clean_agents
            if deadline:
                manifest_data["deadline"] = deadline
            vm.write(manifest_path, manifest_data)

        return {
            "success": True,
            "project_id": proj_id,
            "name": clean_name,
            "user_goal": clean_goal,
            "priority": priority,
            "status": "planning",
            "assigned_agents": clean_agents,
            "thread_id": f"thread_{proj_id}_main",
            "message": f"Project '{clean_name}' successfully created with ID '{proj_id}'.",
        }
    except Exception as e:
        logger.error("Unexpected error in project_create: %s", e, exc_info=True)
        return {
            "success": False,
            "name": name,
            "error": f"Internal error during project_create: {str(e)}",
        }


def project_update_status(
    project_id: str,
    status: str,
    agent_id: str,
    note: str = "",
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Update the status of an existing project and record audit history.

    Args:
        project_id: Target project identifier.
        status: Target lifecycle status ('planning', 'in_progress', 'in_audit', 'awaiting_approval', 'complete', 'archived').
        agent_id: Requesting agent ID.
        note: Transition rationale or audit note.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    clean_status = status.lower().strip()
    allowed_statuses = {"planning", "in_progress", "in_audit", "awaiting_approval", "complete", "archived"}
    if clean_status not in allowed_statuses:
        raise ValueError(f"Invalid project status: {status}")

    try:
        vm = vault_manager or VaultManager()
        clean_pid = project_id.strip()

        manifest_path = f"projects/{clean_pid}/manifest.json"
        manifest = vm.read(manifest_path)
        if manifest is None:
            return {
                "success": False,
                "updated": False,
                "project_id": clean_pid,
                "error": f"Project manifest not found at '{manifest_path}'.",
            }

        previous_status = manifest.get("status", "unknown")
        manifest["status"] = clean_status
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

        if note:
            if "status_history" not in manifest or not isinstance(manifest["status_history"], list):
                manifest["status_history"] = []
            manifest["status_history"].append({
                "from_status": previous_status,
                "to_status": clean_status,
                "agent_id": agent_id,
                "note": note,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        vm.write(manifest_path, manifest, agent_id=agent_id)

        # Sync thread status in SQLite if thread exists
        thread_id = f"thread_{clean_pid}_main"
        if hasattr(vm, "sqlite"):
            try:
                vm.sqlite.upsert_thread({
                    "thread_id": thread_id,
                    "project_id": clean_pid,
                    "project_name": manifest.get("name", clean_pid),
                    "thread_status": "completed" if clean_status in ("complete", "archived") else "active",
                })
            except Exception as te:
                logger.debug("SQLite thread status update notice: %s", te)

        return {
            "success": True,
            "updated": True,
            "project_id": clean_pid,
            "previous_status": previous_status,
            "status": clean_status,
            "current_status": clean_status,
            "agent_id": agent_id,
            "note": note,
            "message": f"Project '{clean_pid}' status updated to '{clean_status}'.",
        }
    except Exception as e:
        logger.error("Unexpected error in project_update_status: %s", e, exc_info=True)
        return {
            "success": False,
            "updated": False,
            "project_id": project_id,
            "error": f"Internal error during project_update_status: {str(e)}",
        }


def project_list(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 20,
    include_archived: bool = False,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """List projects from Vault and SQLite with flexible filtering.

    Args:
        status: Optional lifecycle status filter.
        agent_id: Optional assigned agent filter.
        limit: Maximum results (1-100).
        include_archived: If False, omits projects in 'archived' status.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary containing list of projects.
    """
    try:
        vm = vault_manager or VaultManager()
        safe_limit = max(1, min(100, int(limit)))
        filter_status = status.lower().strip() if status else None
        filter_agent = agent_id.upper().strip() if agent_id else None

        projects: List[Dict[str, Any]] = []
        vroot = getattr(vm, "vault_root", getattr(vm, "vault_path", None))
        projects_dir = Path(vroot) / "projects" if vroot else None

        if projects_dir and projects_dir.is_dir():
            for pdir in sorted(projects_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                if not pdir.is_dir():
                    continue
                manifest_file = pdir / "manifest.json"
                if not manifest_file.is_file():
                    continue

                manifest_data = vm.read(f"projects/{pdir.name}/manifest.json")
                if not manifest_data:
                    continue

                proj_status = str(manifest_data.get("status", "planning")).lower()

                # Archive filter
                if not include_archived and proj_status == "archived" and filter_status != "archived":
                    continue

                # Status filter
                if filter_status and proj_status != filter_status:
                    continue

                # Agent assignment filter
                if filter_agent:
                    assigned = [str(a).upper() for a in manifest_data.get("assigned_agents", [])]
                    lead = str(manifest_data.get("lead_agent", "")).upper()
                    if filter_agent not in assigned and filter_agent != lead:
                        continue

                projects.append({
                    "project_id": manifest_data.get("project_id", pdir.name),
                    "name": manifest_data.get("name", pdir.name),
                    "status": proj_status,
                    "priority": manifest_data.get("priority", "medium"),
                    "user_goal": manifest_data.get("user_goal", ""),
                    "lead_agent": manifest_data.get("lead_agent", "CEO"),
                    "assigned_agents": manifest_data.get("assigned_agents", []),
                    "created_at": manifest_data.get("created_at"),
                    "updated_at": manifest_data.get("updated_at"),
                })

                if len(projects) >= safe_limit:
                    break

        if not projects and hasattr(vm, "projects") and isinstance(vm.projects, dict):
            for pid, pdata in vm.projects.items():
                proj_status = str(pdata.get("status", "planning")).lower()
                if not include_archived and proj_status == "archived" and filter_status != "archived":
                    continue
                if filter_status and proj_status != filter_status:
                    continue
                projects.append({
                    "project_id": pid,
                    "name": pdata.get("title") or pdata.get("name", pid),
                    "status": proj_status,
                    "priority": pdata.get("priority", "medium"),
                    "user_goal": pdata.get("description") or pdata.get("user_goal", ""),
                    "lead_agent": pdata.get("lead_agent", "CEO"),
                    "assigned_agents": pdata.get("assigned_agents", ["CEO"]),
                    "created_at": pdata.get("created_at"),
                    "updated_at": pdata.get("updated_at"),
                })
                if len(projects) >= safe_limit:
                    break

        return {
            "success": True,
            "count": len(projects),
            "limit": safe_limit,
            "projects": projects,
        }
    except Exception as e:
        logger.error("Unexpected error in project_list: %s", e, exc_info=True)
        return {
            "success": False,
            "count": 0,
            "projects": [],
            "error": f"Internal error during project_list: {str(e)}",
        }
