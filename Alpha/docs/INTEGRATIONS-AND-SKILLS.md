# 🚀 Project Alpha — Framework Integrations & Skill Ingestion

> **Document Version:** 1.0.0  
> **Classification:** Architecture Standard & Toolchain Integration  
> **Source Repositories Ingested:**
> - [tt-a1i/archify](https://github.com/tt-a1i/archify) — Interactive Architecture & System Diagramming
> - [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — Production Engineering Workflows & Quality Gates
> - [affaan-m/ECC](https://github.com/affaan-m/ECC) — Agent Harness Memory & Guardrail System
> - [ag2ai/ag2](https://github.com/ag2ai/ag2) — Multi-Agent Conversational AgentOS
> - [crewaiinc/crewai](https://github.com/crewaiinc/crewai) — Hierarchical Orchestration, Flows & Role-Playing

---

## 1. EXECUTIVE SYNTHESIS: HOW THESE 5 REPOS POWER ALPHA

Project Alpha synthesizes the strengths of these five industry-standard repositories into a unified, autonomous company operating system:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             PROJECT ALPHA CORE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [1. AG2 + CrewAI Hybrid Orchestration Engine]                             │
│   • CrewAI Hierarchical Flows: CEO as Master Director, Tasks as units      │
│   • AG2 GroupChat: Dynamic peer-to-peer C-Suite deliberation & consensus    │
│                                                                             │
│   [2. ECC (Agent Harness & Guardrails)]                                     │
│   • Alpha's Vault Session Context Optimizer (dynamic token compression)     │
│   • Pre/Post execution safety hooks & policy validation                     │
│                                                                             │
│   [3. Addy Osmani Agent Skills (The 6-Phase Engineering Lifecycle)]          │
│   • Phase 1: DEFINE  (CPO + CMO)                                            │
│   • Phase 2: PLAN    (CEO + CTO + COO)                                      │
│   • Phase 3: BUILD   (TDD & Idiomatic code)                                 │
│   • Phase 4: VERIFY  (Automated test suites & runtime checks)               │
│   • Phase 5: REVIEW  (CAO Five-Axis Audit: Correctness, Simplicity,         │
│                       Architecture, Security, Performance)                  │
│   • Phase 6: SHIP    (DevOps, release packaging, APK & web distribution)    │
│                                                                             │
│   [4. Archify (Interactive Visual Architecture Engine)]                     │
│   • Standalone interactive HTML/SVG diagrams for every project              │
│   • Light/Dark interactive node tracing & delta comparison (archify diff)   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. INTEGRATION SPECIFICATIONS

### 2.1 Archify Integration (`tt-a1i/archify`)
* **Role Owner:** CTO & CDO
* **Functionality:**
  - Whenever the CTO defines technical specifications, Archify generates interactive, self-contained HTML/SVG system architecture diagrams.
  - Generates sequence flows, data pipelines, and microservice topologies.
  - Produces delta architecture diffs (`archify compare`) showing "before and after" system evolution for any refactor or sub-project.
* **Storage in Alpha:** Output saved to `Alpha-Vault/projects/{project_id}/deliverables/architecture-diagram.html` and rendered directly inside the Flutter APK via WebView.

### 2.2 Addy Osmani Agent Skills (`addyosmani/agent-skills`)
* **Role Owner:** CHRO, CTO, CAO
* **Functionality:**
  - Ingests production-grade engineering principles across all C-suite playbooks.
  - **TDD Enforcement:** All coding tasks follow strict Test-Driven Development (Red-Green-Refactor).
  - **CAO Five-Axis Review:** Dual CAO agents (Claude and ChatGPT) audit all deliverables against:
    1. *Correctness:* Factual validity, edge case handling, constraint satisfaction.
    2. *Simplicity:* Anti-overengineering, YAGNI compliance, readability.
    3. *Architecture:* Clean modular separation, cohesion, interface stability.
    4. *Security:* OWASP compliance, zero credential leakage, sandbox safety.
    5. *Performance:* Time/space complexity, resource consumption, latency budgets.

### 2.3 ECC Framework (`affaan-m/ECC`)
* **Role Owner:** CIO & System Administrator
* **Functionality:**
  - **Harness Memory Management:** Provides memory compression algorithms to prevent token overflow in Alpha's Vault.
  - **Session Continuity:** Maintains cross-session state when the desktop or APK disconnects and reconnects.
  - **Guardrail Hooks:** Intercepts agent actions with pre-execution safety gates (ensuring no unauthorized network access or dangerous command executions).

### 2.4 AG2 (`ag2ai/ag2`)
* **Role Owner:** CEO & COO
* **Functionality:**
  - **Structured GroupChat:** Provides the inter-agent conversational protocol where agents speak in turn, ask peer questions, and resolve conflicts autonomously.
  - **Dynamic Speaker Selection:** The CEO dynamically invites the CMO, CTO, or CFO based on the current deliberation topic.
  - **Consensus Termination:** Recognizes when all C-suite members agree on a plan and triggers final synthesis.

### 2.5 CrewAI (`crewaiinc/crewai`)
* **Role Owner:** CEO (Manager), All C-Suite (Crew)
* **Functionality:**
  - **Hierarchical Process:** The CEO acts as the CrewAI hierarchical manager delegating atomic `Task` objects with strict context dependencies.
  - **Event-Driven Flows:** Deterministic state machine pipelines controlling the journey from User Goal → Project Brief → Agent Deliberation → Audit → Delivery.
  - **Tool Binding:** Integrates Python-native tools and MCP capabilities directly to agents.

---

## 3. UPDATED DEPENDENCIES (`requirements.txt`)

These packages are added to the project's dependency manifest:

```text
# Multi-Agent Orchestration
ag2>=0.4.0
crewai>=0.80.0
langgraph>=0.2.0

# Memory & Embeddings
chromadb>=0.5.0
pydantic>=2.7.0
sqlite3-api>=0.1.0

# API & Server
fastapi>=0.111.0
uvicorn>=0.30.0
websockets>=12.0
mcp>=1.0.0

# LLM Providers & Routing
groq>=0.9.0
google-generativeai>=0.7.0
anthropic>=0.28.0
openai>=1.35.0
ollama>=0.2.1

# Architecture & Visualization (Archify integration)
jinja2>=3.1.4
pyyaml>=6.0.1
```

---

## 4. CANONICAL EXECUTION CYCLE IN ALPHA

With these skills installed:
1. **User inputs a goal in APK:** (e.g. *"Create a multi-agent AI research tool"*)
2. **CrewAI Flow triggers:** CEO instantiates the project using **Addy Osmani's Phase 1 (Define)**.
3. **AG2 GroupChat convenes:** CTO, CMO, and CPO deliberate in structured threads.
4. **CTO uses Archify:** Generates an interactive visual diagram of the proposed architecture.
5. **ECC Guardrails engage:** Memory state is compressed and logged into **Alpha's Vault**.
6. **Dual CAO executes 5-Axis Review:** Claude audits reasoning; ChatGPT audits alternatives.
7. **CEO synthesizes & ships:** Final deliverable, visual diagram, and project spec delivered to the Founder's APK.
