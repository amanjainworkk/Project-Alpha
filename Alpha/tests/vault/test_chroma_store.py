"""tests/vault/test_chroma_store.py - Tests for ChromaStore vector store."""

import gc
from pathlib import Path
import pytest

from backend.vault.chroma_store import ChromaStore


def test_chroma_init_creates_persistent_directory(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    assert Path(temp_chroma_dir).exists()
    assert (Path(temp_chroma_dir) / "chroma.sqlite3").exists()


def test_chroma_get_or_create_collection_idempotent(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    c1 = store.get_or_create_collection("vault_knowledge")
    c2 = store.get_or_create_collection("vault_knowledge")
    assert c1.name == c2.name
    assert "vault_knowledge" in store.list_collections()


def test_chroma_add_single_document(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    success = store.add(
        collection_name="vault_knowledge",
        id="doc-1",
        text="SQLite storage engine architecture and indexing.",
        metadata={"type": "spec", "tags": ["sqlite", "storage"]},
    )
    assert success is True
    assert store.count("vault_knowledge") == 1


def test_chroma_upsert_on_duplicate_id(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("vault_knowledge", id="doc-1", text="Initial architecture draft.")
    assert store.count("vault_knowledge") == 1

    store.add("vault_knowledge", id="doc-1", text="Updated architecture draft with WAL mode.")
    assert store.count("vault_knowledge") == 1

    hits = store.search("vault_knowledge", query="WAL mode architecture", top_k=1)
    assert len(hits) == 1
    assert "WAL mode" in hits[0]["document"]


def test_chroma_semantic_ranking_relevance(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("vault_knowledge", id="doc-api", text="FastAPI REST API routes and endpoints.")
    store.add("vault_knowledge", id="doc-ui", text="Flutter Mobile Canvas UI CustomPainter rendering.")
    store.add("vault_knowledge", id="doc-db", text="SQLite index optimization and relational foreign keys.")

    results = store.search("vault_knowledge", query="Flutter Mobile Canvas UI", top_k=3)
    assert len(results) == 3
    assert results[0]["id"] == "doc-ui"
    assert results[0]["distance"] < results[1]["distance"]


def test_chroma_search_with_metadata_filter(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("projects_semantic", id="p1-task", text="Python backend task", metadata={"project_id": "p1"})
    store.add("projects_semantic", id="p2-task", text="Python backend task", metadata={"project_id": "p2"})

    results = store.search("projects_semantic", query="Python backend", top_k=5, where={"project_id": "p1"})
    assert len(results) == 1
    assert results[0]["id"] == "p1-task"
    assert results[0]["metadata"]["project_id"] == "p1"


def test_chroma_search_empty_collection(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    results = store.search("empty_coll", query="any query", top_k=5)
    assert results == []


def test_chroma_search_top_k_exceeds_collection_size(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("vault_knowledge", id="doc-1", text="First doc")
    store.add("vault_knowledge", id="doc-2", text="Second doc")

    results = store.search("vault_knowledge", query="doc", top_k=10)
    assert len(results) == 2


def test_chroma_delete_document_by_id(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("vault_knowledge", id="doc-1", text="To be deleted")
    assert store.count("vault_knowledge") == 1

    assert store.delete("vault_knowledge", "doc-1") is True
    assert store.count("vault_knowledge") == 0
    assert store.search("vault_knowledge", query="deleted", top_k=5) == []


def test_chroma_delete_collection(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("temp_coll", id="d1", text="Sample")
    assert "temp_coll" in store.list_collections()

    assert store.delete_collection("temp_coll") is True
    assert "temp_coll" not in store.list_collections()


def test_chroma_partitioned_agent_memory_isolation(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("agent_memory_CEO", id="mem-ceo-1", text="Decision on company vision and leadership.")

    res_ceo = store.search("agent_memory_CEO", query="leadership", top_k=5)
    assert len(res_ceo) == 1
    assert res_ceo[0]["id"] == "mem-ceo-1"

    res_cto = store.search("agent_memory_CTO", query="leadership", top_k=5)
    assert len(res_cto) == 0


def test_chroma_persistence_across_reconnect(temp_chroma_dir: str) -> None:
    store1 = ChromaStore(temp_chroma_dir)
    for i in range(5):
        store1.add("vault_knowledge", id=f"doc-{i}", text=f"Document content {i}")
    assert store1.count("vault_knowledge") == 5

    del store1
    gc.collect()

    store2 = ChromaStore(temp_chroma_dir)
    assert store2.count("vault_knowledge") == 5
    hits = store2.search("vault_knowledge", query="Document content 3", top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "doc-3"


def test_chroma_sanitize_metadata_complex_types(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    complex_meta = {
        "title": "Complex",
        "count": 10,
        "ratio": 0.95,
        "flag": True,
        "null_val": None,
        "tags": ["alpha", "beta"],
        "nested": {"k": "v"},
    }
    sanitized = store._sanitize_metadata(complex_meta)
    assert sanitized["title"] == "Complex"
    assert sanitized["count"] == 10
    assert sanitized["ratio"] == 0.95
    assert sanitized["flag"] is True
    assert "null_val" not in sanitized
    assert isinstance(sanitized["tags"], str)
    assert isinstance(sanitized["nested"], str)


def test_chroma_delete_nonexistent_collection(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    # Deleting non-existent collection returns False
    res = store.delete_collection("nonexistent_collection_xyz")
    assert res is False


def test_chroma_reset(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    store.add("reset_coll", id="d1", text="Text to reset")
    assert "reset_coll" in store.list_collections()
    store.reset()


def test_chroma_add_without_metadata_and_empty_sanitize(temp_chroma_dir: str) -> None:
    store = ChromaStore(temp_chroma_dir)
    assert store._sanitize_metadata(None) == {}
    assert store.add("no_meta_coll", id="nm-1", text="Text without metadata", metadata=None) is True
    hits = store.search("no_meta_coll", query="without metadata", top_k=1)
    assert len(hits) == 1


def test_chroma_store_type_hints_resolvable() -> None:
    """Verify that type annotations on ChromaStore methods resolve without NameError.

    Guards against missing imports (e.g., Union) in annotations evaluated dynamically
    by typing.get_type_hints(), FastAPI reflection, or Pydantic inspection.
    """
    import typing

    # Test method with complex return type Dict[str, Union[str, int, float, bool]]
    hints = typing.get_type_hints(ChromaStore._sanitize_metadata)
    assert "return" in hints
    assert "metadata" in hints

    # Test class-level type hint resolution
    class_hints = typing.get_type_hints(ChromaStore.get_or_create_collection)
    assert "return" in class_hints



