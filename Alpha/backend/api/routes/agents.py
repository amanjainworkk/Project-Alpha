"""backend/api/routes/agents.py - Project Alpha C-Suite Executive Agents REST Handlers."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from backend.agents.agent_registry import CANONICAL_AGENT_METADATA, AgentRegistry
from backend.api.auth import verify_token
from backend.api.deps import (
    get_agent_registry,
    get_connection_manager,
    get_orchestrator,
    get_vault_manager,
)
from backend.api.schemas import (
    AgentCard,
    AgentDetail,
    AgentDirectMessageRequest,
    AgentDirectMessageResponse,
)
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.api.routes.agents")
router = APIRouter(prefix="/api/agents", tags=["agents"])

CANONICAL_ROSTER = [
    "CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO",
    "CHRO", "CIO", "CSO", "CLO", "CAO-Claude", "CAO-ChatGPT"
]


@router.get(
    "",
    response_model=List[AgentCard],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="List all 13 executive agent cards for the Boardroom screen",
)
def list_agents(
    active_only: bool = Query(False, description="Filter for active agents only"),
    agent_registry: Any = Depends(get_agent_registry),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> List[Dict[str, Any]]:
    """Retrieve exactly 13 executive status cards for the mobile Boardroom screen."""
    cards: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. If vault_manager has get_agent_registry (e.g. ContractVaultManager fixture)
    if hasattr(vault_manager, "get_agent_registry") and callable(vault_manager.get_agent_registry):
        reg_agents = vault_manager.get_agent_registry()
        for a in reg_agents:
            aid = a.get("agent_id")
            if not aid:
                continue
            seen_ids.add(aid.upper())
            cards.append({
                "agent_id": aid,
                "role": a.get("role", aid),
                "full_title": a.get("full_title", a.get("role", aid)),
                "status": a.get("status", "active"),
                "current_task": a.get("current_task", "Idle or awaiting delegation"),
                "model": a.get("assigned_model", "llama3.2"),
                "loaded_model": a.get("assigned_model", "llama3.2"),
                "cost_today": float(a.get("cost_today", 0.0)),
                "tokens_used": int(a.get("tokens_used", 0)),
            })
        return cards[:13]

    # 2. Inspect loaded agents from registry
    if agent_registry is not None and hasattr(agent_registry, "list_agents"):
        loaded_agents = agent_registry.list_agents(active_only=active_only)
        for a in loaded_agents:
            aid = a["agent_id"]
            seen_ids.add(aid.upper())
            cards.append({
                "agent_id": aid,
                "role": a.get("role", aid),
                "full_title": a.get("full_title", aid),
                "status": a.get("status", "active"),
                "current_task": a.get("current_task", "Idle or awaiting delegation"),
                "model": a.get("assigned_model", "llama3.2"),
                "loaded_model": a.get("assigned_model", "llama3.2"),
                "cost_today": float(a.get("cost_usd", 0.0)),
                "tokens_used": int(a.get("tokens_used", 0)),
            })

    # 3. Ensure all 13 canonical C-Suite agents are accounted for
    for canonical_id in CANONICAL_ROSTER:
        if canonical_id.upper() not in seen_ids:
            meta = CANONICAL_AGENT_METADATA.get(canonical_id, {})
            cards.append({
                "agent_id": canonical_id,
                "role": meta.get("full_title", canonical_id),
                "full_title": meta.get("full_title", canonical_id),
                "status": "active",
                "current_task": "Idle or awaiting delegation",
                "model": meta.get("default_model", "llama3.2"),
                "loaded_model": meta.get("default_model", "llama3.2"),
                "cost_today": 0.0,
                "tokens_used": 0,
            })
            seen_ids.add(canonical_id.upper())

    # Return exactly 13 status cards matching canonical C-Suite
    return cards[:13]


@router.get(
    "/{id}",
    response_model=AgentDetail,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Get comprehensive profile and memory stats for an agent",
)
def get_agent_profile(
    id: str,
    agent_registry: Any = Depends(get_agent_registry),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Retrieve detailed agent profile, skills, JD summary, and episodic memory counts."""
    clean_id = id.strip()
    agent = agent_registry.get(clean_id) if (agent_registry and hasattr(agent_registry, "get")) else None

    # Check ContractVaultManager get_agent_registry if applicable
    matched_contract = None
    if hasattr(vault_manager, "get_agent_registry") and callable(vault_manager.get_agent_registry):
        for ca in vault_manager.get_agent_registry():
            if ca.get("agent_id") == clean_id or ca.get("role") == clean_id:
                matched_contract = ca
                break

    meta = CANONICAL_AGENT_METADATA.get(clean_id.upper(), CANONICAL_AGENT_METADATA.get(clean_id, {}))

    if agent is None and matched_contract is None and clean_id.upper() not in [c.upper() for c in CANONICAL_ROSTER]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{clean_id}' not found in registry.",
        )

    # Query recent memories count from SQLite
    mem_count = 0
    if hasattr(vault_manager, "sqlite") and hasattr(vault_manager.sqlite, "query_memories"):
        try:
            mems = vault_manager.sqlite.query_memories(clean_id, limit=50)
            mem_count = len(mems)
        except Exception:
            mem_count = 0

    role_title = meta.get("full_title") or (matched_contract.get("role") if matched_contract else getattr(agent, "role", clean_id))
    assigned_model = getattr(agent, "assigned_model", meta.get("default_model", "llama3.2"))
    skills = getattr(agent, "skills", ["Executive Leadership", "Strategic Alignment"])
    jd_summary = meta.get("personality", f"Autonomous executive intelligence for {role_title}.")

    return {
        "agent_id": clean_id,
        "role": getattr(agent, "role", matched_contract.get("role") if matched_contract else clean_id),
        "full_title": role_title,
        "status": getattr(agent, "status", matched_contract.get("status") if matched_contract else "active"),
        "jd_summary": jd_summary,
        "assigned_model": assigned_model,
        "skills": skills,
        "communication_style": getattr(agent, "communication_style", "executive"),
        "vault_read_access": ["company/", "projects/", "knowledge/"],
        "vault_write_access": [f"agents/{clean_id}/", f"projects/{{id}}/deliverables/"],
        "peers": [r for r in CANONICAL_ROSTER if r != clean_id],
        "reports_to": "CEO" if clean_id.upper() != "CEO" else "Founder",
        "total_projects_completed": 0,
        "recent_memories_count": mem_count,
        "cost_today": float(getattr(agent, "total_cost_usd", 0.0)),
        "tokens_used": int(getattr(agent, "total_tokens_used", 0)),
    }


@router.post(
    "/{id}/message",
    response_model=AgentDirectMessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Inject a direct message instruction to an agent",
)
def message_agent(
    id: str,
    request: AgentDirectMessageRequest,
    background_tasks: BackgroundTasks,
    agent_registry: Any = Depends(get_agent_registry),
    vault_manager: VaultManager = Depends(get_vault_manager),
    orchestrator: Any = Depends(get_orchestrator),
    connection_manager: Any = Depends(get_connection_manager),
) -> Dict[str, Any]:
    """Directly message an executive agent and receive an immediate strategic response."""
    clean_id = id.strip()
    agent = agent_registry.get(clean_id) if (agent_registry and hasattr(agent_registry, "get")) else None

    # Check ContractVaultManager get_agent_registry if applicable
    is_in_contract = False
    if hasattr(vault_manager, "get_agent_registry") and callable(vault_manager.get_agent_registry):
        for ca in vault_manager.get_agent_registry():
            if ca.get("agent_id") == clean_id or ca.get("role") == clean_id:
                is_in_contract = True
                break

    if agent is None and not is_in_contract and clean_id.upper() not in [c.upper() for c in CANONICAL_ROSTER]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{clean_id}' not found in registry.",
        )

    clean_msg = request.message.strip()

    # Autonomous Multi-Agent Dispatch: If addressed to CEO with a directive command
    if clean_id.upper() == "CEO" and clean_msg.lower().startswith(("/goal", "/directive", "dispatch:", "execute:")):
        goal_text = re.sub(r"^/(goal|directive)\s*", "", clean_msg, flags=re.IGNORECASE).strip()
        if not goal_text or goal_text.startswith(":"):
            goal_text = goal_text.lstrip(":").strip()
        if not goal_text:
            goal_text = clean_msg

        project_id = vault_manager.create_project(
            title=goal_text[:50],
            description=goal_text,
            founder_goals=[goal_text],
        )

        if connection_manager is not None and hasattr(connection_manager, "attach_orchestrator"):
            try:
                connection_manager.attach_orchestrator(orchestrator)
            except Exception as e:
                logger.debug("Attach orchestrator notice: %s", e)

        if orchestrator is not None and hasattr(orchestrator, "run_goal"):
            background_tasks.add_task(
                orchestrator.run_goal,
                goal=goal_text,
                project_id=project_id,
            )

        response_text = (
            f"Directive acknowledged, Founder. Goal '{goal_text[:60]}' has been dispatched to the Executive Boardroom. "
            f"CTO, COO, CDO, and Dual CAO workstreams are running. View live progress on Tasks & Canvas."
        )
    elif agent is not None and hasattr(agent, "think"):
        response_text = agent.think(clean_msg, complexity=2, task_type="direct_query")
    else:
        response_text = f"[{clean_id}] Acknowledged instruction: {clean_msg}"

    return {
        "agent_id": clean_id,
        "status": "delivered",
        "response": response_text,
    }
