"""backend/mcp/__init__.py - Project Alpha MCP Package Exports.

Exports the core FastMCP / MCP SDK server, Native pure-Python server fallback,
canonical tool definitions, and canonical resources.
"""

from __future__ import annotations

from .server import (
    ALPHA_RESOURCES,
    ALPHA_TOOLS,
    AlphaMCPServer,
    NativeMCPServer,
    ResourceDefinition,
    TextContent,
    ToolDefinition,
    create_mcp_server,
)

__all__ = [
    "AlphaMCPServer",
    "NativeMCPServer",
    "create_mcp_server",
    "ALPHA_TOOLS",
    "ALPHA_RESOURCES",
    "TextContent",
    "ToolDefinition",
    "ResourceDefinition",
]
