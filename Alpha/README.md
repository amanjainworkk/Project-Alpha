# Project Alpha — Sovereign AI Executive Operating System

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Flutter](https://img.shields.io/badge/flutter->=3.22.0-02569B.svg)](https://flutter.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![FastMCP](https://img.shields.io/badge/FastMCP-15%20Tools-FF6F00.svg)](https://github.com/jlowin/fastmcp)
[![Tests Passing](https://img.shields.io/badge/tests-1%2C252%20passed-success.svg)](Alpha/tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Project Alpha is a sovereign, local-first AI Executive Operating System designed for founders and operators. It orchestrates a complete 13-agent C-Suite powered by multi-tier local inference (Ollama `llama3.2:1b`), persistent hybrid memory ("Alpha's Vault" with SQLite and ChromaDB), a 15-tool FastMCP server, and an OLED-optimized mobile companion APK featuring an interactive **Archify+** living canvas.

---

## Key Features

1. **Autonomous 13-Agent C-Suite**:
   - **CEO**: Goal intake, task decomposition, strategic synthesis, and executive steering.
   - **CTO, CPO, COO, CIO, CMO, CDO, CFO, CHRO, CSO, CLO**: Specialized executives operating with dedicated 10-page equivalent operational job descriptions.
   - **Dual CAO Engine**: Independent audit committee (Claude + ChatGPT perspectives) enforcing a strict 2-round cap and 5-axis review.

2. **Sovereign Local-First Architecture (Option 4)**:
   - Zero-cloud, zero-cost fallback mode using Ollama (`llama3.2:1b`) and local embeddings.
   - Fast desktop double-click launchers (`start_alpha_local.bat` and `start_alpha_local.ps1`).

3. **Alpha's Vault (Hybrid Storage)**:
   - Relational ACID persistence via SQLite (`Alpha-Vault/vault.db`) with foreign key integrity.
   - Semantic vector embeddings with ChromaDB (`Alpha-Vault/chroma/`).

4. **Tri-Framework Orchestration**:
   - Seamless workflow synthesis combining LangGraph StateGraphs, CrewAI hierarchical delegations, and AG2 GroupChat deliberations.
   - Kahn Critical Path Method (CPM) scheduler with dependency resolution.

5. **FastMCP Server (15 Enterprise Tools)**:
   - Full MCP protocol support across 6 namespaces: `alpha_vault`, `alpha_agent`, `alpha_project`, `alpha_thread`, `alpha_model`, `alpha_user`.

6. **FastAPI Desktop Engine & WebSocket Telemetry**:
   - Hardened REST API routes with constant-time Bearer authentication and RFC 6750 enforcement.
   - Real-time 6-event WebSocket telemetry broadcasting agent deliberations and CPM progress.

7. **Mobile APK Companion (Archify+ Living Canvas)**:
   - OLED pitch-black dark theme (`#0A0A0F`) with neon cyan (`#00F0FF`) telemetry indicators.
   - Dynamic CustomPainter canvas rendering cubic Bézier data splines and traveling glow packets.
   - Five full command center screens: Canvas, Task Board, Founder Chat, C-Suite Boardroom, and Vault Browser.

---

## Quickstart

### 1. Launch Sovereign Local Mode (Windows)
Double-click:
```cmd
start_alpha_local.bat
```
Or run via PowerShell:
```powershell
.\start_alpha_local.ps1
```

### 2. Manual CLI Operations
```bash
# Initialize Vault and SQLite tables
python alpha.py setup

# Start the desktop API and WebSocket server
python alpha.py start --host 127.0.0.1 --port 8000

# Inspect operational health and model status
python alpha.py status

# Run the 15-tool FastMCP server
python alpha.py mcp
```

### 3. Build Android Mobile Companion
```cmd
cd apk
build_apk.bat
```

---

## Test Suite & Verification

Project Alpha maintains an extensive automated regression test suite covering unit, integration, adversarial stress, and AST syntax balance tests:

```bash
pytest Alpha/tests -q
# Result: 1,252 passed (100% pass rate)
```

Mobile verification script:
```bash
python .agents/teamwork/explorer_m11_3/master_verification.py
# Validates 35/35 Dart files, delimiter balance, imports, and zero anti-cheat violations.
```

---

## License
MIT License. Open source and self-sustaining.
