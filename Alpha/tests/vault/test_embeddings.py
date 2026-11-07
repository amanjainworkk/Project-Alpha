"""tests/vault/test_embeddings.py - Tests for Ollama nomic-embed-text wrapper and fallback."""

import math
import os
import pytest

from backend.vault.embeddings import EMBEDDING_DIM, _deterministic_mock_embed, embed_batch, embed_text


def test_embed_text_dimension_strict_768() -> None:
    vec = embed_text("Project Alpha Vault Storage Architecture")
    assert len(vec) == 768
    assert all(isinstance(x, float) for x in vec)


def test_embed_text_l2_normalization() -> None:
    vec = embed_text("L2 normalization verification for embeddings")
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_embed_text_determinism() -> None:
    text = "Autonomous Agent C-Suite Tri-Framework Orchestration"
    v1 = embed_text(text)
    v2 = embed_text(text)
    assert v1 == v2


def test_embed_text_empty_string_handling() -> None:
    for empty_input in ("", "   ", "\n\t"):
        vec = embed_text(empty_input)
        assert len(vec) == 768
        norm = math.sqrt(sum(x * x for x in vec))
        assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_embed_text_long_context_truncation() -> None:
    long_text = "Executive autonomous intelligence " * 2000
    vec = embed_text(long_text)
    assert len(vec) == 768
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_embed_text_ollama_daemon_down_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure ALPHA_MOCK_EMBEDDINGS is not set
    monkeypatch.delenv("ALPHA_MOCK_EMBEDDINGS", raising=False)
    # Point OLLAMA_HOST to a non-existent port to simulate offline daemon
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:59999")

    vec = embed_text("Fallback trigger text")
    assert len(vec) == 768
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_embed_batch() -> None:
    texts = ["Document one", "Document two", "Document three"]
    vectors = embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 768
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, rel_tol=1e-3)
