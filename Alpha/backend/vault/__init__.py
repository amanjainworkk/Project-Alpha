"""Project Alpha — Vault Subsystem.

Persistent institutional memory, dual-paradigm SQLite (KV & Relational),
ChromaDB semantic vector storage, and VaultManager facade.
"""

from .chroma_store import ChromaStore
from .embeddings import embed_batch, embed_text
from .schemas import (
    AgentProfile,
    AgentStatus,
    AssignedModel,
    AuditStatus,
    CompanyIdentity,
    EpisodicMemory,
    MemoryEntry,
    MemoryType,
    OutputPreferences,
    ProjectManifest,
    ProjectPriority,
    ProjectStatus,
    ThreadMessage,
    ThreadMessageType,
    UserProfile,
)
from .sqlite_store import SQLiteStore
from .vault_manager import AccessDeniedError, VaultManager

__all__ = [
    "AccessDeniedError",
    "AgentProfile",
    "AgentStatus",
    "AssignedModel",
    "AuditStatus",
    "ChromaStore",
    "CompanyIdentity",
    "EpisodicMemory",
    "MemoryEntry",
    "MemoryType",
    "OutputPreferences",
    "ProjectManifest",
    "ProjectPriority",
    "ProjectStatus",
    "SQLiteStore",
    "ThreadMessage",
    "ThreadMessageType",
    "UserProfile",
    "VaultManager",
    "embed_batch",
    "embed_text",
]
