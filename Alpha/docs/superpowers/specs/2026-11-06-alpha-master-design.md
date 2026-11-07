# Project Alpha — Master Design Document

> **Status:** In Design — Approved for Implementation Planning
> **Version:** 1.0
> **Author:** Aman Jain + Antigravity
> **Date:** 2026-11-06

---

## 1. Vision

**Project Alpha** is a personal AI-powered company operating system — a JARVIS-like platform where the user (Aman) commands a full AI C-suite that autonomously delegates, collaborates, and delivers on any goal.

Alpha is not a chatbot. It is a **company**.

The user is the **Founder/Chairman**. Alpha's CEO is their executive arm. The C-suite are skilled domain experts. Together, they can take on any project — from building a website to launching a product — with minimal user involvement beyond providing the goal and approving final outputs.

---

## 2. Goals

- **G1:** A fully autonomous AI C-suite that handles any task end-to-end
- **G2:** Minimal user touch — give a goal, get a result
- **G3:** Agents persist, learn, and grow smarter over time (Alpha's Vault)
- **G4:** Free-first model routing — sustainable, open-source, self-hostable
- **G5:** Android APK as primary mobile interface (desktop is the brain)
- **G6:** Open source GitHub release — others can run their own Alpha

## 3. Non-Goals

- **NG1:** Alpha is NOT an integration hub — no Slack, Gmail, Notion sync
- **NG2:** Alpha does NOT replace the user's judgment — only advises and executes on approved goals
- **NG3:** Alpha is NOT cloud-dependent — must run fully locally

## 4. Anti-Goals (Failure Conditions)

- If Alpha requires constant user prompting for every sub-task → FAILURE
- If agents don't remember past context → FAILURE
- If the mobile app requires a powerful phone to run agents → FAILURE (agents run on desktop)
- If setup requires more than 1 command → FAILURE for open-source adoption

---

## 5. The Alpha Company Structure

### 5.1 Org Chart

```
┌─────────────────────────────────────────────┐
│              AMAN JAIN (Founder)             │
│           Communicates via APK               │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │        CEO          │
         │  (Goal Intake &     │
         │   Delegation Hub)   │
         └─────────┬───────────┘
                   │
    ┌──────────────┼──────────────────────┐
    │              │                      │
┌───▼───┐    ┌────▼────┐          ┌──────▼──────┐
│  CTO  │    │   CMO   │          │    CPO      │
└───┬───┘    └────┬────┘          └──────┬──────┘
    │              │                      │
┌───▼───┐    ┌────▼────┐          ┌──────▼──────┐
│  CDO  │    │   CFO   │          │    COO      │
└───────┘    └────┬────┘          └─────────────┘
                  │
         ┌────────┼─────────┐
         │                  │
    ┌────▼────┐        ┌────▼────┐
    │   CIO   │        │   CSO   │
    └─────────┘        └─────────┘
         │
    ┌────▼────┐        ┌──────────┐
    │  CHRO   │        │   CLO    │
    └─────────┘        └──────────┘
                            │
                  ┌─────────┼─────────┐
                  │                   │
            ┌─────▼──────┐  ┌────────▼────┐
            │  CAO        │  │    CAO      │
            │ (Claude)    │  │  (ChatGPT)  │
            └─────────────┘  └─────────────┘
```

### 5.2 The C-Suite Roster

| Agent | Full Title | Core Domain | Model Tier |
|-------|-----------|-------------|------------|
| **CEO** | Chief Executive Officer | Strategy, Delegation, Synthesis | Medium-High |
| **CTO** | Chief Technology Officer | Architecture, Tech Stack, Specs | Medium-High |
| **CMO** | Chief Marketing Officer | Brand, Market, Go-to-Market | Medium |
| **CPO** | Chief Product Officer | Product, Roadmap, User Stories | Medium |
| **CDO** | Chief Design Officer | UI/UX, Design System, Experience | Medium |
| **CFO** | Chief Financial Officer | Budget, Cost, ROI, Risk | Low-Medium |
| **COO** | Chief Operations Officer | Execution, Timelines, Process | Low-Medium |
| **CHRO** | Chief Human Resources Officer | Agent Hiring, Culture, Training | Low-Medium |
| **CIO** | Chief Information Officer | Data, Systems, Vault Management | Medium |
| **CSO** | Chief Strategy Officer | Long-term Strategy, OKRs | High |
| **CLO** | Chief Legal Officer | Legal Risk, Compliance, IP | Medium |
| **CAO-C** | Chief Audit Officer (Claude) | Reasoning Quality, Depth Audit | Always Claude |
| **CAO-G** | Chief Audit Officer (GPT) | Breadth, Alternatives Audit | Always GPT-4o |

---

## 6. Alpha's Vault — Persistent Context Architecture

### 6.1 What is Alpha's Vault?

Alpha's Vault is the **central memory and context system** for all agents. It is a structured, queryable knowledge base that persists all decisions, outputs, agent memories, company context, project history, and user preferences.

Think of it as the company's **institutional knowledge** — it makes agents smarter the longer they work for you.

### 6.2 Vault Structure

```
Alpha-Vault/
├── company/
│   ├── identity.json          # Company name, vision, values, user prefs
│   ├── okrs.json              # Current and historical OKRs
│   └── culture.md             # Company culture and operating principles
│
├── agents/
│   ├── {agent_id}/
│   │   ├── profile.json       # Agent's role, skills, model assignment
│   │   ├── memory.json        # Agent's episodic memory (past decisions)
│   │   ├── preferences.json   # Agent's learned preferences
│   │   └── performance.json   # Agent's performance history
│
├── projects/
│   ├── {project_id}/
│   │   ├── manifest.json      # Project metadata (name, goal, status, dates)
│   │   ├── brief.md           # CEO's initial project brief
│   │   ├── threads/           # Inter-agent communication threads
│   │   │   ├── {thread_id}.json
│   │   ├── deliverables/      # Final outputs per agent
│   │   │   ├── technical-spec.md   # CTO output
│   │   │   ├── marketing-brief.md  # CMO output
│   │   │   ├── product-prd.md      # CPO output
│   │   │   ├── design-system.md    # CDO output
│   │   │   └── ...
│   │   ├── audit/
│   │   │   ├── claude-audit.md     # CAO-C audit report
│   │   │   └── gpt-audit.md        # CAO-G audit report
│   │   └── final-output.md    # CEO's synthesized final output to user
│
├── knowledge/
│   ├── tech-decisions.json    # All past tech decisions (CTO builds this)
│   ├── brand-guidelines.json  # Brand identity (CMO builds this)
│   ├── design-system.json     # Design tokens and system (CDO builds this)
│   ├── financial-history.json # Budget and cost history (CFO builds this)
│   └── legal-registry.json   # Legal notes, licenses, compliance (CLO builds)
│
└── user/
    ├── profile.json           # User preferences, working style, goals
    ├── interaction-log.json   # History of user ↔ CEO interactions
    └── feedback-log.json      # User feedback on outputs
```

### 6.3 Vault Access Rules

| Agent | Read Access | Write Access |
|-------|------------|--------------|
| CEO | All | projects/, user/, company/ |
| CTO | projects/, knowledge/tech-decisions | projects/{id}/deliverables/technical-spec |
| CMO | projects/, knowledge/brand-guidelines | projects/{id}/deliverables/marketing-brief |
| CPO | projects/, knowledge/ | projects/{id}/deliverables/product-prd |
| CDO | projects/, knowledge/design-system | projects/{id}/deliverables/design-system |
| CFO | projects/, knowledge/financial-history | projects/{id}/deliverables/financial-report |
| COO | projects/ (all) | projects/{id}/manifest, timelines |
| CIO | All (read) | knowledge/, agents/ |
| CHRO | agents/ | agents/ |
| CAO | projects/{id}/ (read-only) | projects/{id}/audit/ |
| CLO | projects/, knowledge/legal-registry | projects/{id}/deliverables/legal-review |
| CSO | All (read) | company/okrs, projects/{id}/strategic-alignment |

### 6.4 Vault Technology

- **Storage Backend:** ChromaDB (vector embeddings for semantic search) + SQLite (structured metadata)
- **Embedding Model:** `nomic-embed-text` via Ollama (runs locally, free)
- **Query Interface:** REST API exposed by CIO's Vault Manager service
- **Backup:** Auto-snapshot to local `Alpha-Vault/backups/` on every write

---

## 7. Inter-Agent Communication Protocol

### 7.1 Project Thread Structure

When CEO receives a goal and delegates, it creates a **Project Thread** — a structured conversation space all relevant agents write into.

```json
{
  "thread_id": "thread_20261106_001",
  "project_id": "proj_website_001",
  "created_by": "CEO",
  "topic": "Build consultancy website",
  "participants": ["CEO", "CTO", "CMO", "CPO", "CDO"],
  "status": "active",
  "messages": [
    {
      "from": "CEO",
      "to": ["CTO", "CMO", "CPO", "CDO"],
      "type": "DELEGATION",
      "content": "...",
      "timestamp": "2026-11-06T16:00:00Z",
      "deadline": "2026-11-06T17:00:00Z"
    },
    {
      "from": "CTO",
      "to": ["thread"],
      "type": "DELIVERABLE",
      "content": "...",
      "timestamp": "2026-11-06T16:20:00Z"
    }
  ]
}
```

### 7.2 Message Types

| Type | Usage |
|------|-------|
| `DELEGATION` | CEO assigns work to agent(s) |
| `DELIVERABLE` | Agent posts their completed work |
| `QUESTION` | Agent asks another agent a clarifying question |
| `RESPONSE` | Reply to a question |
| `REVIEW_REQUEST` | Agent asks another to review their draft |
| `SYNTHESIS` | CEO's final compiled output |
| `AUDIT_REQUEST` | CEO sends to CAO agents |
| `AUDIT_REPORT` | CAO's findings |
| `USER_ESCALATION` | CEO escalates to user for decision |

---

## 8. Model Routing System

### 8.1 Routing Logic

```python
def route_model(task_type: str, complexity: int, agent: str) -> str:
    """
    complexity: 1 (trivial) to 5 (highly complex)
    """
    # CAO agents always use their designated model
    if agent == "CAO-C":
        return "claude-3-5-sonnet"
    if agent == "CAO-G":
        return "gpt-4o"
    
    # Route by complexity
    if complexity <= 2:
        return "ollama/llama3.2"       # Free, local
    elif complexity == 3:
        return "groq/llama-3.1-70b"   # Free tier, fast
    elif complexity == 4:
        return "gemini/gemini-1.5-flash"  # Free tier
    else:  # complexity == 5
        return "claude-3-5-sonnet"    # Paid, highest quality

TASK_COMPLEXITY_MAP = {
    "summarize": 1,
    "reformat": 1,
    "draft_copy": 2,
    "user_persona": 2,
    "cost_estimate": 2,
    "technical_spec": 4,
    "architecture_design": 5,
    "strategic_planning": 5,
    "audit": 5,  # Always uses designated model
}
```

### 8.2 Available Models

| Tier | Models | Cost | Use Case |
|------|--------|------|----------|
| Local (Free) | Llama 3.2, Mistral 7B, Gemma 2, Phi-3 | Free | Drafting, formatting, simple reasoning |
| Cloud Free | Groq (Llama 70B), Gemini Flash | Free tier | Complex reasoning, planning |
| Cloud Paid | Claude 3.5 Sonnet, GPT-4o | Pay-per-use | Architecture, strategy, audit only |

---

## 9. Technical Architecture

### 9.1 System Components

```
Alpha System
├── Backend (Desktop — Python)
│   ├── orchestrator/          # CEO + delegation engine
│   │   ├── goal_parser.py     # Parses user goals into workstreams
│   │   ├── delegation.py      # Routes work to right agents
│   │   ├── synthesizer.py     # CEO synthesizes agent outputs
│   │   └── scheduler.py       # Manages agent work order
│   │
│   ├── agents/                # C-suite agent implementations
│   │   ├── base_agent.py      # Base agent class
│   │   ├── ceo.py
│   │   ├── cto.py
│   │   ├── cmo.py
│   │   ├── cpo.py
│   │   ├── cdo.py
│   │   ├── cfo.py
│   │   ├── coo.py
│   │   ├── chro.py
│   │   ├── cio.py
│   │   ├── cso.py
│   │   ├── clo.py
│   │   └── cao.py             # Dual-instance: claude + gpt
│   │
│   ├── vault/                 # Alpha's Vault
│   │   ├── vault_manager.py   # Read/write/query interface
│   │   ├── embeddings.py      # nomic-embed-text via Ollama
│   │   ├── sqlite_store.py    # Structured metadata storage
│   │   └── chroma_store.py    # Vector search storage
│   │
│   ├── model_router/          # LLM routing
│   │   ├── router.py          # Complexity → model selection
│   │   ├── ollama_client.py   # Local model interface
│   │   ├── groq_client.py     # Groq API client
│   │   ├── gemini_client.py   # Gemini API client
│   │   ├── claude_client.py   # Anthropic client
│   │   └── openai_client.py   # OpenAI client
│   │
│   ├── mcp/                   # MCP Server
│   │   ├── server.py          # MCP server exposing Alpha tools
│   │   └── tools/             # MCP tool definitions
│   │       ├── vault_tools.py
│   │       ├── agent_tools.py
│   │       └── project_tools.py
│   │
│   └── api/                   # REST API for APK
│       ├── main.py            # FastAPI app
│       ├── routes/
│       │   ├── goals.py       # Submit goals, get outputs
│       │   ├── projects.py    # View project status
│       │   ├── agents.py      # Agent status and profiles
│       │   └── vault.py       # Vault read access
│       └── websocket.py       # Real-time updates to APK
│
└── APK (Android — Flutter)
    ├── lib/
    │   ├── screens/
    │   │   ├── home.dart          # Dashboard — active projects
    │   │   ├── chat.dart          # Chat with CEO
    │   │   ├── project_view.dart  # Project detail — threads, outputs
    │   │   ├── agents.dart        # View all C-suite agents
    │   │   └── vault.dart         # Browse Alpha's Vault
    │   ├── models/
    │   └── services/
    │       └── alpha_api.dart     # Connects to desktop backend
```

### 9.2 MCP Server Design

Alpha exposes an MCP server so the AI agents (and future Alpha sub-projects) can call Alpha's tools programmatically.

**MCP Tools Exposed:**
```
alpha://vault/read      - Read from Alpha's Vault
alpha://vault/write     - Write to Alpha's Vault
alpha://vault/search    - Semantic search across Vault
alpha://agents/delegate - Delegate a task to an agent
alpha://agents/status   - Get agent's current task status
alpha://projects/create - Start a new project
alpha://projects/update - Update project status
alpha://projects/list   - List all projects
alpha://user/profile    - Read user preferences
alpha://thread/post     - Post a message to a project thread
alpha://thread/read     - Read a project thread
alpha://model/route     - Get model recommendation for a task
```

---

## 10. APK & Interface Design (The "Archify+" Visual Command Center)

### 10.1 Core Concept: The Visual Living Canvas
Project Alpha’s Android APK is not merely a chat client or static list. It is an **interactive visual command center inspired by Archify, elevated with real-time operational telemetries**:
- **Interactive Node Graph (Archify Engine):** Visualizes the company hierarchy, project system architecture, and real-time inter-agent message flows with animated pulsing data lines and node states.
- **Granular Progress Bars:** Every project, workstream, and individual agent task features live percentage progress bars with micro-status indicators (e.g., `CTO: Generating Spec [████████░░] 80%`).
- **Interactive Zoom & Inspect:** Tap any agent node to see their active task, assigned model, and episodic memory. Tap any task node to view dependencies, deliverables, and CAO audit scorecards.
- **Delta Architecture Diff View:** Switch to comparison mode (`archify diff`) to see the system before and after a project execution.

### 10.2 Core Screens & Navigation

```
┌────────────────────────────────────────────────────────┐
│                   ALPHA MOBILE APK                     │
├───────────┬───────────┬───────────┬───────────┬────────┤
│  CANVAS   │   TASKS   │   CHAT    │ BOARDROOM │ VAULT  │
│ Visual OS │ Progress  │  CEO Talk │  C-Suite  │ Memory │
└───────────┴───────────┴───────────┴───────────┴────────┘
```

**Screen 1 — The Living Canvas (Visual Architecture & Flow)**
- **Interactive Vector Graph:** Zoomable, pannable canvas showing active projects as interconnected nodes.
- **Pulsing Data Paths:** Real-time visual packets flowing between agents (e.g., CEO → CTO → CAO) as inter-agent thread messages occur.
- **Layer Filters:**
  - *Company View:* 13 C-Suite nodes and their collaboration links.
  - *Project Architecture View:* Microservices, databases, APIs, and client layers generated by CTO & Archify.
  - *Execution Flow View:* Sequence diagram of tasks from goal intake to verified delivery.
- **Export & Share:** One-tap export to standalone interactive HTML, SVG, or high-res PNG.

**Screen 2 — Task Command & Progress Center**
- **Overall Project Progress:** Circular and linear progress indicators reflecting completed milestones.
- **Granular Sub-task Cards:**
  ```text
  ┌──────────────────────────────────────────────────────┐
  │ [P0] Technical Architecture Spec (CTO)      [85%]    │
  │ Progress: [████████████████░░░]                       │
  │ Status: Resolving CAO-Claude security audit flags    │
  │ Dependencies: PRD Approved ✓ | Archify Diagram ✓     │
  └──────────────────────────────────────────────────────┘
  ```
- **Live Execution Ticker:** Real-time stream of agent actions, token usage, and latency.

**Screen 3 — Chat with CEO (The Command Console)**
- Voice or text goal input.
- Real-time plan confirmation card with instant "Approve & Execute" button.
- Live expandable progress view embedded directly in chat messages.

**Screen 4 — The Boardroom (Agent Network)**
- 3D / Isometric card view of all 13 C-Suite executives.
- Live status badges: `Idle`, `Thinking`, `Auditing`, `Blocked`.
- Resource telemetry: Model currently loaded, token cost today ($0.00 Free-First tracking).

**Screen 5 — Alpha's Vault (Knowledge Browser)**
- Searchable repository of all project briefs, interactive diagrams, and legal licenses.
- Markdown document viewer with integrated Archify interactive canvas embed.

---

## 11. Tech Stack Decisions

| Component | Technology | Reason |
|-----------|-----------|--------|
| Backend language | Python 3.11+ | Best AI/ML ecosystem |
| Agent framework | LangGraph | Native multi-agent support, local-first |
| API server | FastAPI | Fast, async, great for WebSocket |
| Local LLMs | Ollama | Best local model runner, free |
| Vector DB | ChromaDB | Local-first, free, Python-native |
| Structured DB | SQLite | Zero-config, local, perfect for Vault |
| Embeddings | nomic-embed-text (Ollama) | Free, runs locally |
| MCP | Python MCP SDK | Official, well-supported |
| APK framework | Flutter | Single codebase, beautiful native UI |
| APK-Desktop comms | FastAPI + WebSocket | Real-time updates to APK |
| Cloud LLMs | Groq (free), Gemini Flash (free) | Free tiers for medium tasks |
| Audit LLMs | Claude API + OpenAI API | Pay-per-use, only for audits |
| Containerization | Docker Compose | One-command setup for open source |

---

## 12. Implementation Phases

### Phase 1 — The Foundation (MVP)
- [ ] Project structure setup
- [ ] Alpha's Vault (SQLite + ChromaDB)
- [ ] Base agent class + CEO agent
- [ ] Model router (Ollama + Groq)
- [ ] FastAPI backend with basic routes
- [ ] Simple CLI interface (before APK)
- [ ] 3 agents: CEO, CTO, CMO

### Phase 2 — Full C-Suite
- [ ] All 13 agents implemented
- [ ] Inter-agent threading system
- [ ] Vault fully populated by agents
- [ ] MCP server
- [ ] Dual CAO audit system

### Phase 3 — Mobile APK
- [ ] Flutter APK scaffolding
- [ ] WebSocket real-time updates
- [ ] All 5 screens implemented
- [ ] Desktop ↔ APK connectivity

### Phase 4 — Polish & Open Source
- [ ] Docker Compose setup
- [ ] README + setup guide
- [ ] GitHub Actions CI
- [ ] GitHub release

---

## 13. Open Source Strategy

**Repository:** `github.com/amanjain/alpha` (suggested)
**License:** MIT (permissive, maximum adoption)

**Setup Command:**
```bash
git clone https://github.com/amanjain/alpha
cd alpha
cp .env.example .env  # Add API keys
docker-compose up
```

**What users get:**
- Fully functional AI company OS
- Their own C-suite
- Their own Alpha's Vault
- Mobile APK to connect to their desktop
- All agents with detailed JDs pre-loaded

---

## 14. Approaches Considered

### Approach A: AutoGen / CrewAI based (Rejected)
Use an existing multi-agent framework as the backbone.
- **Pro:** Faster start
- **Con:** Limited control over agent personalities, no built-in Vault, opinionated APIs that limit Alpha's UX vision

### Approach B: LangGraph Custom (Chosen ✓)
Build on LangGraph for agent orchestration with custom Vault and routing.
- **Pro:** Full control, production-grade, great multi-agent support, well-documented
- **Con:** More build time upfront

### Approach C: Fully Custom from Scratch (Rejected)
Build the entire orchestration layer without any framework.
- **Pro:** Maximum control
- **Con:** Months of work before any value, wheel reinvention

---

## Appendix A — Agent JD File Index

All Job Descriptions are located at: `d:\AI\Aman Jain - Master\Alpha\agents\job-descriptions\`

| File | Agent |
|------|-------|
| `CEO-Chief-Executive-Officer.md` | CEO |
| `CHRO-Chief-Human-Resources-Officer.md` | CHRO |
| `CTO-Chief-Technology-Officer.md` | CTO |
| `CMO-Chief-Marketing-Officer.md` | CMO |
| `CPO-Chief-Product-Officer.md` | CPO |
| `CDO-Chief-Design-Officer.md` | CDO |
| `CFO-Chief-Financial-Officer.md` | CFO |
| `COO-Chief-Operations-Officer.md` | COO |
| `CIO-Chief-Information-Officer.md` | CIO |
| `CSO-Chief-Strategy-Officer.md` | CSO |
| `CLO-Chief-Legal-Officer.md` | CLO |
| `CAO-Chief-Audit-Officer.md` | CAO (dual) |
