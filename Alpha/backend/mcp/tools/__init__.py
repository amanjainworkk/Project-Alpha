"""backend/mcp/tools/__init__.py - Project Alpha MCP Tool Registry & Package Exports.

Exports all 15 system tools across 6 operational namespaces:
1. Vault: vault_read, vault_write, vault_search, vault_save_memory
2. Agents: agent_delegate, agent_status, agent_hire
3. Projects: project_create, project_update_status, project_list
4. Threads: thread_post, thread_read
5. Model: model_route
6. User: user_profile_read, user_escalate
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from pydantic import ValidationError

from backend.mcp.tools.vault_tools import (
    VaultReadInput,
    VaultSearchInput,
    VaultWriteInput,
    VaultSaveMemoryInput,
    vault_read,
    vault_search,
    vault_write,
    vault_save_memory,
)
from backend.mcp.tools.agent_tools import (
    AgentDelegateInput,
    AgentHireInput,
    AgentStatusInput,
    agent_delegate,
    agent_hire,
    agent_status,
)
from backend.mcp.tools.project_tools import (
    ProjectCreateInput,
    ProjectListInput,
    ProjectUpdateStatusInput,
    project_create,
    project_list,
    project_update_status,
)
from backend.mcp.tools.thread_tools import (
    ThreadPostInput,
    ThreadReadInput,
    thread_post,
    thread_read,
)
from backend.mcp.tools.model_tools import (
    ModelRouteInput,
    model_route,
)
from backend.mcp.tools.user_tools import (
    UserEscalateInput,
    UserProfileReadInput,
    user_escalate,
    user_profile_read,
)

logger = logging.getLogger("alpha.mcp.tools")

# ============================================================================
# Master Schema & Handler Mappings
# ============================================================================

TOOL_INPUT_SCHEMAS: Dict[str, Any] = {
    "vault_read": VaultReadInput,
    "vault_write": VaultWriteInput,
    "vault_search": VaultSearchInput,
    "vault_save_memory": VaultSaveMemoryInput,
    "agent_delegate": AgentDelegateInput,
    "agent_status": AgentStatusInput,
    "agent_hire": AgentHireInput,
    "project_create": ProjectCreateInput,
    "project_update_status": ProjectUpdateStatusInput,
    "project_list": ProjectListInput,
    "thread_post": ThreadPostInput,
    "thread_read": ThreadReadInput,
    "model_route": ModelRouteInput,
    "user_profile_read": UserProfileReadInput,
    "user_escalate": UserEscalateInput,
}

TOOL_HANDLERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "vault_read": vault_read,
    "vault_write": vault_write,
    "vault_search": vault_search,
    "vault_save_memory": vault_save_memory,
    "agent_delegate": agent_delegate,
    "agent_status": agent_status,
    "agent_hire": agent_hire,
    "project_create": project_create,
    "project_update_status": project_update_status,
    "project_list": project_list,
    "thread_post": thread_post,
    "thread_read": thread_read,
    "model_route": model_route,
    "user_profile_read": user_profile_read,
    "user_escalate": user_escalate,
}

# Canonical MCP Tool Metadata conforming to Model Context Protocol v1.0
TOOL_METADATA: List[Dict[str, Any]] = [
    {
        "name": "vault_read",
        "description": "Read structured or document data from a specific path in Alpha's Vault.",
        "inputSchema": VaultReadInput.model_json_schema(),
    },
    {
        "name": "vault_write",
        "description": "Write or update data in Alpha's Vault with strict RBAC enforcement (e.g. CAO confinement).",
        "inputSchema": VaultWriteInput.model_json_schema(),
    },
    {
        "name": "vault_search",
        "description": "Perform semantic search across Alpha's Vault to find relevant past context, decisions, or knowledge.",
        "inputSchema": VaultSearchInput.model_json_schema(),
    },
    {
        "name": "vault_save_memory",
        "description": "Save an episodic memory entry for an executive agent in Vault.",
        "inputSchema": VaultSaveMemoryInput.model_json_schema(),
    },
    {
        "name": "agent_delegate",
        "description": "CEO delegates a specific task to one or more C-suite agents with an executive brief.",
        "inputSchema": AgentDelegateInput.model_json_schema(),
    },
    {
        "name": "agent_status",
        "description": "Get current status, telemetry, model allocation, and episodic memory of a C-suite agent.",
        "inputSchema": AgentStatusInput.model_json_schema(),
    },
    {
        "name": "agent_hire",
        "description": "CHRO creates and onboards a new executive agent in Alpha's company.",
        "inputSchema": AgentHireInput.model_json_schema(),
    },
    {
        "name": "project_create",
        "description": "Create a new project with manifest, goal file, SQLite thread, and Chroma index.",
        "inputSchema": ProjectCreateInput.model_json_schema(),
    },
    {
        "name": "project_update_status",
        "description": "Update the status of an existing project and record audit history.",
        "inputSchema": ProjectUpdateStatusInput.model_json_schema(),
    },
    {
        "name": "project_list",
        "description": "List all projects with optional status and agent assignment filters.",
        "inputSchema": ProjectListInput.model_json_schema(),
    },
    {
        "name": "thread_post",
        "description": "Post a message to a project's inter-agent communication thread.",
        "inputSchema": ThreadPostInput.model_json_schema(),
    },
    {
        "name": "thread_read",
        "description": "Read all messages in a project thread, optionally filtered by type, sender, or timestamp.",
        "inputSchema": ThreadReadInput.model_json_schema(),
    },
    {
        "name": "model_route",
        "description": "Get the recommended AI model for a task based on complexity and agent role.",
        "inputSchema": ModelRouteInput.model_json_schema(),
    },
    {
        "name": "user_profile_read",
        "description": "Read current Founder (Aman Jain) profile, working style, and preferences.",
        "inputSchema": UserProfileReadInput.model_json_schema(),
    },
    {
        "name": "user_escalate",
        "description": "Escalate a critical decision or deadlock to Founder Aman Jain via CEO interface.",
        "inputSchema": UserEscalateInput.model_json_schema(),
    },
]


def dispatch_tool(
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
    **dependencies: Any,
) -> Dict[str, Any]:
    """Validate arguments and dispatch execution to the target tool handler.

    Args:
        name: Tool name (e.g. 'vault_read', 'agent_delegate').
        arguments: Raw parameter dictionary.
        **dependencies: Subsystem instances (vault_manager, agent_registry, model_router, thread_manager).

    Returns:
        Structured response dictionary.
    """
    clean_name = name.strip()
    handler = TOOL_HANDLERS.get(clean_name)
    if not handler:
        return {
            "success": False,
            "error": f"Unknown tool: '{name}'. Available tools: {sorted(list(TOOL_HANDLERS.keys()))}",
        }

    args = arguments if isinstance(arguments, dict) else {}

    # Validate against Pydantic schema
    schema_cls = TOOL_INPUT_SCHEMAS.get(clean_name)
    validated_kwargs = dict(args)
    if schema_cls:
        try:
            model_instance = schema_cls.model_validate(args)
            validated_kwargs = model_instance.model_dump()
        except ValidationError as ve:
            logger.warning("Tool parameter validation failed for %s: %s", clean_name, ve)
            raise ValueError(f"Invalid tool arguments for '{clean_name}': {ve}") from ve

    import inspect
    sig = inspect.signature(handler)
    accepted_params = sig.parameters.keys()

    call_kwargs: Dict[str, Any] = {}
    for k, v in validated_kwargs.items():
        if k in accepted_params:
            call_kwargs[k] = v

    # Pass subsystem dependencies if accepted by handler signature
    for dep_key, dep_val in dependencies.items():
        if dep_val is not None and dep_key in accepted_params:
            call_kwargs[dep_key] = dep_val

    try:
        return handler(**call_kwargs)
    except (ValueError, PermissionError):
        raise
    except Exception as e:
        logger.error("Error executing tool %s: %s", clean_name, e, exc_info=True)
        return {
            "success": False,
            "tool": clean_name,
            "error": f"Internal tool execution error: {str(e)}",
        }


def get_tool_metadata() -> List[Dict[str, Any]]:
    """Return canonical MCP metadata for all 15 Alpha tools."""
    return list(TOOL_METADATA)


__all__ = [
    # Schemas
    "VaultReadInput",
    "VaultWriteInput",
    "VaultSearchInput",
    "VaultSaveMemoryInput",
    "AgentDelegateInput",
    "AgentStatusInput",
    "AgentHireInput",
    "ProjectCreateInput",
    "ProjectUpdateStatusInput",
    "ProjectListInput",
    "ThreadPostInput",
    "ThreadReadInput",
    "ModelRouteInput",
    "UserProfileReadInput",
    "UserEscalateInput",
    # Handlers
    "vault_read",
    "vault_write",
    "vault_search",
    "vault_save_memory",
    "agent_delegate",
    "agent_status",
    "agent_hire",
    "project_create",
    "project_update_status",
    "project_list",
    "thread_post",
    "thread_read",
    "model_route",
    "user_profile_read",
    "user_escalate",
    # Registry & Dispatch
    "TOOL_INPUT_SCHEMAS",
    "TOOL_HANDLERS",
    "TOOL_METADATA",
    "dispatch_tool",
    "get_tool_metadata",
]
