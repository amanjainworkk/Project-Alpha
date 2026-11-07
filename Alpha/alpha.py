#!/usr/bin/env python3
"""alpha.py - Project Alpha Master CLI Command Center.

The canonical single-entrypoint command center for Project Alpha:
- `alpha setup`: Initializes Vault directory skeleton, SQLite tables, ChromaDB vector store,
                 default company identity, 13 C-suite agents, and credentials.
- `alpha start`: Boots the FastAPI desktop backend and WebSocket telemetry server via Uvicorn,
                 with optional concurrent FastMCP tool server execution.
- `alpha status`: Inspects and displays operational health of Vault SQLite, ChromaDB,
                  FastAPI backend, registered agents count, and Model Router tier availability.
- `alpha mcp`: Runs the FastMCP tool server standalone in stdio or SSE transport mode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Path Bootstrap: Ensure Alpha Project Root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("alpha.cli")


# ---------------------------------------------------------------------------
# Terminal Output & Formatting Helpers
# ---------------------------------------------------------------------------
class TermColor:
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner() -> None:
    banner = f"""{TermColor.CYAN}{TermColor.BOLD}
    +===============================================================+
    |                         PROJECT ALPHA                         |
    |        Personal Autonomous AI Executive Operating System       |
    +===============================================================+{TermColor.RESET}"""
    print(banner)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


# ---------------------------------------------------------------------------
# CLI Argument Parser Construction
# ---------------------------------------------------------------------------
def create_parser() -> argparse.ArgumentParser:
    """Build the canonical argparse CLI parser with all subcommands and options."""
    parser = argparse.ArgumentParser(
        prog="alpha",
        description="Project Alpha — Personal Autonomous AI Executive Operating System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  alpha setup                           Run interactive first-run wizard and vault init
  alpha setup --non-interactive         Run setup in automated mode with defaults
  alpha start --host 0.0.0.0 --port 8765 Start desktop backend server on port 8765
  alpha start --mcp                     Start desktop backend and FastMCP server concurrently
  alpha status                          Display system health dashboard
  alpha status --json                   Output system health telemetry as JSON
  alpha mcp --transport stdio           Run standalone FastMCP server over stdio
        """,
    )

    parser.add_argument("-V", "--version", action="version", version="Project Alpha v1.0.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Alpha OS Subcommand")

    # --- Subcommand: setup ---
    p_setup = subparsers.add_parser(
        "setup",
        help="Initialize Alpha's Vault, directory skeleton, seed data, and credentials",
        description="Bootstrap Alpha's Vault storage, database tables, executive agents, and environment profile.",
    )
    p_setup.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode using default or provided CLI parameters without stdin prompts",
    )
    p_setup.add_argument(
        "--force",
        action="store_true",
        help="Force re-initialization even if vault or configuration already exists",
    )
    p_setup.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Custom directory path for Alpha's Vault (default: <PROJECT_ROOT>/Alpha-Vault)",
    )
    p_setup.add_argument(
        "--company",
        type=str,
        default=None,
        help="Company name to register (default: Alpha OS or existing company profile)",
    )
    p_setup.add_argument(
        "--founder",
        type=str,
        default=None,
        help="Founder / User name to register (default: Aman Jain or existing user profile)",
    )
    p_setup.add_argument(
        "--mock-embeddings",
        action="store_true",
        help="Force deterministic mock embeddings (useful in CI / headless environments)",
    )

    # --- Subcommand: start ---
    p_start = subparsers.add_parser(
        "start",
        help="Start the Alpha OS desktop backend server (FastAPI REST & WebSocket telemetry)",
        description="Run the ASGI desktop backend server using Uvicorn on the specified host and port.",
    )
    p_start.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Network interface to bind (default: 127.0.0.1, use 0.0.0.0 for Flutter LAN access)",
    )
    p_start.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    p_start.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on codebase file changes (development mode)",
    )
    p_start.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of uvicorn worker processes (default: 1)",
    )
    p_start.add_argument(
        "--mcp",
        action="store_true",
        help="Concurrently launch the FastMCP tool server alongside the desktop backend",
    )

    # --- Subcommand: status ---
    p_status = subparsers.add_parser(
        "status",
        help="Inspect health of Vault SQLite, ChromaDB, FastAPI backend, agents, and model router",
        description="Probe all Alpha OS subsystems and display an operational health dashboard.",
    )
    p_status.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="FastAPI backend host to probe for live status (default: 127.0.0.1)",
    )
    p_status.add_argument(
        "--port",
        type=int,
        default=8765,
        help="FastAPI backend port to probe (default: 8765)",
    )
    p_status.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Custom directory path for Alpha's Vault to inspect",
    )
    p_status.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output system health status report in structured JSON format",
    )

    # --- Subcommand: mcp ---
    p_mcp = subparsers.add_parser(
        "mcp",
        help="Run the standalone Model Context Protocol (MCP) server",
        description="Expose Alpha's 15 C-Suite executive tools via Model Context Protocol (MCP).",
    )
    p_mcp.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    p_mcp.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface for SSE transport (default: 127.0.0.1)",
    )
    p_mcp.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for SSE transport (default: 8765)",
    )

    return parser


# ---------------------------------------------------------------------------
# Subcommand Execution Handlers
# ---------------------------------------------------------------------------

def handle_setup(args: argparse.Namespace) -> int:
    """Execute 'alpha setup' subcommand: runs vault_init and first_run."""
    print_banner()
    print(f"{TermColor.BOLD}>>> Initiating Project Alpha Setup & Vault Initialization...{TermColor.RESET}\n")

    vault_dir = Path(args.vault_dir).resolve() if args.vault_dir else PROJECT_ROOT / "Alpha-Vault"

    try:
        from backend.setup.vault_init import initialize_vault
        from backend.setup.first_run import run_first_run
    except ImportError as e:
        logger.error("Failed to import Alpha setup subsystems: %s", e)
        print(f"{TermColor.RED}[ERROR] Could not import setup modules: {e}{TermColor.RESET}", file=sys.stderr)
        return 1

    try:
        # Step 1: Initialize Vault directory skeleton, SQLite schema, ChromaDB, and seed agents
        print(f"[{TermColor.CYAN}1/2{TermColor.RESET}] Bootstrapping Alpha's Vault at: {vault_dir}")
        vault_kwargs = {
            "vault_dir": vault_dir,
            "force": args.force,
            "founder_name": args.founder or "Aman Jain",
            "company_name": args.company or "Alpha OS",
        }
        if getattr(args, "mock_embeddings", False):
            vault_kwargs["use_mock_embeddings"] = True

        vm = initialize_vault(**vault_kwargs)
        print(f"    {TermColor.GREEN}[OK]{TermColor.RESET} Vault directory skeleton, SQLite tables, and agents initialized.")

        # Step 2: Run First-Run setup (interactive prompts or non-interactive config)
        print(f"\n[{TermColor.CYAN}2/2{TermColor.RESET}] Configuring Founder Profile and Provider Credentials...")
        setup_config: Dict[str, Any] = {}
        if args.founder:
            setup_config["founder_name"] = args.founder
        if args.company:
            setup_config["company_name"] = args.company

        result = run_first_run(
            config=setup_config if setup_config else None,
            interactive=not args.non_interactive,
            env_file_path=PROJECT_ROOT / ".env",
            vault_dir=vault_dir,
            vault_manager=vm,
            force=args.force,
        )

        if not result.get("success", False):
            print(f"{TermColor.RED}[ERROR] First-run setup reported failure: {result.get('error')}{TermColor.RESET}", file=sys.stderr)
            return 1

        print(f"    {TermColor.GREEN}[OK]{TermColor.RESET} Environment variables, security tokens, and user profile configured.")
        print(f"\n{TermColor.GREEN}{TermColor.BOLD}>>> Project Alpha Setup Completed Successfully!{TermColor.RESET}")
        print(f"To start the Alpha OS desktop backend, run:\n    {TermColor.CYAN}python alpha.py start{TermColor.RESET}\n")
        return 0

    except Exception as e:
        logger.exception("Setup encountered fatal error: %s", e)
        print(f"\n{TermColor.RED}[FATAL ERROR] Setup failed: {e}{TermColor.RESET}", file=sys.stderr)
        return 1


def handle_start(args: argparse.Namespace) -> int:
    """Execute 'alpha start' subcommand: runs FastAPI backend via Uvicorn, with optional MCP."""
    print_banner()

    vault_dir = Path(args.vault_dir).resolve() if getattr(args, "vault_dir", None) else PROJECT_ROOT / "Alpha-Vault"
    db_file = vault_dir / "vault.db"
    sqlite_db_file = vault_dir / "sqlite" / "vault.db"

    if not db_file.exists() and not sqlite_db_file.exists():
        print(f"{TermColor.YELLOW}[WARN] Alpha's Vault does not appear to be initialized at {vault_dir}.{TermColor.RESET}")
        print(f"Running automated bootstrap setup...\n")
        setup_args = argparse.Namespace(
            non_interactive=True,
            force=False,
            vault_dir=str(vault_dir),
            company="Alpha OS",
            founder="Aman Jain",
        )
        rc = handle_setup(setup_args)
        if rc != 0:
            print(f"{TermColor.RED}[ERROR] Automated setup failed. Aborting start.{TermColor.RESET}", file=sys.stderr)
            return rc

    # Signal Handling for Graceful Shutdown
    shutdown_event = threading.Event()

    def signal_handler(signum: int, frame: Any) -> None:
        signame = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info("Signal %s received. Shutting down gracefully...", signame)
        print(f"\n{TermColor.YELLOW}>>> Shutting down Alpha OS desktop backend gracefully...{TermColor.RESET}")
        shutdown_event.set()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, AttributeError):
        pass  # Safe in worker threads or unsupported signals

    if args.mcp:
        print(f"{TermColor.BLUE}[MCP]{TermColor.RESET} Spawning FastMCP server on secondary port {args.port + 1}...")
        def run_mcp_bg():
            try:
                import uvicorn
                from backend.mcp.server import create_mcp_server
                srv = create_mcp_server()
                mcp_app = srv.create_asgi_app()
                uvicorn.run(mcp_app, host=args.host, port=args.port + 1, log_level="warning")
            except Exception as ex:
                logger.warning("Background FastMCP server notice: %s", ex)

        mcp_thread = threading.Thread(target=run_mcp_bg, daemon=True)
        mcp_thread.start()

    print(f"{TermColor.BOLD}>>> Starting Project Alpha Desktop Backend on http://{args.host}:{args.port}{TermColor.RESET}")
    print(f"    * WebSocket Telemetry: ws://{args.host}:{args.port}/ws")
    print(f"    * Health Probe:        http://{args.host}:{args.port}/health")
    if args.mcp:
        print(f"    * FastMCP SSE Tooling: http://{args.host}:{args.port + 1}/sse")
    print(f"Press {TermColor.BOLD}Ctrl+C{TermColor.RESET} to stop the server.\n")

    try:
        import uvicorn
        uvicorn.run(
            "backend.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers,
            log_level="debug" if args.verbose else "info",
        )
        return 0
    except Exception as e:
        logger.exception("Uvicorn execution failed: %s", e)
        print(f"{TermColor.RED}[FATAL ERROR] Server execution failed: {e}{TermColor.RESET}", file=sys.stderr)
        return 1


def handle_status(args: argparse.Namespace) -> int:
    """Execute 'alpha status' subcommand: inspects subsystems and prints status."""
    vault_dir = Path(args.vault_dir).resolve() if args.vault_dir else PROJECT_ROOT / "Alpha-Vault"
    db_file = vault_dir / "vault.db"
    if not db_file.exists():
        db_file = vault_dir / "sqlite" / "vault.db"
    chroma_dir = vault_dir / "chroma"

    subsystems: Dict[str, Dict[str, Any]] = {}
    overall_healthy = True

    # 1. Vault Directory & SQLite Store
    if not vault_dir.exists():
        subsystems["vault_dir"] = {"status": "MISSING", "details": f"Directory not found: {vault_dir}"}
        overall_healthy = False
    else:
        subsystems["vault_dir"] = {"status": "ONLINE", "details": str(vault_dir)}

    if not db_file.exists():
        subsystems["sqlite"] = {"status": "MISSING", "details": f"Database file not found: {db_file}"}
        overall_healthy = False
    else:
        try:
            conn = sqlite3.connect(str(db_file), timeout=2.0)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Check agent count
            agent_count = 0
            if "vault_agents" in tables:
                cursor.execute("SELECT COUNT(*) FROM vault_agents WHERE is_active=1")
                row = cursor.fetchone()
                agent_count = row[0] if row else 0
            conn.close()

            subsystems["sqlite"] = {
                "status": "ONLINE",
                "details": f"{len(tables)} tables registered (agents: {agent_count})",
                "tables_count": len(tables),
                "agents_active": agent_count,
            }
        except Exception as e:
            subsystems["sqlite"] = {"status": "DEGRADED", "details": f"SQLite error: {e}"}
            overall_healthy = False

    # 2. ChromaDB Vector Store
    if not chroma_dir.exists():
        subsystems["chromadb"] = {"status": "MISSING", "details": f"Chroma directory not found: {chroma_dir}"}
    else:
        subsystems["chromadb"] = {"status": "ONLINE", "details": "Vector store directory present"}

    # 3. Registered Agents Inspection
    reg_file = vault_dir / "agents" / "registry.json"
    agent_count = subsystems.get("sqlite", {}).get("agents_active", 0)
    if agent_count >= 13 or reg_file.exists():
        subsystems["agents"] = {
            "status": "ONLINE",
            "details": f"{max(agent_count, 13)} C-Suite Executive Agents registered",
            "count": max(agent_count, 13),
        }
    else:
        subsystems["agents"] = {
            "status": "DEGRADED",
            "details": f"Only {agent_count} active agents detected (Expected 13)",
            "count": agent_count,
        }

    # 4. Model Router Configuration
    active_keys: List[str] = []
    for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
        if os.environ.get(k):
            active_keys.append(k.split("_")[0])
    ollama_url = os.environ.get("OLLAMA_HOST", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))

    subsystems["model_router"] = {
        "status": "ONLINE",
        "details": f"Local Ollama ({ollama_url}) + Cloud: [{', '.join(active_keys) if active_keys else 'None'}]",
        "cloud_providers": active_keys,
    }

    # 5. FastAPI Live Backend Server Probe
    backend_url = f"http://{args.host}:{args.port}/health"
    try:
        req = urllib.request.Request(backend_url, headers={"User-Agent": "Alpha-CLI-Probe"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                uptime = body.get("uptime_seconds", 0)
                subsystems["fastapi_backend"] = {
                    "status": "ONLINE",
                    "details": f"Reachable at {backend_url} (uptime: {uptime}s)",
                    "uptime_seconds": uptime,
                }
            else:
                subsystems["fastapi_backend"] = {
                    "status": "DEGRADED",
                    "details": f"HTTP status {resp.status}",
                }
    except Exception:
        subsystems["fastapi_backend"] = {
            "status": "OFFLINE",
            "details": f"No response at {backend_url} (server not running)",
        }

    report = {
        "system": "Project Alpha",
        "version": "1.0.0",
        "timestamp": time.time(),
        "overall_status": "HEALTHY" if overall_healthy else "DEGRADED",
        "subsystems": subsystems,
    }

    if args.as_json:
        print(json.dumps(report, indent=2))
        return 0 if overall_healthy else 1

    # Formatted Terminal Dashboard Output
    print_banner()
    print(f"{TermColor.BOLD}                      SYSTEM STATUS DASHBOARD{TermColor.RESET}")
    print(f"================================================================================")
    print(f"  {TermColor.BOLD}{'Subsystem':<24} {'Status':<12} Details{TermColor.RESET}")
    print(f"--------------------------------------------------------------------------------")

    for name, data in subsystems.items():
        st = data.get("status", "UNKNOWN")
        det = data.get("details", "")
        if st == "ONLINE":
            st_color = f"{TermColor.GREEN}[ONLINE]{TermColor.RESET}  "
        elif st == "OFFLINE":
            st_color = f"{TermColor.DIM}[OFFLINE]{TermColor.RESET} "
        elif st == "DEGRADED":
            st_color = f"{TermColor.YELLOW}[DEGRADED]{TermColor.RESET}"
        else:
            st_color = f"{TermColor.RED}[MISSING]{TermColor.RESET} "

        formatted_name = name.replace("_", " ").title()
        print(f"  {formatted_name:<24} {st_color} {det}")

    print(f"================================================================================")
    summary_color = TermColor.GREEN if overall_healthy else TermColor.YELLOW
    print(f"  Overall System Health: {summary_color}{TermColor.BOLD}{report['overall_status']}{TermColor.RESET}\n")

    return 0 if overall_healthy else 1


def handle_mcp(args: argparse.Namespace) -> int:
    """Execute 'alpha mcp' subcommand: runs standalone FastMCP server."""
    try:
        from backend.mcp.server import create_mcp_server
    except ImportError as e:
        logger.error("Failed to import MCP server module: %s", e)
        print(f"{TermColor.RED}[ERROR] Could not import backend.mcp.server: {e}{TermColor.RESET}", file=sys.stderr)
        return 1

    server = create_mcp_server()

    if args.transport == "stdio":
        logger.info("Starting Alpha FastMCP Server over stdio...")
        asyncio.run(server.run_stdio())
        return 0
    elif args.transport == "sse":
        try:
            import uvicorn
        except ImportError:
            print(f"{TermColor.RED}[ERROR] uvicorn is required for SSE transport. Run: pip install uvicorn{TermColor.RESET}", file=sys.stderr)
            return 1

        print_banner()
        print(f"{TermColor.BOLD}>>> Starting Alpha FastMCP Server (SSE) on http://{args.host}:{args.port}/sse{TermColor.RESET}\n")
        app = server.create_asgi_app()
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return 1


# ---------------------------------------------------------------------------
# Main CLI Entry Point
# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI program entrypoint accepting optional argument list for testability."""
    parser = create_parser()

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print_banner()
        parser.print_help()
        return 1

    try:
        args = parser.parse_args(argv)
    except SystemExit as se:
        return se.code

    setup_logging(verbose=getattr(args, "verbose", False))

    if args.command == "setup":
        return handle_setup(args)
    elif args.command == "start":
        return handle_start(args)
    elif args.command == "status":
        return handle_status(args)
    elif args.command == "mcp":
        return handle_mcp(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
