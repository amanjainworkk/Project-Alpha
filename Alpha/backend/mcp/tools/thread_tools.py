"""backend/mcp/tools/thread_tools.py - Alpha MCP Thread Tool Handlers.

Implements MCP tools for inter-agent communication and deliberation:
- thread_post: Post structured messages to project discussion threads.
- thread_read: Read chronological thread history with sender, message type, and temporal filters.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.schemas import ThreadMessageType
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.mcp.tools.threads")

ALLOWED_THREAD_MESSAGE_TYPES = {
    "DELEGATION",
    "DELIVERABLE",
    "QUESTION",
    "RESPONSE",
    "REVIEW_REQUEST",
    "SYNTHESIS",
    "AUDIT_REQUEST",
    "AUDIT_REPORT",
    "USER_ESCALATION",
    "INPUT",
    "OUTPUT",
}


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class ThreadPostInput(BaseModel):
    """Input schema for thread_post MCP tool."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Project identifier (e.g. 'proj-20261107-abc123')")
    from_agent: str = Field(..., description="Sender agent ID (e.g. 'CTO')")
    to_agents: List[str] = Field(..., min_length=1, description="Recipient agent IDs, e.g. ['CEO', 'CMO'] or ['*']")
    type: str = Field(
        ...,
        description="Message classification: DELEGATION, DELIVERABLE, QUESTION, RESPONSE, REVIEW_REQUEST, SYNTHESIS, AUDIT_REQUEST, AUDIT_REPORT, USER_ESCALATION",
    )
    content: str = Field(..., description="Message payload or deliverable content")
    subject: str = Field(default="", description="Optional message header / subject")
    in_reply_to: Optional[str] = Field(default=None, description="Optional parent message ID for thread nesting")

    @field_validator("project_id", "from_agent", "content")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        s = v.strip().upper()
        if s not in ALLOWED_THREAD_MESSAGE_TYPES:
            raise ValueError(f"Message type '{v}' is invalid. Allowed: {sorted(list(ALLOWED_THREAD_MESSAGE_TYPES))}")
        return s


class ThreadReadInput(BaseModel):
    """Input schema for thread_read MCP tool."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Project identifier")
    agent_id: str = Field(..., description="Requesting agent ID")
    filter_type: Optional[str] = Field(default=None, description="Optional message type filter (e.g. 'DELIVERABLE')")
    filter_from_agent: Optional[str] = Field(default=None, description="Optional sender filter (e.g. 'CTO')")
    since: Optional[str] = Field(default=None, description="Optional ISO timestamp to filter messages created after this time")

    @field_validator("project_id", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


# ============================================================================
# Tool Handlers
# ============================================================================

def thread_post(
    project_id: str,
    from_agent: str,
    to_agents: List[str],
    type: str,
    content: str,
    subject: str = "",
    in_reply_to: Optional[str] = None,
    thread_manager: Optional[ThreadManager] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Post an inter-agent message to a project discussion thread.

    Dual-persists to SQLite `vault_thread_messages` and `projects/{project_id}/threads/{thread_id}.jsonl`.

    Args:
        project_id: Project identifier.
        from_agent: Sender agent ID.
        to_agents: List of recipient agent IDs.
        type: Message classification.
        content: Message body.
        subject: Optional message subject.
        in_reply_to: Optional parent message ID.
        thread_manager: Optional ThreadManager instance.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    try:
        vm = vault_manager or VaultManager()
        tm = thread_manager or ThreadManager(vault_manager=vm)

        clean_pid = project_id.strip()
        clean_from = from_agent.strip()
        clean_to = [a.strip() for a in to_agents if a.strip()]
        clean_type = type.strip().upper()

        thread_id = f"thread_{clean_pid}_main"

        # FK Precondition: Ensure project thread exists in SQLite before posting
        try:
            tm.create_thread(
                project_id=clean_pid,
                thread_id=thread_id,
                topic=f"Executive Discussion: {clean_pid}",
                stakeholders=["CEO", clean_from] + clean_to,
                owner_agent=clean_from,
            )
        except Exception as te:
            logger.debug("Thread creation notice (may already exist): %s", te)

        msg = tm.post_message(
            thread_id=thread_id,
            sender_agent=clean_from,
            content=content,
            to_agents=clean_to,
            message_type=clean_type,
            subject=subject or f"[{clean_type}] from {clean_from}",
            in_reply_to=in_reply_to,
            project_id=clean_pid,
        )

        return {
            "success": True,
            "posted": True,
            "status": "sent",
            "message_id": msg.message_id,
            "thread_id": thread_id,
            "project_id": clean_pid,
            "from_agent": clean_from,
            "to_agents": clean_to,
            "type": clean_type,
            "subject": msg.subject,
            "timestamp": msg.timestamp,
        }
    except Exception as e:
        logger.error("Unexpected error in thread_post: %s", e, exc_info=True)
        return {
            "success": False,
            "posted": False,
            "status": "error",
            "project_id": project_id,
            "error": f"Internal error during thread_post: {str(e)}",
        }


def thread_read(
    project_id: str,
    agent_id: str,
    filter_type: Optional[str] = None,
    filter_from_agent: Optional[str] = None,
    since: Optional[str] = None,
    thread_manager: Optional[ThreadManager] = None,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Read all messages in a project's communication thread with optional filters.

    Args:
        project_id: Target project identifier.
        agent_id: Requesting agent ID.
        filter_type: Optional message type filter (e.g. 'DELIVERABLE').
        filter_from_agent: Optional sender agent filter (e.g. 'CTO').
        since: Optional ISO 8601 timestamp cutoff.
        thread_manager: Optional ThreadManager instance.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary containing list of messages.
    """
    try:
        vm = vault_manager or VaultManager()
        tm = thread_manager or ThreadManager(vault_manager=vm)

        clean_pid = project_id.strip()
        thread_id = f"thread_{clean_pid}_main"

        raw_messages = tm.get_thread_messages(thread_id, limit=200, ascending=True, project_id=clean_pid)

        filtered: List[Dict[str, Any]] = []
        for m in raw_messages:
            msg_dict: Dict[str, Any]
            if hasattr(m, "model_dump"):
                msg_dict = m.model_dump(by_alias=False)
            elif isinstance(m, dict):
                msg_dict = dict(m)
            else:
                msg_dict = {
                    "message_id": getattr(m, "message_id", ""),
                    "content": getattr(m, "content", ""),
                    "subject": getattr(m, "subject", ""),
                    "type": getattr(m, "type", ""),
                    "from_agent": getattr(m, "from_agent", ""),
                    "timestamp": getattr(m, "timestamp", ""),
                }

            # Normalize sender keys
            sender = msg_dict.get("from_agent") or msg_dict.get("from") or ""
            msg_dict["from_agent"] = sender
            msg_dict["from"] = sender

            # Type filter
            if filter_type and str(msg_dict.get("type", "")).upper() != filter_type.strip().upper():
                continue

            # Sender filter
            if filter_from_agent and str(sender).upper() != filter_from_agent.strip().upper():
                continue

            # Temporal filter
            if since and str(msg_dict.get("timestamp", "")) < since.strip():
                continue

            filtered.append(msg_dict)

        return {
            "success": True,
            "project_id": clean_pid,
            "thread_id": thread_id,
            "agent_id": agent_id,
            "count": len(filtered),
            "messages": filtered,
        }
    except Exception as e:
        logger.error("Unexpected error in thread_read: %s", e, exc_info=True)
        return {
            "success": False,
            "project_id": project_id,
            "agent_id": agent_id,
            "count": 0,
            "messages": [],
            "error": f"Internal error during thread_read: {str(e)}",
        }
