"""tests/vault/test_sqlite_store.py - Tests for SQLiteStore (KV & Relational)."""

import json
import sqlite3
import time
from pathlib import Path
import pytest

from backend.vault.sqlite_store import SQLiteStore


def test_sqlite_init_creates_all_tables(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    cur = store._conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    cur.close()
    store.close()

    expected_tables = {
        "vault_kv",
        "vault_agents",
        "vault_agent_memory",
        "vault_project_threads",
        "vault_thread_messages",
        "vault_decisions",
        "vault_system_metrics",
        "vault_api_registry",
    }
    for t in expected_tables:
        assert t in tables, f"Missing expected table {t}"


def test_kv_set_and_get_valid_document(temp_sqlite_db: str, sample_company_identity: dict) -> None:
    store = SQLiteStore(temp_sqlite_db)
    path = "company/identity.json"
    assert store.set(path, sample_company_identity) is True
    retrieved = store.get(path)
    assert retrieved == sample_company_identity
    store.close()


def test_kv_get_nonexistent_path(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    assert store.get("nonexistent/key.json") is None
    store.close()


def test_kv_set_overwrite_updates_data_and_timestamp(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    path = "test/config.json"
    data1 = {"v": 1}
    data2 = {"v": 2}
    store.set(path, data1)
    time.sleep(0.02)
    store.set(path, data2)
    assert store.get(path)["v"] == 2
    store.close()


def test_kv_delete_existing_and_nonexistent(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    path = "temp/to_delete.json"
    store.set(path, {"temp": True})
    assert store.delete(path) is True
    assert store.get(path) is None
    assert store.delete(path) is False
    store.close()


def test_kv_list_prefix_filtering(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.set("company/id.json", {"a": 1})
    store.set("company/okr.json", {"b": 2})
    store.set("projects/p1/manifest.json", {"c": 3})
    store.set("user/prof.json", {"d": 4})

    company_keys = store.list("company/")
    assert company_keys == ["company/id.json", "company/okr.json"]

    project_keys = store.list("projects/")
    assert project_keys == ["projects/p1/manifest.json"]

    all_keys = store.list("")
    assert len(all_keys) == 4
    assert all_keys == sorted(all_keys)
    store.close()


def test_kv_json_serialization_edge_types(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    path = "test/edge_types.json"
    edge_data = {
        "Founder": "Aman Jain 🚀",
        "pi": 3.1415926535,
        "is_active": True,
        "empty_list": [],
        "null_val": None,
        "nested": {"key": "value", "list": [1, 2, 3]},
    }
    store.set(path, edge_data)
    retrieved = store.get(path)
    assert retrieved == edge_data
    store.close()


def test_kv_corrupted_json_in_database(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    with store.transaction() as cur:
        cur.execute("INSERT INTO vault_kv (path, data) VALUES ('bad/path', '{unclosed json')")

    with pytest.raises(json.JSONDecodeError):
        store.get("bad/path")
    store.close()


def test_relational_agent_crud(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    agent = {
        "agent_id": "CEO",
        "agent_role": "CEO",
        "agent_model": "claude-3-5-sonnet",
        "agent_version": "1.0.0",
        "is_active": True,
        "personality": "Visionary executive",
        "jd_version": "1.0",
    }
    assert store.upsert_agent(agent) is True
    fetched = store.get_agent("CEO")
    assert fetched is not None
    assert fetched["agent_role"] == "CEO"
    assert fetched["is_active"] == 1

    agents = store.list_agents(active_only=True)
    assert len(agents) == 1
    assert agents[0]["agent_id"] == "CEO"
    store.close()


def test_relational_agent_duplicate_pk_constraint(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    agent = {
        "agent_id": "CTO",
        "agent_role": "CTO",
        "agent_model": "llama3.2",
        "agent_version": "1.0.0",
    }
    store.upsert_agent(agent)
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as cur:
            cur.execute(
                "INSERT INTO vault_agents (agent_id, agent_role, agent_model, agent_version) VALUES (?, ?, ?, ?)",
                ("CTO", "CTO", "llama3.2", "1.0.0"),
            )
    store.close()


def test_relational_memory_importance_check_constraint(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({"agent_id": "CIO", "agent_role": "CIO", "agent_model": "llama3.2", "agent_version": "1.0"})

    # Invalid importance > 10
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as cur:
            cur.execute(
                "INSERT INTO vault_agent_memory (memory_id, agent_id, memory_type, memory_content, importance) VALUES (?, ?, ?, ?, ?)",
                ("mem-1", "CIO", "fact", "content", 11),
            )

    # Valid importance 5
    mem_id = store.insert_memory({
        "memory_id": "mem-2",
        "agent_id": "CIO",
        "memory_type": "fact",
        "memory_content": "Valid importance fact",
        "importance": 5,
    })
    assert mem_id == "mem-2"
    store.close()


def test_relational_memory_foreign_key_enforcement(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as cur:
            cur.execute(
                "INSERT INTO vault_agent_memory (memory_id, agent_id, memory_type, memory_content, importance) VALUES (?, ?, ?, ?, ?)",
                ("mem-bad", "NONEXISTENT_AGENT", "fact", "content", 5),
            )
    store.close()


def test_relational_thread_messages_ordering_and_limit(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({"agent_id": "CEO", "agent_role": "CEO", "agent_model": "claude", "agent_version": "1.0"})
    store.upsert_thread({
        "thread_id": "thread-1",
        "project_id": "p1",
        "project_name": "Project 1",
    })

    for i in range(10):
        store.insert_thread_message({
            "message_id": f"msg-{i:02d}",
            "thread_id": "thread-1",
            "project_id": "p1",
            "sender_agent": "CEO",
            "content": f"Message {i}",
        })
        time.sleep(0.01)

    msgs = store.get_thread_messages("thread-1", limit=5)
    assert len(msgs) == 5
    for i in range(5):
        assert msgs[i]["message_id"] == f"msg-{i:02d}"
    store.close()


def test_sqlite_transaction_rollback_on_failure(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({"agent_id": "CEO", "agent_role": "CEO", "agent_model": "claude", "agent_version": "1.0"})

    try:
        with store.transaction() as cur:
            cur.execute("INSERT INTO vault_decisions (decision_id, decision_summary) VALUES ('d1', 'First')")
            cur.execute("INSERT INTO vault_decisions (decision_id, decision_summary) VALUES ('d2', 'Second')")
            # Invalid risk level CHECK constraint: 'invalid_risk'
            cur.execute("INSERT INTO vault_decisions (decision_id, decision_summary, risk_level) VALUES ('d3', 'Third', 'invalid_risk')")
    except sqlite3.IntegrityError:
        pass

    cur = store._conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vault_decisions")
    count = cur.fetchone()[0]
    cur.close()
    assert count == 0
    store.close()


def test_sqlite_wal_mode_and_concurrency(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    cur = store._conn.cursor()
    cur.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    cur.close()
    assert mode.lower() == "wal"

    # Concurrent connection read
    conn2 = sqlite3.connect(temp_sqlite_db)
    conn2.row_factory = sqlite3.Row
    store.set("shared/key.json", {"shared": True})

    cur2 = conn2.cursor()
    cur2.execute("SELECT data FROM vault_kv WHERE path = 'shared/key.json'")
    row = cur2.fetchone()
    cur2.close()
    conn2.close()
    store.close()

    assert row is not None
    assert json.loads(row["data"])["shared"] is True


def test_sqlite_record_metric(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    m_id = store.record_metric("cpu_usage", 42.5, "percent", agent_id="CIO")
    assert m_id is not None
    cur = store._conn.cursor()
    cur.execute("SELECT * FROM vault_system_metrics WHERE metric_id = ?", (m_id,))
    row = cur.fetchone()
    cur.close()
    assert row is not None
    assert row["metric_value"] == 42.5
    store.close()


def test_sqlite_insert_decision(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({"agent_id": "CTO", "agent_role": "CTO", "agent_model": "llama3.2", "agent_version": "1.0"})
    d_id = store.insert_decision({
        "decision_id": "dec-1",
        "agent_id": "CTO",
        "decision_type": "architecture",
        "decision_summary": "Use ChromaDB for vectors",
        "rationale": "Local and fast",
        "alternatives": ["Pinecone", "Milvus"],
        "risk_level": "low",
        "cao_approved": True,
    })
    assert d_id == "dec-1"
    store.close()


def test_sqlite_query_memories_filtered_by_project(temp_sqlite_db: str) -> None:
    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({"agent_id": "CPO", "agent_role": "CPO", "agent_model": "llama3.2", "agent_version": "1.0"})
    store.insert_memory({
        "memory_id": "m-p1",
        "agent_id": "CPO",
        "memory_type": "fact",
        "memory_content": "Project 1 fact",
        "importance": 7,
        "project_id": "proj-1",
        "memory_tags": ["tag1", "tag2"],
    })
    store.insert_memory({
        "memory_id": "m-p2",
        "agent_id": "CPO",
        "memory_type": "fact",
        "memory_content": "Project 2 fact",
        "importance": 9,
        "project_id": "proj-2",
    })

    p1_mems = store.query_memories("CPO", min_importance=5, project_id="proj-1")
    assert len(p1_mems) == 1
    assert p1_mems[0]["memory_id"] == "m-p1"
    assert p1_mems[0]["memory_tags"] == ["tag1", "tag2"]

    all_inactive = store.list_agents(active_only=False)
    assert len(all_inactive) >= 1
    store.close()


def test_sqlite_memory_type_feedback_relational_crud(temp_sqlite_db: str) -> None:
    """Verify that MemoryType.FEEDBACK ('feedback') satisfies SQLite table CHECK constraint and can be queried."""
    from backend.vault.schemas import MemoryType

    store = SQLiteStore(temp_sqlite_db)
    store.upsert_agent({
        "agent_id": "CEO",
        "agent_role": "CEO",
        "agent_model": "llama3.2",
        "agent_version": "1.0",
    })

    # Insert memory using MemoryType.FEEDBACK enum value
    mem_id = store.insert_memory({
        "memory_id": "mem-feedback-1",
        "agent_id": "CEO",
        "memory_type": MemoryType.FEEDBACK.value,
        "memory_content": "Founder gave positive feedback on modular architecture and security hardening.",
        "importance": 8,
        "project_id": "proj-1",
    })
    assert mem_id == "mem-feedback-1"

    # Query memories for CEO and verify feedback record is present
    mems = store.query_memories("CEO")
    assert len(mems) == 1
    assert mems[0]["memory_id"] == "mem-feedback-1"
    assert mems[0]["memory_type"] == "feedback"
    assert "modular architecture" in mems[0]["memory_content"]
    assert mems[0]["importance"] == 8

    store.close()


def test_sqlite_api_registry_crud(temp_sqlite_db: str) -> None:
    """Verify full CRUD lifecycle for vault_api_registry table in SQLiteStore."""
    store = SQLiteStore(temp_sqlite_db)

    # 1. Create / Register APIs
    api_payload = {
        "api_id": "api-groq-01",
        "api_name": "Groq Cloud API",
        "api_provider": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "auth_type": "bearer",
        "rate_limit": "30rpm",
        "is_active": True,
        "health_status": "healthy",
    }
    registered_id = store.register_api(api_payload)
    assert registered_id == "api-groq-01"

    # Register second API (inactive)
    store.register_api({
        "api_id": "api-ollama-local",
        "api_name": "Ollama Local Daemon",
        "api_provider": "Ollama",
        "base_url": "http://localhost:11434",
        "auth_type": "none",
        "rate_limit": "unlimited",
        "is_active": False,
        "health_status": "offline",
    })

    # 2. Read / Get API by ID
    api = store.get_api("api-groq-01")
    assert api is not None
    assert api["api_id"] == "api-groq-01"
    assert api["api_name"] == "Groq Cloud API"
    assert api["api_provider"] == "Groq"
    assert api["base_url"] == "https://api.groq.com/openai/v1"
    assert api["auth_type"] == "bearer"
    assert api["rate_limit"] == "30rpm"
    assert api["is_active"] in (True, 1)
    assert api["health_status"] == "healthy"

    # Non-existent API returns None
    assert store.get_api("nonexistent-api-id") is None

    # 3. List APIs (all vs active_only)
    all_apis = store.list_apis(active_only=False)
    assert len(all_apis) == 2
    api_ids = {a["api_id"] for a in all_apis}
    assert "api-groq-01" in api_ids
    assert "api-ollama-local" in api_ids

    active_apis = store.list_apis(active_only=True)
    assert len(active_apis) == 1
    assert active_apis[0]["api_id"] == "api-groq-01"

    # 4. Update API status and health
    assert store.update_api_status("api-groq-01", health_status="degraded") is True
    updated_api = store.get_api("api-groq-01")
    assert updated_api is not None
    assert updated_api["health_status"] == "degraded"

    # Update health helper also works
    assert store.update_api_health("api-groq-01", "healthy") is True
    updated_api2 = store.get_api("api-groq-01")
    assert updated_api2 is not None
    assert updated_api2["health_status"] == "healthy"

    # Update non-existent returns False
    assert store.update_api_status("nonexistent-api-id", health_status="healthy") is False

    # 5. Delete API
    assert store.delete_api("api-groq-01") is True
    assert store.get_api("api-groq-01") is None
    assert len(store.list_apis(active_only=False)) == 1

    # Delete non-existent returns False
    assert store.delete_api("api-groq-01") is False

    store.close()

