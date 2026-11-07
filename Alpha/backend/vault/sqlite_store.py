"""backend/vault/sqlite_store.py - SQLite Storage Engine for Alpha's Vault.

Dual-paradigm SQLite storage supporting key-value document paths (vault_kv)
and relational tables for agents, memories, project threads, decisions,
system metrics, and API registry.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("alpha.vault.sqlite_store")


class SQLiteStore:
    """Dual-paradigm SQLite storage supporting key-value document paths

    and structured relational schemas with WAL concurrency and thread locks.
    """

    DDL_STATEMENTS = [
        # Key-Value Document Store
        """
        CREATE TABLE IF NOT EXISTS vault_kv (
            path TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # 1. Agent Registry
        """
        CREATE TABLE IF NOT EXISTS vault_agents (
            agent_id TEXT PRIMARY KEY,
            agent_role TEXT NOT NULL,
            agent_model TEXT NOT NULL,
            agent_version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            personality TEXT,
            jd_version TEXT
        );
        """,
        # 2. Agent Episodic Memory Store
        """
        CREATE TABLE IF NOT EXISTS vault_agent_memory (
            memory_id TEXT PRIMARY KEY,
            agent_id TEXT REFERENCES vault_agents(agent_id),
            memory_type TEXT CHECK(memory_type IN ('fact','decision','preference','skill','relationship','observation','lesson','feedback')),
            memory_content TEXT NOT NULL,
            memory_tags TEXT, -- JSON array
            importance INTEGER CHECK(importance BETWEEN 1 AND 10),
            project_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP,
            access_count INTEGER DEFAULT 0,
            is_archived BOOLEAN DEFAULT FALSE,
            data_tier TEXT DEFAULT 'T3'
        );
        """,
        # 3. Project Discussion Threads
        """
        CREATE TABLE IF NOT EXISTS vault_project_threads (
            thread_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            thread_status TEXT CHECK(thread_status IN ('active','paused','completed','archived')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            owner_agent TEXT REFERENCES vault_agents(agent_id),
            stakeholders TEXT, -- JSON array
            priority INTEGER CHECK(priority BETWEEN 1 AND 5),
            tags TEXT -- JSON array
        );
        """,
        # 4. Inter-Agent Thread Messages
        """
        CREATE TABLE IF NOT EXISTS vault_thread_messages (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT REFERENCES vault_project_threads(thread_id),
            project_id TEXT NOT NULL,
            sender_agent TEXT REFERENCES vault_agents(agent_id),
            to_agents TEXT, -- JSON array
            message_type TEXT CHECK(message_type IN (
                'DELEGATION','DELIVERABLE','QUESTION','RESPONSE',
                'REVIEW_REQUEST','SYNTHESIS','AUDIT_REQUEST','AUDIT_REPORT',
                'USER_ESCALATION','input','output','audit','decision','escalation'
            )),
            subject TEXT,
            content TEXT NOT NULL,
            attachments TEXT, -- JSON array
            in_reply_to TEXT,
            model_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            audit_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'sent',
            data_tier TEXT DEFAULT 'T3'
        );
        """,
        # 5. Decision Log
        """
        CREATE TABLE IF NOT EXISTS vault_decisions (
            decision_id TEXT PRIMARY KEY,
            thread_id TEXT REFERENCES vault_project_threads(thread_id),
            project_id TEXT,
            agent_id TEXT REFERENCES vault_agents(agent_id),
            decision_type TEXT,
            decision_summary TEXT NOT NULL,
            rationale TEXT,
            alternatives TEXT, -- JSON array
            risk_level TEXT CHECK(risk_level IN ('low','medium','high','critical')),
            cao_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # 6. System Metadata & Health Metrics
        """
        CREATE TABLE IF NOT EXISTS vault_system_metrics (
            metric_id TEXT PRIMARY KEY,
            metric_type TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT,
            agent_id TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # 7. External API Registry
        """
        CREATE TABLE IF NOT EXISTS vault_api_registry (
            api_id TEXT PRIMARY KEY,
            api_name TEXT NOT NULL,
            api_provider TEXT NOT NULL,
            base_url TEXT,
            auth_type TEXT,
            rate_limit TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_tested TIMESTAMP,
            health_status TEXT DEFAULT 'unknown'
        );
        """,
        # Performance Indices
        "CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON vault_agent_memory(agent_id);",
        "CREATE INDEX IF NOT EXISTS idx_agent_memory_importance ON vault_agent_memory(importance DESC);",
        "CREATE INDEX IF NOT EXISTS idx_agent_memory_project ON vault_agent_memory(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_threads_project ON vault_project_threads(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_thread ON vault_thread_messages(thread_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_created ON vault_thread_messages(created_at ASC);",
        "CREATE INDEX IF NOT EXISTS idx_decisions_project ON vault_decisions(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_metrics_type ON vault_system_metrics(metric_type);",
    ]

    def __init__(self, db_path: str = "Alpha-Vault/vault.db"):
        self.db_path = db_path
        self._lock = threading.RLock()

        if self.db_path != ":memory:":
            abs_dir = os.path.dirname(os.path.abspath(self.db_path))
            os.makedirs(abs_dir, exist_ok=True)

        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._init_schema()

    def _configure_pragmas(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("PRAGMA busy_timeout = 5000;")
            if self.db_path != ":memory:":
                cur.execute("PRAGMA journal_mode = WAL;")
                cur.execute("PRAGMA synchronous = NORMAL;")
            cur.close()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for stmt in self.DDL_STATEMENTS:
                cur.execute(stmt)
            self._conn.commit()
            cur.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Provides a managed database transaction with rollback on failure."""
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cursor.close()

    # ---------------------------------------------------------
    # Key-Value Document Store Operations (vault_kv)
    # ---------------------------------------------------------
    def get(self, path: str) -> Optional[Dict[str, Any]]:
        """Retrieves and deserializes JSON document at path."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data FROM vault_kv WHERE path = ?", (path,))
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            return json.loads(row["data"])

    def set(self, path: str, data: Dict[str, Any]) -> bool:
        """Serializes and upserts JSON document at path."""
        serialized = json.dumps(data, ensure_ascii=False)
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_kv (path, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    data = excluded.data,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (path, serialized),
            )
        return True

    def delete(self, path: str) -> bool:
        """Deletes key-value document at path."""
        with self.transaction() as cur:
            cur.execute("DELETE FROM vault_kv WHERE path = ?", (path,))
            return cur.rowcount > 0

    def list(self, prefix: str = "") -> List[str]:
        """Lists all keys matching given prefix in ascending order."""
        pattern = f"{prefix}%"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT path FROM vault_kv WHERE path LIKE ? ORDER BY path ASC", (pattern,))
            rows = cur.fetchall()
            cur.close()
            return [row["path"] for row in rows]

    # ---------------------------------------------------------
    # Relational Helpers
    # ---------------------------------------------------------
    def upsert_agent(self, agent_data: Dict[str, Any]) -> bool:
        """Upserts an executive agent profile into vault_agents."""
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_agents (
                    agent_id, agent_role, agent_model, agent_version,
                    is_active, personality, jd_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    agent_role = excluded.agent_role,
                    agent_model = excluded.agent_model,
                    agent_version = excluded.agent_version,
                    is_active = excluded.is_active,
                    personality = excluded.personality,
                    jd_version = excluded.jd_version
                """,
                (
                    agent_data["agent_id"],
                    agent_data["agent_role"],
                    agent_data["agent_model"],
                    agent_data["agent_version"],
                    agent_data.get("is_active", True),
                    agent_data.get("personality"),
                    agent_data.get("jd_version"),
                ),
            )
        return True

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves agent record by ID."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM vault_agents WHERE agent_id = ?", (agent_id,))
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def list_agents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Lists registered agents."""
        with self._lock:
            cur = self._conn.cursor()
            query = (
                "SELECT * FROM vault_agents WHERE is_active = TRUE ORDER BY agent_id ASC"
                if active_only
                else "SELECT * FROM vault_agents ORDER BY agent_id ASC"
            )
            cur.execute(query)
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]

    def insert_memory(self, memory_data: Dict[str, Any]) -> str:
        """Inserts an episodic memory record into vault_agent_memory."""
        tags_str = json.dumps(memory_data.get("memory_tags", []))
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_agent_memory (
                    memory_id, agent_id, memory_type, memory_content,
                    memory_tags, importance, project_id, data_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_data["memory_id"],
                    memory_data["agent_id"],
                    memory_data["memory_type"],
                    memory_data["memory_content"],
                    tags_str,
                    memory_data.get("importance", 3),
                    memory_data.get("project_id"),
                    memory_data.get("data_tier", "T3"),
                ),
            )
        return memory_data["memory_id"]

    def query_memories(
        self,
        agent_id: str,
        limit: int = 10,
        min_importance: int = 1,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries episodic memories for an agent."""
        with self._lock:
            cur = self._conn.cursor()
            if project_id:
                cur.execute(
                    """
                    SELECT * FROM vault_agent_memory
                    WHERE agent_id = ? AND importance >= ? AND project_id = ? AND is_archived = FALSE
                    ORDER BY importance DESC, created_at DESC LIMIT ?
                    """,
                    (agent_id, min_importance, project_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM vault_agent_memory
                    WHERE agent_id = ? AND importance >= ? AND is_archived = FALSE
                    ORDER BY importance DESC, created_at DESC LIMIT ?
                    """,
                    (agent_id, min_importance, limit),
                )
            rows = cur.fetchall()
            cur.close()
            res = []
            for r in rows:
                item = dict(r)
                if item.get("memory_tags"):
                    try:
                        item["memory_tags"] = json.loads(item["memory_tags"])
                    except Exception:
                        pass
                res.append(item)
            return res

    def upsert_thread(self, thread_data: Dict[str, Any]) -> bool:
        """Upserts a project thread into vault_project_threads."""
        stakeholders_str = json.dumps(thread_data.get("stakeholders", []))
        tags_str = json.dumps(thread_data.get("tags", []))
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_project_threads (
                    thread_id, project_id, project_name, thread_status,
                    owner_agent, stakeholders, priority, tags, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(thread_id) DO UPDATE SET
                    thread_status = excluded.thread_status,
                    updated_at = CURRENT_TIMESTAMP,
                    stakeholders = excluded.stakeholders,
                    priority = excluded.priority,
                    tags = excluded.tags
                """,
                (
                    thread_data["thread_id"],
                    thread_data["project_id"],
                    thread_data["project_name"],
                    thread_data.get("thread_status", "active"),
                    thread_data.get("owner_agent"),
                    stakeholders_str,
                    thread_data.get("priority", 3),
                    tags_str,
                ),
            )
        return True

    def insert_thread_message(self, message_data: Dict[str, Any]) -> str:
        """Inserts an inter-agent message into vault_thread_messages."""
        to_agents_str = json.dumps(message_data.get("to_agents", []))
        attachments_str = json.dumps(message_data.get("attachments", []))
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_thread_messages (
                    message_id, thread_id, project_id, sender_agent,
                    to_agents, message_type, subject, content, attachments,
                    in_reply_to, model_used, tokens_used, latency_ms,
                    audit_status, status, data_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_data["message_id"],
                    message_data["thread_id"],
                    message_data["project_id"],
                    message_data.get("sender_agent"),
                    to_agents_str,
                    message_data.get("message_type", "input"),
                    message_data.get("subject"),
                    message_data["content"],
                    attachments_str,
                    message_data.get("in_reply_to"),
                    message_data.get("model_used"),
                    message_data.get("tokens_used", 0),
                    message_data.get("latency_ms", 0),
                    message_data.get("audit_status", "pending"),
                    message_data.get("status", "sent"),
                    message_data.get("data_tier", "T3"),
                ),
            )
        return message_data["message_id"]

    def get_thread_messages(self, thread_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves chronological messages for a project thread."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM vault_thread_messages WHERE thread_id = ? ORDER BY created_at ASC LIMIT ?",
                (thread_id, limit),
            )
            rows = cur.fetchall()
            cur.close()
            res = []
            for r in rows:
                item = dict(r)
                for field in ("to_agents", "attachments"):
                    if item.get(field):
                        try:
                            item[field] = json.loads(item[field])
                        except Exception:
                            pass
                res.append(item)
            return res

    def insert_decision(self, decision_data: Dict[str, Any]) -> str:
        """Inserts an architectural or executive decision into vault_decisions."""
        alternatives_str = json.dumps(decision_data.get("alternatives", []))
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_decisions (
                    decision_id, thread_id, project_id, agent_id,
                    decision_type, decision_summary, rationale, alternatives,
                    risk_level, cao_approved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_data["decision_id"],
                    decision_data.get("thread_id"),
                    decision_data.get("project_id"),
                    decision_data.get("agent_id"),
                    decision_data.get("decision_type"),
                    decision_data["decision_summary"],
                    decision_data.get("rationale"),
                    alternatives_str,
                    decision_data.get("risk_level", "low"),
                    decision_data.get("cao_approved", False),
                ),
            )
        return decision_data["decision_id"]

    def record_metric(
        self,
        metric_type: str,
        metric_value: float,
        metric_unit: str = "",
        agent_id: Optional[str] = None,
        metric_id: Optional[str] = None,
    ) -> str:
        """Records a system health or operational metric."""
        import uuid

        m_id = metric_id or str(uuid.uuid4())
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_system_metrics (metric_id, metric_type, metric_value, metric_unit, agent_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (m_id, metric_type, metric_value, metric_unit, agent_id),
            )
        return m_id

    # ---------------------------------------------------------
    # API Registry Helpers
    # ---------------------------------------------------------
    def register_api(self, api_data: Dict[str, Any]) -> str:
        """Registers or updates an external API provider in vault_api_registry."""
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO vault_api_registry (
                    api_id, api_name, api_provider, base_url, auth_type,
                    rate_limit, is_active, last_tested, health_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(api_id) DO UPDATE SET
                    api_name = excluded.api_name,
                    api_provider = excluded.api_provider,
                    base_url = excluded.base_url,
                    auth_type = excluded.auth_type,
                    rate_limit = excluded.rate_limit,
                    is_active = excluded.is_active,
                    last_tested = COALESCE(excluded.last_tested, vault_api_registry.last_tested),
                    health_status = excluded.health_status
                """,
                (
                    api_data["api_id"],
                    api_data["api_name"],
                    api_data["api_provider"],
                    api_data.get("base_url"),
                    api_data.get("auth_type"),
                    api_data.get("rate_limit"),
                    api_data.get("is_active", True),
                    api_data.get("last_tested"),
                    api_data.get("health_status", "unknown"),
                ),
            )
        return api_data["api_id"]

    def get_api(self, api_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves external API registry record by API ID."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM vault_api_registry WHERE api_id = ?", (api_id,))
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def list_apis(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Lists external API registry records."""
        with self._lock:
            cur = self._conn.cursor()
            query = (
                "SELECT * FROM vault_api_registry WHERE is_active = TRUE ORDER BY api_name ASC"
                if active_only
                else "SELECT * FROM vault_api_registry ORDER BY api_name ASC"
            )
            cur.execute(query)
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]

    def update_api_status(
        self,
        api_id: str,
        health_status: Optional[str] = None,
        is_active: Optional[bool] = None,
        last_tested: Optional[str] = None,
    ) -> bool:
        """Updates the status and health for an API provider."""
        with self.transaction() as cur:
            updates = []
            params = []
            if health_status is not None:
                updates.append("health_status = ?")
                params.append(health_status)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            if last_tested is not None:
                updates.append("last_tested = ?")
                params.append(last_tested)
            else:
                updates.append("last_tested = CURRENT_TIMESTAMP")

            if not updates:
                return False

            sql = f"UPDATE vault_api_registry SET {', '.join(updates)} WHERE api_id = ?"
            params.append(api_id)
            cur.execute(sql, tuple(params))
            return cur.rowcount > 0

    def update_api_health(self, api_id: str, health_status: str, last_tested: Optional[str] = None) -> bool:
        """Updates the health status and last tested timestamp for an API."""
        return self.update_api_status(api_id, health_status=health_status, last_tested=last_tested)

    def delete_api(self, api_id: str) -> bool:
        """Deletes an API provider record from vault_api_registry."""
        with self.transaction() as cur:
            cur.execute("DELETE FROM vault_api_registry WHERE api_id = ?", (api_id,))
            return cur.rowcount > 0

    def close(self) -> None:
        """Closes the underlying SQLite database connection."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
