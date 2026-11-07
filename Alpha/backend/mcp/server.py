"""backend/mcp/server.py - Project Alpha FastMCP / MCP SDK Core Server.

Exposes Alpha's complete autonomous AI executive operating system capabilities as
Model Context Protocol (MCP) v1.0 tools and resources across both stdio and HTTP/SSE transports.

Architecture:
- Resilient Dual-Mode Design:
  * When official `mcp` SDK is installed: wires standard FastMCP / MCP Server decorators, types, and stdio/SSE streams.
  * When running in pure-Python or environments without `mcp`: activates high-reliability NativeMCPServer providing
    identical `list_tools()`, `call_tool(name, arguments)`, `list_resources()`, `read_resource(uri)`, and JSON-RPC 2.0 message dispatching.
- 15 Core Tools across 6 namespaces:
  1. Vault Tools: vault_read, vault_write, vault_search, vault_save_memory
  2. Agent Tools: agent_delegate, agent_status, agent_hire
  3. Project Tools: project_create, project_update_status, project_list
  4. Thread Tools: thread_post, thread_read
  5. Model Routing Tools: model_route
  6. User Tools: user_profile_read, user_escalate
- Canonical Resource URIs:
  * vault://company/identity
  * vault://user/profile
  * agents://registry
  * projects://list
  * vault://{path}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# Optional import of official MCP SDK
try:
    import mcp
    from mcp.server import Server as OfficialMCPServer
    from mcp.server.stdio import stdio_server as official_stdio_server
    from mcp.types import (
        EmptyResult,
        Resource as OfficialResource,
        ResourceTemplate as OfficialResourceTemplate,
        TextContent as OfficialTextContent,
        Tool as OfficialTool,
    )
    HAS_OFFICIAL_MCP = True
except ImportError:
    HAS_OFFICIAL_MCP = False
    OfficialMCPServer = None
    official_stdio_server = None
    OfficialTool = None
    OfficialTextContent = None
    OfficialResource = None
    OfficialResourceTemplate = None

# Optional import of Starlette for ASGI / SSE HTTP transport
try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response, StreamingResponse
    from starlette.routing import Route
    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False

# Optional dynamic import of backend.mcp.tools package if installed
try:
    from backend.mcp.tools import (
        TOOL_HANDLERS,
        TOOL_INPUT_SCHEMAS,
        TOOL_METADATA,
        dispatch_tool,
        get_tool_metadata,
    )
    HAS_TOOL_MODULES = True
except ImportError:
    try:
        from .tools import (
            TOOL_HANDLERS,
            TOOL_INPUT_SCHEMAS,
            TOOL_METADATA,
            dispatch_tool,
            get_tool_metadata,
        )
        HAS_TOOL_MODULES = True
    except ImportError:
        HAS_TOOL_MODULES = False
        TOOL_HANDLERS = {}
        TOOL_INPUT_SCHEMAS = {}
        TOOL_METADATA = []
        dispatch_tool = None
        get_tool_metadata = None

logger = logging.getLogger("alpha.mcp.server")


# ============================================================================
# Universal Lightweight MCP Types (Compatible with official MCP SDK)
# ============================================================================

@dataclass
class TextContent:
    """Standard MCP text content block."""
    text: str
    type: str = "text"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass
class ToolDefinition:
    """MCP tool metadata and JSON Schema definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


@dataclass
class ResourceDefinition:
    """MCP resource metadata and URI definition."""
    uri: str
    name: str
    description: str
    mimeType: str = "application/json"


# ============================================================================
# Canonical 15 MCP Tool Schemas (conforming to MCP-SERVER-DESIGN.md)
# ============================================================================

ALPHA_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "vault_read",
        "description": "Read structured data from a specific path in Alpha's Vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault path e.g. 'company/identity'"},
                "agent_id": {"type": "string", "description": "Requesting agent's ID"},
            },
            "required": ["path", "agent_id"],
        },
    },
    {
        "name": "vault_write",
        "description": "Write structured data to Alpha's Vault. Agent must have write access to the path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Vault path to write data to"},
                "data": {"type": "object", "description": "Structured JSON object to persist"},
                "agent_id": {"type": "string", "description": "Requesting agent's ID enforcing RBAC"},
                "append": {"type": "boolean", "default": False, "description": "Whether to append or overwrite"},
            },
            "required": ["path", "data", "agent_id"],
        },
    },
    {
        "name": "vault_search",
        "description": "Perform semantic search across Alpha's Vault to find relevant past context, decisions, or knowledge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "scope": {
                    "type": "string",
                    "enum": ["all", "projects", "knowledge", "agents", "user"],
                    "default": "all",
                    "description": "Search scope partition",
                },
                "top_k": {"type": "integer", "default": 5, "maximum": 20, "description": "Maximum results to return"},
                "agent_id": {"type": "string", "description": "Requesting agent's ID"},
            },
            "required": ["query", "agent_id"],
        },
    },
    {
        "name": "vault_save_memory",
        "description": "Save a memory entry to an agent's episodic memory log in the Vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent saving the episodic memory"},
                "memory": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["decision", "observation", "feedback", "lesson", "fact", "preference", "skill", "relationship"],
                            "description": "Classification category of memory",
                        },
                        "content": {"type": "string", "description": "Memory content body"},
                        "context": {"type": "string", "description": "Contextual background"},
                        "project_id": {"type": "string", "description": "Associated project ID"},
                        "importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Importance score"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Categorical tags"},
                    },
                    "required": ["type", "content", "importance"],
                },
            },
            "required": ["agent_id", "memory"],
        },
    },
    {
        "name": "agent_delegate",
        "description": "CEO delegates a specific task to one or more C-suite agents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Associated project ID"},
                "from_agent": {"type": "string", "description": "Delegating agent, typically CEO", "default": "CEO"},
                "to_agents": {"type": "array", "items": {"type": "string"}, "description": "Target agent roles"},
                "task": {"type": "string", "description": "Task description"},
                "context": {"type": "string", "description": "Background context for the task"},
                "expected_deliverable": {"type": "string", "description": "Deliverable specification"},
                "deadline_minutes": {"type": "integer", "description": "Minutes to complete task"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "default": "medium"},
            },
            "required": ["project_id", "from_agent", "to_agents", "task", "expected_deliverable"],
        },
    },
    {
        "name": "agent_status",
        "description": "Get the current status and active task of a C-suite agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID to query"},
                "include_memory_summary": {"type": "boolean", "default": False, "description": "Include recent memories"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "agent_hire",
        "description": "CHRO creates and registers a new agent in Alpha's company. Requires a complete agent profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "description": "Role acronym e.g. CQO"},
                "full_title": {"type": "string", "description": "Full formal title"},
                "jd_content": {"type": "string", "description": "Full Job Description markdown content"},
                "skills": {"type": "array", "items": {"type": "string"}, "description": "Core competencies"},
                "assigned_model": {"type": "string", "description": "Default model e.g. llama3.2"},
                "reports_to": {"type": "string", "default": "CEO", "description": "Direct supervisor"},
                "peers": {"type": "array", "items": {"type": "string"}, "description": "Peer agent IDs"},
            },
            "required": ["role", "full_title", "jd_content", "skills", "assigned_model"],
        },
    },
    {
        "name": "project_create",
        "description": "Create a new project. Called by CEO when a new user goal arrives.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project title"},
                "user_goal": {"type": "string", "description": "Verbatim user goal"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Project priority"},
                "assigned_agents": {"type": "array", "items": {"type": "string"}, "default": ["CEO"], "description": "Assigned agents"},
                "deadline": {"type": "string", "description": "ISO-8601 deadline date-time string"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Project tags"},
            },
            "required": ["name", "user_goal", "priority"],
        },
    },
    {
        "name": "project_update_status",
        "description": "Update the status of an existing project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID to update"},
                "status": {
                    "type": "string",
                    "enum": ["planning", "in_progress", "in_audit", "awaiting_approval", "complete", "archived"],
                    "description": "New project status",
                },
                "agent_id": {"type": "string", "description": "Agent initiating update"},
                "note": {"type": "string", "description": "Transition note"},
            },
            "required": ["project_id", "status", "agent_id"],
        },
    },
    {
        "name": "project_list",
        "description": "List projects with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status"},
                "agent_id": {"type": "string", "description": "Filter by assigned agent"},
                "limit": {"type": "integer", "default": 20, "description": "Max results to return"},
                "include_archived": {"type": "boolean", "default": False, "description": "Include archived projects"},
            },
        },
    },
    {
        "name": "thread_post",
        "description": "Post a message to a project's inter-agent communication thread.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "from_agent": {"type": "string", "description": "Sender agent ID"},
                "to_agents": {"type": "array", "items": {"type": "string"}, "description": "Recipient agent IDs"},
                "type": {
                    "type": "string",
                    "enum": ["DELEGATION", "DELIVERABLE", "QUESTION", "RESPONSE", "REVIEW_REQUEST", "SYNTHESIS", "AUDIT_REQUEST", "AUDIT_REPORT", "USER_ESCALATION"],
                    "description": "Message category",
                },
                "subject": {"type": "string", "description": "Message subject"},
                "content": {"type": "string", "description": "Message content"},
                "in_reply_to": {"type": "string", "description": "Message ID being replied to"},
            },
            "required": ["project_id", "from_agent", "to_agents", "type", "content"],
        },
    },
    {
        "name": "thread_read",
        "description": "Read all messages in a project's thread, optionally filtered by type or agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "agent_id": {"type": "string", "description": "Requesting agent ID"},
                "filter_type": {"type": "string", "description": "Filter by message type"},
                "filter_from_agent": {"type": "string", "description": "Filter by sender"},
                "since": {"type": "string", "description": "ISO-8601 timestamp cutoff"},
                "limit": {"type": "integer", "default": 100, "description": "Max messages"},
            },
            "required": ["project_id", "agent_id"],
        },
    },
    {
        "name": "model_route",
        "description": "Get the recommended AI model for a specific task based on complexity and type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Type of task e.g. 'technical_spec', 'draft_copy'"},
                "complexity": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Complexity tier (1-5)"},
                "agent_id": {"type": "string", "description": "Requesting agent ID"},
                "prefer_free": {"type": "boolean", "default": True, "description": "Prioritize zero-cost tiers"},
            },
            "required": ["task_type", "complexity", "agent_id"],
        },
    },
    {
        "name": "user_profile_read",
        "description": "Read the current user's profile and preferences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Requesting agent ID"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "user_escalate",
        "description": "Escalate a decision or question to the user via the CEO interface. Used when agents cannot proceed without user input.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Associated project ID"},
                "from_agent": {"type": "string", "description": "Escalating agent ID"},
                "question": {"type": "string", "description": "Escalation query for Founder"},
                "context": {"type": "string", "description": "Background context"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Suggested choices"},
                "urgency": {"type": "string", "enum": ["low", "medium", "high"], "description": "Urgency rating"},
            },
            "required": ["project_id", "from_agent", "question", "context", "urgency"],
        },
    },
]

# Canonical Resources conforming to MCP-SERVER-DESIGN.md
ALPHA_RESOURCES: List[Dict[str, Any]] = [
    {
        "uri": "vault://company/identity",
        "name": "Company Identity",
        "description": "Alpha company core vision, mission, and values document",
        "mimeType": "application/json",
    },
    {
        "uri": "vault://user/profile",
        "name": "Founder Profile",
        "description": "Founder personal profile, communication style, and preferences",
        "mimeType": "application/json",
    },
    {
        "uri": "agents://registry",
        "name": "Agent Registry",
        "description": "Current catalog and telemetry of all 12 executive C-suite agents",
        "mimeType": "application/json",
    },
    {
        "uri": "projects://list",
        "name": "Projects Directory",
        "description": "Catalog of all active and completed projects in Alpha",
        "mimeType": "application/json",
    },
]


# ============================================================================
# Core Server Engine: AlphaMCPServer (Dual-Mode FastMCP / NativeMCPServer)
# ============================================================================

class AlphaMCPServer:
    """Master Model Context Protocol (MCP) Tool Server for Project Alpha.
    
    Provides 100% contract compliance across both official MCP SDK (if installed)
    and Native Pure-Python JSON-RPC 2.0 dispatching.
    """

    def __init__(
        self,
        vault_manager: Optional[Any] = None,
        agent_registry: Optional[Any] = None,
        model_router: Optional[Any] = None,
        thread_manager: Optional[Any] = None,
        server_name: str = "alpha-mcp",
        server_version: str = "1.0.0",
    ) -> None:
        self.server_name = server_name
        self.server_version = server_version

        # Inject or lazy-load subsystems
        self.vault = vault_manager
        self.agents = agent_registry
        self.router = model_router
        self.threads = thread_manager

        # In-memory storage for active threads & hired personas if managers uninitialized
        self._local_threads: Dict[str, List[Dict[str, Any]]] = {}
        self._local_projects: Dict[str, Dict[str, Any]] = {}
        self._local_agents: Dict[str, Dict[str, Any]] = {}

        # Tool map & Schema cache
        self._tool_defs: Dict[str, Dict[str, Any]] = {t["name"]: t for t in ALPHA_TOOLS}
        self._resource_defs: Dict[str, Dict[str, Any]] = {r["uri"]: r for r in ALPHA_RESOURCES}

        # Handler dispatcher table (built-in fallbacks)
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "vault_read": self._handle_vault_read,
            "vault_write": self._handle_vault_write,
            "vault_search": self._handle_vault_search,
            "vault_save_memory": self._handle_vault_save_memory,
            "agent_delegate": self._handle_agent_delegate,
            "agent_status": self._handle_agent_status,
            "agent_hire": self._handle_agent_hire,
            "project_create": self._handle_project_create,
            "project_update_status": self._handle_project_update_status,
            "project_list": self._handle_project_list,
            "thread_post": self._handle_thread_post,
            "thread_read": self._handle_thread_read,
            "model_route": self._handle_model_route,
            "user_profile_read": self._handle_user_profile_read,
            "user_escalate": self._handle_user_escalate,
        }

        # Wire official MCP Server if SDK is present
        self._official_server: Optional[Any] = None
        if HAS_OFFICIAL_MCP and OfficialMCPServer is not None:
            self._init_official_server()

    def _init_official_server(self) -> None:
        """Wires decorators and routes onto the official mcp.server.Server."""
        try:
            self._official_server = OfficialMCPServer(self.server_name)

            @self._official_server.list_tools()
            async def list_tools_wrapper() -> List[OfficialTool]:
                return [
                    OfficialTool(
                        name=t["name"],
                        description=t["description"],
                        inputSchema=t["inputSchema"],
                    )
                    for t in ALPHA_TOOLS
                ]

            @self._official_server.call_tool()
            async def call_tool_wrapper(name: str, arguments: Dict[str, Any]):
                result = await self.call_tool(name, arguments)
                return [OfficialTextContent(type="text", text=str(result))]

            @self._official_server.list_resources()
            async def list_resources_wrapper() -> List[OfficialResource]:
                return [
                    OfficialResource(
                        uri=r["uri"],
                        name=r["name"],
                        description=r["description"],
                        mimeType=r["mimeType"],
                    )
                    for r in ALPHA_RESOURCES
                ]

            @self._official_server.read_resource()
            async def read_resource_wrapper(uri: str):
                return await self.read_resource(uri)

            logger.info("Official MCP Server SDK initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize official MCP Server SDK: %s", e)
            self._official_server = None

    # ========================================================================
    # Public MCP Interface Methods
    # ========================================================================

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return canonical list of all 15 Alpha MCP tools."""
        return list(ALPHA_TOOLS)

    def get_tool_names(self) -> List[str]:
        """Return list of all registered tool names."""
        return [t["name"] for t in ALPHA_TOOLS]

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve tool definition schema by name."""
        return self._tool_defs.get(name)

    def list_resources(self) -> List[Dict[str, Any]]:
        """Return canonical list of Alpha MCP resources."""
        return list(ALPHA_RESOURCES)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute tool by name with arguments and return standard TextContent list."""
        result_dict = await self.call_tool_dict(name, arguments)
        json_text = json.dumps(result_dict, default=str)
        return [TextContent(type="text", text=json_text)]

    async def call_tool_dict(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool and return structured Python dictionary directly."""
        if name not in self._tool_defs:
            raise ValueError(f"Unknown MCP tool: {name}")

        handler = self._handlers.get(name)
        if not handler:
            raise ValueError(f"No handler registered for tool: {name}")

        # Validate required arguments according to inputSchema
        schema = self._tool_defs[name]["inputSchema"]
        required_fields = schema.get("required", [])
        missing = [f for f in required_fields if f not in arguments or arguments[f] is None]
        if missing:
            raise ValueError(f"Tool '{name}' missing required argument(s): {', '.join(missing)}")

        # Strict RBAC Gateway Check: CAO confinement on vault_write
        if name == "vault_write":
            agent_id = arguments.get("agent_id")
            path = str(arguments.get("path", ""))
            agent_upper = str(agent_id or "").strip().upper()
            norm_parts = str(path).strip("/\\").replace("\\", "/").split("/")
            is_audit = len(norm_parts) >= 3 and norm_parts[0] == "projects" and norm_parts[2] == "audit"
            if agent_upper.startswith("CAO") and not is_audit:
                raise PermissionError(
                    f"Access Denied: CAO agent '{agent_id}' is restricted to projects/{{id}}/audit/* (attempted: {path})"
                )

        if name == "agent_delegate":
            from_agent = arguments.get("from_agent", "CEO")
            if str(from_agent).strip().upper() != "CEO":
                raise PermissionError(
                    f"Authority Denied: Only CEO holds delegation authority. Agent '{from_agent}' cannot delegate."
                )

        # Normalize CAO agent identifiers for model routing
        if name == "model_route" and "agent_id" in arguments:
            agent_raw = str(arguments.get("agent_id", "")).strip().upper().replace("_", "-")
            if agent_raw in ("CAO", "CAO-C", "CAO-CLAUDE") or (agent_raw.startswith("CAO") and not ("G" in agent_raw or "GPT" in agent_raw)):
                arguments = dict(arguments)
                arguments["agent_id"] = "CAO-Claude"
            elif agent_raw in ("CAO-G", "CAO-CHATGPT", "CAO-GPT") or (agent_raw.startswith("CAO") and ("G" in agent_raw or "GPT" in agent_raw)):
                arguments = dict(arguments)
                arguments["agent_id"] = "CAO-ChatGPT"

        # Delegate to modular tools package if installed
        if HAS_TOOL_MODULES and dispatch_tool is not None:
            try:
                mod_res = dispatch_tool(
                    name=name,
                    arguments=arguments,
                    vault_manager=self.vault,
                    agent_registry=self.agents,
                    model_router=self.router,
                    thread_manager=self.threads,
                )
                if isinstance(mod_res, dict):
                    # Check for RBAC access denied envelope
                    if not mod_res.get("success", True) and (
                        "Access Denied" in str(mod_res.get("error", ""))
                        or "Authority Denied" in str(mod_res.get("error", ""))
                    ):
                        raise PermissionError(mod_res.get("error"))
                    return mod_res
            except (PermissionError, ValueError):
                raise
            except Exception as mod_err:
                logger.debug("Modular tool dispatch fallback for %s: %s", name, mod_err)

        # Execute built-in fallback handler
        if asyncio.iscoroutinefunction(handler):
            return await handler(arguments)
        else:
            return handler(arguments)

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read resource content by URI (e.g. vault://company/identity)."""
        if uri.startswith("vault://"):
            path = uri[8:]
            return await self.call_tool_dict("vault_read", {"path": path, "agent_id": "CEO"})
        elif uri == "agents://registry":
            if self.agents and hasattr(self.agents, "list_agents"):
                return {"agents": self.agents.list_agents()}
            elif self.vault and hasattr(self.vault, "get_agent_registry"):
                return {"agents": self.vault.get_agent_registry()}
            return {"agents": list(self._local_agents.values())}
        elif uri == "projects://list":
            return await self.call_tool_dict("project_list", {})
        else:
            raise ValueError(f"Unknown resource URI: {uri}")

    def call_tool_sync(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Synchronous wrapper for call_tool."""
        return asyncio.run(self.call_tool(name, arguments))

    def call_tool_dict_sync(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for call_tool_dict."""
        return asyncio.run(self.call_tool_dict(name, arguments))

    def read_resource_sync(self, uri: str) -> Dict[str, Any]:
        """Synchronous wrapper for read_resource."""
        return asyncio.run(self.read_resource(uri))

    def handle_jsonrpc_sync(self, request_payload: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synchronous wrapper for handle_jsonrpc."""
        return asyncio.run(self.handle_jsonrpc(request_payload))

    # ========================================================================
    # JSON-RPC 2.0 Protocol Dispatcher (for stdio and HTTP/SSE clients)
    # ========================================================================

    async def handle_jsonrpc(self, request_payload: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Processes JSON-RPC 2.0 request and returns formatted JSON-RPC 2.0 response."""
        # Parse payload
        if isinstance(request_payload, str):
            try:
                data = json.loads(request_payload)
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                }
        else:
            data = request_payload

        if not isinstance(data, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: payload must be a JSON object",
                },
            }

        req_id = data.get("id")
        if data.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: 'jsonrpc' must be exactly '2.0'",
                },
            }

        method = data.get("method")
        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"},
            }

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                        },
                        "serverInfo": {
                            "name": self.server_name,
                            "version": self.server_version,
                        },
                    },
                }

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": self.list_tools()},
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                if not tool_name or not isinstance(tool_name, str):
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Missing 'name' in tool call params"},
                    }
                if not isinstance(arguments, dict):
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Invalid params: 'arguments' must be an object"},
                    }

                try:
                    text_contents = await self.call_tool(tool_name, arguments)
                    is_error = False
                    for tc in text_contents:
                        try:
                            parsed = json.loads(tc.text)
                            if isinstance(parsed, dict):
                                if (
                                    parsed.get("success") is False
                                    or bool(parsed.get("error"))
                                    or parsed.get("isError") is True
                                ):
                                    is_error = True
                                    break
                        except Exception:
                            pass

                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [tc.to_dict() for tc in text_contents],
                            "isError": is_error,
                        },
                    }
                except PermissionError as pe:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32003, "message": f"RBAC Permission Denied: {str(pe)}"},
                    }
                except ValueError as ve:
                    # Check if unknown tool or invalid params
                    if "Unknown MCP tool" in str(ve):
                        code = -32601
                    else:
                        code = -32602
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": code, "message": str(ve)},
                    }
                except Exception as ex:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": f"Tool execution failed: {str(ex)}"},
                    }

            elif method == "resources/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"resources": self.list_resources()},
                }

            elif method == "resources/read":
                uri = params.get("uri")
                if not uri:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Missing 'uri' in resource params"},
                    }
                content = await self.read_resource(uri)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(content, default=str),
                            }
                        ]
                    },
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

        except Exception as e:
            logger.error("Unhandled exception in handle_jsonrpc for method %s: %s", method, e)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": f"Internal error: {str(e)}"},
            }

    # ========================================================================
    # Stdio and HTTP/SSE Transports
    # ========================================================================

    async def run_stdio(self) -> None:
        """Run standard I/O JSON-RPC transport loop over stdin/stdout."""
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

        logger.info("Alpha MCP Server started on stdio transport.")

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue

            response = await self.handle_jsonrpc(line)
            response_json = json.dumps(response) + "\n"
            writer.write(response_json.encode("utf-8"))
            await writer.drain()

    def create_asgi_app(self) -> Any:
        """Creates an ASGI Starlette application supporting HTTP POST and SSE."""
        if not HAS_STARLETTE:
            raise RuntimeError("Starlette is required to run the HTTP/SSE transport. Install starlette or fastapi.")

        async def mcp_endpoint(request: Request) -> Response:
            body = await request.json()
            response = await self.handle_jsonrpc(body)
            return JSONResponse(response)

        async def sse_endpoint(request: Request) -> Response:
            async def event_generator():
                yield f"event: endpoint\ndata: /mcp\n\n"
                while True:
                    await asyncio.sleep(15)
                    yield f": ping\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        routes = [
            Route("/mcp", mcp_endpoint, methods=["POST"]),
            Route("/sse", sse_endpoint, methods=["GET"]),
        ]
        return Starlette(routes=routes)

    # ========================================================================
    # 15 Built-in Tool Handlers (Binding to Subsystems with Graceful Fallbacks)
    # ========================================================================

    def _handle_vault_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        agent_id = args.get("agent_id", "CEO")

        if self.vault and hasattr(self.vault, "read"):
            data = self.vault.read(path)
            return {"path": path, "found": data is not None, "data": data, "success": data is not None}

        return {"path": path, "found": False, "data": None, "success": False}

    def _handle_vault_write(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        data = args["data"]
        agent_id = args.get("agent_id")

        # Inviolable CAO Confinement Rule at MCP Gateway
        agent_upper = str(agent_id or "").strip().upper()
        norm_parts = str(path).strip("/\\").replace("\\", "/").split("/")
        is_audit = len(norm_parts) >= 3 and norm_parts[0] == "projects" and norm_parts[2] == "audit"
        if agent_upper.startswith("CAO") and not is_audit:
            raise PermissionError(
                f"Access Denied: CAO agent '{agent_id}' is restricted to projects/{{id}}/audit/* (attempted: {path})"
            )

        if self.vault and hasattr(self.vault, "write"):
            success = self.vault.write(path, data, agent_id=agent_id)
            return {"path": path, "success": bool(success)}

        return {"path": path, "success": True}

    def _handle_vault_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args["query"]
        scope = args.get("scope", "all")
        top_k = min(20, max(1, int(args.get("top_k", 5))))
        agent_id = args.get("agent_id", "CEO")

        path_prefix = None if scope == "all" else scope

        if self.vault and hasattr(self.vault, "search"):
            results = self.vault.search(query, n_results=top_k, path_prefix=path_prefix)
            return {"query": query, "scope": scope, "count": len(results), "results": results, "success": True}

        return {"query": query, "scope": scope, "count": 0, "results": [], "success": True}

    def _handle_vault_save_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = args["agent_id"]
        mem = args["memory"]
        mem_type = mem["type"]
        content = mem["content"]
        importance = int(mem.get("importance", 3))
        project_id = mem.get("project_id")
        context = mem.get("context")
        tags = mem.get("tags", [])

        if importance < 1 or importance > 10:
            raise ValueError(f"importance must be between 1 and 10, got {importance}")

        if self.vault and hasattr(self.vault, "append_memory"):
            try:
                mem_id = self.vault.append_memory(
                    agent_id=agent_id,
                    memory_type=mem_type,
                    content=content,
                    importance=importance,
                    project_id=project_id,
                    context=context,
                    tags=tags,
                )
            except TypeError:
                mem_id = self.vault.append_memory(
                    agent_id=agent_id,
                    memory_type=mem_type,
                    content=content,
                    importance=importance,
                    project_id=project_id,
                )
            return {"memory_id": mem_id, "agent_id": agent_id, "saved": True, "success": True}

        mem_id = f"mem_{agent_id}_{uuid.uuid4().hex[:8]}"
        return {"memory_id": mem_id, "agent_id": agent_id, "saved": True, "success": True}

    def _handle_agent_delegate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        project_id = args["project_id"]
        from_agent = args.get("from_agent", "CEO")
        to_agents = args["to_agents"]
        task = args["task"]
        expected_deliverable = args["expected_deliverable"]
        priority = args.get("priority", "medium")
        del_id = f"del_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        if str(from_agent).strip().upper() != "CEO":
            raise PermissionError(f"Authority Denied: Only CEO holds delegation authority. Agent '{from_agent}' cannot delegate.")

        if not to_agents or not isinstance(to_agents, list):
            raise ValueError("to_agents must be a non-empty list of agent IDs")

        return {
            "delegation_id": del_id,
            "project_id": project_id,
            "from_agent": from_agent,
            "to_agents": to_agents,
            "task": task,
            "expected_deliverable": expected_deliverable,
            "priority": priority,
            "status": "dispatched",
            "delegated": True,
            "success": True,
        }

    def _handle_agent_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = args["agent_id"]
        include_mem = args.get("include_memory_summary", False)

        if self.agents and hasattr(self.agents, "get"):
            agent = self.agents.get(agent_id)
            if agent:
                status = getattr(agent, "status", "active")
                role = getattr(agent, "role", agent_id)
                model = getattr(agent, "assigned_model", "llama3.2")
                tokens = getattr(agent, "total_tokens_used", 0)
                res = {
                    "agent_id": agent_id,
                    "status": status,
                    "role": role,
                    "assigned_model": model,
                    "tokens_used": tokens,
                    "success": True,
                }
                if include_mem and self.vault and hasattr(self.vault, "search"):
                    memories = self.vault.search(agent_id, n_results=3, path_prefix=f"agents/{agent_id}")
                    res["memory_summary"] = memories
                return res

        return {
            "agent_id": agent_id,
            "status": "active",
            "role": agent_id,
            "assigned_model": "llama3.2",
            "current_task": "Idle or executing",
            "success": True,
        }

    def _handle_agent_hire(self, args: Dict[str, Any]) -> Dict[str, Any]:
        role = args["role"]
        full_title = args["full_title"]
        jd_content = args["jd_content"]
        skills = args["skills"]
        assigned_model = args["assigned_model"]
        reports_to = args.get("reports_to", "CEO")
        peers = args.get("peers", [])

        profile = {
            "agent_id": role,
            "role": role,
            "full_title": full_title,
            "jd_content": jd_content,
            "skills": skills,
            "assigned_model": assigned_model,
            "reports_to": reports_to,
            "peers": peers,
            "status": "active",
            "hired_at": time.time(),
        }

        self._local_agents[role] = profile

        if self.vault and hasattr(self.vault, "write"):
            self.vault.write(f"agents/{role}/profile.json", profile, agent_id="CHRO")

        return {
            "agent_id": role,
            "role": role,
            "full_title": full_title,
            "hired": True,
            "status": "active",
            "success": True,
        }

    def _handle_project_create(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args["name"]
        user_goal = args["user_goal"]
        priority = args["priority"]
        assigned_agents = args.get("assigned_agents", ["CEO"])
        tags = args.get("tags", [user_goal])

        if self.vault and hasattr(self.vault, "create_project"):
            proj_id = self.vault.create_project(title=name, description=user_goal, founder_goals=tags)
            return {
                "project_id": proj_id,
                "name": name,
                "status": "planning",
                "priority": priority,
                "assigned_agents": assigned_agents,
                "success": True,
            }

        proj_id = f"proj_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self._local_projects[proj_id] = {
            "project_id": proj_id,
            "name": name,
            "user_goal": user_goal,
            "priority": priority,
            "status": "planning",
            "assigned_agents": assigned_agents,
            "created_at": time.time(),
        }
        return {
            "project_id": proj_id,
            "name": name,
            "status": "planning",
            "priority": priority,
            "assigned_agents": assigned_agents,
            "success": True,
        }

    def _handle_project_update_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        project_id = args["project_id"]
        status = args["status"]
        agent_id = args["agent_id"]
        note = args.get("note")

        if status not in ("planning", "in_progress", "in_audit", "awaiting_approval", "complete", "archived"):
            raise ValueError(f"Invalid project status: {status}")

        if project_id in self._local_projects:
            self._local_projects[project_id]["status"] = status
            self._local_projects[project_id]["updated_at"] = time.time()

        if self.vault and hasattr(self.vault, "read") and hasattr(self.vault, "write"):
            manifest = self.vault.read(f"projects/{project_id}/manifest.json")
            if manifest:
                manifest["status"] = status
                manifest["updated_at"] = time.time()
                self.vault.write(f"projects/{project_id}/manifest.json", manifest, agent_id=agent_id)

        return {
            "project_id": project_id,
            "status": status,
            "updated_by": agent_id,
            "note": note,
            "updated": True,
            "success": True,
        }

    def _handle_project_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        status_filter = args.get("status")
        agent_filter = args.get("agent_id")
        limit = int(args.get("limit", 20))

        projects = []
        if self.vault and hasattr(self.vault, "projects") and isinstance(self.vault.projects, dict):
            projects = list(self.vault.projects.values())
        else:
            projects = list(self._local_projects.values())

        if status_filter:
            projects = [p for p in projects if p.get("status") == status_filter]
        if agent_filter:
            projects = [p for p in projects if agent_filter in p.get("assigned_agents", [])]

        return {"count": len(projects[:limit]), "projects": projects[:limit], "success": True}

    def _handle_thread_post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        project_id = args["project_id"]
        from_agent = args["from_agent"]
        to_agents = args["to_agents"]
        msg_type = args["type"]
        content = args["content"]
        subject = args.get("subject", f"[{msg_type}] From {from_agent}")
        in_reply_to = args.get("in_reply_to")

        if self.threads and hasattr(self.threads, "post_message"):
            msg = self.threads.post_message(
                thread_id=f"thread_{project_id}_main",
                sender_agent=from_agent,
                content=content,
                to_agents=to_agents,
                message_type=msg_type,
                subject=subject,
                in_reply_to=in_reply_to,
                project_id=project_id,
            )
            return {
                "message_id": getattr(msg, "message_id", str(uuid.uuid4())),
                "thread_id": f"thread_{project_id}_main",
                "project_id": project_id,
                "posted": True,
                "status": "sent",
                "success": True,
            }

        # In-memory thread fallback
        if project_id not in self._local_threads:
            self._local_threads[project_id] = []

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        msg_dict = {
            "message_id": msg_id,
            "project_id": project_id,
            "from_agent": from_agent,
            "to_agents": to_agents,
            "type": msg_type,
            "subject": subject,
            "content": content,
            "in_reply_to": in_reply_to,
            "timestamp": time.time(),
        }
        self._local_threads[project_id].append(msg_dict)

        return {
            "message_id": msg_id,
            "thread_id": f"thread_{project_id}_main",
            "project_id": project_id,
            "posted": True,
            "status": "sent",
            "message_count": len(self._local_threads[project_id]),
            "success": True,
        }

    def _handle_thread_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        project_id = args["project_id"]
        filter_type = args.get("filter_type")
        filter_from = args.get("filter_from_agent")
        limit = int(args.get("limit", 100))

        messages: List[Dict[str, Any]] = []
        if self.threads and hasattr(self.threads, "get_thread_messages"):
            msgs = self.threads.get_thread_messages(f"thread_{project_id}_main", limit=limit, project_id=project_id)
            for m in msgs:
                if hasattr(m, "model_dump"):
                    messages.append(m.model_dump(mode="json"))
                elif isinstance(m, dict):
                    messages.append(m)
        else:
            messages = list(self._local_threads.get(project_id, []))

        if filter_type:
            messages = [m for m in messages if str(m.get("type", "")).strip().upper() == filter_type.strip().upper()]
        if filter_from:
            messages = [
                m for m in messages
                if str(m.get("from_agent", "")).strip().upper() == filter_from.strip().upper()
                or str(m.get("from", "")).strip().upper() == filter_from.strip().upper()
            ]

        return {"project_id": project_id, "count": len(messages[:limit]), "messages": messages[:limit], "success": True}

    def _handle_model_route(self, args: Dict[str, Any]) -> Dict[str, Any]:
        task_type = args["task_type"]
        complexity = int(args["complexity"])
        agent_id = args["agent_id"]
        prefer_free = args.get("prefer_free", True)

        if complexity < 1 or complexity > 5:
            raise ValueError(f"complexity must be between 1 and 5, got {complexity}")

        # Case-insensitive agent_id normalization for CAO overrides
        clean_agent = str(agent_id or "").strip().upper().replace("_", "-")

        # Inviolable CAO Audit Gate Override Rules
        if clean_agent in ("CAO", "CAO-C", "CAO-CLAUDE") or (clean_agent.startswith("CAO") and not ("G" in clean_agent or "GPT" in clean_agent)):
            return {
                "agent_id": agent_id,
                "task_type": task_type,
                "complexity": complexity,
                "recommended_model": "claude-3-5-sonnet",
                "model": "claude-3-5-sonnet",
                "provider": "anthropic",
                "tier": 5,
                "is_free": False,
                "success": True,
            }
        elif clean_agent in ("CAO-G", "CAO-CHATGPT", "CAO-GPT") or (clean_agent.startswith("CAO") and ("G" in clean_agent or "GPT" in clean_agent)):
            return {
                "agent_id": agent_id,
                "task_type": task_type,
                "complexity": complexity,
                "recommended_model": "gpt-4o",
                "model": "gpt-4o",
                "provider": "openai",
                "tier": 5,
                "is_free": False,
                "success": True,
            }

        if self.router and hasattr(self.router, "route"):
            config = self.router.route(task_type, complexity, agent_id)
            return {
                "agent_id": agent_id,
                "task_type": task_type,
                "complexity": complexity,
                "recommended_model": getattr(config, "model", str(config)),
                "model": getattr(config, "model", str(config)),
                "provider": getattr(config, "provider", "ollama"),
                "tier": getattr(config, "tier", complexity),
                "is_free": getattr(config, "is_free", True),
                "success": True,
            }
        elif complexity == 1:
            return {"agent_id": agent_id, "recommended_model": "llama3.2:1b", "model": "llama3.2:1b", "provider": "ollama", "tier": 1, "is_free": True, "success": True}
        elif complexity == 2:
            return {"agent_id": agent_id, "recommended_model": "llama3.2:3b", "model": "llama3.2:3b", "provider": "ollama", "tier": 2, "is_free": True, "success": True}
        elif complexity == 3:
            return {"agent_id": agent_id, "recommended_model": "llama-3.1-70b-versatile", "model": "llama-3.1-70b-versatile", "provider": "groq", "tier": 3, "is_free": True, "success": True}
        elif complexity == 4:
            return {"agent_id": agent_id, "recommended_model": "gemini-1.5-flash", "model": "gemini-1.5-flash", "provider": "gemini", "tier": 4, "is_free": True, "success": True}
        else:
            return {"agent_id": agent_id, "recommended_model": "claude-3-5-sonnet", "model": "claude-3-5-sonnet", "provider": "anthropic", "tier": 5, "is_free": False, "success": True}

    def _handle_user_profile_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = args.get("agent_id", "CEO")
        if self.vault and hasattr(self.vault, "get_user_profile"):
            prof = self.vault.get_user_profile()
            if isinstance(prof, dict):
                return prof

        return {
            "name": "Aman Jain",
            "role": "Founder & Chairman",
            "preferred_communication": "concise",
            "escalation_policy": "critical_only",
            "success": True,
        }

    def _handle_user_escalate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        project_id = args["project_id"]
        from_agent = args["from_agent"]
        question = args["question"]
        context = args["context"]
        urgency = args["urgency"]
        options = args.get("options", [])

        if urgency not in ("low", "medium", "high"):
            raise ValueError(f"Invalid urgency value: {urgency}. Must be one of: low, medium, high")

        esc_id = f"esc_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        return {
            "escalation_id": esc_id,
            "project_id": project_id,
            "from_agent": from_agent,
            "question": question,
            "context": context,
            "urgency": urgency,
            "options": options,
            "escalated": True,
            "status": "pending_founder_response",
            "success": True,
        }


# ============================================================================
# Factory Functions & Compatibility Aliases
# ============================================================================

NativeMCPServer = AlphaMCPServer


def create_mcp_server(
    vault_manager: Optional[Any] = None,
    agent_registry: Optional[Any] = None,
    model_router: Optional[Any] = None,
    thread_manager: Optional[Any] = None,
) -> AlphaMCPServer:
    """Factory creating configured AlphaMCPServer instance."""
    return AlphaMCPServer(
        vault_manager=vault_manager,
        agent_registry=agent_registry,
        model_router=model_router,
        thread_manager=thread_manager,
    )


# ============================================================================
# CLI Execution Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Alpha MCP Core Tool Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="MCP transport protocol")
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport")
    args = parser.parse_args()

    server = create_mcp_server()

    if args.transport == "stdio":
        asyncio.run(server.run_stdio())
    elif args.transport == "sse":
        if not HAS_STARLETTE:
            print("Error: Starlette or FastAPI required for SSE transport. Run: pip install starlette uvicorn", file=sys.stderr)
            sys.exit(1)
        import uvicorn
        app = server.create_asgi_app()
        uvicorn.run(app, host=args.host, port=args.port)
