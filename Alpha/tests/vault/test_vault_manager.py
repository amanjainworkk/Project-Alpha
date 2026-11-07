"""tests/vault/test_vault_manager.py - Integration and contract tests for VaultManager facade."""

import json
import os
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.vault.vault_manager import AccessDeniedError, VaultManager


@pytest.fixture
def test_vault(tmp_path: Path) -> VaultManager:
    vault_dir = tmp_path / "vault_root"
    db_file = tmp_path / "test_vault.db"
    chroma_dir = tmp_path / "test_chroma"
    vm = VaultManager(vault_root=vault_dir, db_path=str(db_file), chroma_path=str(chroma_dir))
    return vm


def test_vault_manager_initialize_directory_tree(test_vault: VaultManager) -> None:
    assert test_vault.initialize() is True
    for sub in ["company", "agents", "projects", "knowledge", "user", "backups"]:
        assert (test_vault.vault_root / sub).is_dir()


def test_vault_manager_write_and_read_roundtrip(test_vault: VaultManager, sample_company_identity: dict) -> None:
    path = "company/identity.json"
    assert test_vault.write(path, sample_company_identity) is True

    # Read back
    data = test_vault.read(path)
    assert data is not None
    assert data["company_name"] == sample_company_identity["company_name"]
    assert data["founder"] == sample_company_identity["founder"]

    # Verify file exists on disk
    fs_file = test_vault.vault_root / "company" / "identity.json"
    assert fs_file.is_file()


def test_vault_manager_read_nonexistent_returns_none(test_vault: VaultManager) -> None:
    assert test_vault.read("missing/document.json") is None


def test_vault_manager_schema_validation_on_write(test_vault: VaultManager) -> None:
    # Missing required field 'role' for user/profile.json
    invalid_profile = {"name": "Test User"}
    with pytest.raises(ValidationError):
        test_vault.write("user/profile.json", invalid_profile)


def test_vault_manager_cao_read_only_protection(test_vault: VaultManager) -> None:
    # CAO cannot write to project manifests or deliverables
    with pytest.raises(AccessDeniedError):
        test_vault.write(
            "projects/proj-1/manifest.json",
            {"project_id": "proj-1", "name": "Hack"},
            agent_id="CAO-Claude",
        )

    with pytest.raises(AccessDeniedError):
        test_vault.write(
            "projects/proj-1/deliverables/spec.md",
            {"content": "Unauthorized"},
            agent_id="CAO-ChatGPT",
        )

    # CAO CAN write to its designated audit directory
    audit_write = test_vault.write(
        "projects/proj-1/audit/claude_audit.json",
        {"score": 95, "verdict": "pass"},
        agent_id="CAO-Claude",
    )
    assert audit_write is True


def test_vault_manager_system_identity_write_protection(test_vault: VaultManager, sample_company_identity: dict) -> None:
    # CTO cannot overwrite company identity
    with pytest.raises(AccessDeniedError):
        test_vault.write("company/identity.json", sample_company_identity, agent_id="CTO")

    # CEO can write company identity
    ceo_write = test_vault.write("company/identity.json", sample_company_identity, agent_id="CEO")
    assert ceo_write is True


def test_vault_manager_create_project_scaffolding(test_vault: VaultManager) -> None:
    title = "Alpha Autonomous OS"
    desc = "Master executive operating system"
    goals = ["Goal 1: Hybrid Store", "Goal 2: Tri-Framework Engine"]

    project_id = test_vault.create_project(title, desc, goals)
    assert project_id.startswith("proj-")

    proj_dir = test_vault.vault_root / "projects" / project_id
    assert (proj_dir / "threads").is_dir()
    assert (proj_dir / "deliverables").is_dir()
    assert (proj_dir / "audit").is_dir()
    assert (proj_dir / "goal.md").is_file()

    manifest = test_vault.read(f"projects/{project_id}/manifest.json")
    assert manifest is not None
    assert manifest["name"] == title
    assert manifest["status"] == "planning"
    assert manifest["assigned_agents"] == ["CEO"]


def test_vault_manager_append_memory_multi_store_sync(test_vault: VaultManager) -> None:
    # First register CTO agent in relational store
    test_vault.sqlite.upsert_agent({
        "agent_id": "CTO",
        "agent_role": "CTO",
        "agent_model": "llama3.2",
        "agent_version": "1.0",
    })

    mem_id = test_vault.append_memory(
        agent_id="CTO",
        memory_type="decision",
        content="Selected ChromaDB for local persistent vector storage.",
        importance=8,
        project_id="proj-alpha-001",
        context="Storage Architecture Decision",
        tags=["chroma", "sqlite", "vector"],
    )
    assert mem_id.startswith("mem_CTO_")

    # 1. Verify relational query
    mems = test_vault.sqlite.query_memories("CTO", min_importance=5)
    assert len(mems) == 1
    assert mems[0]["memory_id"] == mem_id
    assert mems[0]["importance"] == 8

    # 2. Verify JSONL on disk
    jsonl_path = test_vault.vault_root / "agents" / "CTO" / "episodic_memory.jsonl"
    assert jsonl_path.is_file()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        line = json.loads(f.readline())
        assert line["memory_id"] == mem_id
        assert line["content"] == "Selected ChromaDB for local persistent vector storage."

    # 3. Verify ChromaDB index
    hits = test_vault.chroma.search("agent_memory_CTO", query="ChromaDB persistent vector", top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == mem_id


def test_vault_manager_append_memory_importance_validation(test_vault: VaultManager) -> None:
    with pytest.raises(ValueError, match="importance must be between 1 and 10"):
        test_vault.append_memory(
            agent_id="CTO",
            memory_type="decision",
            content="Invalid importance",
            importance=0,
        )

    with pytest.raises(ValueError, match="importance must be between 1 and 10"):
        test_vault.append_memory(
            agent_id="CTO",
            memory_type="decision",
            content="Invalid importance",
            importance=15,
        )


def test_vault_manager_hybrid_search(test_vault: VaultManager) -> None:
    # Ingest knowledge and project docs
    test_vault.write(
        "knowledge/tech_decisions.json",
        {"title": "Database Indexing Strategy", "content": "B-tree indices on SQLite tables."},
    )
    test_vault.write(
        "projects/proj-1/deliverables/technical.json",
        {"title": "API Specification", "content": "FastAPI REST and WebSocket interfaces."},
    )

    results = test_vault.search("Database Indexing Strategy", n_results=5, path_prefix="knowledge/")
    assert len(results) >= 1
    for r in results:
        path = r.get("metadata", {}).get("path", "")
        assert path.startswith("knowledge/")


def test_vault_manager_get_user_profile(test_vault: VaultManager, sample_user_profile: dict) -> None:
    # Initially default profile
    default_prof = test_vault.get_user_profile()
    assert default_prof["name"] == "Aman Jain"
    assert default_prof["role"] == "Founder"

    # Write custom profile and retrieve
    test_vault.write("user/profile.json", sample_user_profile)
    prof = test_vault.get_user_profile()
    assert prof["escalation_threshold"] == "P0 or P1 architectural defects only"


def test_vault_manager_get_agent_registry(test_vault: VaultManager) -> None:
    test_vault.sqlite.upsert_agent({
        "agent_id": "CEO",
        "agent_role": "Chief Executive Officer",
        "agent_model": "claude-3-5-sonnet",
        "agent_version": "1.0",
        "is_active": True,
    })
    test_vault.sqlite.upsert_agent({
        "agent_id": "CTO",
        "agent_role": "Chief Technology Officer",
        "agent_model": "llama3.2",
        "agent_version": "1.0",
        "is_active": True,
    })

    registry = test_vault.get_agent_registry()
    assert len(registry) >= 2
    roles = {a["role"] for a in registry}
    assert "Chief Executive Officer" in roles
    assert "Chief Technology Officer" in roles


def test_vault_manager_atomic_write_crash_resilience(test_vault: VaultManager, monkeypatch: pytest.MonkeyPatch) -> None:
    path = "company/identity.json"
    initial_data = {"company_name": "Original Corp", "founder": "Aman Jain", "vision": "V1", "mission": "M1", "industry": "AI"}
    assert test_vault.write(path, initial_data) is True

    # Simulate crash during atomic replace
    def broken_replace(src: str, dst: str) -> None:
        raise OSError("Simulated disk replacement failure")

    monkeypatch.setattr(os, "replace", broken_replace)

    update_attempt = {"company_name": "Corrupted Corp", "founder": "Aman Jain", "vision": "V2", "mission": "M2", "industry": "AI"}
    success = test_vault.write(path, update_attempt)
    assert success is False

    # Original file remains intact and uncorrupted
    data = test_vault.read(path)
    assert data["company_name"] == "Original Corp"


def test_vault_manager_corrupted_json_recovery(test_vault: VaultManager) -> None:
    # Write corrupted raw text to file on disk
    corrupted_path = test_vault.vault_root / "company" / "okrs.json"
    corrupted_path.parent.mkdir(parents=True, exist_ok=True)
    with open(corrupted_path, "w", encoding="utf-8") as f:
        f.write("{corrupted: unclosed json[")

    # read() handles corruption safely without throwing an unhandled exception
    res = test_vault.read("company/okrs.json")
    assert res is None


def test_vault_manager_backup_creation_and_integrity(test_vault: VaultManager) -> None:
    test_vault.write("company/identity.json", {"company_name": "Backup Corp", "founder": "Aman", "vision": "V", "mission": "M", "industry": "AI"})
    backup_path = test_vault.backup()
    assert Path(backup_path).is_dir()
    assert (Path(backup_path) / "company" / "identity.json").is_file()


def test_vault_manager_path_traversal_prevention(test_vault: VaultManager) -> None:
    with pytest.raises(AccessDeniedError):
        test_vault._get_fs_path("../../etc/passwd")


def test_vault_manager_delete(test_vault: VaultManager) -> None:
    test_vault.write("test/del.json", {"key": "value"})
    assert test_vault.read("test/del.json") is not None
    assert test_vault.delete("test/del.json") is True
    assert test_vault.read("test/del.json") is None


def test_vault_manager_departmental_rbac_permissions(test_vault: VaultManager) -> None:
    # CTO allowed on technical deliverables
    assert test_vault.write("projects/p1/deliverables/technical.json", {"spec": "ok"}, agent_id="CTO") is True
    # CMO allowed on brand guidelines
    assert test_vault.write("knowledge/brand_guidelines.json", {"brand": "ok"}, agent_id="CMO") is True
    # CHRO allowed on agents
    assert test_vault.write("agents/CTO/skills.json", {"skills": ["py"]}, agent_id="CHRO") is True
    # CIO allowed on knowledge
    assert test_vault.write("knowledge/standards.json", {"std": "ok"}, agent_id="CIO") is True
    # Standard agent denied system path
    with pytest.raises(AccessDeniedError):
        test_vault.write("backups/test.json", {"data": 1}, agent_id="CTO")
    # CIO allowed system path
    assert test_vault.write("backups/test.json", {"data": 1}, agent_id="CIO") is True
    # Unmapped write denied
    with pytest.raises(AccessDeniedError):
        test_vault.write("deliverables/financial.json", {"data": 1}, agent_id="CMO")


def test_vault_manager_registry_document_fallback(test_vault: VaultManager) -> None:
    # 1. As list
    agents_list = [{"agent_id": "CEO", "role": "CEO", "status": "active"}]
    test_vault.write("agents/registry.json", agents_list)
    reg = test_vault.get_agent_registry()
    assert len(reg) == 1

    # 2. As dict with "agents"
    agents_dict = {"agents": [{"agent_id": "CTO", "role": "CTO", "status": "active"}]}
    test_vault.write("agents/registry.json", agents_dict)
    reg2 = test_vault.get_agent_registry()
    assert len(reg2) == 1
    assert reg2[0]["agent_id"] == "CTO"


def test_vault_manager_schema_validation_failures(test_vault: VaultManager) -> None:
    # Invalid ProjectManifest
    with pytest.raises(ValidationError):
        test_vault.write("projects/p1/manifest.json", {"bad": "data"})

    # Invalid CompanyIdentity
    with pytest.raises(ValidationError):
        test_vault.write("company/identity.json", {"bad": "data"})


def test_vault_manager_close(test_vault: VaultManager) -> None:
    test_vault.close()


def test_vault_manager_additional_roles_and_search_prefix(test_vault: VaultManager, sample_agent_profile: dict) -> None:
    # CDO, CFO, COO, CLO, CSO write permissions
    assert test_vault.write("projects/p1/deliverables/design.json", {"d": 1}, agent_id="CDO") is True
    assert test_vault.write("projects/p1/deliverables/financial.json", {"f": 1}, agent_id="CFO") is True
    assert test_vault.write("projects/p1/timelines.json", {"t": 1}, agent_id="COO") is True
    assert test_vault.write("projects/p1/deliverables/legal.json", {"l": 1}, agent_id="CLO") is True
    assert test_vault.write("company/okrs.json", {"o": 1}, agent_id="CSO") is True

    # Agent writing to its own folder
    assert test_vault.write("agents/CTO/profile.json", sample_agent_profile, agent_id="CTO") is True

    # Search with agents/ path prefix
    test_vault.sqlite.upsert_agent({"agent_id": "CTO", "agent_role": "CTO", "agent_model": "llama3.2", "agent_version": "1.0"})
    test_vault.append_memory(
        agent_id="CTO",
        memory_type="skill",
        content="Expert in distributed indexing and caching.",
        importance=6,
    )
    hits = test_vault.search("distributed indexing", n_results=5, path_prefix="agents/CTO")
    assert len(hits) >= 1


def test_vault_manager_in_vault_path_traversal_rejection(test_vault: VaultManager) -> None:
    """Test that relative in-vault path traversal is rejected and cannot bypass RBAC or schema validation."""
    # 1. CAO agent attempting traversal from audit folder to overwrite company/identity.json
    with pytest.raises(AccessDeniedError):
        test_vault.write(
            "projects/p1/audit/../../../company/identity.json",
            {"compromised": True},
            agent_id="CAO-Claude",
        )

    # 2. CMO agent attempting traversal from agent folder to overwrite technical knowledge
    with pytest.raises(AccessDeniedError):
        test_vault.write(
            "agents/CMO/../../knowledge/tech.json",
            {"compromised": True},
            agent_id="CMO",
        )

    # 3. Check write permission explicitly rejects or denies traversal paths
    assert test_vault.check_write_permission("CAO-Claude", "projects/p1/audit/../../../company/identity.json") is False
    assert test_vault.check_write_permission("CMO", "agents/CMO/../../knowledge/tech.json") is False

    # 4. Verify unauthorized targets were never created or modified on disk or in SQLite
    assert test_vault.read("company/identity.json") is None
    assert test_vault.read("knowledge/tech.json") is None
    assert not (test_vault.vault_root / "company" / "identity.json").exists()
    assert not (test_vault.vault_root / "knowledge" / "tech.json").exists()


def test_vault_manager_in_vault_path_traversal_schema_validation(test_vault: VaultManager) -> None:
    """Verifies that in-vault traversal paths enforce Pydantic schema validation."""
    with pytest.raises(ValidationError):
        test_vault.write(
            "projects/p1/deliverables/../../../company/identity.json",
            {"bad_payload": True},
            agent_id="CEO",
        )


def test_vault_manager_cao_unauthorized_direct_write_raises_access_denied(test_vault: VaultManager) -> None:
    """Test that unauthorized direct writes by CAO agents raise AccessDeniedError across all unauthorized paths."""
    cao_agents = ["CAO", "CAO-Claude", "CAO-ChatGPT"]
    unauthorized_targets = [
        ("company/identity.json", {"company_name": "Hacked", "founder": "Attacker", "vision": "V", "mission": "M", "industry": "AI"}),
        ("projects/p1/manifest.json", {"project_id": "p1", "name": "Hacked"}),
        ("knowledge/tech.json", {"architecture": "Corrupted"}),
    ]

    for agent in cao_agents:
        for path, payload in unauthorized_targets:
            with pytest.raises(AccessDeniedError):
                test_vault.write(path, payload, agent_id=agent)

    # Confirm authorized write to project audit folder succeeds for all CAO variants
    for agent in cao_agents:
        success = test_vault.write(
            f"projects/p1/audit/{agent}_report.json",
            {"verdict": "pass", "score": 90},
            agent_id=agent,
        )
        assert success is True


def test_vault_manager_null_byte_path_rejection(test_vault: VaultManager) -> None:
    """Test that paths containing embedded null bytes raise AccessDeniedError rather than crashing with ValueError."""
    null_byte_paths = [
        "knowledge/secret\x00_hidden.json",
        "company/\x00identity.json",
        "projects/p1/deliverables/doc\x00.json",
        "agents/CEO/\x00keys.json",
    ]

    for p in null_byte_paths:
        with pytest.raises(AccessDeniedError):
            test_vault.write(p, {"payload": "data"}, agent_id="CIO")

        with pytest.raises(AccessDeniedError):
            test_vault.read(p)

        with pytest.raises(AccessDeniedError):
            test_vault.delete(p)


def test_vault_manager_windows_extended_prefix_resilience(test_vault: VaultManager) -> None:
    """Verifies that Windows extended path prefix (\\\\?\\) is cleanly normalized."""
    from backend.vault.vault_manager import _normalize_fs_path

    ext_path = Path(r"\\?\C:\Users\Alpha\Vault\company\identity.json")
    clean = _normalize_fs_path(ext_path)
    assert not str(clean).startswith("\\\\?\\")
    assert str(clean) == r"C:\Users\Alpha\Vault\company\identity.json"


def test_vault_manager_agent_registry_auto_seeding(test_vault: VaultManager) -> None:
    """Verifies that 14 executive agents are auto-seeded upon initialization."""
    agents = test_vault.sqlite.list_agents(active_only=False)
    agent_ids = {a["agent_id"] for a in agents}
    expected = {
        "CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO",
        "CHRO", "CIO", "CSO", "CLO", "CAO", "CAO-Claude", "CAO-ChatGPT"
    }
    assert expected.issubset(agent_ids)

    # append_memory without pre-registering must succeed and persist to SQLite
    mid = test_vault.append_memory("CEO", "decision", "Auto-seeded agent test", 7)
    sqlite_mems = test_vault.sqlite.query_memories("CEO", min_importance=5)
    assert any(m["memory_id"] == mid for m in sqlite_mems)


def test_vault_manager_atomic_write_concurrency_retry(test_vault: VaultManager) -> None:
    """Verifies that Windows NTFS os.replace retry backoff prevents dropped writes under concurrency."""
    import threading

    num_threads = 5
    writes_per_thread = 15
    errors = []

    def worker(tid: int):
        for i in range(writes_per_thread):
            ok = test_vault.write(
                "company/identity.json",
                {
                    "company_name": f"Alpha Tech {tid}_{i}",
                    "founder": "Aman Jain",
                    "vision": "Autonomous OS",
                    "mission": "Empower builders",
                    "industry": "AI Systems",
                },
                agent_id="CEO",
            )
            if not ok:
                errors.append(f"Write failed at thread {tid} iter {i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Expected 0 dropped writes with retry backoff, got {len(errors)}: {errors[:5]}"


def test_vault_manager_append_memory_feedback_sync(test_vault: VaultManager) -> None:
    """Verify VaultManager.append_memory stores 'feedback' memory atomically across SQLite, Chroma, and disk."""
    from backend.vault.schemas import MemoryType

    test_vault.sqlite.upsert_agent({
        "agent_id": "CEO",
        "agent_role": "CEO",
        "agent_model": "claude",
        "agent_version": "1.0",
    })

    mem_id = test_vault.append_memory(
        agent_id="CEO",
        memory_type=MemoryType.FEEDBACK.value,
        content="Board confirmed milestone roadmap approval with zero defects.",
        importance=9,
        project_id="proj-alpha",
        tags=["board", "feedback", "roadmap"],
    )
    assert mem_id.startswith("mem_CEO_")

    # 1. Verify relational query is populated (no silent SQLite drop)
    mems = test_vault.sqlite.query_memories("CEO")
    assert len(mems) == 1
    assert mems[0]["memory_id"] == mem_id
    assert mems[0]["memory_type"] == "feedback"
    assert "milestone roadmap approval" in mems[0]["memory_content"]

    # 2. Verify disk JSONL record exists and matches
    jsonl_path = test_vault.vault_root / "agents" / "CEO" / "episodic_memory.jsonl"
    assert jsonl_path.is_file()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        line_data = json.loads(f.readline())
        assert line_data["memory_id"] == mem_id
        assert (line_data.get("type") or line_data.get("memory_type")) == "feedback"

    # 3. Verify ChromaDB index contains the vector
    hits = test_vault.chroma.search("agent_memory_CEO", query="milestone roadmap approval", top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == mem_id


def test_vault_manager_clean_vault_agent_autoseed_foreign_keys(tmp_path: Path) -> None:
    """Verify that operations on a completely clean/unseeded vault auto-seed agents, preventing silent foreign key drops."""
    vault_dir = tmp_path / "clean_vault"
    db_file = tmp_path / "clean_vault.db"
    chroma_dir = tmp_path / "clean_chroma"
    vm = VaultManager(vault_root=vault_dir, db_path=str(db_file), chroma_path=str(chroma_dir))
    vm.initialize()

    # 1. append_memory for CEO on clean vault without prior upsert_agent
    mem_id = vm.append_memory(
        agent_id="CEO",
        memory_type="decision",
        content="Clean vault autonomous startup decision.",
        importance=10,
    )
    assert mem_id.startswith("mem_CEO_")

    # Verify SQLite record is present (foreign key constraint must pass!)
    stored_mems = vm.sqlite.query_memories("CEO")
    assert len(stored_mems) == 1
    assert stored_mems[0]["memory_id"] == mem_id
    assert stored_mems[0]["memory_content"] == "Clean vault autonomous startup decision."

    # 2. create_project on clean vault without prior upsert_agent
    proj_id = vm.create_project("Project Alpha", "Autonomous Executive OS", ["Build Vault"])
    assert proj_id.startswith("proj-")

    # Verify thread registration succeeded in SQLite with owner_agent='CEO'
    cur = vm.sqlite._conn.cursor()
    cur.execute("SELECT * FROM vault_project_threads WHERE project_id = ?", (proj_id,))
    thread_row = cur.fetchone()
    cur.close()
    assert thread_row is not None
    assert thread_row["owner_agent"] == "CEO"

    # 3. append_memory for another unseeded agent (e.g. CTO)
    cto_mem_id = vm.append_memory(
        agent_id="CTO",
        memory_type="skill",
        content="Automated vector indexing capability.",
        importance=7,
    )
    cto_mems = vm.sqlite.query_memories("CTO")
    assert len(cto_mems) == 1
    assert cto_mems[0]["memory_id"] == cto_mem_id

    vm.close()



