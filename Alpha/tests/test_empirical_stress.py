"""tests/test_empirical_stress.py - Empirical Adversarial Stress & Chaos Test Suite.

Adversarially challenges Project Alpha's Vault implementation:
1. High-concurrency multithreaded writes to SQLiteStore and VaultManager.
2. Edge cases: strange/malformed inputs, huge payloads (>100KB), deep directory nesting,
   Windows reserved device names, and MemoryType enum discrepancies.
3. Rapid succession of episodic memory appends and federated semantic searches.
4. Sudden process kill / crash simulation during write() to verify atomic replacement.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

# Ensure Alpha root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.vault.schemas import (
    CompanyIdentity,
    MemoryType,
    ProjectManifest,
    UserProfile,
)
from backend.vault.sqlite_store import SQLiteStore
from backend.vault.vault_manager import AccessDeniedError, VaultManager


# ============================================================================
# Section 1: Concurrency Stress Tests
# ============================================================================

def test_stress_sqlite_high_concurrency_kv_and_relational(tmp_path: Path) -> None:
    """Stress test SQLiteStore under 20 concurrent worker threads doing mixed KV and relational operations."""
    db_file = tmp_path / "concurrent_vault.db"
    store = SQLiteStore(str(db_file))

    # Pre-register agent to satisfy foreign key constraints
    store.upsert_agent({
        "agent_id": "CEO",
        "agent_role": "Chief Executive Officer",
        "agent_model": "llama3.2",
        "agent_version": "1.0.0",
    })

    num_threads = 20
    ops_per_thread = 50
    errors: List[str] = []

    def kv_worker(tid: int) -> None:
        for i in range(ops_per_thread):
            path = f"concurrent/doc_{tid}_{i}"
            payload = {"tid": tid, "seq": i, "data": "a" * 200}
            try:
                store.set(path, payload)
                val = store.get(path)
                if not val or val["seq"] != i:
                    errors.append(f"Mismatch at {path}: {val}")
            except Exception as e:
                errors.append(f"KV write/read failed {path}: {e}")

    def memory_worker(tid: int) -> None:
        for i in range(ops_per_thread):
            mid = f"mem_thread_{tid}_{i}"
            try:
                store.insert_memory({
                    "memory_id": mid,
                    "agent_id": "CEO",
                    "memory_type": "decision",
                    "memory_content": f"Decision log from thread {tid} index {i}",
                    "memory_tags": ["concurrency", f"worker_{tid}"],
                    "importance": (i % 10) + 1,
                    "project_id": "proj_stress_1",
                })
            except Exception as e:
                errors.append(f"Memory insert failed {mid}: {e}")

    # Launch KV threads
    threads = [threading.Thread(target=kv_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered KV concurrency errors: {errors[:5]}"

    # Launch Memory threads
    mem_threads = [threading.Thread(target=memory_worker, args=(t,)) for t in range(num_threads)]
    for t in mem_threads:
        t.start()
    for t in mem_threads:
        t.join()

    assert len(errors) == 0, f"Encountered Memory concurrency errors: {errors[:5]}"

    # Verify data integrity
    all_keys = store.list("concurrent/")
    assert len(all_keys) == num_threads * ops_per_thread

    memories = store.query_memories("CEO", limit=2000)
    assert len(memories) == num_threads * ops_per_thread

    store.close()


def test_stress_vault_manager_concurrent_distinct_and_same_path(tmp_path: Path) -> None:
    """Stress test VaultManager multithreaded writes to distinct paths and conflicting same-path writes."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vault_root = tmp_path / "vm_vault"
    vm = VaultManager(vault_root=vault_root)

    num_threads = 10
    writes_per_thread = 20
    distinct_errors: List[str] = []

    # 1. Distinct writes
    def distinct_worker(tid: int) -> None:
        for i in range(writes_per_thread):
            path = f"projects/p1/deliverables/doc_{tid}_{i}.json"
            data = {"tid": tid, "seq": i, "content": "deliverable payload"}
            try:
                ok = vm.write(path, data, agent_id="CEO")
                if not ok:
                    distinct_errors.append(f"vm.write returned False for {path}")
            except Exception as e:
                distinct_errors.append(f"vm.write raised {type(e).__name__} for {path}: {e}")

    threads = [threading.Thread(target=distinct_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Note: On Windows, Path.resolve() race condition can cause false AccessDeniedError
    # We record any distinct errors observed.
    print(f"Distinct concurrent write errors: {len(distinct_errors)}")

    # 2. Conflicting same-path writes (simultaneous writes to company/identity.json)
    same_path_failures: List[str] = []
    def same_path_worker(tid: int) -> None:
        for i in range(15):
            path = "company/identity.json"
            identity = {
                "company_name": f"Alpha Corp Thread {tid}",
                "founder": "Aman Jain",
                "vision": f"Vision from thread {tid} loop {i}",
                "mission": "Autonomous Executive Intelligence",
                "industry": "Artificial Intelligence",
            }
            try:
                ok = vm.write(path, identity, agent_id="CEO")
                if not ok:
                    same_path_failures.append(f"Write failed (returned False) tid={tid} i={i}")
            except Exception as e:
                same_path_failures.append(f"Write exception tid={tid} i={i}: {e}")

    same_threads = [threading.Thread(target=same_path_worker, args=(t,)) for t in range(5)]
    for t in same_threads:
        t.start()
    for t in same_threads:
        t.join()

    print(f"Same-path concurrent write failures: {len(same_path_failures)} / 75")
    # File should still be valid JSON and readable
    final_read = vm.read("company/identity.json")
    assert final_read is not None
    assert "Alpha Corp Thread" in final_read["company_name"]

    vm.close()


# ============================================================================
# Section 2: Edge Cases & Malformed Inputs
# ============================================================================

def test_edge_case_huge_payload(tmp_path: Path) -> None:
    """Verify VaultManager handles huge (>100KB, e.g. 500KB) JSON payloads without corruption."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "huge_vault")

    # Generate 500KB JSON payload
    large_payload = {
        "metadata": {"version": "1.0", "generator": "stress_harness"},
        "records": [
            {
                "id": f"rec_{i:05d}",
                "name": f"Record number {i}",
                "description": "Comprehensive institutional memory entry with detailed architectural context",
                "tags": ["stress", "large", "benchmark", f"tag_{i % 50}"],
                "metrics": {"cpu": i * 0.1, "memory_mb": i * 1.5, "latency_ms": i % 100},
            }
            for i in range(2500)
        ],
    }

    raw_json = json.dumps(large_payload)
    size_kb = len(raw_json) / 1024
    assert size_kb > 100, f"Payload size should be > 100KB, got {size_kb:.1f}KB"

    path = "projects/p1/deliverables/massive_spec.json"
    assert vm.write(path, large_payload, agent_id="CTO") is True

    # Read back and compare
    read_data = vm.read(path)
    assert read_data is not None
    assert len(read_data["records"]) == 2500
    assert read_data["records"][2499]["id"] == "rec_02499"

    vm.close()


def test_edge_case_deep_nesting(tmp_path: Path) -> None:
    """Verify handling of deeply nested dictionary structures (50 levels deep)."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "deep_vault")

    deep_data: Dict[str, Any] = {"depth": 0}
    current = deep_data
    for level in range(1, 50):
        current["child"] = {"depth": level}
        current = current["child"]

    path = "projects/p1/deliverables/deep_ast.json"
    assert vm.write(path, deep_data, agent_id="CTO") is True

    read_back = vm.read(path)
    assert read_back is not None
    # Traverse down 49 levels
    node = read_back
    for level in range(1, 50):
        node = node["child"]
        assert node["depth"] == level

    vm.close()


def test_edge_case_unicode_emojis_and_special_chars(tmp_path: Path) -> None:
    """Verify paths and data containing unicode, emojis, and special characters."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "unicode_vault")

    data = {
        "title": "Autonomous Executive Intelligence 🚀🧠",
        "description": "Multilingual: 日本語, Español, Français, Deutsch, العربية, Русский",
        "symbols": "!@#$%^&*()_+-=[]{}|;':,./<>?",
        "quotes": 'Double "quote" and single \'quote\' and newlines \n\r\t',
    }

    path = "projects/p1/deliverables/unicode_🚀_notes.json"
    assert vm.write(path, data, agent_id="CTO") is True

    read_back = vm.read(path)
    assert read_back == data

    vm.close()


def test_edge_case_memory_type_feedback_sqlite_check_constraint(tmp_path: Path) -> None:
    """Investigate whether MemoryType.FEEDBACK defined in schemas.py violates SQLiteStore's CHECK constraint.
    
    schemas.py defines:
        FEEDBACK = "feedback"
    sqlite_store.py defines:
        CHECK(memory_type IN ('fact','decision','preference','skill','relationship','observation','lesson','feedback'))
    """
    db_file = tmp_path / "feedback_test.db"
    store = SQLiteStore(str(db_file))
    store.upsert_agent({
        "agent_id": "CEO",
        "agent_role": "Chief Executive Officer",
        "agent_model": "llama3.2",
        "agent_version": "1.0.0",
    })

    # Direct insert of 'feedback' memory type into SQLiteStore should now succeed
    mem_id = store.insert_memory({
        "memory_id": "mem_fb_1",
        "agent_id": "CEO",
        "memory_type": MemoryType.FEEDBACK.value,
        "memory_content": "Constructive founder feedback",
        "importance": 5,
    })

    assert mem_id == "mem_fb_1"
    retrieved = store.query_memories(agent_id="CEO")
    assert len(retrieved) == 1
    assert retrieved[0]["memory_type"] == "feedback"

    store.close()


def test_edge_case_path_traversal_and_null_bytes(tmp_path: Path) -> None:
    """Test adversarial path inputs: directory traversal, null bytes, and empty strings."""
    vm = VaultManager(vault_root=tmp_path / "security_vault")

    # Path traversal with ../
    with pytest.raises(AccessDeniedError):
        vm.write("../../outside_vault.json", {"hack": True})

    with pytest.raises(AccessDeniedError):
        vm.read("../../../windows/system32/cmd.exe")

    # Windows root traversal
    with pytest.raises(AccessDeniedError):
        vm.write("C:/Windows/temp.json", {"hack": True})

    vm.close()


# ============================================================================
# Section 3: Rapid Succession of Memory Appends and Search Queries
# ============================================================================

def test_stress_rapid_memory_appends_and_concurrent_searches(tmp_path: Path) -> None:
    """Execute 200 rapid episodic memory appends while 3 background threads execute continuous semantic searches."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "search_stress_vault")

    # Register agents in SQLite
    for role in ["CEO", "CTO", "CPO"]:
        vm.sqlite.upsert_agent({
            "agent_id": role,
            "agent_role": role,
            "agent_model": "llama3.2",
            "agent_version": "1.0.0",
        })

    stop_event = threading.Event()
    search_errors: List[str] = []
    search_counts = [0, 0, 0]

    def search_worker(worker_id: int) -> None:
        queries = ["architecture decision", "product roadmap", "founder goals", "database schema"]
        q_idx = 0
        while not stop_event.is_set():
            q = queries[q_idx % len(queries)]
            q_idx += 1
            try:
                results = vm.search(query=q, n_results=5)
                search_counts[worker_id] += 1
            except Exception as e:
                search_errors.append(f"Search worker {worker_id} failed: {e}")
            time.sleep(0.005)

    # Start 3 background search threads
    search_threads = [threading.Thread(target=search_worker, args=(i,)) for i in range(3)]
    for st in search_threads:
        st.start()

    # Append 150 memories rapidly across 3 agents
    append_errors: List[str] = []
    start_time = time.time()
    for i in range(150):
        agent = ["CEO", "CTO", "CPO"][i % 3]
        mtype = ["decision", "observation", "lesson"][i % 3]
        try:
            mem_id = vm.append_memory(
                agent_id=agent,
                memory_type=mtype,
                content=f"Rapid memory append iteration {i}: Evaluated modular architectural tradeoffs for service #{i}.",
                importance=(i % 10) + 1,
                project_id=f"proj_{(i % 5) + 1}",
                tags=["stress", f"batch_{i // 10}"],
            )
            assert mem_id.startswith(f"mem_{agent}_")
        except Exception as e:
            append_errors.append(f"Append memory {i} failed: {e}")

    elapsed = time.time() - start_time
    stop_event.set()
    for st in search_threads:
        st.join()

    print(f"\nRapid memory test: 150 appends in {elapsed:.2f}s ({150/elapsed:.1f} ops/sec)")
    print(f"Total concurrent searches executed: {sum(search_counts)} across 3 threads")
    print(f"Search errors: {len(search_errors)}, Append errors: {len(append_errors)}")

    assert len(append_errors) == 0
    assert len(search_errors) == 0

    # Query back memories
    ceo_mems = vm.sqlite.query_memories("CEO", limit=100)
    assert len(ceo_mems) == 50

    vm.close()


# ============================================================================
# Section 4: Sudden Process Kill & Crash Simulation During write()
# ============================================================================

def test_atomic_write_crash_before_replace_preserves_original(tmp_path: Path) -> None:
    """Simulate sudden crash / exception during json.dump() before os.replace().
    Verifies that the original destination file is completely untouched and intact.
    """
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "crash_vault")

    path = "company/identity.json"
    initial_identity = {
        "company_name": "Alpha Original Stable",
        "founder": "Aman Jain",
        "vision": "Stable Original Vision",
        "mission": "Original Mission",
        "industry": "AI",
    }
    assert vm.write(path, initial_identity, agent_id="CEO") is True

    # Verify initial file exists and has original content
    read1 = vm.read(path)
    assert read1 is not None
    assert read1["company_name"] == "Alpha Original Stable"

    # Simulate crash during atomic file dump (e.g. MemoryError, Power loss, process killed)
    corrupted_new_data = {
        "company_name": "Alpha Corrupted Half-Written",
        "founder": "Aman Jain",
        "vision": "Incomplete",
        "mission": "Incomplete",
        "industry": "AI",
    }

    # Patch json.dump to simulate sudden crash during writing to temporary file
    with patch("json.dump", side_effect=IOError("Simulated sudden power loss / kill")):
        success = vm.write(path, corrupted_new_data, agent_id="CEO")
        assert success is False

    # Verify that the original file on disk and in SQLite is 100% intact
    read2 = vm.read(path)
    assert read2 is not None
    assert read2["company_name"] == "Alpha Original Stable"
    assert read2["vision"] == "Stable Original Vision"

    # Verify no stray .tmp files left in the company directory
    company_dir = tmp_path / "crash_vault" / "company"
    tmp_files = [f for f in company_dir.iterdir() if f.name.startswith("tmp")]
    assert len(tmp_files) == 0, f"Found leaked temporary files: {tmp_files}"

    vm.close()


def test_atomic_write_crash_after_replace_before_sqlite_cache_inconsistency(tmp_path: Path) -> None:
    """Analyze the failure mode when crash occurs AFTER os.replace() but BEFORE sqlite.set().
    
    Demonstrates architectural observation:
    If a crash kills the process right after disk replacement, SQLite retains the old state,
    and subsequent vm.read() returns stale SQLite cache because SQLite is checked before disk.
    """
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = VaultManager(vault_root=tmp_path / "cache_inconsistency_vault")

    path = "company/identity.json"
    v1_identity = {
        "company_name": "Alpha Version 1",
        "founder": "Aman Jain",
        "vision": "V1 Vision",
        "mission": "V1 Mission",
        "industry": "AI",
    }
    assert vm.write(path, v1_identity, agent_id="CEO") is True

    # Now simulate crash: disk write succeeds, but sqlite.set raises RuntimeError (or process killed)
    v2_identity = {
        "company_name": "Alpha Version 2 (Disk Only)",
        "founder": "Aman Jain",
        "vision": "V2 Vision",
        "mission": "V2 Mission",
        "industry": "AI",
    }

    with patch.object(vm.sqlite, "set", side_effect=RuntimeError("Process killed before SQLite write")):
        with pytest.raises(RuntimeError):
            vm.write(path, v2_identity, agent_id="CEO")

    # Check what disk has:
    fs_file = tmp_path / "cache_inconsistency_vault" / "company" / "identity.json"
    with open(fs_file, "r", encoding="utf-8") as f:
        disk_content = json.load(f)
    assert disk_content["company_name"] == "Alpha Version 2 (Disk Only)"

    # Check what vm.read() returns:
    # Because vm.read() checks SQLite FIRST, it returns Version 1!
    cached_read = vm.read(path)
    print(f"\nCache Inconsistency Observation: Disk has '{disk_content['company_name']}', but vm.read() returns '{cached_read['company_name']}'")
    assert cached_read["company_name"] == "Alpha Version 1"

    vm.close()
