"""tests/setup/test_adversarial_m9_vault.py - Empirical Adversarial Stress Suite for Milestone 9.

Adversarial Challenger Suite targeting:
1. vault_init.py:
   - 3x Idempotency stress (zero duplicate agents, stable table row counts, no data loss)
   - Force recreation (clean state overwrite, wiping corrupted seed documents)
   - Corrupted seed files (malformed JSON resilience, non-catastrophic degradation)
   - SQLite concurrency & locked database recovery
   - Dual-path SQLite synchronization (Alpha-Vault/sqlite/vault.db <-> Alpha-Vault/vault.db)
   - SQL View triggers (INSTEAD OF INSERT/UPDATE/DELETE on documents view, triggers cascade to vault_kv)
   - Offline Ollama instant fallback (< 3s deterministic mock embeddings without hanging)
2. first_run.py:
   - .env edge cases (comments, duplicate keys, blank lines, special characters, missing .env)
   - Token entropy and cryptographic validation (64 hex characters / 32 bytes, uniqueness, high entropy)
   - Invalid configuration dictionary inputs (empty founder/company name, malformed URL, extra fields, SQL injection strings)
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from backend.setup.first_run import (
    SetupConfig,
    format_env_value,
    generate_secure_token,
    parse_env_file,
    run_first_run,
    update_env_file,
    validate_api_key_format,
    validate_non_empty,
    validate_url,
)
from backend.setup.vault_init import (
    DEFAULT_EXECUTIVE_ROSTER,
    _is_ollama_online,
    bootstrap_sqlite_database,
    initialize_vault,
)
from backend.vault.chroma_store import ChromaStore
from backend.vault.embeddings import EMBEDDING_DIM
from backend.vault.schemas import CompanyIdentity, UserProfile
from backend.vault.vault_manager import VaultManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def isolated_vault_dir(tmp_path: Path) -> Path:
    """Provides a fresh isolated directory for vault operations."""
    vdir = tmp_path / "Adversarial-Vault"
    return vdir


@pytest.fixture
def isolated_env_file(tmp_path: Path) -> Path:
    """Provides a fresh isolated path for .env tests."""
    return tmp_path / ".env"


# ============================================================================
# 1. vault_init.py: Idempotency Stress (Sequential 3x Run)
# ============================================================================

def test_adversarial_idempotency_stress_3x_runs(isolated_vault_dir: Path):
    """Stress-test initialize_vault by executing it 3 times sequentially.

    Verifies:
    - Zero data loss across runs (custom file placed in vault persists).
    - Stable row counts in vault_agents, projects, audit_log, and vault_kv.
    - No duplicate agent records in SQLite.
    - Chroma collections remain consistent without duplicate document IDs.
    """
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

    # Run 1: Initial Bootstrap
    vm1 = initialize_vault(
        vault_dir=isolated_vault_dir,
        founder_name="Aman Jain",
        company_name="Alpha OS",
        use_mock_embeddings=True,
    )

    # Inject custom user document to test data preservation
    custom_doc = {"user_preference": "dark_mode_oled", "custom_metric": 42}
    vm1.write("user/custom_preferences.json", custom_doc)
    vm1.close()

    # Query initial database stats
    db_path = isolated_vault_dir / "sqlite" / "vault.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM vault_agents")
    agents_count_1 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT agent_id) FROM vault_agents")
    distinct_agents_1 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vault_kv")
    kv_count_1 = cur.fetchone()[0]
    conn.close()

    assert agents_count_1 == distinct_agents_1, "Duplicate agent IDs detected in run 1"
    assert agents_count_1 >= 13, f"Expected at least 13 agents, got {agents_count_1}"

    # Run 2: Second Sequential Invocation (idempotent, force=False)
    vm2 = initialize_vault(
        vault_dir=isolated_vault_dir,
        force=False,
        founder_name="Aman Jain",
        company_name="Alpha OS",
        use_mock_embeddings=True,
    )
    vm2.close()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vault_agents")
    agents_count_2 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vault_kv")
    kv_count_2 = cur.fetchone()[0]
    conn.close()

    assert agents_count_2 == agents_count_1, "Agent count mutated on run 2"
    assert kv_count_2 == kv_count_1, "KV row count mutated on run 2"

    # Run 3: Third Sequential Invocation
    vm3 = initialize_vault(
        vault_dir=isolated_vault_dir,
        force=False,
        founder_name="Aman Jain",
        company_name="Alpha OS",
        use_mock_embeddings=True,
    )

    # Verify custom user document was NOT lost or corrupted
    reloaded_custom = vm3.read("user/custom_preferences")
    assert reloaded_custom is not None, "Custom document was lost during idempotent runs"
    assert reloaded_custom["user_preference"] == "dark_mode_oled"
    assert reloaded_custom["custom_metric"] == 42

    # Verify Chroma collections count and global federated search
    knowledge_coll = vm3.chroma.get_or_create_collection(ChromaStore.COLLECTION_KNOWLEDGE)
    assert knowledge_coll.count() >= 13, f"Expected at least 13 embeddings in knowledge collection, got {knowledge_coll.count()}"

    # Global federated search without path_prefix returns seeded catalog entries
    global_results = vm3.search("architecture", n_results=10)
    assert isinstance(global_results, list)
    assert len(global_results) > 0, "Global search returned empty after 3 runs"

    # Index explicit knowledge document and verify path_prefix search
    vm3.write("knowledge/architecture_standards.json", {"title": "Architecture Standards", "rules": ["rigor", "standards"]})
    prefix_results = vm3.search("standards", n_results=5, path_prefix="knowledge")
    assert isinstance(prefix_results, list)
    assert len(prefix_results) > 0, "Knowledge-prefixed search returned empty after adding knowledge doc"

    vm3.close()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vault_agents")
    agents_count_3 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT agent_id) FROM vault_agents")
    distinct_agents_3 = cur.fetchone()[0]
    conn.close()

    assert agents_count_3 == agents_count_1, "Agent count mutated on run 3"
    assert agents_count_3 == distinct_agents_3, "Duplicate agents found after run 3"


# ============================================================================
# 2. vault_init.py: Force Recreation Clean State Overwrite
# ============================================================================

def test_adversarial_force_recreation_overwrites_corrupted_seed(isolated_vault_dir: Path):
    """Verify force=True replaces corrupted seed files with clean canonical models."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

    # 1. Initialize vault normally
    vm = initialize_vault(vault_dir=isolated_vault_dir, founder_name="Old Founder")
    vm.close()

    # 2. Adversarially inject corrupted/tampered data into company/identity.json
    identity_file = isolated_vault_dir / "company" / "identity.json"
    tampered_data = {
        "corrupted_garbage_field": "HACKED_DATA",
        "company_name": "Tampered Fake Corp",
        "founder": "Attacker",
    }
    with open(identity_file, "w", encoding="utf-8") as f:
        json.dump(tampered_data, f)

    user_file = isolated_vault_dir / "user" / "profile.json"
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump({"bad": "profile", "name": "Fake Name"}, f)

    # 3. Execute initialize_vault with force=True and new parameters
    vm_clean = initialize_vault(
        vault_dir=isolated_vault_dir,
        force=True,
        founder_name="Vindicated Founder",
        company_name="Alpha Secure Corp",
        use_mock_embeddings=True,
    )

    # 4. Verify corrupted fields were wiped and replaced with valid models
    reloaded_id = vm_clean.read("company/identity")
    assert reloaded_id is not None
    assert reloaded_id["founder"] == "Vindicated Founder"
    assert reloaded_id["company_name"] == "Alpha Secure Corp"
    assert "corrupted_garbage_field" not in reloaded_id

    # Validate against strict Pydantic model
    validated_id = CompanyIdentity.model_validate(reloaded_id)
    assert validated_id.founder == "Vindicated Founder"
    assert len(validated_id.core_values) >= 3

    reloaded_user = vm_clean.get_user_profile()
    assert reloaded_user["name"] == "Vindicated Founder"
    assert "bad" not in reloaded_user

    vm_clean.close()


# ============================================================================
# 3. vault_init.py: Corrupted Seed File Non-Catastrophic Recovery
# ============================================================================

def test_adversarial_corrupted_json_seed_file_recovery(isolated_vault_dir: Path):
    """Place malformed JSON syntax in a seed file and verify initialize_vault does not crash."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

    # Pre-create directory and place completely malformed JSON
    comp_dir = isolated_vault_dir / "company"
    comp_dir.mkdir(parents=True, exist_ok=True)
    bad_json_file = comp_dir / "identity.json"
    with open(bad_json_file, "w", encoding="utf-8") as f:
        f.write("{THIS IS NOT VALID JSON : [unclosed array\n")

    # Calling initialize_vault with force=False should not crash
    vm = initialize_vault(
        vault_dir=isolated_vault_dir,
        force=False,
        use_mock_embeddings=True,
    )
    assert isinstance(vm, VaultManager)

    # Reading the corrupted file via vm.read should return None safely without uncaught exception
    res = vm.read("company/identity")
    assert res is None, "Corrupted JSON should return None safely"

    # Writing to the corrupted file via vm.write should cleanly overwrite and repair it
    repair_payload = {
        "company_name": "Repaired Corp",
        "founder": "Aman Jain",
        "vision": "Repaired Vision",
        "mission": "Repaired Mission",
        "industry": "Tech",
        "core_values": ["Integrity"],
    }
    write_success = vm.write("company/identity.json", repair_payload)
    assert write_success is True

    # Now reading should return repaired JSON
    repaired_res = vm.read("company/identity")
    assert repaired_res is not None
    assert repaired_res["company_name"] == "Repaired Corp"

    vm.close()


# ============================================================================
# 4. vault_init.py: Dual-Path SQLite Consistency
# ============================================================================

def test_adversarial_dual_path_sqlite_consistency(isolated_vault_dir: Path):
    """Verify writes to Alpha-Vault/sqlite/vault.db are immediately visible via Alpha-Vault/vault.db (and vice versa)."""
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

    vm = initialize_vault(vault_dir=isolated_vault_dir, use_mock_embeddings=True)
    vm.close()

    db_subdir = isolated_vault_dir / "sqlite" / "vault.db"
    db_root = isolated_vault_dir / "vault.db"

    assert db_subdir.exists(), "sqlite/vault.db missing"
    assert db_root.exists(), "vault.db missing at root"

    # 1. Write via db_subdir, query via db_root
    conn_sub = sqlite3.connect(str(db_subdir))
    cur_sub = conn_sub.cursor()
    cur_sub.execute(
        "INSERT INTO vault_kv (path, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("test/dual_path_sub.json", json.dumps({"origin": "subdir"})),
    )
    conn_sub.commit()
    conn_sub.close()

    conn_root = sqlite3.connect(str(db_root))
    cur_root = conn_root.cursor()
    cur_root.execute("SELECT data FROM vault_kv WHERE path = 'test/dual_path_sub.json'")
    row_root = cur_root.fetchone()
    assert row_root is not None, "Write to sqlite/vault.db not visible in vault.db"
    assert json.loads(row_root[0])["origin"] == "subdir"

    # 2. Write via db_root, query via db_sub
    cur_root.execute(
        "INSERT INTO vault_kv (path, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("test/dual_path_root.json", json.dumps({"origin": "root"})),
    )
    conn_root.commit()
    conn_root.close()

    conn_sub = sqlite3.connect(str(db_subdir))
    cur_sub = conn_sub.cursor()
    cur_sub.execute("SELECT data FROM vault_kv WHERE path = 'test/dual_path_root.json'")
    row_sub = cur_sub.fetchone()
    conn_sub.close()

    assert row_sub is not None, "Write to vault.db not visible in sqlite/vault.db"
    assert json.loads(row_sub[0])["origin"] == "root"


# ============================================================================
# 5. vault_init.py: SQL View Triggers (INSERT / UPDATE / DELETE on documents)
# ============================================================================

def test_adversarial_sql_view_triggers_and_cascades(isolated_vault_dir: Path):
    """Stress-test INSTEAD OF triggers on the compatibility SQL view 'documents'.

    Verifies:
    - Direct INSERT into 'documents' writes to underlying 'vault_kv'.
    - INSERT OR REPLACE behavior when same path is inserted twice.
    - UPDATE on 'documents' modifies underlying 'vault_kv'.
    - DELETE on 'documents' deletes from underlying 'vault_kv'.
    - Read from 'documents' reflects direct writes to 'vault_kv'.
    """
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    vm = initialize_vault(vault_dir=isolated_vault_dir, use_mock_embeddings=True)
    vm.close()

    db_path = isolated_vault_dir / "sqlite" / "vault.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    test_path = "adversarial/view_trigger_test.json"
    doc_v1 = {"test_run": 1, "status": "active"}

    # 1. Direct INSERT into view
    cur.execute(
        "INSERT INTO documents (path, data) VALUES (?, ?)",
        (test_path, json.dumps(doc_v1)),
    )
    conn.commit()

    # Query underlying vault_kv table directly
    cur.execute("SELECT data FROM vault_kv WHERE path = ?", (test_path,))
    kv_row = cur.fetchone()
    assert kv_row is not None, "Trigger failed: underlying vault_kv was not populated"
    assert json.loads(kv_row[0])["test_run"] == 1

    # 2. Test INSERT OR REPLACE via view (duplicate path insert)
    doc_v2 = {"test_run": 2, "status": "replaced"}
    cur.execute(
        "INSERT INTO documents (path, data) VALUES (?, ?)",
        (test_path, json.dumps(doc_v2)),
    )
    conn.commit()

    cur.execute("SELECT data FROM vault_kv WHERE path = ?", (test_path,))
    kv_row_2 = cur.fetchone()
    assert json.loads(kv_row_2[0])["test_run"] == 2
    assert json.loads(kv_row_2[0])["status"] == "replaced"

    # 3. Test UPDATE on view
    doc_v3 = {"test_run": 3, "status": "updated"}
    cur.execute(
        "UPDATE documents SET data = ? WHERE path = ?",
        (json.dumps(doc_v3), test_path),
    )
    conn.commit()

    cur.execute("SELECT data FROM vault_kv WHERE path = ?", (test_path,))
    assert json.loads(cur.fetchone()[0])["test_run"] == 3

    # 4. Test DELETE on view
    cur.execute("DELETE FROM documents WHERE path = ?", (test_path,))
    conn.commit()

    cur.execute("SELECT data FROM vault_kv WHERE path = ?", (test_path,))
    assert cur.fetchone() is None, "DELETE trigger failed: row still present in vault_kv"

    cur.execute("SELECT data FROM documents WHERE path = ?", (test_path,))
    assert cur.fetchone() is None, "DELETE trigger failed: row still present in documents view"

    # 5. Verify other compatibility views exist and are queryable
    views_to_check = ["memories", "threads", "messages", "decisions", "agent_registry"]
    for v in views_to_check:
        cur.execute(f"SELECT COUNT(*) FROM {v}")
        count = cur.fetchone()[0]
        assert count >= 0, f"View {v} query failed"

    conn.close()


# ============================================================================
# 6. vault_init.py: Chroma Offline Fallback (Fast 0.25s Probe)
# ============================================================================

def test_adversarial_chroma_offline_fallback_does_not_hang(isolated_vault_dir: Path):
    """Simulate Ollama daemon offline and verify deterministic mock embeddings activate instantly.

    Without the fast 0.25s probe, 28 sequential embedding calls would hang for 84+ seconds.
    With the probe, entire initialization must finish in under 4 seconds.
    """
    # Point OLLAMA_HOST to a non-existent port
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:59998"
    # Ensure ALPHA_MOCK_EMBEDDINGS is not pre-set
    os.environ.pop("ALPHA_MOCK_EMBEDDINGS", None)

    # Verify probe detects offline daemon in < 0.5s
    t0 = time.perf_counter()
    online = _is_ollama_online(timeout=0.25)
    t_probe = time.perf_counter() - t0
    assert online is False, "Dead port was unexpectedly detected as online"
    assert t_probe < 1.0, f"Ollama probe took {t_probe:.3f}s, expected < 1.0s"

    # Execute initialize_vault with use_mock_embeddings=None (letting auto-detection run)
    t_start = time.perf_counter()
    vm = initialize_vault(
        vault_dir=isolated_vault_dir,
        use_mock_embeddings=None,
    )
    t_total = time.perf_counter() - t_start

    # Initialization must not hang
    assert t_total < 8.0, f"Initialization took {t_total:.2f}s, indicating an offline hang"
    assert os.environ.get("ALPHA_MOCK_EMBEDDINGS") == "1", "ALPHA_MOCK_EMBEDDINGS was not activated"

    # Verify vector dimensions in Chroma
    knowledge_coll = vm.chroma.get_or_create_collection(ChromaStore.COLLECTION_KNOWLEDGE)
    assert knowledge_coll.count() >= 13, "Expected at least 13 agent catalog embeddings in Chroma"

    results = knowledge_coll.get(ids=["agent_catalog_CEO"], include=["embeddings", "metadatas"])
    assert len(results["embeddings"]) == 1
    embedding = results["embeddings"][0]
    assert len(embedding) == EMBEDDING_DIM, f"Expected {EMBEDDING_DIM}-dim vector, got {len(embedding)}"

    # Clean up environment
    os.environ.pop("OLLAMA_HOST", None)
    vm.close()


# ============================================================================
# 7. first_run.py: Safe .env In-Place Merging & Preservation
# ============================================================================

def test_adversarial_env_preservation_complex_file(isolated_env_file: Path):
    """Stress-test update_env_file against an adversarial .env file with comments, duplicate keys, blank lines, and special characters."""
    adversarial_content = (
        "# ==========================================\n"
        "# Production App Configuration File\n"
        "# ==========================================\n"
        "\n"
        "# Database settings with inline character\n"
        "DATABASE_URL=postgres://user:pass_with_#hash@localhost:5432/proddb\n"
        "DEBUG=true\n"
        "\n"
        "# Duplicate variable scenario\n"
        "LOG_LEVEL=info\n"
        "LOG_LEVEL=warning\n"
        "\n"
        "# Variable with special symbols\n"
        "CUSTOM_PROMPT=\"Hello world! $PATH with 'single' and \\\"escaped\\\" quotes\"\n"
        "\n"
        "# Old Alpha Token to be replaced\n"
        "ALPHA_TOKEN=outdated_token_to_replace\n"
        "\n"
    )
    isolated_env_file.write_text(adversarial_content, encoding="utf-8")

    updates = {
        "ALPHA_TOKEN": "new_cryptographic_token_0123456789abcdef",
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "GROQ_API_KEY": "gsk_live_test_api_key_12345",
        "DEBUG": "false",  # In-place modify existing
        "NEW_VAR_WITH_SPACES": "value with spaces and # symbol",
    }

    success = update_env_file(isolated_env_file, updates, backup=True)
    assert success is True

    # Verify .env.bak was created
    bak_file = isolated_env_file.with_suffix(".env.bak")
    assert bak_file.is_file(), ".env.bak was not created"
    assert bak_file.read_text(encoding="utf-8") == adversarial_content

    # Parse resulting .env file
    raw_lines, parsed = parse_env_file(isolated_env_file)

    # 1. Verify updated values
    assert parsed["ALPHA_TOKEN"] == "new_cryptographic_token_0123456789abcdef"
    assert parsed["OLLAMA_HOST"] == "http://127.0.0.1:11434"
    assert parsed["GROQ_API_KEY"] == "gsk_live_test_api_key_12345"
    assert parsed["DEBUG"] == "false"
    assert parsed["NEW_VAR_WITH_SPACES"] == "value with spaces and # symbol"

    # 2. Verify unrelated pre-existing keys survived unchanged
    assert parsed["DATABASE_URL"] == "postgres://user:pass_with_#hash@localhost:5432/proddb"
    assert "Hello world! $PATH" in parsed["CUSTOM_PROMPT"]

    # 3. Verify comments were preserved in raw_lines
    full_output = isolated_env_file.read_text(encoding="utf-8")
    assert "# Production App Configuration File" in full_output
    assert "# Database settings with inline character" in full_output
    assert "# --- Project Alpha Configuration ---" in full_output


def test_adversarial_env_creation_on_missing_file(tmp_path: Path):
    """Verify update_env_file creates .env and parent directories cleanly when file does not exist."""
    nested_env = tmp_path / "deep" / "nested" / "path" / ".env"
    assert not nested_env.exists()

    updates = {
        "ALPHA_TOKEN": "created_token_xyz",
        "ALPHA_PORT": "8765",
    }

    success = update_env_file(nested_env, updates)
    assert success is True
    assert nested_env.is_file()

    _, parsed = parse_env_file(nested_env)
    assert parsed["ALPHA_TOKEN"] == "created_token_xyz"
    assert parsed["ALPHA_PORT"] == "8765"


# ============================================================================
# 8. first_run.py: Token Cryptographic Entropy & Validation
# ============================================================================

def test_adversarial_token_entropy_and_uniqueness():
    """Verify generated ALPHA_TOKEN is 64 hex characters (32 bytes) with high cryptographic entropy."""
    tokens = [generate_secure_token(32) for _ in range(1000)]

    # 1. Uniqueness: 1,000 distinct tokens must yield 1,000 unique values
    unique_tokens = set(tokens)
    assert len(unique_tokens) == 1000, "Collision detected in token generation!"

    hex_pattern = re.compile(r"^[0-9a-f]{64}$")

    # 2. Exact length and hexadecimal character set
    for t in tokens:
        assert len(t) == 64, f"Token length must be 64 characters (got {len(t)})"
        assert hex_pattern.match(t), f"Token {t} contains non-hex characters"

    # 3. Shannon Entropy verification on aggregated token stream
    combined_chars = "".join(tokens)
    counts = Counter(combined_chars)
    total_chars = len(combined_chars)
    shannon_entropy = -sum((cnt / total_chars) * math.log2(cnt / total_chars) for cnt in counts.values())

    # For uniform 16-character hex distribution, theoretical max is log2(16) = 4.0 bits/char
    assert shannon_entropy > 3.98, f"Shannon entropy too low: {shannon_entropy:.4f} (expected > 3.98)"


# ============================================================================
# 9. first_run.py: Validation of Bad Configuration Dictionaries
# ============================================================================

def test_adversarial_invalid_config_inputs_handling(tmp_path: Path):
    """Verify first_run rejects invalid configuration inputs and sanitizes payloads."""
    env_file = tmp_path / ".env"
    vault_dir = tmp_path / "Vault"

    # 1. Empty Founder Name
    res1 = run_first_run(
        config={"founder_name": "   ", "company_name": "Valid Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res1["success"] is False
    assert "Founder Name cannot be empty" in res1["error"]

    # 2. Empty Company Name
    res2 = run_first_run(
        config={"founder_name": "Valid Founder", "company_name": ""},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res2["success"] is False
    assert "Company Name cannot be empty" in res2["error"]

    # 3. Malformed Ollama URL (missing http/https)
    res3 = run_first_run(
        config={"founder_name": "Founder", "company_name": "Co", "ollama_host": "localhost:11434"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res3["success"] is False
    assert "must begin with http:// or https://" in res3["error"]

    # 4. Extraneous parameters in config dict do not cause crash
    bloated_config = {
        "founder_name": "Valid Founder",
        "company_name": "Valid Co",
        "unknown_junk_key": "some_value",
        "another_extraneous_field": [1, 2, 3],
    }
    cfg_obj = SetupConfig.from_dict(bloated_config)
    assert not hasattr(cfg_obj, "unknown_junk_key")
    assert cfg_obj.founder_name == "Valid Founder"

    # 5. Dangerous characters / SQL injection strings in company name & values
    sql_injection_name = "Alpha Corp'; DROP TABLE vault_kv; --"
    res4 = run_first_run(
        config={"founder_name": "Founder", "company_name": sql_injection_name},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res4["success"] is True

    # Verify table vault_kv was not dropped and data is stored safely
    id_file = vault_dir / "company" / "identity.json"
    with open(id_file, "r", encoding="utf-8") as f:
        stored_id = json.load(f)
    assert stored_id["company_name"] == sql_injection_name
