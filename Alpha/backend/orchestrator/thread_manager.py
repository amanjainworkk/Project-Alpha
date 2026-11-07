"""backend/orchestrator/thread_manager.py - Project Alpha Thread Manager.

Manages inter-agent message routing, dual-write persistence into SQLite
(vault_project_threads, vault_thread_messages) and append-only JSONL files,
real-time subscriber notifications, and WebSocket broadcast payloads.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from backend.vault.schemas import ThreadMessage, ThreadMessageType
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.orchestrator.thread_manager")


class ThreadManager:
    """Enterprise inter-agent threading and message routing engine."""

    def __init__(
        self,
        vault_manager: Optional[VaultManager] = None,
        vault_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self.vault_manager = vault_manager
        if vault_root is not None:
            self.vault_root = Path(vault_root).resolve()
        elif vault_manager is not None and hasattr(vault_manager, "vault_root"):
            self.vault_root = Path(vault_manager.vault_root).resolve()
        else:
            self.vault_root = Path(__file__).resolve().parent.parent.parent / "Alpha-Vault"

        self._subscribers: Dict[str, Dict[str, Callable[[ThreadMessage], Any]]] = {}
        self._global_subscribers: Dict[str, Callable[[ThreadMessage], Any]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------------
    # 1. Thread Lifecycle Management
    # ------------------------------------------------------------------------

    def create_thread(
        self,
        project_id: str,
        thread_id: Optional[str] = None,
        topic: str = "",
        stakeholders: Optional[List[str]] = None,
        owner_agent: str = "CEO",
        priority: int = 3,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or initialize a project communication thread."""
        if not project_id:
            raise ValueError("project_id cannot be empty.")

        tid = thread_id or f"thread_{project_id}_{uuid.uuid4().hex[:6]}"
        safe_topic = topic or f"Executive discussion for {project_id}"
        safe_stakeholders = stakeholders or ["CEO", "COO", "CTO"]
        safe_tags = tags or ["general"]

        thread_record = {
            "thread_id": tid,
            "project_id": project_id,
            "project_name": safe_topic,
            "thread_status": "active",
            "owner_agent": owner_agent,
            "stakeholders": safe_stakeholders,
            "priority": max(1, min(5, priority)),
            "tags": safe_tags,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Dual-write: SQLite Store
        if self.vault_manager and hasattr(self.vault_manager, "sqlite"):
            try:
                self.vault_manager.sqlite.upsert_thread(thread_record)
            except Exception as e:
                logger.warning("SQLite upsert_thread failed for %s: %s", tid, e)

        # 2. Dual-write: Ensure JSONL thread file directory exists
        thread_file = self._resolve_jsonl_path(project_id, tid)
        try:
            thread_file.parent.mkdir(parents=True, exist_ok=True)
            if not thread_file.exists():
                thread_file.touch()
        except Exception as e:
            logger.warning("Could not create thread JSONL file %s: %s", thread_file, e)

        return thread_record

    # ------------------------------------------------------------------------
    # 2. Message Posting & Dual Persistence
    # ------------------------------------------------------------------------

    def post_message(
        self,
        thread_id: str,
        sender_agent: str,
        content: str,
        to_agents: Optional[List[str]] = None,
        message_type: Union[ThreadMessageType, str] = ThreadMessageType.QUESTION,
        subject: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        in_reply_to: Optional[str] = None,
        model_used: Optional[str] = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
        project_id: Optional[str] = None,
    ) -> ThreadMessage:
        """Route, persist, and broadcast an inter-agent thread message."""
        if not thread_id:
            raise ValueError("thread_id cannot be empty.")
        if not sender_agent:
            raise ValueError("sender_agent cannot be empty.")
        if not content:
            raise ValueError("content cannot be empty.")

        resolved_pid = project_id or self._extract_project_id(thread_id)
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Normalize message type
        mtype = message_type.value if isinstance(message_type, ThreadMessageType) else str(message_type).upper()
        recipients = to_agents if to_agents is not None else ["*"]

        message = ThreadMessage(
            message_id=msg_id,
            thread_id=thread_id,
            project_id=resolved_pid,
            timestamp=now_iso,
            from_agent=sender_agent,
            to_agents=recipients,
            type=mtype,
            subject=subject or f"[{mtype}] From {sender_agent}",
            content=content,
            attachments=attachments or [],
            in_reply_to=in_reply_to,
            model_used=model_used or "unknown",
            tokens_used=tokens_used,
            status="sent",
        )

        with self._lock:
            # 1. Persist to SQLite
            if self.vault_manager and hasattr(self.vault_manager, "sqlite"):
                sqlite_data = {
                    "message_id": msg_id,
                    "thread_id": thread_id,
                    "project_id": resolved_pid,
                    "sender_agent": sender_agent,
                    "to_agents": recipients,
                    "message_type": mtype,
                    "subject": message.subject,
                    "content": content,
                    "attachments": message.attachments,
                    "in_reply_to": in_reply_to,
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "audit_status": "pending",
                    "status": "sent",
                    "data_tier": "T3",
                }
                try:
                    self.vault_manager.sqlite.insert_thread_message(sqlite_data)
                except Exception as e:
                    logger.warning("Failed SQLite insert for message %s: %s", msg_id, e)

            # 2. Append to JSONL thread file
            self._append_to_jsonl(resolved_pid, thread_id, message)

            # 3. Notify subscribers & broadcast
            self.notify_subscribers(thread_id, message)

        return message

    def _append_to_jsonl(self, project_id: str, thread_id: str, message: ThreadMessage) -> None:
        """Atomically append message line to local JSONL log."""
        try:
            path = self._resolve_jsonl_path(project_id, thread_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            msg_dict = message.model_dump(by_alias=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg_dict) + "\n")
                f.flush()
        except Exception as e:
            logger.error("Failed to append to JSONL %s: %s", thread_id, e)

    def _resolve_jsonl_path(self, project_id: str, thread_id: str) -> Path:
        return self.vault_root / "projects" / project_id / "threads" / f"{thread_id}.jsonl"

    def _extract_project_id(self, thread_id: str) -> str:
        """Infer project_id from thread naming convention."""
        if thread_id.startswith("thread_"):
            parts = thread_id[7:].split("_")
            if len(parts) >= 2 and parts[0] == "proj":
                return f"{parts[0]}_{parts[1]}"
            elif len(parts) >= 1:
                return parts[0]
        return "default_project"

    # ------------------------------------------------------------------------
    # 3. Message Querying & Thread History
    # ------------------------------------------------------------------------

    def get_thread_messages(
        self,
        thread_id: str,
        limit: int = 100,
        ascending: bool = True,
        project_id: Optional[str] = None,
    ) -> List[ThreadMessage]:
        """Fetch chronological message history from SQLite or JSONL fallback."""
        with self._lock:
            # 1. Attempt SQLite query
            if self.vault_manager and hasattr(self.vault_manager, "sqlite"):
                try:
                    raw_messages = self.vault_manager.sqlite.get_thread_messages(thread_id, limit=limit)
                    if raw_messages:
                        messages = []
                        for m in raw_messages:
                            # Reconstitute to_agents JSON if string
                            to_ag = m.get("to_agents")
                            if isinstance(to_ag, str):
                                try:
                                    to_ag = json.loads(to_ag)
                                except Exception:
                                    to_ag = [to_ag]
                            att = m.get("attachments")
                            if isinstance(att, str):
                                try:
                                    att = json.loads(att)
                                except Exception:
                                    att = []
                            messages.append(ThreadMessage(
                                message_id=m["message_id"],
                                thread_id=m["thread_id"],
                                project_id=m.get("project_id"),
                                timestamp=str(m.get("created_at")),
                                from_agent=m.get("sender_agent", "UNKNOWN"),
                                to_agents=to_ag or [],
                                type=m.get("message_type", "QUESTION"),
                                subject=m.get("subject"),
                                content=m.get("content", ""),
                                attachments=att or [],
                                in_reply_to=m.get("in_reply_to"),
                                model_used=m.get("model_used"),
                                tokens_used=int(m.get("tokens_used") or 0),
                                status=m.get("status", "sent"),
                            ))
                        if not ascending:
                            messages.reverse()
                        return messages
                except Exception as e:
                    logger.debug("SQLite get_thread_messages failed, falling back to JSONL: %s", e)

            # 2. JSONL Fallback
            pid = project_id or self._extract_project_id(thread_id)
            jsonl_path = self._resolve_jsonl_path(pid, thread_id)
            if not jsonl_path.exists():
                return []

            results: List[ThreadMessage] = []
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            data = json.loads(line_str)
                            results.append(ThreadMessage(**data))
            except Exception as e:
                logger.error("Error reading JSONL thread file %s: %s", jsonl_path, e)

            if not ascending:
                results.reverse()
            return results[:limit]

    # ------------------------------------------------------------------------
    # 4. PubSub Subscriptions & WebSocket Payload Formatting
    # ------------------------------------------------------------------------

    def subscribe(self, thread_id: str, callback: Callable[[ThreadMessage], Any]) -> str:
        """Register a callback for messages on a specific thread."""
        with self._lock:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            if thread_id not in self._subscribers:
                self._subscribers[thread_id] = {}
            self._subscribers[thread_id][sub_id] = callback
            return sub_id

    def subscribe_all(self, callback: Callable[[ThreadMessage], Any]) -> str:
        """Register a global listener for all posted messages."""
        with self._lock:
            sub_id = f"sub_global_{uuid.uuid4().hex[:8]}"
            self._global_subscribers[sub_id] = callback
            return sub_id

    def unsubscribe(self, thread_id: str, subscription_id: str) -> bool:
        """Remove a subscriber."""
        with self._lock:
            if thread_id in self._subscribers and subscription_id in self._subscribers[thread_id]:
                del self._subscribers[thread_id][subscription_id]
                return True
            if subscription_id in self._global_subscribers:
                del self._global_subscribers[subscription_id]
                return True
            return False

    def notify_subscribers(self, thread_id: str, message: ThreadMessage) -> None:
        """Dispatch message to local and global subscribers without raising exceptions."""
        callbacks: List[Callable[[ThreadMessage], Any]] = []
        with self._lock:
            if thread_id in self._subscribers:
                callbacks.extend(self._subscribers[thread_id].values())
            callbacks.extend(self._global_subscribers.values())

        for cb in callbacks:
            try:
                cb(message)
            except Exception as e:
                logger.warning("Subscriber callback error on thread %s: %s", thread_id, e)

    def format_websocket_payload(
        self,
        message: Union[ThreadMessage, Dict[str, Any]],
        event_type: str = "THREAD_MESSAGE_POSTED",
    ) -> Dict[str, Any]:
        """Construct structured event payload for Flutter APK / Archify Canvas."""
        if isinstance(message, dict):
            pid = message.get("project_id", "default_project")
            tid = message.get("thread_id", "main")
            payload = message
        else:
            pid = message.project_id
            tid = message.thread_id
            payload = {
                "message_id": message.message_id,
                "timestamp": str(message.timestamp),
                "from": message.from_agent,
                "to": message.to_agents,
                "type": str(message.type),
                "subject": message.subject,
                "content": message.content,
                "attachments": message.attachments,
                "tokens_used": message.tokens_used,
                "model_used": message.model_used,
            }

        return {
            "event": event_type,
            "project_id": pid,
            "thread_id": tid,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
