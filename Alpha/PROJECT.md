# Project: Alpha — Personal Autonomous AI Executive Operating System

## Architecture
Project Alpha is a personal autonomous AI executive operating system comprising a desktop backend brain, a Model Context Protocol (MCP) tool server, and an interactive Flutter mobile interface.

```
                                  ┌────────────────────────────────────────────────┐
                                  │                FOUNDER (USER)                  │
                                  │           Flutter Mobile Application           │
                                  │   (Archify+ Canvas, Pulsing Flows, Tasks UI)   │
                                  └───────────────▲────────────────┬───────────────┘
                                                  │                │
                                  WebSocket Telemetry         REST Goal Input
                                  (Progress, Archify Nodes)   (/api/goals)
                                                  │                │
                                  ┌───────────────┴────────────────▼───────────────┐
                                  │            FastAPI REST & WebSocket            │
                                  │       (backend/api/main.py, port 8765)         │
                                  └───────────────▲────────────────┬───────────────┘
                                                  │                │
                                  ┌───────────────┴────────────────▼───────────────┐    ┌──────────────────────────┐
┌───────────────────────────┐     │      Tri-Framework Orchestration Engine        ├───►│       Model Router       │
│     Model Context         │◄────┤  - Goal Parser & Decomposition                 │    │  (backend/model_router)  │
│     Protocol (MCP)        │     │  - CrewAI Hierarchical Task Execution          │    │                          │
│  (backend/mcp/server.py)  │     │  - AG2 GroupChat Deliberation Threads          │    │  • Tier 1-2: Ollama      │
│                           │     │  - LangGraph State Machine & Self-Correction   │    │  • Tier 3: Groq 70B      │
│  15 Registered Tools:     │     │  - Archify Visual Graph Generator              │    │  • Tier 4: Gemini Flash  │
│  • vault_read/write/search│     │  - Dual CAO Audit Gate (2-Round Escalation Cap)│    │  • Tier 5: Claude Sonnet │
│  • agent_delegate/status  │     └───────────────▲────────────────┬───────────────┘    │  • CAO: Claude & GPT-4o  │
│  • project_create/list    │                     │                │                    └──────────────────────────┘
│  • thread_post/read       │                     │                │
│  • model_route            │     ┌───────────────┴────────────────▼───────────────┐
│  • user_profile/escalate  │     │                 Alpha's Vault                  │
└───────────────────────────┘     │             (backend/vault/vault_manager)      │
                                  ├────────────────────────┬───────────────────────┤
                                  │      ChromaDB Store    │      SQLite Store     │
                                  │   (nomic-embed-text)   │  (Metadata, Schemas,  │
                                  │  Semantic Vector Search│   JSONL Thread Logs)  │
                                  └────────────────────────┴───────────────────────┘
```

---

## Feature Inventory
Every feature identified during the comprehensive survey across backend, vault, agents, MCP, mobile, and orchestration specs is cataloged below with its designated implementation milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SQLite KV Store | Key-value document store with path indexing (`get`, `set`, `delete`, `list`) | M1 | Implementation Plan Task 1; Vault Arch §2 |
| 2 | SQLite Relational Schema | Tables for agents, episodic memory, threads, decisions, system metrics, API registry | M1 | CIO JD §5.2; Vault Arch §4 |
| 3 | ChromaDB Vector Store | Persistent vector store partitioned by collections (`knowledge`, `agent_memory`, `projects`) | M1 | Implementation Plan Task 1; Vault Arch §2 |
| 4 | Ollama Embeddings Wrapper | `nomic-embed-text` wrapper for vector embeddings with mock/fallback support | M1 | Implementation Plan Task 1; Master Design §6.4 |
| 5 | Pydantic Vault Schemas | Schemas for `CompanyIdentity`, `AgentProfile`, `ProjectManifest`, `EpisodicMemory`, `ThreadMessage`, `UserProfile` | M1 | Master Design §6.2; Vault Arch §4 |
| 6 | Vault Manager Engine | Unified facade combining SQLite, Chroma, access control rules, and directory snapshots | M1 | Implementation Plan Task 1; Vault Arch §5 |
| 7 | Model Router Core | Routes tasks across 5 complexity tiers with zero-cost priority | M2 | Implementation Plan Task 2; Master Design §8.1 |
| 8 | Ollama Client | Free local LLM client for Tier 1 & 2 (`llama3.2`) | M2 | Implementation Plan Task 2 |
| 9 | Groq Client | Fast free cloud client for Tier 3 (`llama-3.1-70b`) | M2 | Implementation Plan Task 2 |
| 10 | Gemini Client | High-context free cloud client for Tier 4 (`gemini-1.5-flash`) | M2 | Implementation Plan Task 2 |
| 11 | Claude Client | Paid Anthropic client for Tier 5 and mandatory `CAO-Claude` (`claude-3-5-sonnet`) | M2 | Implementation Plan Task 2; CAO JD §9 |
| 12 | OpenAI Client | Paid OpenAI client for Tier 5 and mandatory `CAO-ChatGPT` (`gpt-4o`) | M2 | Implementation Plan Task 2; CAO JD §9 |
| 13 | Model Fallback System | Step-down degradation to local Ollama on cloud failure; CAO override preservation | M2 | Implementation Plan Task 2 |
| 14 | Base Agent Class | Abstract agent base: JD loading, context packing, memory saving, execution harness | M3 | Implementation Plan Task 3 |
| 15 | Agent Registry | Lifecycle registry, active status tracking, and directory loading for 12 agents | M3 | Implementation Plan Task 3 |
| 16 | CEO Agent Core | Intake, workstream decomposition, brief creation, monitoring, synthesis, user relationship | M3 | Implementation Plan Task 3; CEO JD |
| 17 | CTO Agent | Architecture Design Documents, Tech Specs, Archify HTML diagrams, code standards | M4 | Implementation Plan Task 4; CTO JD |
| 18 | CMO Agent | Marketing growth engine, personas, messaging frameworks, competitive intelligence | M4 | Implementation Plan Task 4; CMO JD |
| 19 | CPO Agent | Product PRDs, user story maps, MVP scoping (MoSCoW/RICE), anti-gold-plating | M4 | Implementation Plan Task 4; CPO JD |
| 20 | CDO Agent | Alpha Design System, OLED tokens, Archify visual styling, wireframes | M4 | Implementation Plan Task 4; CDO JD |
| 21 | CFO Agent | Free-first token governance, budget modeling, unit economics (CPQ, CTS) | M4 | Implementation Plan Task 4; CFO JD |
| 22 | COO Agent | Project Execution Plans (PEP), timeline matrices, critical path tracking | M4 | Implementation Plan Task 4; COO JD |
| 23 | CHRO Agent | Agent lifecycle onboarding, Agent Registry management, performance reviews | M4 | Implementation Plan Task 4; CHRO JD |
| 24 | CIO Agent | Vault primary custodian, schema governance, ECC memory compression | M4 | Implementation Plan Task 4; CIO JD |
| 25 | CSO Agent | Strategic alignment, OKRs (annual & quarterly), alignment checking | M4 | Implementation Plan Task 4; CSO JD |
| 26 | CLO Agent | Legal risk shield, GPL contamination defense, permissive licensing governance | M4 | Implementation Plan Task 4; CLO JD |
| 27 | Dual CAO Agent (Claude & GPT) | Dual-instance auditing using Addy Osmani 5-axis review rubric (Min score 85%) | M5 | Implementation Plan Task 5; CAO JD |
| 28 | CAO Consensus & Consolidated Report | Combines independent Claude and GPT audits, separating defects from alternative views | M5 | Implementation Plan Task 5; CAO JD |
| 29 | 2-Round Escalation Cap | Strict maximum of 2 revision rounds before mandatory escalation to human Founder | M5 | Implementation Plan Task 5; CAO JD |
| 30 | Goal Parser | Natural language parser converting user directives into structured workstreams | M6 | Implementation Plan Task 6; Master Design §9.1 |
| 31 | Thread Manager | Project thread message routing, persistence in JSONL/SQLite, broadcast to WebSocket | M6 | Implementation Plan Task 6; Master Design §7 |
| 32 | Delegation Engine | Workstream dispatch, dependency execution, parallel agent management | M6 | Implementation Plan Task 6; CEO JD §5 |
| 33 | Output Synthesizer | Combines multi-agent deliverables, resolves contradictions, formats per user preferences | M6 | Implementation Plan Task 6; CEO JD §3 |
| 34 | Scheduler | Critical path and dependency ordering engine | M6 | Implementation Plan Task 6 |
| 35 | LangGraph State Graph | Cyclic state machine, checkpointing, and reflection loops for self-correction | M6 | Master Design §14; Integrations §1 |
| 36 | CrewAI Hierarchical Flow | Structured task delegation with CEO as manager and agents as role players | M6 | Integrations §2.5 |
| 37 | AG2 GroupChat Engine | Multi-agent conversational deliberation and consensus termination in project threads | M6 | Integrations §2.4 |
| 38 | Archify Diagram Engine | Visual architecture diagram generation (HTML/SVG/JSON graph) for mobile embedding | M6 | Integrations §2.1 |
| 39 | 15-Tool MCP Server Core | FastMCP / MCP SDK server on stdio / SSE registering all 15 system tools | M7 | Implementation Plan Task 7; MCP Design |
| 40 | MCP Tool: vault_read | Reads structured or raw document from Vault by path | M7 | MCP Design §3.1 |
| 41 | MCP Tool: vault_write | Writes data to Vault path with schema validation | M7 | MCP Design §3.1 |
| 42 | MCP Tool: vault_search | Hybrid semantic & keyword search across Vault | M7 | MCP Design §3.1 |
| 43 | MCP Tool: vault_save_memory | Appends episodic memory for an agent with importance rating | M7 | MCP Design §3.1 |
| 44 | MCP Tool: agent_delegate | CEO delegates subtask to an executive agent | M7 | MCP Design §3.2 |
| 45 | MCP Tool: agent_status | Queries current activity and health of an agent | M7 | MCP Design §3.2 |
| 46 | MCP Tool: agent_hire | CHRO registers a new agent persona | M7 | MCP Design §3.2 |
| 47 | MCP Tool: project_create | Scaffolds a new project directory and manifest in Vault | M7 | MCP Design §3.3 |
| 48 | MCP Tool: project_update_status | Updates project status (`planning`, `active`, `review`, `completed`, `blocked`) | M7 | MCP Design §3.3 |
| 49 | MCP Tool: project_list | Lists all projects filtered by status | M7 | MCP Design §3.3 |
| 50 | MCP Tool: thread_post | Posts a message to a project discussion thread | M7 | MCP Design §3.4 |
| 51 | MCP Tool: thread_read | Reads messages from a project thread with optional limit | M7 | MCP Design §3.4 |
| 52 | MCP Tool: model_route | Resolves optimal model tier for given task and complexity | M7 | MCP Design §3.5 |
| 53 | MCP Tool: user_profile_read | Reads Founder user profile and preferences | M7 | MCP Design §3.6 |
| 54 | MCP Tool: user_escalate | Triggers push escalation to Founder mobile client upon CAO deadlocks | M7 | MCP Design §3.6 |
| 55 | FastAPI Backend Engine | ASGI application on port 8765 with CORS, error handling, and lifespan management | M8 | Implementation Plan Task 8; Master Design §9.1 |
| 56 | Local Token Authentication | Bearer token verification from `.env` (`ALPHA_TOKEN`) for API and WebSocket requests | M8 | Implementation Plan Task 8 |
| 57 | REST API: /api/goals | Goal submission and status query endpoints | M8 | Implementation Plan Task 8 |
| 58 | REST API: /api/projects | Project list, detail, and thread endpoints | M8 | Implementation Plan Task 8 |
| 59 | REST API: /api/agents | Agent list, profile, and telemetry endpoints | M8 | Implementation Plan Task 8 |
| 60 | REST API: /api/vault | Vault document read and hybrid search endpoints | M8 | Implementation Plan Task 8 |
| 61 | WebSocket Telemetry Stream | Real-time bi-directional streaming for progress bars, graph nodes, and thread logs | M8 | Implementation Plan Task 8; Master Design §10 |
| 62 | Vault Initializer & Bootstrapper | Creates initial directory tree, pre-populates company identity, agent registry | M9 | Implementation Plan Task 9; Vault Arch §6 |
| 63 | Interactive First-Run Setup | Interactive prompt configuring Founder profile, company name, API keys | M9 | Implementation Plan Task 9 |
| 64 | Alpha CLI Tool (`alpha.py`) | Main CLI entry point: `alpha setup`, `alpha start`, `alpha status` | M9 | Implementation Plan Task 9 |
| 65 | Flutter Project & Dependencies | Flutter app structure, `pubspec.yaml`, assets, fonts, provider state management | M10 | Implementation Plan Task 10; Mobile Survey |
| 66 | OLED Dark Mode Theme System | Alpha visual styling tokens, deep blacks (`#0A0A0F`), neon accents (`#06B6D4`, `#3B82F6`) | M10 | Implementation Plan Task 10; CDO JD |
| 67 | Mobile Data Models | Dart models: `Project`, `Agent`, `TaskProgress`, `GraphNode`, `GraphEdge`, `ThreadMessage` | M10 | Implementation Plan Task 10; Mobile Survey |
| 68 | REST API Client (`AlphaApiClient`) | HTTP service with Bearer auth, timeout handling, error envelopes | M10 | Implementation Plan Task 10; Mobile Survey |
| 69 | WebSocket Service (`AlphaWebSocketService`) | Event streaming, typed message envelopes, auto-reconnect with exponential backoff | M10 | Implementation Plan Task 10; Mobile Survey |
| 70 | Archify+ Interactive Canvas | Native Flutter `CustomPainter` with `InteractiveViewer` (0.5x–3.0x pan/zoom, 4 node types) | M11 | Implementation Plan Task 11; Mobile Survey |
| 71 | Live Pulsing Data Flows | Bezier edge splines with animated particle simulations and glow halos | M11 | Implementation Plan Task 11; Master Design §11.1 |
| 72 | Granular Task Progress Bars | `ProgressBarCard` rendering step indicators `[████████░░] 80%`, subtask checklists | M11 | Implementation Plan Task 11; Master Design §11.2 |
| 73 | Mobile Screen: Chat Screen | CEO command console with integrated progress bubbles and quick-action chips | M11 | Implementation Plan Task 11 |
| 74 | Mobile Screen: Boardroom Screen | 13 executive agent cards with live status indicators and telemetry | M11 | Implementation Plan Task 11 |
| 75 | Mobile Screen: Tasks Screen | Filterable task list with real-time progress bars, dependencies, and execution logs | M11 | Implementation Plan Task 11 |
| 76 | Mobile Screen: Vault Screen | Knowledge repository browser with embedded Archify HTML diagram viewer (`webview_flutter`)| M11 | Implementation Plan Task 11 |
| 77 | Audio Feedback & SFX Engine | Auditory triggers: completion chime, audit warning, goal submission whoosh | M11 | Implementation Plan Task 11; Master Design §11.4 |
| 78 | Production Hardening & Packaging | Dockerfile, docker-compose.yml, `.env.example`, documentation, CI workflow | M12 | Implementation Plan Task 12 |
| 79 | E2E Test Suite Pass (Tiers 1-4) | 100% pass rate across Pytest (backend, vault, router, agents, mcp, api) and Flutter test | M12 | Implementation Plan Task 12; ORIGINAL_REQUEST |
| 80 | Adversarial Coverage Hardening (Tier 5) | White-box stress testing, memory leak checks, boundary values, fault injection | M12 | Project Pattern Dual Track Phase 2 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Vault Foundation & Hybrid Store | Features 1–6: SQLite KV & Relational, ChromaDB, Nomic Embeddings, Schemas, VaultManager | none | DONE |
| M2 | Model Router & Multi-Tier Inference Engine | Features 7–13: 5 Complexity Tiers, Ollama, Groq, Gemini, Claude, OpenAI clients, Fallbacks | none | DONE |
| M3 | Base Agent, CEO & Agent Registry | Features 14–16: BaseAgent, JD loading, AgentRegistry, CEO Core intake & synthesis | M1, M2 | DONE |
| M4 | Full C-Suite Executive Agents | Features 17–26: CTO, CMO, CPO, CDO, CFO, COO, CHRO, CIO, CSO, CLO implementations | M3 | DONE |
| M5 | Dual CAO Audit System & 2-Round Escalation Cap | Features 27–29: CAO Claude & GPT, 5-Axis Rubric, Consensus consolidation, 2-round cap | M3, M4 | DONE |
| M6 | Tri-Framework Orchestration Engine | Features 30–38: LangGraph StateGraph, CrewAI flows, AG2 GroupChat, Archify diagram engine | M1, M2, M3, M4, M5 | DONE |
| M7 | 15-Tool MCP Server Implementation | Features 39–54: FastMCP server registering all 15 Alpha tools across 6 namespaces | M1, M2, M3, M5, M6 | DONE |
| M8 | FastAPI Desktop Backend & WebSocket Streaming | Features 55–61: FastAPI ASGI engine, REST routes, WebSocket event broadcasting, Token Auth | M1, M3, M6 | DONE |
| M9 | CLI Entrypoint & Vault Initializer | Features 62–64: `alpha.py`, `vault_init.py`, interactive first-run setup | M1, M8 | DONE |
| M10 | Flutter Mobile Foundation, Theme, Models & Comms | Features 65–69: Flutter scaffolding, OLED dark theme, Models, REST & WebSocket services | M8 | IN_PROGRESS |
| M11 | Archify+ Living Canvas, Pulsing Flows & Mobile UI | Features 70–77: Archify+ CustomPainter canvas, pulsing flows, progress bars, 5 screens, SFX | M10 | PLANNED |
| M12 | Production Hardening, 100% E2E Test Suite & Tier 5 | Features 78–80: Docker, CI, 100% E2E test suite pass across Pytest & Flutter, Tier 5 hardening | M1–M11 | PLANNED |

---

## Interface Contracts

### 1. Vault ↔ Agent / Orchestrator
- **VaultManager**:
  - `read(path: str) -> dict | None`
  - `write(path: str, data: dict, agent_id: str | None = None) -> bool`
  - `search(query: str, n_results: int = 5, path_prefix: str | None = None) -> list[dict]`
  - `append_memory(agent_id: str, memory_type: str, content: str, importance: int, project_id: str | None = None) -> str`
  - `create_project(title: str, description: str, founder_goals: list[str]) -> str`
  - `get_user_profile() -> dict`
  - `get_agent_registry() -> list[dict]`

### 2. Model Router ↔ Agents
- **ModelRouter**:
  - `route(task_type: str, complexity: int, agent_role: str | None = None) -> ModelConfig`
  - `call(prompt: str, system: str, model_config: ModelConfig | None = None, task_type: str = "general", complexity: int = 2, agent_role: str | None = None) -> str`
  - Uniform client interface: `generate(prompt: str, system: str, model: str) -> str`

### 3. Orchestrator ↔ Dual CAO Audit Gate
- **DualCAO**:
  - `audit(deliverables: dict, project_id: str, round_num: int) -> CAOAuditResult`
  - `CAOAuditResult`: `passed: bool`, `claude_score: float`, `gpt_score: float`, `consolidated_report: str`, `p0_defects: list[str]`, `p1_defects: list[str]`, `escalation_required: bool`
  - Rule: If `round_num >= 2` and `passed == False`, `escalation_required = True`.

### 4. Desktop Backend ↔ Mobile Flutter Client
- **REST Endpoints (`http://<ip>:8765/api/`)**:
  - `POST /api/goals` -> `{ "title": str, "description": str, "complexity": int }` returns `{ "project_id": str, "status": "planning" }`
  - `GET /api/projects` -> returns list of `ProjectSummary`
  - `GET /api/projects/{id}` -> returns full `ProjectDetail` with manifest and deliverables
  - `GET /api/projects/{id}/threads` -> returns JSONL thread messages
  - `GET /api/agents` -> returns list of 13 agent status cards
  - `GET /api/vault/read?path={path}` -> returns JSON content
  - `GET /api/vault/search?query={q}` -> returns top semantic results
- **WebSocket (`ws://<ip>:8765/ws`)**:
  - Envelopes: `{ "event": str, "data": dict, "timestamp": str }`
  - Events: `task_progress_update`, `agent_status_change`, `node_flow_pulse`, `audit_status_update`, `project_state_change`, `telemetry_heartbeat`

---

## Code Layout

```
Alpha/
├── backend/
│   ├── __init__.py
│   ├── vault/
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic data models
│   │   ├── sqlite_store.py      # SQLite KV and relational tables
│   │   ├── chroma_store.py      # ChromaDB vector store wrapper
│   │   ├── embeddings.py        # Ollama nomic-embed-text wrapper
│   │   └── vault_manager.py     # Main VaultManager facade
│   ├── model_router/
│   │   ├── __init__.py
│   │   ├── router.py            # 5-tier routing logic & fallback cascade
│   │   ├── ollama_client.py     # Local LLM client
│   │   ├── groq_client.py       # Groq cloud client
│   │   ├── gemini_client.py     # Gemini Flash client
│   │   ├── claude_client.py     # Anthropic client
│   │   └── openai_client.py     # OpenAI client
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py        # Base class for all executive agents
│   │   ├── agent_registry.py    # Agent lifecycle registry
│   │   ├── ceo.py               # CEO Chief Executive Officer
│   │   ├── cto.py               # CTO Chief Technology Officer
│   │   ├── cmo.py               # CMO Chief Marketing Officer
│   │   ├── cpo.py               # CPO Chief Product Officer
│   │   ├── cdo.py               # CDO Chief Design Officer
│   │   ├── cfo.py               # CFO Chief Financial Officer
│   │   ├── coo.py               # COO Chief Operations Officer
│   │   ├── chro.py              # CHRO Chief Human Resources Officer
│   │   ├── cio.py               # CIO Chief Information Officer
│   │   ├── cso.py               # CSO Chief Strategy Officer
│   │   ├── clo.py               # CLO Chief Legal Officer
│   │   └── cao.py               # Dual CAO (Claude & GPT) & 2-round cap
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── goal_parser.py       # Goal decomposition & workstream planner
│   │   ├── thread_manager.py    # AG2 thread manager & persistence
│   │   ├── delegation.py        # CrewAI delegation engine
│   │   ├── synthesizer.py       # CEO output synthesizer
│   │   ├── scheduler.py         # Critical path task scheduler
│   │   ├── state_graph.py       # LangGraph cyclic execution graph
│   │   └── archify_engine.py    # Visual diagram & graph generator
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py            # FastMCP server registration
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── vault_tools.py   # vault_read, vault_write, vault_search, vault_save_memory
│   │       ├── agent_tools.py   # agent_delegate, agent_status, agent_hire
│   │       ├── project_tools.py # project_create, project_update_status, project_list
│   │       ├── thread_tools.py  # thread_post, thread_read
│   │       ├── model_tools.py   # model_route
│   │       └── user_tools.py    # user_profile_read, user_escalate
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app setup, CORS, lifespan
│   │   ├── auth.py              # Local token auth
│   │   ├── websocket.py         # WebSocket telemetry broadcaster
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── goals.py
│   │       ├── projects.py
│   │       ├── agents.py
│   │       └── vault.py
│   └── setup/
│       ├── __init__.py
│       ├── vault_init.py        # Initial directory & SQLite/Chroma bootstrapper
│       └── first_run.py         # Interactive wizard
├── alpha.py                     # Main CLI command center (`alpha setup`, `alpha start`)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (temp db, mock LLMs, mock Ollama)
│   ├── vault/                   # Vault tests
│   ├── model_router/            # Model router tests
│   ├── agents/                  # Agent unit and CAO escalation tests
│   ├── orchestrator/            # Orchestrator & pipeline tests
│   ├── mcp/                     # 15 MCP tool tests
│   ├── api/                     # FastAPI & WebSocket tests
│   └── e2e/                     # End-to-end full flow tests
└── apk/                         # Flutter Mobile Application
    ├── pubspec.yaml
    ├── lib/
    │   ├── main.dart
    │   ├── theme/
    │   │   └── alpha_theme.dart
    │   ├── models/
    │   │   └── alpha_models.dart
    │   ├── services/
    │   │   ├── alpha_api.dart
    │   │   └── websocket_service.dart
    │   ├── widgets/
    │   │   ├── interactive_canvas/
    │   │   │   ├── archify_canvas.dart
    │   │   │   └── pulse_painter.dart
    │   │   └── progress_bar_card.dart
    │   └── screens/
    │       ├── canvas_screen.dart
    │       ├── tasks_screen.dart
    │       ├── chat_screen.dart
    │       ├── boardroom_screen.dart
    │       └── vault_screen.dart
    └── test/
        ├── unit/
        └── widget/
```
