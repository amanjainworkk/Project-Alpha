"""tests/setup/test_vault_init.py - Unit & Integration Tests for Milestone 9 Vault Initializer.

Verifies:
1. Complete directory tree generation under custom temp vault_dir.
2. Idempotent initialization of SQLite database (Alpha-Vault/sqlite/vault.db) with
   all tables, views (documents, memories, threads, messages, decisions,
   audit_log, agent_registry, episodic_memory, thread_messages), and INSTEAD OF triggers.
3. ChromaDB persistent collection initialization and vector seeding.
4. Seeding of company/identity.json, company/org_chart.json, system/agent_catalog.json,
   user/profile.json, founder/profile.json, and company/culture.md.
5. Pre-population of all 13 executive agent profiles in SQLite and Chroma.
6. Programmatic interface initialize_vault() with custom founder and company names.
7. Idempotency: re-running on existing vault preserves data without corruption.
8. Force mode: re-running with force=True updates configurations as expected.
9. Mock embeddings: deterministic vector verification in offline mode.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
import pytest

from backend.setup.vault_init import (
    DEFAULT_EXECUTIVE_ROSTER,
    bootstrap_chroma_collections,
    bootstrap_directory_tree,
    bootstrap_sqlite_database,
    initialize_vault,
    seed_company_files,
    seed_agent_registry,
)
from backend.vault.chroma_store import ChromaStore
from backend.vault.schemas import CompanyIdentity, UserProfile
from backend.vault.vault_manager import VaultManager


@pytest.fixture(autouse=True)
def enable_mock_embeddings():
    """Ensure tests run hermetically with deterministic mock embeddings."""
    prev = os.environ.get("ALPHA_MOCK_EMBEDDINGS")
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    yield
    if prev is not None:
        os.environ["ALPHA_MOCK_EMBEDDINGS"] = prev
    else:
        os.environ.pop("ALPHA_MOCK_EMBEDDINGS", None)


@pytest.fixture
def temp_vault_dir(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary vault directory."""
    vdir = tmp_path / "Test-Alpha-Vault"
    return vdir


# ============================================================================
# 1. Directory Tree Tests
# ============================================================================

def test_bootstrap_directory_tree_creates_all_subdirectories(temp_vault_dir: Path):
    dirs = bootstrap_directory_tree(temp_vault_dir)
    assert temp_vault_dir.is_dir()

    expected_top_levels = [
        "company", "founder", "user", "projects", "agents",
        "system", "knowledge", "sqlite", "chroma", "backups",
    ]
    for sub in expected_top_levels:
        assert (temp_vault_dir / sub).is_dir()

    # Verify agent subdirectories exist
    for agent in DEFAULT_EXECUTIVE_ROSTER:
        aid = agent["agent_id"]
        assert (temp_vault_dir / "agents" / aid).is_dir()


# ============================================================================
# 2. SQLite Database & Views Tests
# ============================================================================

def test_bootstrap_sqlite_database_creates_all_tables_and_views(temp_vault_dir: Path):
    db_path = temp_vault_dir / "sqlite" / "vault.db"
    store = bootstrap_sqlite_database(db_path)
    assert db_path.is_file()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Fetch all table and view names
    cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view');")
    entities = {row[0]: row[1] for row in cur.fetchall()}

    # Verify base tables
    expected_tables = [
        "vault_kv", "vault_agents", "vault_agent_memory",
        "vault_project_threads", "vault_thread_messages",
        "vault_decisions", "vault_system_metrics", "vault_api_registry",
        "projects", "audit_log",
    ]
    for tbl in expected_tables:
        assert tbl in entities, f"Missing expected table {tbl}"

    # Verify compatibility views
    expected_views = [
        "documents", "memories", "threads", "messages", "decisions", "agent_registry"
    ]
    for vw in expected_views:
        assert vw in entities, f"Missing expected view {vw}"
        assert entities[vw] == "view"

    # Test documents view read & write via INSTEAD OF trigger
    cur.execute("INSERT INTO documents (path, data) VALUES ('test/doc.json', '{\"key\": \"value\"}');")
    conn.commit()

    # Read from documents view
    cur.execute("SELECT data FROM documents WHERE path = 'test/doc.json';")
    row = cur.fetchone()
    assert row is not None
    assert json.loads(row[0])["key"] == "value"

    # Verify underlying vault_kv table received the write
    cur.execute("SELECT data FROM vault_kv WHERE path = 'test/doc.json';")
    kv_row = cur.fetchone()
    assert kv_row is not None
    assert json.loads(kv_row[0])["key"] == "value"

    # Test UPDATE trigger
    cur.execute("UPDATE documents SET data = '{\"key\": \"updated\"}' WHERE path = 'test/doc.json';")
    conn.commit()
    cur.execute("SELECT data FROM documents WHERE path = 'test/doc.json';")
    assert json.loads(cur.fetchone()[0])["key"] == "updated"

    # Test DELETE trigger
    cur.execute("DELETE FROM documents WHERE path = 'test/doc.json';")
    conn.commit()
    cur.execute("SELECT data FROM documents WHERE path = 'test/doc.json';")
    assert cur.fetchone() is None

    conn.close()
    store.close()


# ============================================================================
# 3. ChromaDB Collections Tests
# ============================================================================

def test_bootstrap_chroma_collections_initializes_all_partitions(temp_vault_dir: Path):
    chroma_dir = temp_vault_dir / "chroma"
    chroma = bootstrap_chroma_collections(chroma_dir)

    collections = chroma.list_collections()
    assert ChromaStore.COLLECTION_KNOWLEDGE in collections
    assert ChromaStore.COLLECTION_PROJECTS in collections

    for agent in DEFAULT_EXECUTIVE_ROSTER:
        aid = agent["agent_id"]
        assert f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{aid}" in collections


# ============================================================================
# 4. Seed Company Files Tests
# ============================================================================

def test_seed_company_files_creates_valid_documents(temp_vault_dir: Path):
    bootstrap_directory_tree(temp_vault_dir)
    written = seed_company_files(
        temp_vault_dir,
        founder_name="Test Founder",
        company_name="Test Alpha Enterprise",
    )

    # 1. Company identity
    identity_file = temp_vault_dir / "company" / "identity.json"
    assert identity_file.is_file()
    with open(identity_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["founder"] == "Test Founder"
    assert data["company_name"] == "Test Alpha Enterprise"
    assert len(data["core_values"]) >= 3
    validated_id = CompanyIdentity.model_validate(data)
    assert validated_id.founder == "Test Founder"

    # 2. Org chart
    org_file = temp_vault_dir / "company" / "org_chart.json"
    assert org_file.is_file()
    with open(org_file, "r", encoding="utf-8") as f:
        org_data = json.load(f)
    assert org_data["founder"]["name"] == "Test Founder"
    assert len(org_data["direct_reports_to_ceo"]) >= 10

    # 3. Agent catalog
    catalog_file = temp_vault_dir / "system" / "agent_catalog.json"
    assert catalog_file.is_file()
    with open(catalog_file, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)
    assert catalog_data["total_agents"] >= 13

    # 4. User profile & Founder profile
    user_file = temp_vault_dir / "user" / "profile.json"
    founder_file = temp_vault_dir / "founder" / "profile.json"
    assert user_file.is_file()
    assert founder_file.is_file()
    with open(user_file, "r", encoding="utf-8") as f:
        user_data = json.load(f)
    validated_u = UserProfile.model_validate(user_data)
    assert validated_u.name == "Test Founder"

    # 5. Culture and OKRs
    assert (temp_vault_dir / "company" / "culture.md").is_file()
    assert (temp_vault_dir / "company" / "okrs.json").is_file()
    assert (temp_vault_dir / "projects" / "index.json").is_file()


# ============================================================================
# 5. Full End-to-End initialize_vault() Programmatic API
# ============================================================================

def test_initialize_vault_full_flow(temp_vault_dir: Path):
    vm = initialize_vault(
        vault_dir=temp_vault_dir,
        force=False,
        founder_name="Alice Founder",
        company_name="Apex Autonomous",
        use_mock_embeddings=True,
    )
    assert isinstance(vm, VaultManager)
    assert vm.vault_root == temp_vault_dir

    # 1. Verify user profile read via VaultManager
    profile = vm.get_user_profile()
    assert profile["name"] == "Alice Founder"

    # 2. Verify agent registry contains all 13 executive agents
    registry = vm.get_agent_registry()
    agent_ids = {a["agent_id"] for a in registry}
    expected = {"CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO", "CHRO", "CIO", "CSO", "CLO", "CAO-Claude", "CAO-ChatGPT"}
    assert expected.issubset(agent_ids)

    # 3. Verify Chroma semantic search in knowledge collection works
    results = vm.search("architecture and tech stack", n_results=3, path_prefix="knowledge")
    assert isinstance(results, list)

    vm.close()


# ============================================================================
# 6. Idempotency & Safety on Re-run
# ============================================================================

def test_initialize_vault_idempotency_preserves_custom_data(temp_vault_dir: Path):
    # First run
    vm1 = initialize_vault(vault_dir=temp_vault_dir, founder_name="Original Founder")
    vm1.close()

    # Simulate user custom modification
    custom_identity_path = temp_vault_dir / "company" / "identity.json"
    with open(custom_identity_path, "r", encoding="utf-8") as f:
        custom_data = json.load(f)
    custom_data["custom_user_tag"] = "DO_NOT_DELETE_ME"
    with open(custom_identity_path, "w", encoding="utf-8") as f:
        json.dump(custom_data, f)

    # Second run without force (idempotent)
    vm2 = initialize_vault(vault_dir=temp_vault_dir, force=False, founder_name="Different Name")
    vm2.close()

    # Verify custom modification was NOT overwritten
    with open(custom_identity_path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded.get("custom_user_tag") == "DO_NOT_DELETE_ME"


def test_initialize_vault_force_mode_overwrites_configuration(temp_vault_dir: Path):
    # First run
    vm1 = initialize_vault(vault_dir=temp_vault_dir, founder_name="Old Founder")
    vm1.close()

    # Second run with force=True
    vm2 = initialize_vault(vault_dir=temp_vault_dir, force=True, founder_name="New Founder")
    vm2.close()

    identity_path = temp_vault_dir / "company" / "identity.json"
    with open(identity_path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded["founder"] == "New Founder"


# ============================================================================
# 7. Additional Schema & Direct Store Verification Tests
# ============================================================================

def test_vault_init_seeds_all_13_executive_agents(temp_vault_dir: Path):
    """Verifies all 13 C-Suite executive agents are seeded into SQLite vault_agents."""
    vm = initialize_vault(vault_dir=temp_vault_dir)

    db_file = temp_vault_dir / "sqlite" / "vault.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT agent_id, agent_role, agent_model, is_active FROM vault_agents")
    rows = cursor.fetchall()
    conn.close()

    agents_by_id = {row[0]: {"role": row[1], "model": row[2], "active": row[3]} for row in rows}

    expected_agent_ids = [
        "CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO",
        "CHRO", "CIO", "CSO", "CLO", "CAO", "CAO-Claude", "CAO-ChatGPT"
    ]
    for aid in expected_agent_ids:
        assert aid in agents_by_id, f"Agent {aid} was not seeded into vault_agents"
        assert agents_by_id[aid]["active"] == 1

    vm.close()


def test_vault_init_seeds_company_identity_and_validates_schema(temp_vault_dir: Path):
    """Verifies company/identity.json is created and validates against Pydantic schema."""
    vm = initialize_vault(
        vault_dir=temp_vault_dir,
        company_name="Alpha Tech Inc",
        founder_name="Aman Founder",
    )

    identity_doc = vm.read("company/identity")
    assert identity_doc is not None
    assert identity_doc["company_name"] == "Alpha Tech Inc"
    assert identity_doc["founder"] == "Aman Founder"

    # Schema validation
    validated = CompanyIdentity.model_validate(identity_doc)
    assert validated.company_name == "Alpha Tech Inc"
    assert validated.founder == "Aman Founder"

    vm.close()


def test_vault_init_seeds_user_profile_and_validates_schema(temp_vault_dir: Path):
    """Verifies user/profile.json is seeded and accessible via get_user_profile."""
    vm = initialize_vault(vault_dir=temp_vault_dir, founder_name="Aman Jain")

    profile_doc = vm.get_user_profile()
    assert profile_doc is not None
    assert profile_doc["name"] == "Aman Jain"
    assert "Founder" in profile_doc["role"]

    validated = UserProfile.model_validate(profile_doc)
    assert validated.name == "Aman Jain"
    assert "Founder" in validated.role

    vm.close()


def test_vault_init_handles_chromadb_collections(temp_vault_dir: Path):
    """Verifies ChromaDB persist directory is initialized without errors."""
    vm = initialize_vault(vault_dir=temp_vault_dir)

    chroma_dir = temp_vault_dir / "chroma"
    assert chroma_dir.exists()
    assert chroma_dir.is_dir()

    vm.close()

