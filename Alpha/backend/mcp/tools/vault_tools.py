"""backend/mcp/tools/vault_tools.py - Alpha MCP Vault Tool Handlers.

Implements MCP tools for interacting with Alpha's Vault:
- vault_read: Read structured or document data from a Vault path.
- vault_write: Write or update data in Vault with strict RBAC enforcement (e.g. CAO confinement).
- vault_search: Semantic vector search across Vault collections with scope filtering.
- vault_save_memory: Append episodic memory entry for an executive agent.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from backend.vault.vault_manager import AccessDeniedError, VaultManager

logger = logging.getLogger("alpha.mcp.tools.vault")


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class VaultReadInput(BaseModel):
    """Input schema for vault_read MCP tool."""
    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Vault path, e.g. 'company/identity' or 'projects/proj_001/manifest'")
    agent_id: str = Field(..., description="Requesting agent ID, e.g. 'CEO', 'CTO', 'CAO'")

    @field_validator("path", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


class VaultWriteInput(BaseModel):
    """Input schema for vault_write MCP tool."""
    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Target Vault path to write, e.g. 'projects/proj_001/audit/report'")
    data: Dict[str, Any] = Field(..., description="Structured dictionary or JSON document to store")
    agent_id: str = Field(..., description="Calling agent ID for RBAC validation")
    append: bool = Field(default=False, description="If True, append to existing list/dict rather than overwrite")

    @field_validator("path", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


class VaultSearchInput(BaseModel):
    """Input schema for vault_search MCP tool."""
    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, description="Natural language search query")
    agent_id: str = Field(..., min_length=1, description="Requesting agent ID")
    scope: str = Field(
        default="all",
        description="Search domain: 'all', 'projects', 'knowledge', 'agents', or 'user'",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of matches to return (1-20)")

    @field_validator("query", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        allowed = {"all", "projects", "knowledge", "agents", "user"}
        s = v.lower().strip()
        if s not in allowed:
            raise ValueError(f"Invalid scope '{v}'. Allowed scopes: {sorted(list(allowed))}")
        return s


class MemoryData(BaseModel):
    """Sub-schema for episodic memory entry in vault_save_memory."""
    model_config = ConfigDict(extra="ignore")

    type: str = Field(..., min_length=1, description="Memory classification: 'decision', 'observation', 'feedback', 'lesson'")
    content: str = Field(..., min_length=1, description="Verbatim episodic observation or decision content")
    importance: int = Field(default=3, ge=1, le=10, description="Significance rating from 1 (minor) to 10 (critical)")
    context: Optional[str] = Field(default=None, description="Optional situational context")
    project_id: Optional[str] = Field(default=None, description="Optional associated project ID")
    tags: Optional[List[str]] = Field(default=None, description="Keywords or tags for categorization")

    @field_validator("type", "content")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


class VaultSaveMemoryInput(BaseModel):
    """Input schema for vault_save_memory MCP tool."""
    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(..., min_length=1, description="Agent saving the episodic memory, e.g. 'CTO'")
    memory: MemoryData = Field(..., description="Memory payload")

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("agent_id cannot be empty or whitespace.")
        return s


# ============================================================================
# Tool Handlers
# ============================================================================

def vault_read(
    path: str,
    agent_id: str,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Read a specific document from Alpha's Vault.

    Args:
        path: Vault relative path (e.g. 'company/identity').
        agent_id: Requesting agent ID.
        vault_manager: Optional VaultManager instance (defaults to global singleton).

    Returns:
        Structured response dictionary containing the document or error status.
    """
    try:
        vm = vault_manager or VaultManager()
        norm_path = path.strip()
        data = vm.read(norm_path)

        if data is None:
            return {
                "success": False,
                "found": False,
                "path": norm_path,
                "agent_id": agent_id,
                "data": None,
                "error": f"Document not found at path '{norm_path}'.",
            }

        return {
            "success": True,
            "found": True,
            "path": norm_path,
            "agent_id": agent_id,
            "data": data,
        }
    except AccessDeniedError as ade:
        logger.warning("Access denied during vault_read for agent %s on %s: %s", agent_id, path, ade)
        return {
            "success": False,
            "found": False,
            "path": path,
            "agent_id": agent_id,
            "data": None,
            "error": f"Access Denied: {ade}",
        }
    except Exception as e:
        logger.error("Unexpected error in vault_read: %s", e, exc_info=True)
        return {
            "success": False,
            "found": False,
            "path": path,
            "agent_id": agent_id,
            "data": None,
            "error": f"Internal error during vault_read: {str(e)}",
        }


def vault_write(
    path: str,
    data: Dict[str, Any],
    agent_id: str,
    append: bool = False,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Write or update structured data in Alpha's Vault with strict RBAC enforcement.

    RBAC Rules Enforced:
    - CAO agents (CAO, CAO-Claude, CAO-ChatGPT, CAO-C, CAO-G) can ONLY write to
      projects/{project_id}/audit/*. All other writes are strictly denied.
    - Protected system paths (backups/, *.db, chroma/) require CIO or Admin.
    - Company identity writes require CEO, CIO, or Admin.
    - Departmental write boundaries per role taxonomy.

    Args:
        path: Target Vault path.
        data: Payload dictionary to persist.
        agent_id: Calling agent ID.
        append: If True, append/merge with existing document.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response dictionary.
    """
    try:
        vm = vault_manager or VaultManager()
        norm_path = path.strip()

        # Explicit RBAC Permission Check
        agent_upper = str(agent_id or "").strip().upper()
        if agent_upper.startswith("CAO"):
            norm_parts = str(norm_path).strip("/\\").replace("\\", "/").split("/")
            is_audit = len(norm_parts) >= 3 and norm_parts[0] == "projects" and norm_parts[2] == "audit"
            if not is_audit:
                logger.warning("RBAC rejected CAO write for agent '%s' on path '%s'", agent_id, norm_path)
                return {
                    "success": False,
                    "path": norm_path,
                    "agent_id": agent_id,
                    "error": (
                        f"Access Denied: CAO agent '{agent_id}' is restricted to projects/{{id}}/audit/* (attempted: {norm_path})"
                    ),
                }

        check_perm = getattr(vm, "check_write_permission", getattr(vm, "_check_write_permission", None))
        if check_perm and not check_perm(agent_id, norm_path):
            logger.warning("RBAC rejected write for agent '%s' on path '%s'", agent_id, norm_path)
            return {
                "success": False,
                "path": norm_path,
                "agent_id": agent_id,
                "error": (
                    f"Access Denied: Agent '{agent_id}' does not have write permission for '{norm_path}' "
                    f"(RBAC enforcement: CAO confined to audit/, system paths restricted to CIO)."
                ),
            }

        target_data = data
        if append:
            existing = vm.read(norm_path)
            if existing is not None:
                if isinstance(existing, list):
                    new_list = list(existing)
                    if isinstance(data, list):
                        new_list.extend(data)
                    else:
                        new_list.append(data)
                    target_data = new_list  # type: ignore[assignment]
                elif isinstance(existing, dict) and isinstance(data, dict):
                    merged = dict(existing)
                    merged.update(data)
                    target_data = merged

        success = vm.write(norm_path, target_data, agent_id=agent_id)
        if not success:
            return {
                "success": False,
                "path": norm_path,
                "agent_id": agent_id,
                "error": f"Failed to persist document to '{norm_path}'.",
            }

        return {
            "success": True,
            "path": norm_path,
            "agent_id": agent_id,
            "append": append,
            "message": f"Successfully written document to '{norm_path}'.",
        }
    except ValidationError as ve:
        logger.warning("Schema validation failed during vault_write on %s: %s", path, ve)
        return {
            "success": False,
            "path": path,
            "agent_id": agent_id,
            "error": f"Schema Validation Error: {ve}",
        }
    except AccessDeniedError as ade:
        return {
            "success": False,
            "path": path,
            "agent_id": agent_id,
            "error": f"Access Denied: {ade}",
        }
    except Exception as e:
        logger.error("Unexpected error in vault_write: %s", e, exc_info=True)
        return {
            "success": False,
            "path": path,
            "agent_id": agent_id,
            "error": f"Internal error during vault_write: {str(e)}",
        }


def vault_search(
    query: str,
    agent_id: str,
    scope: str = "all",
    top_k: int = 5,
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Perform semantic search across Alpha's Vault collections.

    Args:
        query: Natural language search string.
        agent_id: Requesting agent ID.
        scope: Target domain ('all', 'projects', 'knowledge', 'agents', 'user').
        top_k: Maximum results to return (1-20).
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured search response with matching documents.
    """
    try:
        vm = vault_manager or VaultManager()
        safe_top_k = max(1, min(20, int(top_k)))
        clean_scope = scope.lower().strip()

        prefix_map = {
            "all": None,
            "projects": "projects",
            "knowledge": "knowledge",
            "agents": "agents",
            "user": "user",
        }
        path_prefix = prefix_map.get(clean_scope, None)

        results = vm.search(query=query, n_results=safe_top_k, path_prefix=path_prefix)

        return {
            "success": True,
            "query": query,
            "scope": clean_scope,
            "top_k": safe_top_k,
            "agent_id": agent_id,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        logger.error("Unexpected error in vault_search: %s", e, exc_info=True)
        return {
            "success": False,
            "query": query,
            "scope": scope,
            "agent_id": agent_id,
            "count": 0,
            "results": [],
            "error": f"Internal error during vault_search: {str(e)}",
        }


def vault_save_memory(
    agent_id: str,
    memory: Dict[str, Any],
    vault_manager: Optional[VaultManager] = None,
) -> Dict[str, Any]:
    """Save an episodic memory entry for an executive agent in Vault.

    Persists to:
    1. SQLite relational table `vault_agent_memory`.
    2. Append-only JSONL file `agents/{agent_id}/episodic_memory.jsonl`.
    3. ChromaDB vector collection `agent_memory_{agent_id}`.

    Args:
        agent_id: Target agent ID (e.g. 'CTO').
        memory: Dictionary containing type, content, importance, context, project_id, tags.
        vault_manager: Optional VaultManager instance.

    Returns:
        Structured response with generated memory_id.
    """
    try:
        vm = vault_manager or VaultManager()
        clean_agent_id = agent_id.strip()

        mem_type = str(memory.get("type", "observation"))
        content = str(memory.get("content", "")).strip()
        if not content:
            return {
                "success": False,
                "saved": False,
                "agent_id": clean_agent_id,
                "error": "Memory content cannot be empty.",
            }

        # Normalize importance between 1 and 10
        raw_importance = memory.get("importance", 3)
        try:
            importance = int(raw_importance)
            if importance < 1 or importance > 10:
                raise ValueError(f"importance must be between 1 and 10, got {importance}")
        except (ValueError, TypeError) as ve:
            if "importance must be between 1 and 10" in str(ve):
                raise
            importance = 3

        project_id = memory.get("project_id")
        context = memory.get("context")
        tags = memory.get("tags")

        try:
            mem_id = vm.append_memory(
                agent_id=clean_agent_id,
                memory_type=mem_type,
                content=content,
                importance=importance,
                project_id=project_id,
                context=context,
                tags=tags if isinstance(tags, list) else None,
            )
        except TypeError:
            mem_id = vm.append_memory(
                agent_id=clean_agent_id,
                memory_type=mem_type,
                content=content,
                importance=importance,
                project_id=project_id,
            )

        return {
            "success": True,
            "saved": True,
            "memory_id": mem_id,
            "agent_id": clean_agent_id,
            "type": mem_type,
            "importance": importance,
            "message": f"Episodic memory saved successfully for agent '{clean_agent_id}'.",
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error("Unexpected error in vault_save_memory: %s", e, exc_info=True)
        return {
            "success": False,
            "saved": False,
            "agent_id": agent_id,
            "error": f"Internal error during vault_save_memory: {str(e)}",
        }
