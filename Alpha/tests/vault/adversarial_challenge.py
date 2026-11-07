"""adversarial_challenge.py - Empirical Challenger Stress Harness for Project Alpha Vault.

Adversarial stress testing for:
1. Windows NTFS file lock collision resilience (os.replace retry backoff under concurrency & intentional locking).
2. MemoryType.FEEDBACK persistence, constraint enforcement, and semantic recall across SQLite, ChromaDB, and VaultManager.
3. Path canonicalization, edge cases, and unauthorized CAO write confinement.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure Alpha root is on sys.path
ALPHA_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALPHA_ROOT))
os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

from backend.vault.chroma_store import ChromaStore
from backend.vault.schemas import MemoryType
from backend.vault.sqlite_store import SQLiteStore
from backend.vault.vault_manager import AccessDeniedError, VaultManager


def log_test(name: str):
    print(f"\n{'='*70}\nRUNNING: {name}\n{'='*70}")


def test_concurrent_multithreaded_same_path_writes():
    """Objective 1: Verify 5-attempt retry backoff on os.replace eliminates WinError 5 under heavy contention."""
    log_test("Objective 1: Multithreaded Same-Path Concurrent Writes (Stress Harness)")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_concurrency_"))
    try:
        vm = VaultManager(
            vault_root=temp_dir / "vault",
            db_path=str(temp_dir / "vault.db"),
            chroma_path=str(temp_dir / "chroma"),
        )
        vm.initialize()

        num_writer_threads = 6
        writes_per_thread = 15
        total_expected_writes = num_writer_threads * writes_per_thread

        target_path = "company/identity.json"
        write_errors: List[str] = []
        successful_writes = 0

        def writer_worker(tid: int):
            nonlocal successful_writes
            for i in range(writes_per_thread):
                payload = {
                    "company_name": f"Alpha Global Corp T{tid}_I{i}",
                    "founder": "Aman Jain",
                    "vision": "Autonomous AI Enterprise OS",
                    "mission": "Empower founders through autonomous intelligence",
                    "industry": "Artificial Intelligence",
                }
                try:
                    ok = vm.write(target_path, payload, agent_id="CEO")
                    if ok:
                        successful_writes += 1
                    else:
                        write_errors.append(f"Thread {tid} write {i} returned False")
                except Exception as e:
                    write_errors.append(f"Thread {tid} write {i} raised exception: {type(e).__name__}: {e}")

        writer_threads = [threading.Thread(target=writer_worker, args=(w,)) for w in range(num_writer_threads)]
        start_time = time.time()
        for wt in writer_threads:
            wt.start()
        for wt in writer_threads:
            wt.join()

        duration = time.time() - start_time
        print(f"Writers-Only Test Finished in {duration:.2f}s")
        print(f"Total Writes Attempted: {total_expected_writes}, Succeeded: {successful_writes}, Errors: {len(write_errors)}")
        if write_errors:
            print(f"Sample write errors: {write_errors[:5]}")

        assert len(write_errors) == 0, f"Write errors occurred under writers-only contention: {write_errors[:10]}"

        # Check final file content
        fs_path = vm._get_fs_path(target_path)
        assert fs_path.is_file()
        with open(fs_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        assert "Alpha Global Corp" in content["company_name"]

        vm.close()
        print(">>> SUCCESS: Multithreaded same-path concurrent writes verified without WinError 5.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_intentional_file_lock_retry_recovery():
    """Objective 1 (Adversarial): Intentionally lock the destination file on Windows and verify retry backoff succeeds."""
    log_test("Objective 1 (Adversarial): Real Windows NTFS File Lock Recovery Harness")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_lock_"))
    try:
        vm = VaultManager(
            vault_root=temp_dir / "vault",
            db_path=str(temp_dir / "vault.db"),
            chroma_path=str(temp_dir / "chroma"),
        )
        vm.initialize()

        target_path = "company/identity.json"
        init_payload = {
            "company_name": "Alpha Corp Initial",
            "founder": "Aman Jain",
            "vision": "Autonomous OS",
            "mission": "AI",
            "industry": "Tech",
        }
        vm.write(target_path, init_payload, agent_id="CEO")
        fs_path = vm._get_fs_path(target_path)
        assert fs_path.is_file()

        # Background thread that holds an exclusive open file handle for 60ms
        lock_acquired = threading.Event()
        lock_released = threading.Event()

        def locker():
            # Open file without share permissions (exclusive read lock on Windows)
            with open(fs_path, "r+", encoding="utf-8") as f:
                lock_acquired.set()
                time.sleep(0.06)  # Hold lock for 60ms (longer than attempt 0 (20ms), shorter than attempt 1 (40ms, total 60ms))
            lock_released.set()

        t = threading.Thread(target=locker)
        t.start()
        lock_acquired.wait()

        # Immediately attempt to write. On Windows, attempt 0 should fail with WinError 5/PermissionError,
        # and retry loop should back off and succeed once locker releases file.
        new_payload = {
            "company_name": "Alpha Corp Recovered Post Lock",
            "founder": "Aman Jain",
            "vision": "Autonomous OS",
            "mission": "AI",
            "industry": "Tech",
        }
        ok = vm.write(target_path, new_payload, agent_id="CEO")
        t.join()

        assert ok is True, "Write failed to recover from transient Windows file lock"
        read_back = vm.read(target_path)
        assert read_back["company_name"] == "Alpha Corp Recovered Post Lock"

        vm.close()
        print(">>> SUCCESS: Intentional Windows file lock recovery verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_type_feedback_sqlite_relational():
    """Objective 2: Empirically verify MemoryType.FEEDBACK in SQLite relational schema."""
    log_test("Objective 2: SQLite Relational Store MemoryType.FEEDBACK Verification")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_sqlite_fb_"))
    try:
        db_path = str(temp_dir / "vault.db")
        store = SQLiteStore(db_path)

        # 1. Check schema DDL constraint
        cur = store._conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='vault_agent_memory'")
        row = cur.fetchone()
        table_sql = row[0]
        print(f"Table DDL for vault_agent_memory:\n{table_sql}")
        assert "'feedback'" in table_sql, "CHECK constraint missing 'feedback' literal in SQLite DDL"

        # 2. Register test agents
        test_agents = ["CEO", "CAO-Claude", "CAO-ChatGPT", "CTO", "CIO"]
        for aid in test_agents:
            store.upsert_agent({
                "agent_id": aid,
                "agent_role": aid,
                "agent_model": "llama3.2",
                "agent_version": "1.0",
            })

        # 3. Insert feedback memories using both string and enum
        fb1 = store.insert_memory({
            "memory_id": "mem-fb-001",
            "agent_id": "CEO",
            "memory_type": "feedback",
            "memory_content": "Founder praised zero-defect milestone execution.",
            "importance": 9,
            "project_id": "proj-alpha",
            "memory_tags": ["founder", "milestone", "positive"],
        })
        assert fb1 == "mem-fb-001"

        fb2 = store.insert_memory({
            "memory_id": "mem-fb-002",
            "agent_id": "CAO-Claude",
            "memory_type": MemoryType.FEEDBACK.value,
            "memory_content": "CAO Audit review: 5-axis rubric scored 94%. No P0/P1 defects found.",
            "importance": 10,
            "project_id": "proj-alpha",
            "memory_tags": ["audit", "cao", "rubric"],
        })
        assert fb2 == "mem-fb-002"

        fb3 = store.insert_memory({
            "memory_id": "mem-fb-003",
            "agent_id": "CAO-Claude",
            "memory_type": "feedback",
            "memory_content": "Minor feedback: document backoff exponent for Windows NTFS locks.",
            "importance": 4,
            "project_id": "proj-alpha",
            "memory_tags": ["ntfs", "documentation"],
        })
        assert fb3 == "mem-fb-003"

        # 4. Query memories by agent, importance, and project
        ceo_mems = store.query_memories("CEO", min_importance=5)
        assert len(ceo_mems) == 1
        assert ceo_mems[0]["memory_type"] == "feedback"
        assert ceo_mems[0]["importance"] == 9
        assert ceo_mems[0]["memory_tags"] == ["founder", "milestone", "positive"]

        cao_high = store.query_memories("CAO-Claude", min_importance=8)
        assert len(cao_high) == 1
        assert cao_high[0]["memory_id"] == "mem-fb-002"

        cao_all = store.query_memories("CAO-Claude", min_importance=1)
        assert len(cao_all) == 2
        # Verify ordering: importance DESC
        assert cao_all[0]["importance"] >= cao_all[1]["importance"]

        # 5. Adversarial: verify CHECK constraint rejects illegal memory_type
        print("Adversarial check: verifying rejected invalid memory_type...")
        try:
            store.insert_memory({
                "memory_id": "mem-illegal-type",
                "agent_id": "CEO",
                "memory_type": "unsupported_hallucination",
                "memory_content": "This must fail constraint.",
                "importance": 5,
            })
            raise AssertionError("SQLite failed to reject invalid memory_type!")
        except sqlite3.IntegrityError as ie:
            print(f"Correctly rejected illegal memory_type: {ie}")

        # 6. Adversarial: verify CHECK constraint rejects invalid importance (<1 or >10)
        for bad_imp in [0, 11, -1, 100]:
            try:
                store.insert_memory({
                    "memory_id": f"mem-bad-imp-{bad_imp}",
                    "agent_id": "CEO",
                    "memory_type": "feedback",
                    "memory_content": f"Bad importance {bad_imp}",
                    "importance": bad_imp,
                })
                raise AssertionError(f"SQLite failed to reject invalid importance {bad_imp}!")
            except sqlite3.IntegrityError:
                pass

        store.close()
        print(">>> SUCCESS: SQLite relational store MemoryType.FEEDBACK verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_type_feedback_chromadb_semantic():
    """Objective 2: Empirically verify MemoryType.FEEDBACK in ChromaDB vector store."""
    log_test("Objective 2: ChromaDB Vector Store MemoryType.FEEDBACK Verification")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_chroma_fb_"))
    try:
        chroma = ChromaStore(persist_dir=str(temp_dir / "chroma"))
        coll_name = f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}CEO"

        # 1. Add feedback memory vector
        mem_id = "mem-chroma-fb-01"
        mem_text = "Founder feedback: The dual CAO audit cap of 2 rounds worked seamlessly without deadlock."
        metadata = {
            "agent_id": "CEO",
            "type": "feedback",
            "project_id": "proj-m1",
            "path": "agents/CEO/episodic_memory.jsonl",
            "importance": 9,
            "tags": ["feedback", "cao", "deadlock"],
        }
        ok = chroma.add(coll_name, id=mem_id, text=mem_text, metadata=metadata)
        assert ok is True

        # 2. Add second distractor memory (different type)
        chroma.add(
            coll_name,
            id="mem-chroma-dec-01",
            text="Technical decision: Use WAL mode and busy timeout for SQLite connections.",
            metadata={"agent_id": "CEO", "type": "decision", "importance": 7},
        )

        # 3. Query without filter by semantic similarity
        hits = chroma.search(coll_name, query="auditing deadlock founder review", top_k=2)
        assert len(hits) >= 1
        assert hits[0]["id"] == mem_id
        assert hits[0]["metadata"]["type"] == "feedback"
        print(f"Top semantic hit score: {hits[0].get('similarity')} for query 'auditing deadlock founder review'")

        # 4. Query with explicit metadata filter: type == feedback
        filtered_hits = chroma.search(coll_name, query="technical architecture", top_k=5, where={"type": "feedback"})
        assert len(filtered_hits) == 1
        assert filtered_hits[0]["id"] == mem_id
        assert filtered_hits[0]["metadata"]["type"] == "feedback"

        # 5. Query with explicit metadata filter: type == decision
        dec_hits = chroma.search(coll_name, query="auditing deadlock", top_k=5, where={"type": "decision"})
        assert len(dec_hits) == 1
        assert dec_hits[0]["id"] == "mem-chroma-dec-01"

        print(">>> SUCCESS: ChromaDB vector store MemoryType.FEEDBACK verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_vault_manager_append_memory_feedback_full_stack():
    """Objective 2: Full-stack VaultManager verification of append_memory with MemoryType.FEEDBACK."""
    log_test("Objective 2: VaultManager Full-Stack Multi-Store Feedback Sync Verification")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_full_stack_fb_"))
    try:
        vm = VaultManager(
            vault_root=temp_dir / "vault",
            db_path=str(temp_dir / "vault.db"),
            chroma_path=str(temp_dir / "chroma"),
        )
        vm.initialize()

        # Test across multiple executive roles including newly seeded CAO variants
        roles_to_test = ["CEO", "CTO", "CAO-Claude", "CAO-ChatGPT", "CFO", "CIO"]

        for role in roles_to_test:
            content = f"Quarterly milestone audit feedback for {role}: requirements satisfied with 100% test pass rate."
            mem_id = vm.append_memory(
                agent_id=role,
                memory_type=MemoryType.FEEDBACK.value,
                content=content,
                importance=9,
                project_id="proj-audit-2026",
                tags=["audit", "milestone", "feedback", role],
            )
            assert mem_id.startswith(f"mem_{role}_")

            # 1. SQLite verification
            sqlite_rows = vm.sqlite.query_memories(role, min_importance=8)
            matching = [r for r in sqlite_rows if r["memory_id"] == mem_id]
            assert len(matching) == 1, f"Memory {mem_id} not found in SQLite for {role}"
            assert matching[0]["memory_type"] == "feedback"
            assert matching[0]["memory_content"] == content
            assert matching[0]["importance"] == 9

            # 2. Disk JSONL verification
            jsonl_file = vm.vault_root / "agents" / role / "episodic_memory.jsonl"
            assert jsonl_file.is_file(), f"JSONL file missing at {jsonl_file}"
            with open(jsonl_file, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            disk_match = [item for item in lines if item["memory_id"] == mem_id]
            assert len(disk_match) == 1
            assert (disk_match[0].get("type") or disk_match[0].get("memory_type")) == "feedback"

            # 3. ChromaDB verification
            chroma_coll = f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{role}"
            hits = vm.chroma.search(chroma_coll, query="milestone audit feedback", top_k=1)
            assert len(hits) == 1
            assert hits[0]["id"] == mem_id
            assert hits[0]["metadata"]["type"] == "feedback"

            # 4. VaultManager.search federated prefix test
            search_results = vm.search("quarterly milestone audit", path_prefix=f"agents/{role}")
            assert len(search_results) >= 1
            assert search_results[0]["id"] == mem_id

        # 5. Test auto-seeding on unseeded dynamic agent
        custom_agent = "SPECIALIST_AUDITOR"
        spec_mem_id = vm.append_memory(
            agent_id=custom_agent,
            memory_type=MemoryType.FEEDBACK.value,
            content="Dynamic specialist agent successfully logged feedback.",
            importance=8,
        )
        spec_mems = vm.sqlite.query_memories(custom_agent)
        assert len(spec_mems) == 1
        assert spec_mems[0]["memory_id"] == spec_mem_id
        assert spec_mems[0]["agent_id"] == custom_agent

        vm.close()
        print(">>> SUCCESS: VaultManager full-stack multi-store feedback sync verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_adversarial_security_and_path_bounds():
    """Objective: Adversarially challenge path canonicalization, null bytes, and traversal."""
    log_test("Adversarial: Path Canonicalization & Confinement Stress Harness")

    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_sec_"))
    try:
        vm = VaultManager(
            vault_root=temp_dir / "vault",
            db_path=str(temp_dir / "vault.db"),
            chroma_path=str(temp_dir / "chroma"),
        )
        vm.initialize()

        # Traversal attempts that must raise AccessDeniedError
        illegal_paths = [
            "projects/p1/../../Alpha-Vault/company/identity.json",
            "../../../etc/passwd",
            "..\\..\\Windows\\System32\\cmd.exe",
            "company/identity.json\x00.evil",
            "\x00/root/file.json",
            "",
            "   ",
            "/",
            "\\",
            ".",
            "./",
            "..",
        ]

        for p in illegal_paths:
            try:
                vm.write(p, {"bad": "data"}, agent_id="CEO")
                raise AssertionError(f"VaultManager.write failed to reject illegal path: {repr(p)}")
            except AccessDeniedError:
                pass

        # CAO unauthorized writes must raise AccessDeniedError
        for cao in ["CAO", "CAO-Claude", "CAO-ChatGPT"]:
            for target in ["company/identity.json", "agents/CEO/profile.json", "knowledge/tech.json"]:
                try:
                    vm.write(target, {"hacked": True}, agent_id=cao)
                    raise AssertionError(f"VaultManager.write permitted unauthorized CAO write: {cao} -> {target}")
                except AccessDeniedError:
                    pass

            # CAO authorized writes must succeed
            ok = vm.write(f"projects/p1/audit/{cao}_review.json", {"score": 98, "passed": True}, agent_id=cao)
            assert ok is True

        vm.close()
        print(">>> SUCCESS: Path canonicalization and CAO security bounds verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    print("======================================================================")
    print("STARTING EMPIRICAL CHALLENGER ADVERSARIAL TEST SUITE")
    print("======================================================================")

    test_concurrent_multithreaded_same_path_writes()
    test_intentional_file_lock_retry_recovery()
    test_memory_type_feedback_sqlite_relational()
    test_memory_type_feedback_chromadb_semantic()
    test_vault_manager_append_memory_feedback_full_stack()
    test_adversarial_security_and_path_bounds()

    print("\n======================================================================")
    print("ALL EMPIRICAL CHALLENGER ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    main()
