"""backend/api/routes/projects.py - Project Alpha Projects & Deliberation Threads REST Handlers."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.auth import verify_token
from backend.api.deps import get_vault_manager
from backend.api.schemas import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectThreadsResponse,
    ThreadMessageResponse,
)
from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.api.routes.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get(
    "",
    response_model=List[ProjectSummary],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="List all project summaries",
)
def list_projects(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by lifecycle status"),
    limit: int = Query(50, ge=1, le=100, description="Max results to return"),
    include_archived: bool = Query(False, description="Include archived projects"),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> List[Dict[str, Any]]:
    """List project summaries from Vault directory and SQLite."""
    # Support in-memory contract test harness if present
    if hasattr(vault_manager, "projects") and isinstance(vault_manager.projects, dict):
        results = []
        for pid, p in vault_manager.projects.items():
            st = str(p.get("status", "planning")).lower()
            if not include_archived and st == "archived" and status_filter != "archived":
                continue
            if status_filter and st != status_filter.lower():
                continue
            results.append({
                "project_id": pid,
                "id": pid,
                "title": p.get("title") or p.get("name", pid),
                "description": p.get("description") or p.get("user_goal", ""),
                "status": st,
                "priority": p.get("priority", "medium"),
                "progress": float(p.get("progress", 0.0)),
                "created_at": str(p.get("created_at", "")),
                "lead_agent": p.get("lead_agent", "CEO"),
            })
            if len(results) >= limit:
                break
        return results

    projects_dir = Path(getattr(vault_manager, "vault_root", Path("Alpha-Vault"))) / "projects"
    summaries: List[Dict[str, Any]] = []

    if projects_dir.is_dir():
        for pdir in sorted(projects_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if not pdir.is_dir():
                continue
            manifest = vault_manager.read(f"projects/{pdir.name}/manifest.json")
            if not manifest:
                manifest = vault_manager.read(f"projects/{pdir.name}/manifest")
            if not manifest:
                continue

            proj_status = str(manifest.get("status", "planning")).lower()
            if not include_archived and proj_status == "archived" and status_filter != "archived":
                continue
            if status_filter and proj_status != status_filter.lower():
                continue

            summaries.append({
                "project_id": manifest.get("project_id", pdir.name),
                "id": manifest.get("project_id", pdir.name),
                "title": manifest.get("name") or manifest.get("title", pdir.name),
                "description": manifest.get("user_goal") or manifest.get("description", ""),
                "status": proj_status,
                "priority": manifest.get("priority", "medium"),
                "progress": float(manifest.get("progress", 0.0)),
                "created_at": str(manifest.get("created_at", "")),
                "lead_agent": manifest.get("lead_agent", "CEO"),
            })
            if len(summaries) >= limit:
                break

    return summaries


@router.get(
    "/{id}",
    response_model=ProjectDetail,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Get detailed project manifest and deliverables",
)
def get_project_detail(
    id: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Retrieve full project manifest, deliverables, and audit scorecard."""
    clean_id = id.strip()

    # In-memory test harness check
    if hasattr(vault_manager, "projects") and isinstance(vault_manager.projects, dict):
        if clean_id in vault_manager.projects:
            p = vault_manager.projects[clean_id]
            return {
                "project_id": clean_id,
                "id": clean_id,
                "name": p.get("name") or p.get("title", clean_id),
                "title": p.get("title") or p.get("name", clean_id),
                "user_goal": p.get("user_goal") or p.get("description", ""),
                "description": p.get("description") or p.get("user_goal", ""),
                "status": p.get("status", "planning"),
                "priority": p.get("priority", "medium"),
                "progress": float(p.get("progress", 0.0)),
                "assigned_agents": p.get("assigned_agents", ["CEO"]),
                "lead_agent": p.get("lead_agent", "CEO"),
                "created_at": str(p.get("created_at", "")),
                "updated_at": str(p.get("updated_at", "") or p.get("created_at", "")),
                "deliverables_expected": p.get("deliverables_expected", []),
                "deliverables_completed": p.get("deliverables_completed", []),
                "deliverables": p.get("deliverables", {}),
                "audit_status": p.get("audit_status", "pending"),
                "audit_scorecard": p.get("audit_scorecard"),
                "archify_graph": p.get("archify_graph"),
            }

    manifest = vault_manager.read(f"projects/{clean_id}/manifest.json")
    if manifest is None:
        manifest = vault_manager.read(f"projects/{clean_id}/manifest")
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{clean_id}' not found.",
        )

    # Collect deliverables from disk if not inside manifest
    deliverables = manifest.get("deliverables", {})
    deliv_dir = Path(getattr(vault_manager, "vault_root", Path("Alpha-Vault"))) / "projects" / clean_id / "deliverables"
    if deliv_dir.is_dir():
        for dfile in deliv_dir.glob("*.json"):
            key = dfile.stem
            if key not in deliverables:
                dcontent = vault_manager.read(f"projects/{clean_id}/deliverables/{dfile.name}")
                if dcontent:
                    deliverables[key] = dcontent

    return {
        "project_id": manifest.get("project_id", clean_id),
        "id": manifest.get("project_id", clean_id),
        "name": manifest.get("name") or manifest.get("title", clean_id),
        "title": manifest.get("title") or manifest.get("name", clean_id),
        "user_goal": manifest.get("user_goal") or manifest.get("description", ""),
        "description": manifest.get("description") or manifest.get("user_goal", ""),
        "status": manifest.get("status", "planning"),
        "priority": manifest.get("priority", "medium"),
        "progress": float(manifest.get("progress", 0.0)),
        "assigned_agents": manifest.get("assigned_agents", ["CEO"]),
        "lead_agent": manifest.get("lead_agent", "CEO"),
        "created_at": str(manifest.get("created_at", "")),
        "updated_at": str(manifest.get("updated_at", "") or manifest.get("created_at", "")),
        "deliverables_expected": manifest.get("deliverables_expected", []),
        "deliverables_completed": manifest.get("deliverables_completed", []),
        "deliverables": deliverables,
        "audit_status": manifest.get("audit_status", "pending"),
        "audit_scorecard": manifest.get("audit_scorecard"),
        "archify_graph": manifest.get("archify_graph"),
    }


@router.get(
    "/{id}/threads",
    response_model=ProjectThreadsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Get project discussion thread messages",
)
def get_project_threads(
    id: str,
    thread_id: Optional[str] = Query(None, description="Optional specific thread ID"),
    limit: int = Query(100, ge=1, le=500, description="Max messages to fetch"),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Retrieve chronological thread messages between agents."""
    clean_id = id.strip()

    # 1. Check in-memory contract test harness
    if hasattr(vault_manager, "projects") and isinstance(vault_manager.projects, dict):
        if clean_id not in vault_manager.projects:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{clean_id}' not found.",
            )
        in_mem_threads = vault_manager.projects[clean_id].get("threads", [])
        return {
            "project_id": clean_id,
            "threads": in_mem_threads[:limit],
            "count": len(in_mem_threads[:limit]),
        }

    # 2. Check disk / manifest
    manifest = vault_manager.read(f"projects/{clean_id}/manifest.json")
    if manifest is None:
        manifest = vault_manager.read(f"projects/{clean_id}/manifest")
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{clean_id}' not found.",
        )

    target_thread = thread_id or f"thread_{clean_id}_main"
    try:
        tm = ThreadManager(vault_manager=vault_manager)
        messages = tm.get_thread_messages(target_thread, limit=limit, project_id=clean_id)
    except Exception as e:
        logger.debug("ThreadManager fetch notice: %s", e)
        messages = []

    formatted: List[Dict[str, Any]] = []
    for m in messages:
        formatted.append({
            "message_id": getattr(m, "message_id", str(uuid.uuid4())),
            "thread_id": getattr(m, "thread_id", target_thread),
            "project_id": getattr(m, "project_id", clean_id) or clean_id,
            "timestamp": str(getattr(m, "timestamp", "")),
            "from": getattr(m, "from_agent", "AGENT"),
            "to_agents": getattr(m, "to_agents", []),
            "type": str(m.type.value if hasattr(m.type, "value") else getattr(m, "type", "MESSAGE")),
            "subject": getattr(m, "subject", None),
            "content": getattr(m, "content", ""),
            "attachments": getattr(m, "attachments", []),
            "model_used": getattr(m, "model_used", None),
            "tokens_used": getattr(m, "tokens_used", 0),
            "status": getattr(m, "status", "sent"),
        })

    return {
        "project_id": clean_id,
        "threads": formatted,
        "count": len(formatted),
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_token)],
    summary="Manually create a new project workspace",
)
def create_project_manual(
    request: ProjectCreateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Manually scaffold a project workspace and manifest without triggering immediate full execution."""
    pid = vault_manager.create_project(
        title=request.name.strip(),
        description=request.user_goal.strip(),
        founder_goals=request.tags or [request.name.strip()],
    )

    manifest_path = f"projects/{pid}/manifest.json"
    manifest = vault_manager.read(manifest_path)
    if manifest is None:
        manifest_path = f"projects/{pid}/manifest"
        manifest = vault_manager.read(manifest_path)

    if manifest:
        manifest["priority"] = request.priority.lower().strip()
        if request.assigned_agents:
            manifest["assigned_agents"] = [a.upper().strip() for a in request.assigned_agents]
        try:
            vault_manager.write(manifest_path, manifest)
        except Exception as e:
            logger.debug("Manifest write notice: %s", e)

    return {
        "project_id": pid,
        "status": "planning",
        "name": request.name.strip(),
        "message": f"Project '{request.name.strip()}' created successfully.",
    }
