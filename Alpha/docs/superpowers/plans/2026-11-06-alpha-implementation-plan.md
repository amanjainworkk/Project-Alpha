# Project Alpha — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build Project Alpha — a fully autonomous AI C-suite operating system with persistent memory (Alpha's Vault), MCP integration, and a Flutter Android APK interface.

**Architecture:** Python backend (LangGraph + FastAPI) running all 13 C-suite agents on desktop, communicating via Alpha's Vault (ChromaDB + SQLite), exposed via MCP server, with Flutter APK as the mobile interface.

**Tech Stack:** Python 3.11, LangGraph, FastAPI, ChromaDB, SQLite, Ollama, Flutter 3.x, Docker Compose

**Spec:** `docs/superpowers/specs/2026-11-06-alpha-master-design.md`

---

## Global Constraints

- Python 3.11+ required (match-case syntax used in router)
- Ollama must be installed on host machine (not in Docker) for GPU access
- All Vault writes go through VaultManager — agents never write to filesystem directly
- Free models used by default; Claude/GPT only for CAO and complexity-5 tasks
- No external integrations — Alpha is self-contained
- Flutter APK communicates with desktop only via local network (FastAPI + WebSocket)
- MIT license for all source code
- Every agent's JD must be loaded at agent instantiation — JDs are the agent's system prompt

## Review Focus

- Context window overflow when agents load large Vault history → test with projects that have 10+ past memories
- WebSocket disconnect between APK and desktop when desktop sleeps → reconnect logic must be tested
- CAO audit loop: if both CAOs flag same issue, CEO must not loop indefinitely → escalation cap at 2 rounds
- Model routing fallback: if Groq API is down, must fall back to Ollama gracefully
- Vault corruption on interrupted write → test with killed process mid-write

---

## Task 1: Project Scaffold & Vault Foundation

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/vault/__init__.py`
- Create: `backend/vault/vault_manager.py`
- Create: `backend/vault/sqlite_store.py`
- Create: `backend/vault/chroma_store.py`
- Create: `backend/vault/embeddings.py`
- Create: `backend/vault/schemas.py`
- Create: `Alpha-Vault/` (directory structure)
- Create: `requirements.txt`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Test: `tests/vault/test_vault_manager.py`

**Interfaces:**
- Produces: `VaultManager` class with `read()`, `write()`, `search()`, `append_memory()`, `create_project()`, `get_user_profile()`, `get_agent_registry()`

- [ ] **Step 1:** Write failing tests for VaultManager — test `read()`, `write()`, `search()` with mock data
- [ ] **Step 2:** Run tests — confirm they fail (VaultManager not yet implemented)
- [ ] **Step 3:** Implement `sqlite_store.py` — `SQLiteStore(db_path: str)` with `get(path)`, `set(path, data)`, `delete(path)`, `list(prefix)`
- [ ] **Step 4:** Implement `chroma_store.py` — `ChromaStore(persist_dir: str)` with `add(id, text, metadata)`, `search(query, collection, top_k)`, `delete(id)`
- [ ] **Step 5:** Implement `embeddings.py` — `embed_text(text: str) -> list[float]` using Ollama `nomic-embed-text`
- [ ] **Step 6:** Implement `vault_manager.py` — full VaultManager composing SQLite + Chroma
- [ ] **Step 7:** Implement `schemas.py` — Pydantic models for all Vault schemas (AgentProfile, ProjectManifest, ThreadMessage, MemoryEntry, UserProfile, CompanyIdentity)
- [ ] **Step 8:** Create Vault directory structure initialization method `VaultManager.initialize()`
- [ ] **Step 9:** Run all vault tests — confirm pass
- [ ] **Step 10:** Create `.env.example` with all required keys documented
- [ ] **Step 11:** Create `requirements.txt` with pinned versions
- [ ] **Step 12:** Create `docker-compose.yml` for one-command setup
- [ ] **Step 13:** Commit — `feat: Alpha Vault foundation — SQLite + ChromaDB + VaultManager`

---

## Task 2: Model Router

**Files:**
- Create: `backend/model_router/__init__.py`
- Create: `backend/model_router/router.py`
- Create: `backend/model_router/ollama_client.py`
- Create: `backend/model_router/groq_client.py`
- Create: `backend/model_router/gemini_client.py`
- Create: `backend/model_router/claude_client.py`
- Create: `backend/model_router/openai_client.py`
- Test: `tests/model_router/test_router.py`

**Interfaces:**
- Consumes: `.env` with API keys
- Produces: `ModelRouter` with `route(task_type, complexity, agent_id) -> str` and `call(model, prompt, system) -> str`

- [ ] **Step 1:** Write failing tests for router — test routing logic for each complexity tier
- [ ] **Step 2:** Implement `router.py` — `ModelRouter` with `route()` mapping complexity 1-5 to models, `call()` dispatching to right client
- [ ] **Step 3:** Implement each client (`ollama_client.py`, `groq_client.py`, `gemini_client.py`, `claude_client.py`, `openai_client.py`) with uniform interface: `generate(prompt, system, model) -> str`
- [ ] **Step 4:** Add fallback logic — if primary model fails, fall back one tier down
- [ ] **Step 5:** Run router tests
- [ ] **Step 6:** Commit — `feat: model router with 5-tier routing and fallback`

---

## Task 3: Base Agent + CEO Agent

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/base_agent.py`
- Create: `backend/agents/ceo.py`
- Create: `backend/agents/agent_registry.py`
- Test: `tests/agents/test_base_agent.py`
- Test: `tests/agents/test_ceo.py`

**Interfaces:**
- Consumes: `VaultManager`, `ModelRouter`
- Produces: `BaseAgent` with `run(task, project_id) -> str`, `load_context() -> dict`, `save_memory(entry) -> bool`; `CEO` extending BaseAgent with `intake_goal(goal) -> ProjectBrief`, `delegate(project_id, agents, tasks) -> bool`, `synthesize(project_id) -> str`

- [ ] **Step 1:** Write tests for BaseAgent — context loading, task execution, memory saving
- [ ] **Step 2:** Write tests for CEO — goal intake, delegation, synthesis
- [ ] **Step 3:** Implement `base_agent.py` — `BaseAgent(role, vault, router)` with `load_jd()` reading from `agents/job-descriptions/`, `load_context()` fetching Vault data, `run()`, `save_memory()`
- [ ] **Step 4:** Implement `ceo.py` — CEO extending BaseAgent with goal parsing, delegation protocol, synthesis logic per design spec
- [ ] **Step 5:** Implement `agent_registry.py` — `AgentRegistry` manages active agents, instantiates them from Vault profiles
- [ ] **Step 6:** Run all agent tests
- [ ] **Step 7:** Commit — `feat: BaseAgent + CEO with full delegation protocol`

---

## Task 4: Full C-Suite (CTO, CMO, CPO, CDO, CFO, COO, CHRO, CIO, CSO, CLO)

**Files:**
- Create: `backend/agents/cto.py` through `backend/agents/clo.py` (10 files)
- Test: `tests/agents/test_csuite.py`

**Interfaces:**
- Consumes: `BaseAgent`, `VaultManager`, `ModelRouter`
- Produces: Each agent class with `run(task, project_id) -> str` and role-specific methods per JD

- [ ] **Step 1:** Write tests for each agent — that it loads its JD, executes a task, produces correct output format, saves memory
- [ ] **Step 2:** Implement each agent extending BaseAgent with role-specific logic from JD
- [ ] **Step 3:** Test all 10 agents
- [ ] **Step 4:** Commit — `feat: full C-suite 10 agents implemented`

---

## Task 5: Dual CAO (Audit Officers)

**Files:**
- Create: `backend/agents/cao.py`
- Test: `tests/agents/test_cao.py`

**Interfaces:**
- Produces: `CAO(instance="claude"|"gpt")` with `audit(project_id, deliverables) -> AuditReport` and `compare_audits(claude_report, gpt_report) -> ConsolidatedFindings`

- [ ] **Step 1:** Write audit tests — that CAO reads all deliverables, produces structured AuditReport with findings
- [ ] **Step 2:** Implement `cao.py` — dual CAO with Claude and GPT instances, each using their designated model always
- [ ] **Step 3:** Implement `compare_audits()` — identifies agreements and disagreements between both CAOs
- [ ] **Step 4:** Test audit with mock deliverables
- [ ] **Step 5:** Commit — `feat: dual CAO audit system (Claude + GPT)`

---

## Task 6: Inter-Agent Threading System

**Files:**
- Create: `backend/orchestrator/__init__.py`
- Create: `backend/orchestrator/thread_manager.py`
- Create: `backend/orchestrator/goal_parser.py`
- Create: `backend/orchestrator/delegation.py`
- Create: `backend/orchestrator/synthesizer.py`
- Create: `backend/orchestrator/scheduler.py`
- Test: `tests/orchestrator/test_full_flow.py`

**Interfaces:**
- Consumes: All 13 agents, VaultManager
- Produces: `Orchestrator` with `run_goal(goal: str) -> FinalOutput` — the full end-to-end pipeline

- [ ] **Step 1:** Write integration test for full goal flow — input goal, verify project created, threads populated, deliverables saved, audit completed, final output produced
- [ ] **Step 2:** Implement `goal_parser.py` — parses user goal → determines relevant C-suite members, complexity, priority
- [ ] **Step 3:** Implement `thread_manager.py` — manages project threads, routes messages between agents
- [ ] **Step 4:** Implement `delegation.py` — CEO's delegation logic, parallel agent execution
- [ ] **Step 5:** Implement `synthesizer.py` — CEO synthesizes all agent outputs into final deliverable
- [ ] **Step 6:** Implement `scheduler.py` — manages agent work order, ensures dependencies respected
- [ ] **Step 7:** Run full integration test
- [ ] **Step 8:** Commit — `feat: full orchestration engine — goal to output pipeline`

---

## Task 7: MCP Server

**Files:**
- Create: `backend/mcp/__init__.py`
- Create: `backend/mcp/server.py`
- Create: `backend/mcp/tools/vault_tools.py`
- Create: `backend/mcp/tools/agent_tools.py`
- Create: `backend/mcp/tools/project_tools.py`
- Create: `backend/mcp/tools/thread_tools.py`
- Create: `backend/mcp/tools/model_tools.py`
- Create: `backend/mcp/tools/user_tools.py`
- Test: `tests/mcp/test_mcp_server.py`

**Interfaces:**
- Consumes: VaultManager, AgentRegistry, Orchestrator
- Produces: Running MCP server exposing all tools in `backend/mcp/MCP-SERVER-DESIGN.md`

- [ ] **Step 1:** Write tests for each MCP tool — that it accepts correct schema, returns expected output
- [ ] **Step 2:** Implement all tool handler functions in `tools/` modules
- [ ] **Step 3:** Implement `server.py` — MCP server wiring all tools
- [ ] **Step 4:** Test MCP server with MCP inspector
- [ ] **Step 5:** Commit — `feat: MCP server with 15 Alpha tools`

---

## Task 8: FastAPI REST Backend + WebSocket

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/main.py`
- Create: `backend/api/routes/goals.py`
- Create: `backend/api/routes/projects.py`
- Create: `backend/api/routes/agents.py`
- Create: `backend/api/routes/vault.py`
- Create: `backend/api/websocket.py`
- Create: `backend/api/auth.py`
- Test: `tests/api/test_routes.py`

**Interfaces:**
- Consumes: Orchestrator, VaultManager, AgentRegistry
- Produces: FastAPI app on `localhost:8765` with REST routes + WebSocket for real-time APK updates

- [ ] **Step 1:** Write API tests for all routes
- [ ] **Step 2:** Implement `main.py` — FastAPI app setup, middleware, CORS for local APK
- [ ] **Step 3:** Implement each route module
- [ ] **Step 4:** Implement WebSocket handler — pushes real-time project/thread updates to APK
- [ ] **Step 5:** Implement simple local token auth (`auth.py`)
- [ ] **Step 6:** Run API tests
- [ ] **Step 7:** Commit — `feat: FastAPI backend with WebSocket for APK connectivity`

---

## Task 9: Vault Initialization & First-Run Setup

**Files:**
- Create: `backend/setup/first_run.py`
- Create: `backend/setup/vault_init.py`
- Create: `alpha.py` (main entry point)

**Interfaces:**
- Produces: `alpha.py` CLI with `alpha setup` (first run) and `alpha start` (normal run)

- [ ] **Step 1:** Implement `vault_init.py` — creates all Vault directories, initializes ChromaDB collections, registers all agents
- [ ] **Step 2:** Implement `first_run.py` — interactive setup asking user for company name, vision, goals, preferences
- [ ] **Step 3:** Implement `alpha.py` — CLI entry point with `setup` and `start` commands
- [ ] **Step 4:** Test full setup flow
- [ ] **Step 5:** Commit — `feat: first-run setup and alpha CLI entry point`

---

## Task 10: Flutter APK — Foundation & Interactive Canvas Engine

**Files:**
- Create: `apk/pubspec.yaml`
- Create: `apk/lib/main.dart`
- Create: `apk/lib/services/alpha_api.dart`
- Create: `apk/lib/services/websocket_service.dart`
- Create: `apk/lib/models/` (all data models: Project, Agent, TaskProgress, VisualGraphNode, VisualGraphEdge)
- Create: `apk/lib/theme/alpha_theme.dart` (OLED Dark mode with pulsing cyan/blue neon accents)
- Create: `apk/lib/widgets/interactive_canvas/` (Archify+ interactive node graph engine)

**Interfaces:**
- Consumes: FastAPI backend on `desktop_ip:8765` + WebSocket stream
- Produces: Flutter app scaffold with API service layer, WebSocket real-time event pipeline, and interactive vector graph canvas

- [ ] **Step 1:** Initialize Flutter project with dependencies: `webview_flutter`, `flutter_animate`, `provider`, `http`, `web_socket_channel`
- [ ] **Step 2:** Implement `alpha_api.dart` — HTTP client wrapping all FastAPI routes
- [ ] **Step 3:** Implement `websocket_service.dart` — real-time task event stream with auto-reconnect
- [ ] **Step 4:** Implement `alpha_theme.dart` — dark-first design system with high-contrast status colors (Running, Blocked, Done, Auditing)
- [ ] **Step 5:** Implement data models including `TaskProgress(taskId, progressPercent, currentStep, assignedAgent, status)`
- [ ] **Step 6:** Implement `InteractiveCanvasWidget` — touch-interactive zoomable/pannable node graph rendering agent workflows and architecture diagrams
- [ ] **Step 7:** Commit — `feat: Flutter APK foundation with Archify+ interactive canvas and WebSocket telemetry`

---

## Task 11: Flutter APK — The 5 Core Visual Screens

**Files:**
- Create: `apk/lib/screens/canvas_screen.dart` (Archify+ Living Visual Architecture Canvas)
- Create: `apk/lib/screens/tasks_screen.dart` (Granular Progress Bars & Critical Path Tracker)
- Create: `apk/lib/screens/chat_screen.dart` (CEO Command Center with embedded live progress)
- Create: `apk/lib/screens/boardroom_screen.dart` (13 C-Suite Agent cards & live telemetry)
- Create: `apk/lib/screens/vault_screen.dart` (Knowledge browser with interactive diagram viewer)
- Create: `apk/lib/widgets/progress_bar_card.dart` (Animated progress bar with step details)
- Create: `apk/lib/widgets/agent_status_badge.dart`

**Interfaces:**
- Consumes: `alpha_api.dart`, `websocket_service.dart`, `InteractiveCanvasWidget`
- Produces: Fully interactive Flutter app with visual graph rendering, live progress bars, and CEO command chat

- [ ] **Step 1:** Implement Canvas Screen — full-screen interactive node graph showing projects, microservice components, and live agent communication paths
- [ ] **Step 2:** Implement Tasks Screen — granular progress bars per task (`[████████░░] 80%`), sub-task checklists, dependencies, and execution time remaining
- [ ] **Step 3:** Implement Chat Screen — CEO conversation interface with expandable live progress widgets embedded directly inside message bubbles
- [ ] **Step 4:** Implement Boardroom Screen — 13 C-suite executive cards with active task indicators, loaded model name, and token cost counter
- [ ] **Step 5:** Implement Vault Screen — searchable repository with embedded interactive HTML/SVG architecture diagram viewer
- [ ] **Step 6:** Wire smooth bottom navigation bar between all 5 screens
- [ ] **Step 7:** Test APK end-to-end against live desktop WebSocket telemetry
- [ ] **Step 8:** Build release APK
- [ ] **Step 9:** Commit — `feat: complete Flutter APK with Archify+ canvas and live task progress tracking`

---

## Task 12: Docker Compose + Open Source Release

**Files:**
- Create: `docker-compose.yml` (finalize)
- Create: `Dockerfile`
- Create: `README.md`
- Create: `.github/workflows/ci.yml`
- Create: `CONTRIBUTING.md`
- Create: `LICENSE`

- [ ] **Step 1:** Write production `Dockerfile` for backend
- [ ] **Step 2:** Finalize `docker-compose.yml` with all services, volume mounts for Vault persistence
- [ ] **Step 3:** Write comprehensive `README.md` — what Alpha is, quick start, screenshots, architecture diagram, agent roster
- [ ] **Step 4:** Write GitHub Actions CI — lint, test, build APK on every PR
- [ ] **Step 5:** Test clean install from scratch using `docker-compose up`
- [ ] **Step 6:** Final commit — `release: Project Alpha v1.0.0 — open source release`
