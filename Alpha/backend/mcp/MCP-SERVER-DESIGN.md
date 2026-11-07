# Alpha MCP Server — Design & Tool Reference

> **Status:** Design Document
> **Last Updated:** 2026-11-06
> **Standard:** Model Context Protocol (MCP) v1.0

---

## 1. What Is Alpha's MCP Server?

Alpha exposes a **Model Context Protocol (MCP) server** that makes the entire Alpha system accessible as a set of structured tools.

This serves two critical purposes:

1. **Internal:** Alpha's agents themselves use MCP tools to interact with the Vault, communicate with each other, and delegate tasks — giving the AI agents a clean, typed interface to the system
2. **External:** Future Alpha sub-projects (other AI tools built with Alpha) can connect to Alpha's MCP server and use Alpha's C-suite as a service

---

## 2. MCP Server Architecture

```
Alpha MCP Server
├── Transport: stdio (local) + HTTP/SSE (for APK and sub-projects)
├── Authentication: Local token (stored in .env)
├── Tool Groups:
│   ├── vault/      - Vault read/write/search operations
│   ├── agents/     - Agent delegation and status
│   ├── projects/   - Project management operations
│   ├── threads/    - Inter-agent communication
│   ├── model/      - Model routing decisions
│   └── user/       - User profile and preferences
```

---

## 3. MCP Tool Definitions

### 3.1 Vault Tools

#### `vault_read`
Read a specific path from Alpha's Vault.
```json
{
  "name": "vault_read",
  "description": "Read structured data from a specific path in Alpha's Vault.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "Vault path e.g. 'company/identity'" },
      "agent_id": { "type": "string", "description": "Requesting agent's ID" }
    },
    "required": ["path", "agent_id"]
  }
}
```

#### `vault_write`
Write or update data in Alpha's Vault.
```json
{
  "name": "vault_write",
  "description": "Write structured data to Alpha's Vault. Agent must have write access to the path.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "data": { "type": "object" },
      "agent_id": { "type": "string" },
      "append": { "type": "boolean", "default": false }
    },
    "required": ["path", "data", "agent_id"]
  }
}
```

#### `vault_search`
Semantic search across the Vault.
```json
{
  "name": "vault_search",
  "description": "Perform semantic search across Alpha's Vault to find relevant past context, decisions, or knowledge.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Natural language search query" },
      "scope": {
        "type": "string",
        "enum": ["all", "projects", "knowledge", "agents", "user"],
        "default": "all"
      },
      "top_k": { "type": "integer", "default": 5, "maximum": 20 },
      "agent_id": { "type": "string" }
    },
    "required": ["query", "agent_id"]
  }
}
```

#### `vault_save_memory`
Save an episodic memory entry for an agent.
```json
{
  "name": "vault_save_memory",
  "description": "Save a memory entry to an agent's episodic memory log in the Vault.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id": { "type": "string" },
      "memory": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["decision", "observation", "feedback", "lesson"] },
          "content": { "type": "string" },
          "context": { "type": "string" },
          "project_id": { "type": "string" },
          "importance": { "type": "integer", "minimum": 1, "maximum": 5 },
          "tags": { "type": "array", "items": { "type": "string" } }
        },
        "required": ["type", "content", "importance"]
      }
    },
    "required": ["agent_id", "memory"]
  }
}
```

---

### 3.2 Agent Tools

#### `agent_delegate`
CEO delegates a task to one or more agents.
```json
{
  "name": "agent_delegate",
  "description": "CEO delegates a specific task to one or more C-suite agents.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string" },
      "from_agent": { "type": "string", "const": "CEO" },
      "to_agents": { "type": "array", "items": { "type": "string" } },
      "task": { "type": "string", "description": "Task description" },
      "context": { "type": "string", "description": "Background context for the task" },
      "expected_deliverable": { "type": "string" },
      "deadline_minutes": { "type": "integer", "description": "Minutes to complete" },
      "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] }
    },
    "required": ["project_id", "from_agent", "to_agents", "task", "expected_deliverable"]
  }
}
```

#### `agent_status`
Get the current status of an agent.
```json
{
  "name": "agent_status",
  "description": "Get the current status and active task of a C-suite agent.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id": { "type": "string" },
      "include_memory_summary": { "type": "boolean", "default": false }
    },
    "required": ["agent_id"]
  }
}
```

#### `agent_hire`
CHRO uses this to create a new agent.
```json
{
  "name": "agent_hire",
  "description": "CHRO creates and registers a new agent in Alpha's company. Requires a complete agent profile.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "role": { "type": "string" },
      "full_title": { "type": "string" },
      "jd_content": { "type": "string", "description": "Full Job Description markdown content" },
      "skills": { "type": "array", "items": { "type": "string" } },
      "assigned_model": { "type": "string" },
      "reports_to": { "type": "string" },
      "peers": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["role", "full_title", "jd_content", "skills", "assigned_model"]
  }
}
```

---

### 3.3 Project Tools

#### `project_create`
Create a new project in Alpha.
```json
{
  "name": "project_create",
  "description": "Create a new project. Called by CEO when a new user goal arrives.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "user_goal": { "type": "string", "description": "Verbatim user goal" },
      "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
      "assigned_agents": { "type": "array", "items": { "type": "string" } },
      "deadline": { "type": "string", "format": "date-time", "nullable": true },
      "tags": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["name", "user_goal", "priority"]
  }
}
```

#### `project_update_status`
Update project status.
```json
{
  "name": "project_update_status",
  "description": "Update the status of an existing project.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string" },
      "status": {
        "type": "string",
        "enum": ["planning", "in_progress", "in_audit", "awaiting_approval", "complete", "archived"]
      },
      "agent_id": { "type": "string" },
      "note": { "type": "string" }
    },
    "required": ["project_id", "status", "agent_id"]
  }
}
```

#### `project_list`
List all projects with filters.
```json
{
  "name": "project_list",
  "description": "List projects with optional filters.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "status": { "type": "string", "nullable": true },
      "agent_id": { "type": "string", "nullable": true, "description": "Filter by assigned agent" },
      "limit": { "type": "integer", "default": 20 },
      "include_archived": { "type": "boolean", "default": false }
    }
  }
}
```

---

### 3.4 Thread Tools

#### `thread_post`
Post a message to a project thread.
```json
{
  "name": "thread_post",
  "description": "Post a message to a project's inter-agent communication thread.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string" },
      "from_agent": { "type": "string" },
      "to_agents": { "type": "array", "items": { "type": "string" } },
      "type": {
        "type": "string",
        "enum": ["DELEGATION", "DELIVERABLE", "QUESTION", "RESPONSE", "REVIEW_REQUEST", "SYNTHESIS", "AUDIT_REQUEST", "AUDIT_REPORT", "USER_ESCALATION"]
      },
      "subject": { "type": "string" },
      "content": { "type": "string" },
      "in_reply_to": { "type": "string", "nullable": true }
    },
    "required": ["project_id", "from_agent", "to_agents", "type", "content"]
  }
}
```

#### `thread_read`
Read a project's communication thread.
```json
{
  "name": "thread_read",
  "description": "Read all messages in a project's thread, optionally filtered by type or agent.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string" },
      "agent_id": { "type": "string", "description": "Requesting agent" },
      "filter_type": { "type": "string", "nullable": true },
      "filter_from_agent": { "type": "string", "nullable": true },
      "since": { "type": "string", "format": "date-time", "nullable": true }
    },
    "required": ["project_id", "agent_id"]
  }
}
```

---

### 3.5 Model Routing Tools

#### `model_route`
Get the recommended model for a task.
```json
{
  "name": "model_route",
  "description": "Get the recommended AI model for a specific task based on complexity and type.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_type": { "type": "string", "description": "Type of task e.g. 'technical_spec', 'draft_copy'" },
      "complexity": { "type": "integer", "minimum": 1, "maximum": 5 },
      "agent_id": { "type": "string" },
      "prefer_free": { "type": "boolean", "default": true }
    },
    "required": ["task_type", "complexity", "agent_id"]
  }
}
```

---

### 3.6 User Tools

#### `user_profile_read`
Read the user's profile from the Vault.
```json
{
  "name": "user_profile_read",
  "description": "Read the current user's profile and preferences.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id": { "type": "string" }
    },
    "required": ["agent_id"]
  }
}
```

#### `user_escalate`
Escalate a decision to the user.
```json
{
  "name": "user_escalate",
  "description": "Escalate a decision or question to the user via the CEO interface. Used when agents cannot proceed without user input.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": { "type": "string" },
      "from_agent": { "type": "string" },
      "question": { "type": "string" },
      "context": { "type": "string" },
      "options": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Suggested options for user to choose from (optional)"
      },
      "urgency": { "type": "string", "enum": ["low", "medium", "high"] }
    },
    "required": ["project_id", "from_agent", "question", "context", "urgency"]
  }
}
```

---

## 4. MCP Server Implementation

```python
# mcp/server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import asyncio

from vault import VaultManager
from agents import AgentRegistry
from projects import ProjectManager

app = Server("alpha-mcp")
vault = VaultManager()
agents = AgentRegistry()
projects = ProjectManager()

@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return all Alpha MCP tools."""
    return ALPHA_TOOLS  # All tool definitions above

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Route tool calls to appropriate handlers."""
    
    handlers = {
        "vault_read": vault.read,
        "vault_write": vault.write,
        "vault_search": vault.search,
        "vault_save_memory": vault.save_memory,
        "agent_delegate": agents.delegate,
        "agent_status": agents.status,
        "agent_hire": agents.hire,
        "project_create": projects.create,
        "project_update_status": projects.update_status,
        "project_list": projects.list_all,
        "thread_post": projects.post_message,
        "thread_read": projects.read_thread,
        "model_route": route_model,
        "user_profile_read": vault.get_user_profile,
        "user_escalate": agents.escalate_to_user,
    }
    
    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")
    
    result = await handler(**arguments)
    return [TextContent(type="text", text=str(result))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. MCP Configuration (for client agents)

Each agent connects to Alpha's MCP server via this config:

```json
{
  "mcpServers": {
    "alpha": {
      "command": "python",
      "args": ["d:/AI/Aman Jain - Master/Alpha/backend/mcp/server.py"],
      "env": {
        "ALPHA_VAULT_PATH": "d:/AI/Aman Jain - Master/Alpha/Alpha-Vault",
        "ALPHA_TOKEN": "${ALPHA_MCP_TOKEN}"
      }
    }
  }
}
```

---

## 6. MCP Usage Flow — Example

```
User: "Build a website for my AI consultancy"

1. CEO calls: project_create({ name: "AI Consultancy Website", user_goal: "...", priority: "high" })
   → Returns: project_id = "proj_001"

2. CEO calls: model_route({ task_type: "strategic_planning", complexity: 4, agent_id: "CEO" })
   → Returns: "gemini/gemini-1.5-flash"

3. CEO delegates to CTO:
   agent_delegate({ project_id: "proj_001", to_agents: ["CTO"], task: "Define technical architecture..." })

4. CEO delegates to CMO:
   agent_delegate({ project_id: "proj_001", to_agents: ["CMO"], task: "Define brand, audience, features..." })

5. CTO reads vault for past tech decisions:
   vault_search({ query: "web app stack decisions", scope: "knowledge", agent_id: "CTO" })

6. CTO posts deliverable:
   thread_post({ project_id: "proj_001", from_agent: "CTO", type: "DELIVERABLE", content: "..." })

7. CMO reads CTO's post to align on feasibility:
   thread_read({ project_id: "proj_001", agent_id: "CMO" })

8. CEO reads all deliverables and synthesizes:
   thread_read({ project_id: "proj_001", agent_id: "CEO" })
   vault_write({ path: "projects/proj_001/final_output", data: {...}, agent_id: "CEO" })

9. CEO requests audit:
   agent_delegate({ to_agents: ["CAO-C", "CAO-G"], task: "Audit this output", ... })

10. CAO agents post audit reports, CEO incorporates, delivers to user.

11. All agents save memories:
    vault_save_memory({ agent_id: "CTO", memory: { type: "decision", content: "Chose Next.js for...", importance: 4 } })
```

This is the complete, closed loop of Alpha working autonomously on your behalf.
