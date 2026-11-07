"""backend/mcp/tools/user_tools.py - Alpha MCP User Tool Handlers.

Implements MCP tools for Founder interaction and decision escalation:
- user_profile_read: Read Founder (Aman Jain) profile, communication preferences, and working style.
- user_escalate: Escalate critical decisions, CAO audit deadlocks, or budget/legal issues to the Founder.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.mcp.tools.user")


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class UserProfileReadInput(BaseModel):
    """Input schema for user_profile_read MCP tool."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(..., description="Requesting agent ID")

    @field_validator("agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("agent_id cannot be empty or whitespace.")
        return s


class UserEscalateInput(BaseModel):
    """Input schema for user_escalate MCP tool."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Associated project ID")
    from_agent: str = Field(..., description="Calling agent initiating the escalation (e.g. 'CEO', 'CLO', 'CFO')")
    question: str = Field(..., description="Direct decision question for Founder Aman Jain")
    context: str = Field(..., description="Background rationale, trade-offs, and critical constraints")
    urgency: str = Field(
        ...,
        description="Escalation urgency level: 'low', 'medium', or 'high'",
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="Suggested concrete decision options for Founder to select from",
    )

    @field_validator("project_id", "from_agent", "question", "context")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Urgency must be one of {sorted(list(allowed))}")
        return s


# ============================================================================
# Tool Handlers
# ============================================================================

def user_profile_read(
    agent_id: str,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Read current user (Founder Aman Jain) profile, preferences, and focus areas from Vault.

    Args:
        agent_id: Calling agent identifier.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary matching UserProfile canonical schema.
    """
    try:
        vm = vault_manager or VaultManager()
        clean_agent = agent_id.strip()

        profile_data = vm.get_user_profile() if hasattr(vm, "get_user_profile") else None

        if isinstance(profile_data, dict):
            res = dict(profile_data)
            res["success"] = True
            return res

        return {
            "name": "Aman Jain",
            "role": "Founder & Chairman",
            "preferred_communication": "concise",
            "escalation_policy": "critical_only",
            "success": True,
        }
    except Exception as e:
        logger.error("Unexpected error in user_profile_read: %s", e, exc_info=True)
        return {
            "name": "Aman Jain",
            "role": "Founder & Chairman",
            "preferred_communication": "concise",
            "escalation_policy": "critical_only",
            "success": False,
            "error": f"Internal error during user_profile_read: {str(e)}",
        }


def user_escalate(
    project_id: str,
    from_agent: str,
    question: str,
    context: str,
    urgency: str,
    options: Optional[List[str]] = None,
    thread_manager: Optional[ThreadManager] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Escalate a critical decision or deadlock to human Founder (Aman Jain) via CEO interface.

    Used when:
    1. Dual CAO audit reaches maximum 2-round escalation cap.
    2. Critical legal blocker or GPL license conflict detected by CLO.
    3. Severe budget overrun or unauthorized token cost detected by CFO.
    4. Strategic pivot requiring Founder authorization.

    Actions:
    1. Generate unique escalation ID.
    2. Format high-signal escalation message.
    3. Post USER_ESCALATION message to project thread.
    4. Persist escalation record in Vault under projects/{project_id}/escalations/.

    Args:
        project_id: Associated project ID.
        from_agent: Originating agent ID.
        question: Explicit binary or multi-choice question.
        context: Contextual background and risk summary.
        urgency: 'low', 'medium', or 'high'.
        options: Optional list of proposed choices.
        thread_manager: Optional ThreadManager instance.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    clean_urgency = urgency.lower().strip()
    if clean_urgency not in ("low", "medium", "high"):
        raise ValueError(f"Invalid urgency value: {urgency}. Must be one of: low, medium, high")

    try:
        vm = vault_manager or VaultManager()
        tm = thread_manager or ThreadManager(vault_manager=vm)

        clean_pid = project_id.strip()
        clean_from = from_agent.strip()
        escalation_id = f"esc_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Format escalation body for thread
        escalation_content = (
            f"# FOUNDER ESCALATION [{clean_urgency.upper()}]\n"
            f"**From Agent:** {clean_from}\n"
            f"**Project:** {clean_pid}\n"
            f"**Timestamp:** {now_iso}\n\n"
            f"## Question for Founder\n{question}\n\n"
            f"## Strategic Context\n{context}\n"
        )
        if options:
            escalation_content += "\n## Suggested Decision Options\n"
            for idx, opt in enumerate(options, 1):
                escalation_content += f"{idx}. {opt}\n"

        # Ensure project thread exists
        thread_id = f"thread_{clean_pid}_main"
        try:
            tm.create_thread(
                project_id=clean_pid,
                thread_id=thread_id,
                topic=f"Executive Discussion: {clean_pid}",
                stakeholders=["CEO", "USER", clean_from],
                owner_agent=clean_from,
            )
        except Exception as te:
            logger.debug("Thread notice: %s", te)

        # Post message to thread
        msg = tm.post_message(
            thread_id=thread_id,
            sender_agent=clean_from,
            to_agents=["USER", "CEO"],
            message_type="USER_ESCALATION",
            subject=f"[USER_ESCALATION] ({clean_urgency.upper()}) {question[:60]}",
            content=escalation_content,
            project_id=clean_pid,
        )

        # Persist escalation artifact in Vault
        esc_record = {
            "escalation_id": escalation_id,
            "project_id": clean_pid,
            "from_agent": clean_from,
            "urgency": clean_urgency,
            "question": question,
            "context": context,
            "options": options or [],
            "status": "pending_founder_response",
            "message_id": msg.message_id,
            "created_at": now_iso,
        }
        try:
            esc_path = f"projects/{clean_pid}/escalations/{escalation_id}.json"
            vm.write(esc_path, esc_record, agent_id=clean_from)
        except Exception as ve:
            logger.warning("Could not persist escalation artifact to Vault: %s", ve)

        return {
            "success": True,
            "escalated": True,
            "escalation_id": escalation_id,
            "message_id": msg.message_id,
            "project_id": clean_pid,
            "from_agent": clean_from,
            "urgency": clean_urgency,
            "question": question,
            "options": options or [],
            "status": "pending_founder_response",
            "timestamp": now_iso,
            "message": f"Successfully escalated to Founder Aman Jain with urgency '{clean_urgency}'.",
        }
    except Exception as e:
        logger.error("Unexpected error in user_escalate: %s", e, exc_info=True)
        return {
            "success": False,
            "escalated": False,
            "project_id": project_id,
            "error": f"Internal error during user_escalate: {str(e)}",
        }
