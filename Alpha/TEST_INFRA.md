# Project Alpha — Test Infrastructure & Quality Architecture Specification

> **Document Version:** 1.0.0  
> **Classification:** Project Test Infrastructure Standard  
> **Owner:** E2E Test Architect  
> **Status:** Active & Production-Ready  
> **Scope:** Full-System Opaque-Box E2E Testing (Tiers 1–4) & Mobile Interface Quality

---

## 1. Executive Summary & Quality Strategy

Project Alpha is a personal autonomous AI executive operating system comprising:
1. A Python desktop backend brain (`FastAPI`, `LangGraph`, `AG2`, `CrewAI`, port `8765`)
2. A persistent institutional memory subsystem (`Alpha's Vault` via `SQLite` + `ChromaDB`)
3. A 5-tier zero-cost priority Model Router with local `Ollama` fallback
4. A 15-tool Model Context Protocol (`MCP`) server on stdio & HTTP/SSE
5. A Dual `CAO` (Chief Audit Officer) gate enforcing an Addy Osmani 5-axis review rubric with a strict 2-round escalation cap
6. An interactive Flutter mobile interface (`Archify+` living canvas, pulsing data paths, granular progress bars)

### 1.1 Opaque-Box Testing Principles
Testing is conducted strictly from the perspective of an external client, Founder user, and peer service:
- **No Private State Peeking:** Tests interact solely through documented external boundaries:
  - HTTP REST endpoints (`/api/goals`, `/api/projects`, `/api/agents`, `/api/vault`)
  - WebSocket telemetry streams (`/ws`)
  - FastMCP tool execution protocol (`vault_*`, `agent_*`, `project_*`, `thread_*`, `model_*`, `user_*`)
  - CLI commands (`alpha setup`, `alpha start`, `alpha status`)
  - Flutter Mobile UI widgets and HTTP/WebSocket clients
- **Zero Production Data Leakage:** All tests operate against isolated in-memory or temporary directory instances of SQLite and ChromaDB, automatically torn down after execution.
- **Deterministic Offline Execution:** External LLM calls (Anthropic, OpenAI, Gemini, Groq, Ollama) are mediated through predictable contract-driven mocks, guaranteeing zero flaky runs and zero cloud token expenditures during test cycles.

---

## 2. Systematic 4-Tier Test Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          4-TIER E2E TEST HIERARCHY                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [Tier 4: Real-World Application Scenarios]                                │
│   • Multi-agent SaaS lifecycle from Founder goal to Archify diagram & delivery│
│   • Dual CAO 2-round rejection escalation to human Founder mobile push     │
│   • Mobile offline catch-up, reconnection & parallel project execution      │
│                                                                             │
│   [Tier 3: Cross-Feature Integration & System Dynamics]                    │
│   • Goal Intake ➔ Deliberation ➔ Archify SVG ➔ Dual CAO ➔ Vault Persistence│
│   • Model Router cloud-to-local fallback during active agent delegation     │
│   • MCP tool execution emitting real-time WebSocket telemetry packets      │
│                                                                             │
│   [Tier 2: Boundary & Corner Cases (Adversarial Stress)]                    │
│   • 100k+ char prompts, SQL injection & path traversal attempts             │
│   • Malformed JSON payloads, complexity tier clamping, rate limit 429 backoff│
│   • Abrupt WebSocket termination & token authentication revocation          │
│                                                                             │
│   [Tier 1: Feature Coverage (>=5 Test Cases Per Feature Group)]             │
│   • Vault CRUD & semantic vector search                                     │
│   • 5-Tier Model Router & CAO model lock                                    │
│   • 12 C-Suite agents & CEO workstream intake                               │
│   • Dual CAO 5-axis audit & consensus                                       │
│   • 15 FastMCP tools across 6 namespaces                                    │
│   • FastAPI REST routes & WebSocket event broadcasting                      │
│   • Alpha CLI operations                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Layout & Test Mapping

The test harness mirrors the production code layout defined in `Alpha/PROJECT.md`:

```
Alpha/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures, temp vault, mock LLMs, test client
│   └── e2e/
│       ├── __init__.py
│       ├── test_tier1_features.py   # Tier 1: Comprehensive feature coverage (>=5 per feature)
│       ├── test_tier2_boundaries.py # Tier 2: Boundary conditions, malformed inputs, stress
│       ├── test_tier3_interactions.py# Tier 3: Pairwise cross-feature interactions
│       └── test_tier4_scenarios.py  # Tier 4: Real-world founder workflows & CAO escalations
└── apk/
    └── test/
        ├── unit/
        │   └── api_and_models_test.dart       # Dart models & AlphaApiClient tests
        └── widget/
            └── canvas_and_progress_test.dart  # ArchifyCanvas & ProgressBarCard tests
```

---

## 4. Test Environments & Configuration

### 4.1 Prerequisites
- **Python:** 3.11+
- **Pytest:** `>= 8.0.0` with `pytest-asyncio >= 0.23.0`
- **FastAPI / HTTPX:** `fastapi >= 0.111.0`, `httpx >= 0.27.0`
- **Flutter:** `3.x` with `flutter_test`

### 4.2 Test Environment Variables
The test environment enforces isolated offline execution via `tests/conftest.py`:

```bash
ALPHA_ENV=test
ALPHA_TOKEN=test_alpha_bearer_token_secret_xyz789
ALPHA_VAULT_PATH=<temp_directory>
ALPHA_PORT=8765
OLLAMA_HOST=http://127.0.0.1:11434
GROQ_API_KEY=mock-groq-key
GEMINI_API_KEY=mock-gemini-key
ANTHROPIC_API_KEY=mock-anthropic-key
OPENAI_API_KEY=mock-openai-key
```

---

## 5. Core Fixtures & Test Harness Components

| Fixture Name | Scope | Description |
|--------------|-------|-------------|
| `temp_vault_dir` | Function | Creates an isolated filesystem directory structure for `Alpha-Vault/` and cleans up on exit. |
| `vault_manager` | Function | Instantiates `VaultManager` backed by temporary SQLite DB and ChromaDB vector store. |
| `mock_model_router` | Function | Deterministic model router returning role-appropriate responses without cloud API calls. |
| `api_client` | Function | FastAPI `TestClient` pre-configured with Bearer token authentication headers. |
| `mock_ws_client` | Function | In-memory WebSocket communication channel simulating mobile client push/pull. |
| `mcp_client` | Function | Direct invocation client testing the 15 MCP tools against JSON-RPC schemas. |
| `cli_runner` | Function | Invokes `alpha.py` command entry points (`setup`, `start`, `status`) capturing stdout/stderr. |

---

## 6. Verification & Test Execution Commands

### 6.1 Running Python E2E Test Suite

```bash
# Run all E2E test tiers with verbose output
pytest tests/e2e/ -v

# Run individual test tiers
pytest tests/e2e/test_tier1_features.py -v
pytest tests/e2e/test_tier2_boundaries.py -v
pytest tests/e2e/test_tier3_interactions.py -v
pytest tests/e2e/test_tier4_scenarios.py -v

# Run with coverage report
pytest --cov=backend tests/e2e/ --cov-report=term-missing
```

### 6.2 Running Flutter Mobile Test Suite

```bash
cd apk

# Run all unit and widget tests
flutter test

# Run unit tests only
flutter test test/unit/api_and_models_test.dart

# Run widget tests only
flutter test test/widget/canvas_and_progress_test.dart
```

---

## 7. Pass Criteria & Quality Gates

1. **100% Pass Rate:** All E2E test cases in Tiers 1 through 4 must pass without unhandled exceptions or regressions.
2. **Escalation Strictness:** Dual CAO audit must deterministically fail round 1 and round 2 upon critical defects, and trigger Founder escalation without infinite loops.
3. **Zero Secret Leakage:** No mock or real API tokens may appear in logs or exception messages.
4. **Mobile Contract Conformity:** All REST response structures and WebSocket event envelopes must deserialize cleanly into Dart data models.
