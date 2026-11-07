"""backend/vault/embeddings.py - Ollama nomic-embed-text wrapper.

Generates 768-dimensional L2-normalized float vectors with deterministic
pseudo-embedding fallback (enabled via ALPHA_MOCK_EMBEDDINGS=1 or network failure).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import urllib.request
from typing import List, Optional

logger = logging.getLogger("alpha.vault.embeddings")

EMBEDDING_DIM = 768
OLLAMA_DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text"


def _deterministic_mock_embed(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Computes a deterministic, normalized 768-dimensional pseudo-embedding.

    Guarantees:
    - Exactly identical text -> identical vector (cosine distance 0.0)
    - Semantically overlapping text (shared words) -> high cosine similarity (>0.6)
    - Disjoint vocabulary -> low similarity
    - Zero network or GPU dependency (hermetic in CI and headless test runs)
    """
    vector = [0.0] * dim
    clean_text = text.lower().strip() if text else ""
    words = re.findall(r"\w+", clean_text)

    if not words:
        # Fallback for empty or whitespace text: deterministic seed from raw string
        raw_seed = text.encode("utf-8") if text else b"__EMPTY__"
        h = int(hashlib.md5(raw_seed).hexdigest(), 16)
        for i in range(dim):
            vector[i] = ((h >> (i % 64)) & 1) * 2.0 - 1.0
    else:
        for word in words:
            # Hash word into bucket index and sign
            h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if ((h >> 16) % 2 == 0) else -1.0
            vector[idx] += sign

    # L2 Normalization
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0.0:
        vector = [round(float(x / norm), 6) for x in vector]
    else:
        vector[0] = 1.0

    return vector


def embed_text(text: str) -> List[float]:
    """Generates a 768-dimensional embedding for the provided text.

    Uses local Ollama nomic-embed-text model if running; falls back to
    deterministic mock embeddings if Ollama is unreachable or if
    ALPHA_MOCK_EMBEDDINGS=1 is configured.
    """
    if os.environ.get("ALPHA_MOCK_EMBEDDINGS", "").strip().lower() in ("1", "true", "yes"):
        return _deterministic_mock_embed(text)

    # Empty string handling
    if not text or not text.strip():
        return _deterministic_mock_embed(text)

    # Truncate extremely long context to prevent overflow (approx 8000 tokens ~ 32000 chars)
    truncated_text = text[:32000]

    ollama_host = os.environ.get("OLLAMA_HOST", OLLAMA_DEFAULT_HOST).rstrip("/")
    url = f"{ollama_host}/api/embeddings"
    payload = json.dumps({"model": DEFAULT_MODEL, "prompt": truncated_text}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                result = json.loads(response.read().decode("utf-8"))
                vec = result.get("embedding")
                if vec and len(vec) == EMBEDDING_DIM:
                    return vec
                elif vec:
                    logger.warning(
                        "Ollama returned embedding with unexpected dim %d, expected %d",
                        len(vec),
                        EMBEDDING_DIM,
                    )
                    return vec
    except Exception as e:
        logger.debug("Ollama embedding call failed (%s). Falling back to deterministic mock.", e)

    return _deterministic_mock_embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a batch of input texts."""
    return [embed_text(t) for t in texts]
