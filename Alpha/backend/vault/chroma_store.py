"""backend/vault/chroma_store.py - ChromaDB Vector Store Wrapper for Alpha's Vault.

Provides persistent local semantic vector search partitioned across collections:
- vault_knowledge: cross-cutting tech decisions, brand guidelines, etc.
- projects_semantic: goals, briefs, deliverables, and final outputs
- agent_memory_{agent_id}: per-agent semantic episodic recall
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from backend.vault.embeddings import embed_text

logger = logging.getLogger("alpha.vault.chroma_store")


class ChromaStore:
    """Persistent ChromaDB vector store managing partitioned collections."""

    COLLECTION_KNOWLEDGE = "vault_knowledge"
    COLLECTION_PROJECTS = "projects_semantic"
    COLLECTION_AGENT_MEMORY_PREFIX = "agent_memory_"

    def __init__(self, persist_dir: str = "Alpha-Vault/chroma"):
        self.persist_dir = persist_dir
        os.makedirs(os.path.abspath(self.persist_dir), exist_ok=True)
        self.client: ClientAPI = chromadb.PersistentClient(path=self.persist_dir)

    def get_or_create_collection(
        self, collection_name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Collection:
        """Retrieves or initializes a collection configured with cosine distance."""
        meta = metadata or {"hnsw:space": "cosine"}
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata=meta,
        )

    def _sanitize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Union[str, int, float, bool]]:
        """Flattens complex types into JSON strings to conform to ChromaDB's primitive constraint.
        Strips None values.
        """
        if not metadata:
            return {}
        sanitized: Dict[str, Any] = {}
        for k, v in metadata.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
            elif isinstance(v, (list, dict)):
                sanitized[k] = json.dumps(v, ensure_ascii=False)
            else:
                sanitized[k] = str(v)
        return sanitized

    def add(
        self,
        collection_name: str,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> bool:
        """Inserts or updates a document vector in the specified collection.
        Computes embedding via embed_text if not explicitly supplied.
        """
        try:
            col = self.get_or_create_collection(collection_name)
            vec = embedding if embedding is not None else embed_text(text)
            clean_meta = self._sanitize_metadata(metadata)

            col.upsert(
                ids=[id],
                documents=[text],
                embeddings=[vec],
                metadatas=[clean_meta] if clean_meta else None,
            )
            return True
        except Exception as e:
            logger.error("Failed to add document %s to collection %s: %s", id, collection_name, e)
            raise

    def search(
        self,
        collection_name: str,
        query: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Executes semantic vector search and flattens Chroma result envelope.
        Returns empty list if collection is empty or has no matches.
        """
        try:
            col = self.get_or_create_collection(collection_name)
            count = col.count()
            if count == 0:
                return []

            actual_k = min(top_k, count)
            vec = query_embedding
            if vec is None and query is not None:
                vec = embed_text(query)

            if vec is None:
                raise ValueError("Either query string or query_embedding must be provided.")

            results = col.query(
                query_embeddings=[vec],
                n_results=actual_k,
                where=where if where else None,
            )

            hits: List[Dict[str, Any]] = []
            if not results or not results.get("ids") or not results["ids"][0]:
                return hits

            ids = results["ids"][0]
            docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

            for item_id, doc, meta, dist in zip(ids, docs, metas, dists):
                parsed_meta = dict(meta) if meta else {}
                for mk, mv in parsed_meta.items():
                    if isinstance(mv, str) and (mv.startswith("{") or mv.startswith("[")):
                        try:
                            parsed_meta[mk] = json.loads(mv)
                        except Exception:
                            pass

                similarity = max(0.0, 1.0 - dist)
                hits.append({
                    "id": item_id,
                    "document": doc,
                    "metadata": parsed_meta,
                    "distance": dist,
                    "similarity": similarity,
                    "score": similarity,
                })

            return hits
        except Exception as e:
            logger.error("Search failed in collection %s: %s", collection_name, e)
            return []

    def delete(self, collection_name: str, id: str) -> bool:
        """Removes a document from the collection by ID."""
        try:
            col = self.get_or_create_collection(collection_name)
            col.delete(ids=[id])
            return True
        except Exception as e:
            logger.error("Failed to delete %s from %s: %s", id, collection_name, e)
            return False

    def count(self, collection_name: str) -> int:
        """Returns the number of documents in the collection."""
        col = self.get_or_create_collection(collection_name)
        return col.count()

    def list_collections(self) -> List[str]:
        """Lists all existing collection names."""
        return [c.name for c in self.client.list_collections()]

    def delete_collection(self, collection_name: str) -> bool:
        """Deletes an entire collection."""
        try:
            self.client.delete_collection(name=collection_name)
            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Resets the Chroma client database if supported."""
        try:
            self.client.reset()
        except Exception:
            pass
