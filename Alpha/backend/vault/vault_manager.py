"""backend/vault/vault_manager.py - Project Alpha Unified Vault Manager Facade.

Coordinates SQLiteStore (relational + KV) and ChromaStore (vector retrieval)
with strict RBAC access control, CAO confinement, atomic writes, and project lifecycle scaffolding.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from .chroma_store import ChromaStore
from .schemas import (
    AgentProfile,
    AssignedModel,
    AuditStatus,
    CompanyIdentity,
    EpisodicMemory,
    ProjectManifest,
    ProjectPriority,
    ProjectStatus,
    ThreadMessage,
    UserProfile,
)
from .sqlite_store import SQLiteStore

logger = logging.getLogger("alpha.vault.vault_manager")


class AccessDeniedError(PermissionError):
    """Raised when an agent attempts unauthorized write or traversal."""
    pass


class CorruptedVaultFileError(Exception):
    """Raised when a vault document is corrupted or malformed."""
    pass


def _normalize_fs_path(p: Union[str, Path]) -> Path:
    """Normalize Windows extended path prefixes (\\\\?\\ and \\\\?\\UNC\\) to standard paths."""
    s = str(p)
    if s.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + s[8:])
    elif s.startswith("\\\\?\\"):
        return Path(s[4:])
    return Path(s)


DEFAULT_EXECUTIVE_AGENTS: List[Dict[str, Any]] = [
    {"agent_id": "CEO", "agent_role": "Chief Executive Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Visionary, strategic, decisive", "jd_version": "1.0"},
    {"agent_id": "CTO", "agent_role": "Chief Technology Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Architectural, technical, rigorous", "jd_version": "1.0"},
    {"agent_id": "CMO", "agent_role": "Chief Marketing Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Growth-oriented, creative, analytical", "jd_version": "1.0"},
    {"agent_id": "CPO", "agent_role": "Chief Product Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "User-centric, pragmatic, prioritized", "jd_version": "1.0"},
    {"agent_id": "CDO", "agent_role": "Chief Design Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Aesthetic, meticulous, modern", "jd_version": "1.0"},
    {"agent_id": "CFO", "agent_role": "Chief Financial Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Frugal, quantitative, governed", "jd_version": "1.0"},
    {"agent_id": "COO", "agent_role": "Chief Operations Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Operational, process-driven, execution-focused", "jd_version": "1.0"},
    {"agent_id": "CHRO", "agent_role": "Chief Human Resources Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "People-oriented, culture-custodian, empathetic", "jd_version": "1.0"},
    {"agent_id": "CIO", "agent_role": "Chief Information Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Data custodian, security-conscious, structured", "jd_version": "1.0"},
    {"agent_id": "CSO", "agent_role": "Chief Strategy Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Long-term thinker, OKR-aligned, analytical", "jd_version": "1.0"},
    {"agent_id": "CLO", "agent_role": "Chief Legal Officer", "agent_model": "llama3.2", "agent_version": "1.0.0", "personality": "Risk-averse, compliant, protective", "jd_version": "1.0"},
    {"agent_id": "CAO", "agent_role": "Chief Audit Officer", "agent_model": "claude-3-5-sonnet", "agent_version": "1.0.0", "personality": "Uncompromising, objective, rigorous", "jd_version": "1.0"},
    {"agent_id": "CAO-Claude", "agent_role": "Chief Audit Officer (Claude)", "agent_model": "claude-3-5-sonnet", "agent_version": "1.0.0", "personality": "Independent auditor, 5-axis compliance", "jd_version": "1.0"},
    {"agent_id": "CAO-ChatGPT", "agent_role": "Chief Audit Officer (ChatGPT)", "agent_model": "gpt-4o", "agent_version": "1.0.0", "personality": "Independent auditor, code verification", "jd_version": "1.0"},
]


class VaultManager:
    """Unified Facade integrating SQLiteStore and ChromaStore for Project Alpha."""

    def __init__(
        self,
        vault_root: Optional[Union[str, Path]] = None,
        db_path: Optional[str] = None,
        chroma_path: Optional[str] = None,
    ):
        if vault_root is None:
            self.vault_root = _normalize_fs_path(
                Path(__file__).resolve().parent.parent.parent / "Alpha-Vault"
            )
        else:
            self.vault_root = _normalize_fs_path(Path(vault_root).resolve())

        self.db_path = db_path or str(self.vault_root / "vault.db")
        self.chroma_path = chroma_path or str(self.vault_root / "chroma")

        self.sqlite = SQLiteStore(self.db_path)
        self.chroma = ChromaStore(self.chroma_path)

        self.initialize()

    def initialize(self) -> bool:
        """Create canonical directory skeleton if not already present and auto-seed default agents."""
        try:
            for sub in ["company", "agents", "projects", "knowledge", "user", "backups"]:
                (self.vault_root / sub).mkdir(parents=True, exist_ok=True)
            self._seed_default_agents()
            return True
        except Exception as e:
            logger.error("Failed to initialize vault directory structure: %s", e)
            return False

    def _seed_default_agents(self) -> None:
        """Seed default executive agents into vault_agents to satisfy foreign key constraints."""
        for agent in DEFAULT_EXECUTIVE_AGENTS:
            try:
                self.sqlite.upsert_agent(agent)
            except Exception as e:
                logger.warning("Could not auto-seed agent %s: %s", agent.get("agent_id"), e)

    def _ensure_agent_exists(self, agent_id: str) -> None:
        """Ensure agent exists in vault_agents to satisfy foreign key constraints."""
        if not self.sqlite.get_agent(agent_id):
            self.sqlite.upsert_agent({
                "agent_id": agent_id,
                "agent_role": agent_id,
                "agent_model": "llama3.2",
                "agent_version": "1.0.0",
                "is_active": True,
                "personality": f"Dynamic agent {agent_id}",
                "jd_version": "1.0",
            })

    # ========================================================================
    # Path Sanitization & Access Control
    # ========================================================================

    def _normalize_path(self, path: str) -> str:
        """Canonicalize path string, collapsing relative segments ('..'),
        rejecting null bytes, ensuring the path stays strictly within vault_root,
        and returning a normalized relative POSIX path.
        """
        if not isinstance(path, str):
            raise AccessDeniedError(f"Path must be a string, got {type(path).__name__}")
        if "\x00" in path or "\0" in path:
            raise AccessDeniedError(f"Null byte detected in path: {repr(path)}")

        cleaned = path.replace("\\", "/").strip()
        if not cleaned:
            raise AccessDeniedError("Empty path is not allowed.")

        clean_root = _normalize_fs_path(self.vault_root)

        raw_path = Path(cleaned)
        if raw_path.is_absolute() or (len(cleaned) >= 2 and cleaned[1] == ":"):
            resolved = _normalize_fs_path(raw_path.resolve())
        else:
            rel_candidate = cleaned.lstrip("/")
            resolved = _normalize_fs_path((clean_root / rel_candidate).resolve())

        try:
            rel = resolved.relative_to(clean_root)
        except ValueError:
            raise AccessDeniedError(f"Path traversal detected: {path} resolves outside vault root.")

        posix_rel = rel.as_posix()
        if posix_rel == ".":
            raise AccessDeniedError("Path resolving to vault root itself is not a valid document path.")
        return posix_rel

    def _get_fs_path(self, norm_path: str) -> Path:
        """Resolve filesystem path and defend against path traversal attacks.
        Normalizes Windows extended paths (\\\\?\\) to ensure relative_to validation never fails.
        """
        canonical_rel = self._normalize_path(norm_path)
        clean_root = _normalize_fs_path(self.vault_root)
        resolved = _normalize_fs_path((clean_root / canonical_rel).resolve())
        try:
            resolved.relative_to(clean_root)
        except ValueError:
            raise AccessDeniedError(f"Path traversal detected: {norm_path} resolves outside vault root.")
        return resolved

    def check_write_permission(self, agent_id: Optional[str], path: str) -> bool:
        """Enforce strict RBAC and CAO confinement rules.

        Rules:
        - agent_id is None or admin/system: Allow.
        - Path traversal attempts outside vault root: Raise AccessDeniedError / deny.
        - CAO agents (CAO, CAO-Claude, CAO-ChatGPT, CAO-C, CAO-G): ONLY allowed to write to
          projects/{project_id}/audit/*. All other writes DENIED.
        - System paths (backups/, vault.db, chroma/) protected from non-CIO/Admin writes.
        - Company identity writes restricted to Founder, CEO, CIO, or Admin.
        """
        if agent_id is None or agent_id.lower() in ("admin", "system", "setup", "founder"):
            return True

        try:
            norm = self._normalize_path(path)
        except AccessDeniedError:
            return False

        agent_upper = agent_id.upper()

        # 1. System path protection
        if norm.startswith("backups") or norm.endswith(".db") or norm.startswith("chroma"):
            if agent_upper not in ("CIO", "ADMIN"):
                logger.warning(
                    "Access Denied: Agent '%s' attempted write to protected system path '%s'",
                    agent_id,
                    norm,
                )
                return False

        # 2. CAO Confinement Check (Strict Read-Only outside projects/{id}/audit/*)
        if agent_upper.startswith("CAO"):
            parts = norm.split("/")
            if len(parts) >= 3 and parts[0] == "projects" and parts[2] == "audit":
                return True
            logger.warning(
                "Access Denied: CAO agent '%s' is read-only and restricted to projects/{id}/audit/ (attempted: %s)",
                agent_id,
                norm,
            )
            return False

        # 3. Company identity write protection
        if norm.startswith("company/identity"):
            if agent_upper not in ("CEO", "CIO", "ADMIN"):
                logger.warning("Access Denied: Agent '%s' cannot write to company/identity", agent_id)
                return False

        # 4. Role-specific domain checks
        if agent_upper == "CEO":
            return norm.startswith(("projects", "user", "company", "knowledge", "agents/CEO"))

        if agent_upper == "CHRO":
            return norm.startswith(("agents", "projects"))

        if agent_upper == "CIO":
            return norm.startswith(("knowledge", "agents", "backups", "company", "projects"))

        # Departmental deliverables and knowledge domains
        deliverable_map = {
            "CTO": ["deliverables/technical", "knowledge/tech_decisions", "knowledge/tech-decisions", "projects"],
            "CMO": ["deliverables/marketing", "knowledge/brand_guidelines", "knowledge/brand-guidelines", "projects"],
            "CPO": ["deliverables/product", "deliverables/prd", "knowledge", "projects"],
            "CDO": ["deliverables/design", "knowledge/design_system", "knowledge/design-system", "projects"],
            "CFO": ["deliverables/financial", "knowledge/financial_history", "knowledge/financial-history", "projects"],
            "COO": ["projects", "timelines"],
            "CLO": ["deliverables/legal", "knowledge/legal_registry", "knowledge/legal-registry", "projects"],
            "CSO": ["company/okrs", "deliverables/strategic_alignment", "deliverables/strategic-alignment", "projects"],
        }

        # Any agent can write to their own agent directory
        if norm.startswith(f"agents/{agent_id}") or norm.startswith(f"agents/{agent_upper}"):
            return True

        allowed_prefixes = deliverable_map.get(agent_upper, [])
        for prefix in allowed_prefixes:
            if prefix in norm:
                return True

        logger.warning("Access Denied: Agent '%s' lacks write permission for '%s'", agent_id, norm)
        return False

    # ========================================================================
    # Core Read / Write Facade
    # ========================================================================

    def read(self, path: str) -> Optional[Dict[str, Any]]:
        """Read structured document from Vault.
        Checks SQLite KV store first; falls back to disk file and hydrates cache.
        """
        if not path or not str(path).strip():
            return None
        norm = self._normalize_path(path)

        # 1. Check SQLite KV table
        data = self.sqlite.get(norm)
        if data is not None:
            return data

        # Check path variations (.json or without .json)
        if norm.endswith(".json"):
            bare = norm[:-5]
            data = self.sqlite.get(bare)
            if data is not None:
                return data
        else:
            data = self.sqlite.get(norm + ".json")
            if data is not None:
                return data

        # 2. Fallback to filesystem
        fs_path = self._get_fs_path(norm)
        if not fs_path.is_file() and not norm.endswith(".json"):
            fs_path = self._get_fs_path(norm + ".json")

        if fs_path.is_file():
            try:
                with open(fs_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                self.sqlite.set(norm, content)
                return content
            except json.JSONDecodeError as jde:
                logger.error("Corrupted JSON in file %s: %s", fs_path, jde)
                return None
            except Exception as e:
                logger.error("Error reading vault file %s: %s", fs_path, e)
                return None

        return None

    def write(self, path: str, data: Dict[str, Any], agent_id: Optional[str] = None) -> bool:
        """Write data to Vault with access control, schema validation, and atomic disk persistence."""
        norm = self._normalize_path(path)

        # 1. Enforce Access Control
        if not self.check_write_permission(agent_id, norm):
            if agent_id is not None:
                raise AccessDeniedError(
                    f"Agent '{agent_id}' denied write access to '{norm}'."
                )
            return False

        # 2. Schema Validation (Strict check on canonical documents)
        self._validate_schema_if_canonical(norm, data)

        # 3. Atomic Disk Persistence
        disk_path = self._get_fs_path(norm if norm.endswith((".json", ".md", ".jsonl")) else norm + ".json")
        disk_path.parent.mkdir(parents=True, exist_ok=True)

        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=str(disk_path.parent), delete=False, encoding="utf-8") as tf:
                temp_name = tf.name
                json.dump(data, tf, indent=2, ensure_ascii=False)

            # Atomic file replace with retry backoff for Windows NTFS lock contention
            max_retries = 5
            backoff_s = 0.02
            for attempt in range(max_retries):
                try:
                    os.replace(temp_name, str(disk_path))
                    temp_name = None
                    break
                except (PermissionError, OSError) as replace_err:
                    if attempt == max_retries - 1:
                        raise replace_err
                    time.sleep(backoff_s)
                    backoff_s *= 2
        except Exception as e:
            logger.error("Atomic file write failed for %s: %s", disk_path, e)
            if temp_name and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except Exception:
                    pass
            return False

        # 4. Save to SQLiteStore KV
        success = self.sqlite.set(norm, data)
        if not success:
            logger.error("Failed to persist %s to SQLiteStore.", norm)
            return False

        # 5. Semantic indexing in ChromaDB (if text content, deliverables, or knowledge)
        try:
            self._index_document_if_applicable(norm, data)
        except Exception as e:
            logger.debug("Chroma indexing skipped/failed for %s: %s", norm, e)

        return True

    def delete(self, path: str) -> bool:
        """Deletes document from KV store and filesystem."""
        norm = self._normalize_path(path)
        kv_del = self.sqlite.delete(norm)
        fs_path = self._get_fs_path(norm if norm.endswith(".json") else norm + ".json")
        if fs_path.is_file():
            try:
                fs_path.unlink()
                return True
            except Exception:
                pass
        return kv_del

    def _validate_schema_if_canonical(self, path: str, data: Dict[str, Any]) -> None:
        """Validate known canonical paths against Pydantic V2 schemas. Raises ValidationError on bad schema."""
        if path in ("company/identity", "company/identity.json"):
            CompanyIdentity.model_validate(data)
        elif path in ("user/profile", "user/profile.json"):
            UserProfile.model_validate(data)
        elif "manifest" in path:
            ProjectManifest.model_validate(data)
        elif path.startswith("agents/") and path.endswith("profile.json"):
            AgentProfile.model_validate(data)

    def _index_document_if_applicable(self, path: str, data: Dict[str, Any]) -> None:
        """Embeds deliverable or knowledge documents into Chroma collections."""
        if path.startswith("knowledge"):
            text_rep = json.dumps(data)
            self.chroma.add(ChromaStore.COLLECTION_KNOWLEDGE, id=path, text=text_rep, metadata={"path": path})
        elif path.startswith("projects") and ("deliverables" in path or "manifest" in path):
            text_rep = json.dumps(data)
            self.chroma.add(ChromaStore.COLLECTION_PROJECTS, id=path, text=text_rep, metadata={"path": path})

    # ========================================================================
    # Search, Memory, and Project Scaffolding Operations
    # ========================================================================

    def search(self, query: str, n_results: int = 5, path_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """Federated semantic search across Chroma collections with optional path prefix filtering."""
        collections_to_query: List[str] = []
        if path_prefix:
            if path_prefix.startswith("projects"):
                collections_to_query = [ChromaStore.COLLECTION_PROJECTS]
            elif path_prefix.startswith("knowledge"):
                collections_to_query = [ChromaStore.COLLECTION_KNOWLEDGE]
            elif path_prefix.startswith("agents/"):
                # e.g. agents/CTO -> agent_memory_CTO
                parts = path_prefix.split("/")
                agent_id = parts[1] if len(parts) > 1 else ""
                if agent_id:
                    collections_to_query = [f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{agent_id}"]
            else:
                collections_to_query = [ChromaStore.COLLECTION_KNOWLEDGE, ChromaStore.COLLECTION_PROJECTS]
        else:
            collections_to_query = [ChromaStore.COLLECTION_KNOWLEDGE, ChromaStore.COLLECTION_PROJECTS]

        aggregated: List[Dict[str, Any]] = []
        for coll in collections_to_query:
            try:
                results = self.chroma.search(collection_name=coll, query=query, top_k=n_results)
                for res in results:
                    path = res.get("metadata", {}).get("path", "")
                    if path_prefix and not path.startswith(path_prefix):
                        continue
                    aggregated.append(res)
            except Exception as e:
                logger.debug("Search skipped on collection %s: %s", coll, e)

        # Sort by similarity score descending (highest score first)
        aggregated.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
        return aggregated[:n_results]

    def append_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: str,
        importance: int,
        project_id: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Append episodic memory entry. Persists to SQLite relational table,
        appends JSON line to disk, and indexes in ChromaDB agent memory collection.
        Validates importance strictly between 1 and 10.
        """
        if importance < 1 or importance > 10:
            raise ValueError(f"importance must be between 1 and 10, got {importance}")

        mem_id = f"mem_{agent_id}_{uuid.uuid4().hex[:8]}"

        memory = EpisodicMemory(
            memory_id=mem_id,
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_id=project_id,
            type=memory_type,
            content=content,
            context=context,
            importance=importance,
            tags=tags or [],
        )

        # Ensure agent exists to satisfy foreign key constraint
        self._ensure_agent_exists(agent_id)

        # 1. Save to SQLite relational table
        try:
            self.sqlite.insert_memory({
                "memory_id": mem_id,
                "agent_id": agent_id,
                "memory_type": memory_type,
                "memory_content": content,
                "memory_tags": tags or [],
                "importance": importance,
                "project_id": project_id,
                "data_tier": "T3",
            })
        except Exception as e:
            logger.error("Failed to insert memory into SQLite: %s", e)
            raise

        # 2. Append to JSONL on disk
        mem_file = self.vault_root / "agents" / agent_id / "episodic_memory.jsonl"
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(mem_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(memory.model_dump(mode="json")) + "\n")
        except Exception as e:
            logger.error("Failed to append memory to JSONL file: %s", e)

        # 3. Vector embedding in ChromaDB
        try:
            coll_name = f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{agent_id}"
            self.chroma.add(
                coll_name,
                id=mem_id,
                text=content,
                metadata={
                    "agent_id": agent_id,
                    "type": memory_type,
                    "project_id": project_id or "",
                    "path": f"agents/{agent_id}/episodic_memory.jsonl",
                },
            )
        except Exception as e:
            logger.warning("Failed to index memory vector: %s", e)

        return mem_id

    def create_project(self, title: str, description: str, founder_goals: List[str]) -> str:
        """Scaffold new project: directories, manifest.json, goal.md, SQLite thread, and Chroma index."""
        proj_id = f"proj-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        # 1. Create subdirectories
        proj_dir = self.vault_root / "projects" / proj_id
        for sub in ["threads", "deliverables", "audit"]:
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)

        # 2. Manifest model
        manifest = ProjectManifest(
            project_id=proj_id,
            name=title,
            user_goal=description,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            status=ProjectStatus.PLANNING,
            assigned_agents=["CEO"],
            lead_agent="CEO",
            priority=ProjectPriority.MEDIUM,
            deliverables_expected=[],
            deliverables_completed=[],
            audit_status=AuditStatus.PENDING,
            tags=founder_goals,
        )

        self.write(f"projects/{proj_id}/manifest.json", manifest.model_dump(mode="json"))

        # 3. Write goal.md
        goal_md_path = proj_dir / "goal.md"
        goal_content = f"# Project Goal: {title}\n\n{description}\n\n## Founder Objectives\n"
        for g in founder_goals:
            goal_content += f"- {g}\n"
        with open(goal_md_path, "w", encoding="utf-8") as f:
            f.write(goal_content)

        # 4. Register thread in SQLite
        thread_id = f"thread_{proj_id}_main"
        self._ensure_agent_exists("CEO")
        try:
            self.sqlite.upsert_thread({
                "thread_id": thread_id,
                "project_id": proj_id,
                "project_name": title,
                "thread_status": "active",
                "owner_agent": "CEO",
                "stakeholders": ["CEO"],
                "priority": 3,
                "tags": founder_goals,
            })
        except Exception as e:
            logger.error("Failed to register thread in SQLite: %s", e)
            raise

        # 5. Chroma semantic index
        try:
            self.chroma.add(
                ChromaStore.COLLECTION_PROJECTS,
                id=f"{proj_id}_goal",
                text=f"{title}: {description} {' '.join(founder_goals)}",
                metadata={"project_id": proj_id, "name": title, "path": f"projects/{proj_id}/manifest.json"},
            )
        except Exception as e:
            logger.warning("Failed to index project in Chroma: %s", e)

        return proj_id

    def get_user_profile(self) -> Dict[str, Any]:
        """Retrieve founder profile, returning default UserProfile if uninitialized."""
        data = self.read("user/profile")
        if data:
            try:
                return UserProfile.model_validate(data).model_dump(mode="json")
            except Exception:
                return data
        return UserProfile(name="Aman Jain", role="Founder").model_dump(mode="json")

    def get_agent_registry(self) -> List[Dict[str, Any]]:
        """Retrieve list of active agent profiles from registry or relational table."""
        # 1. Try registry document
        reg = self.read("agents/registry")
        if reg:
            if isinstance(reg, list):
                return reg
            if isinstance(reg, dict) and "agents" in reg:
                return reg["agents"]

        # 2. Try SQLite vault_agents table
        try:
            rows = self.sqlite.list_agents(active_only=True)
            if rows:
                return [
                    {
                        "agent_id": r["agent_id"],
                        "role": r["agent_role"],
                        "assigned_model": r["agent_model"],
                        "version": r["agent_version"],
                        "status": "active" if r["is_active"] else "inactive",
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.debug("SQLite agent query fallback failed: %s", e)

        return []

    def backup(self) -> str:
        """Creates a timestamped snapshot backup of the vault under backups/{timestamp}/."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = self.vault_root / "backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for folder in ["company", "agents", "projects", "knowledge", "user"]:
            src = self.vault_root / folder
            if src.exists():
                shutil.copytree(src, backup_dir / folder, dirs_exist_ok=True)

        return str(backup_dir)

    def close(self) -> None:
        """Closes store handles."""
        self.sqlite.close()
