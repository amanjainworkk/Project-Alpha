"""backend/api/routes/goals.py - Project Alpha Goal Intake & Tracking REST Handlers."""

from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.api.auth import verify_token
from backend.api.deps import (
    get_connection_manager,
    get_orchestrator,
    get_vault_manager,
)
from backend.api.schemas import (
    GoalStatusResponse,
    GoalSubmissionRequest,
    GoalSubmissionResponse,
)
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.api.routes.goals")
router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.post(
    "",
    response_model=GoalSubmissionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Submit a high-level goal for autonomous company execution",
)
def submit_goal(
    request: GoalSubmissionRequest,
    background_tasks: BackgroundTasks,
    vault_manager: VaultManager = Depends(get_vault_manager),
    orchestrator: Any = Depends(get_orchestrator),
    connection_manager: Any = Depends(get_connection_manager),
) -> Dict[str, Any]:
    """Submit a high-level directive. Scaffolds project, initiates background pipeline, and emits WebSocket telemetry."""
    clean_title = request.title.strip()
    clean_desc = request.description.strip() or clean_title

    # 1. Scaffold project in Vault
    project_id = vault_manager.create_project(
        title=clean_title,
        description=clean_desc,
        founder_goals=[clean_title],
    )

    # 2. Broadcast project_state_change via WebSocket
    if connection_manager is not None:
        if hasattr(connection_manager, "emit_project_state"):
            try:
                connection_manager.emit_project_state(
                    project_id=project_id,
                    new_state="planning",
                    title=clean_title,
                )
            except Exception as e:
                logger.debug("WebSocket emit_project_state notice: %s", e)
        elif hasattr(connection_manager, "broadcast"):
            try:
                connection_manager.broadcast(
                    "project_state_change",
                    {
                        "project_id": project_id,
                        "old_state": None,
                        "new_state": "planning",
                        "status": "planning",
                        "title": clean_title,
                    },
                )
            except Exception as e:
                logger.debug("WebSocket broadcast notice: %s", e)

    # 3. Queue asynchronous autonomous execution if orchestrator available
    if orchestrator is not None and hasattr(orchestrator, "run_goal"):
        full_directive = f"{clean_title}: {clean_desc}" if clean_desc != clean_title else clean_title
        background_tasks.add_task(
            orchestrator.run_goal,
            goal=full_directive,
            project_id=project_id,
        )

    return {
        "project_id": project_id,
        "status": "planning",
        "title": clean_title,
        "executive_summary": "Autonomous execution pipeline scheduled.",
    }


@router.get(
    "/{id}",
    response_model=GoalStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Query real-time execution status and deliverables for a goal",
)
def get_goal_status(
    id: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
    orchestrator: Any = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Query live execution status, deliverables, and audit result for a project ID."""
    clean_id = id.strip()

    # 1. Check in-memory orchestrator active projects
    if orchestrator and hasattr(orchestrator, "_active_projects") and clean_id in orchestrator._active_projects:
        res = orchestrator._active_projects[clean_id]
        return {
            "project_id": clean_id,
            "status": str(res.status.value if hasattr(res.status, "value") else res.status),
            "goal": res.goal,
            "executive_summary": res.executive_summary,
            "deliverables": res.deliverables,
            "audit_result": res.audit_result.model_dump() if (res.audit_result and hasattr(res.audit_result, "model_dump")) else (res.audit_result.__dict__ if res.audit_result else None),
            "founder_escalation": res.founder_escalation,
            "archify_diagram_html": res.archify_diagram_html,
            "elapsed_seconds": res.elapsed_seconds,
            "passed_audit": res.passed_audit,
            "timestamp": res.timestamp,
        }

    # 2. Check in-memory projects dict on vault_manager (e.g. ContractVaultManager fixture)
    if hasattr(vault_manager, "projects") and isinstance(vault_manager.projects, dict):
        if clean_id in vault_manager.projects:
            proj = vault_manager.projects[clean_id]
            return {
                "project_id": clean_id,
                "status": str(proj.get("status", "planning")),
                "goal": str(proj.get("description") or proj.get("title") or proj.get("user_goal", "")),
                "executive_summary": proj.get("executive_summary", ""),
                "deliverables": proj.get("deliverables", {}),
                "audit_result": proj.get("audit_scorecard"),
                "founder_escalation": proj.get("founder_escalation"),
                "archify_diagram_html": proj.get("archify_diagram_html"),
                "elapsed_seconds": 0.0,
                "passed_audit": proj.get("audit_status") == "complete",
                "timestamp": str(proj.get("created_at", "")),
            }

    # 3. Fallback to Vault manifest document
    manifest_data = vault_manager.read(f"projects/{clean_id}/manifest.json")
    if manifest_data is None:
        manifest_data = vault_manager.read(f"projects/{clean_id}/manifest")
    if manifest_data is not None:
        return {
            "project_id": clean_id,
            "status": str(manifest_data.get("status", "planning")),
            "goal": str(manifest_data.get("user_goal", "") or manifest_data.get("description", "")),
            "executive_summary": manifest_data.get("executive_summary", ""),
            "deliverables": manifest_data.get("deliverables", {}),
            "audit_result": manifest_data.get("audit_scorecard"),
            "founder_escalation": manifest_data.get("founder_escalation"),
            "archify_diagram_html": manifest_data.get("archify_diagram_html"),
            "elapsed_seconds": 0.0,
            "passed_audit": manifest_data.get("audit_status") == "complete",
            "timestamp": str(manifest_data.get("updated_at", "") or manifest_data.get("created_at", "")),
        }

    # 4. Not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Goal project '{clean_id}' not found.",
    )
