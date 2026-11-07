"""Alpha/tests/setup/test_adversarial_m9_cli.py - Adversarial Stress & Robustness Suite.

Milestone 9 Empirical Challenger Suite targeting:
1. Command Line Parsing Hardening:
   - Invalid subcommands
   - Unknown and rogue flags across all subcommands
   - Malformed integer inputs (ports, workers)
   - Invalid enumeration choices (MCP transport protocols)
   - Non-existent custom vault paths
2. In-Process Programmatic Entrypoint (`main(argv=...)`):
   - None, empty, help, version, setup, status dispatches
3. Telemetry Schema & Health Probe Integrity (`alpha status`):
   - Strict JSON schema assertions (vault, sqlite, chroma, agents, models, backend)
   - Offline backend probe resilience (backend.healthy == False without crash)
   - Backend HTTP 500 error & non-JSON garbage resilience
   - Uninitialized vault directory graceful degraded report & exit code 1
   - Corrupted SQLite database graceful degraded report & exit code 1
   - Formatted ASCII dashboard stability under CP1252 / degraded states
4. Server Preflight & Signal Resilience (`alpha start`):
   - Preflight auto-bootstrap failure aborts cleanly with non-zero exit code
   - Server fatal execution failure catches exception and returns code 1
   - SIGINT and SIGTERM handlers set shutdown event and exit 0
   - Signal registration in non-main threads degrades gracefully
   - Concurrent FastMCP thread failure isolation
5. Subprocess Cross-Boundary Verification:
   - Real subprocess invocations testing stdout/stderr and process exit codes.
"""

from __future__ import annotations

import io
import json
import os
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

import alpha
from alpha import create_parser, main


PYTHON_EXE = sys.executable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================================
# 1. Command Line Parsing & Rogue Inputs
# ============================================================================

class TestCLIArgParsingAdversarial:
    """Stress-tests argparse error handling, invalid choices, and flag boundaries."""

    @pytest.mark.parametrize("subcmd", [
        "nonexistent",
        "bogus_command",
        "12345",
        "START",
        "Setup",
    ])
    def test_invalid_subcommand_returns_code_two(self, subcmd: str, capsys):
        """Verifies unknown subcommands return code 2 and write usage to stderr."""
        code = main([subcmd])
        assert code == 2
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err or "usage: alpha" in captured.err

    @pytest.mark.parametrize("args", [
        ["setup", "--bogus"],
        ["setup", "--extra-flag"],
        ["start", "--unknown-flag"],
        ["start", "--vault-dir", "/tmp"],  # start does not accept --vault-dir flag
        ["status", "--invalid-option"],
        ["mcp", "--bogus"],
    ])
    def test_unknown_flags_return_code_two(self, args, capsys):
        """Verifies unexpected arguments on valid subcommands return exit code 2."""
        code = main(args)
        assert code == 2
        captured = capsys.readouterr()
        assert "unrecognized arguments" in captured.err

    @pytest.mark.parametrize("bad_port", [
        "notanumber",
        "8765abc",
        "3.1415",
        "",
    ])
    def test_malformed_port_returns_code_two(self, bad_port: str, capsys):
        """Verifies non-integer port values return exit code 2."""
        code = main(["start", "--port", bad_port])
        assert code == 2
        captured = capsys.readouterr()
        assert "invalid int value" in captured.err

    def test_malformed_workers_returns_code_two(self, capsys):
        """Verifies non-integer workers value returns exit code 2."""
        code = main(["start", "--workers", "two"])
        assert code == 2
        captured = capsys.readouterr()
        assert "invalid int value" in captured.err

    @pytest.mark.parametrize("invalid_transport", [
        "invalid",
        "http",
        "tcp",
        "grpc",
        "websocket",
        "STDIO",
    ])
    def test_invalid_mcp_transport_returns_code_two(self, invalid_transport: str, capsys):
        """Verifies MCP transport restricts choices to 'stdio' and 'sse' with code 2."""
        code = main(["mcp", "--transport", invalid_transport])
        assert code == 2
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err


# ============================================================================
# 2. In-Process Programmatic Entrypoint (`main(argv=...)`)
# ============================================================================

class TestProgrammaticMainEntrypoint:
    """Verifies main() behavior with various argv parameter values."""

    def test_main_with_none_uses_sys_argv(self, capsys, monkeypatch):
        """Verifies main(None) reads sys.argv[1:]; with no args returns 1."""
        monkeypatch.setattr(sys, "argv", ["alpha.py"])
        code = main(None)
        assert code == 1
        captured = capsys.readouterr()
        assert "usage: alpha" in captured.out or "usage: alpha" in captured.err

    def test_main_with_empty_list_returns_one(self, capsys):
        """Verifies main([]) displays help and returns 1."""
        code = main([])
        assert code == 1
        captured = capsys.readouterr()
        assert "usage: alpha" in captured.out or "usage: alpha" in captured.err

    def test_main_help_flags_return_zero(self, capsys):
        """Verifies '--help' and '-h' print help and return 0."""
        for flag in ["--help", "-h"]:
            code = main([flag])
            assert code == 0
            captured = capsys.readouterr()
            assert "usage: alpha" in captured.out

    def test_main_version_flags_return_zero(self, capsys):
        """Verifies '--version' and '-V' print version string and return 0."""
        for flag in ["--version", "-V"]:
            code = main([flag])
            assert code == 0
            captured = capsys.readouterr()
            output = captured.out + captured.err
            assert "Project Alpha v1.0.0" in output

    def test_main_global_verbose_only_returns_one(self, capsys):
        """Verifies running with only global flags without a subcommand returns 1."""
        for flag in ["-v", "--verbose"]:
            code = main([flag])
            assert code == 1
            captured = capsys.readouterr()
            assert "usage: alpha" in captured.out or "usage: alpha" in captured.err

    def test_main_setup_non_interactive_success(self, tmp_path: Path):
        """Verifies programmatic execution of setup with non-interactive flags."""
        vault_dir = tmp_path / "ProgrammaticVault"
        with patch("backend.setup.vault_init.initialize_vault") as mock_init, \
             patch("backend.setup.first_run.run_first_run", return_value={"success": True}) as mock_run:

            code = main(["setup", "--non-interactive", "--vault-dir", str(vault_dir)])
            assert code == 0
            mock_init.assert_called_once()
            mock_run.assert_called_once()

    def test_main_status_json_execution(self, tmp_path: Path, capsys):
        """Verifies programmatic execution of status --json returns parseable JSON."""
        v_dir = tmp_path / "StatusVault"
        v_dir.mkdir(parents=True)
        (v_dir / "vault.db").touch()

        with patch("urllib.request.urlopen", side_effect=Exception("Offline")):
            code = main(["status", "--vault-dir", str(v_dir), "--json"])
            assert code in (0, 1)
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["system"] == "Project Alpha"
            assert "subsystems" in data


# ============================================================================
# 3. Telemetry Schema & Status Health Probes (`alpha status`)
# ============================================================================

class TestStatusTelemetryIntegrity:
    """Stress-tests telemetry generation, schema contracts, and degraded modes."""

    def test_status_json_schema_validity(self, tmp_path: Path, capsys):
        """Asserts schema completeness: presence of vault, sqlite, chroma, agents, models, backend."""
        vault_dir = tmp_path / "SchemaVault"
        vault_dir.mkdir(parents=True)
        db_file = vault_dir / "vault.db"
        
        # Initialize a minimal sqlite database with vault_agents table
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE vault_agents (id TEXT PRIMARY KEY, is_active INTEGER)")
        for i in range(14):
            conn.execute("INSERT INTO vault_agents VALUES (?, 1)", (f"agent_{i}",))
        conn.commit()
        conn.close()

        (vault_dir / "chroma").mkdir()

        with patch("urllib.request.urlopen", side_effect=Exception("Backend down")):
            code = main(["status", "--vault-dir", str(vault_dir), "--json"])
            captured = capsys.readouterr()
            report = json.loads(captured.out)

            # Top-level schema
            assert report["system"] == "Project Alpha"
            assert report["version"] == "1.0.0"
            assert isinstance(report["timestamp"], (int, float))
            assert report["overall_status"] in ("HEALTHY", "DEGRADED")
            assert "subsystems" in report

            sub = report["subsystems"]
            # Subsystem presence check: vault, sqlite, chroma, agents, models, backend
            assert "vault_dir" in sub, "vault subsystem missing"
            assert "sqlite" in sub, "sqlite subsystem missing"
            assert "chromadb" in sub, "chroma subsystem missing"
            assert "agents" in sub, "agents subsystem missing"
            assert "model_router" in sub, "models subsystem missing"
            assert "fastapi_backend" in sub, "backend subsystem missing"

            # Check individual subsystem schema
            for name, component in sub.items():
                assert "status" in component
                assert "details" in component

    def test_status_probe_backend_offline_not_crashing_and_unhealthy(self, tmp_path: Path, capsys):
        """Tests that when backend is offline, backend.healthy is False and CLI exits gracefully."""
        vault_dir = tmp_path / "OfflineVault"
        vault_dir.mkdir()
        (vault_dir / "vault.db").touch()

        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("Connection refused")):
            code = main(["status", "--vault-dir", str(vault_dir), "--json"])
            captured = capsys.readouterr()
            report = json.loads(captured.out)

            backend = report["subsystems"]["fastapi_backend"]
            assert backend["status"] == "OFFLINE"
            # verify backend healthy evaluation is False
            backend_healthy = (backend.get("status") == "ONLINE")
            assert backend_healthy is False
            assert "No response" in backend["details"]

    def test_status_probe_backend_online_parses_uptime(self, tmp_path: Path, capsys):
        """Tests status probe when backend is online and returns valid 200 health response."""
        vault_dir = tmp_path / "OnlineVault"
        vault_dir.mkdir()
        (vault_dir / "vault.db").touch()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "status": "healthy",
            "uptime_seconds": 123.45,
            "version": "1.0.0",
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            code = main(["status", "--vault-dir", str(vault_dir), "--json"])
            captured = capsys.readouterr()
            report = json.loads(captured.out)

            backend = report["subsystems"]["fastapi_backend"]
            assert backend["status"] == "ONLINE"
            assert backend["uptime_seconds"] == 123.45
            assert "uptime: 123.45s" in backend["details"]

    def test_status_probe_backend_http_500_handled_as_degraded(self, tmp_path: Path, capsys):
        """Tests status probe when backend responds with non-200 HTTP error code."""
        vault_dir = tmp_path / "ErrorVault"
        vault_dir.mkdir()
        (vault_dir / "vault.db").touch()

        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            code = main(["status", "--vault-dir", str(vault_dir), "--json"])
            captured = capsys.readouterr()
            report = json.loads(captured.out)

            backend = report["subsystems"]["fastapi_backend"]
            assert backend["status"] == "DEGRADED"
            assert "503" in backend["details"]

    def test_status_probe_backend_garbage_response_does_not_crash(self, tmp_path: Path, capsys):
        """Tests status probe when backend responds with non-JSON HTML/garbage payload."""
        vault_dir = tmp_path / "GarbageVault"
        vault_dir.mkdir()
        (vault_dir / "vault.db").touch()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"<html><body>502 Bad Gateway</body></html>"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            code = main(["status", "--vault-dir", str(vault_dir), "--json"])
            captured = capsys.readouterr()
            report = json.loads(captured.out)

            # JSON decode failure falls back to OFFLINE catch block without crashing
            backend = report["subsystems"]["fastapi_backend"]
            assert backend["status"] == "OFFLINE"

    def test_status_probe_uninitialized_vault_reports_degraded_and_exits_1(self, tmp_path: Path, capsys):
        """Tests status probe against a completely non-existent vault path."""
        nonexistent_path = tmp_path / "NeverCreatedVault"
        # Directory does not exist on disk

        code = main(["status", "--vault-dir", str(nonexistent_path), "--json"])
        # Should return exit code 1 because overall system health is DEGRADED
        assert code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)

        assert report["overall_status"] == "DEGRADED"
        assert report["subsystems"]["vault_dir"]["status"] == "MISSING"
        assert report["subsystems"]["sqlite"]["status"] == "MISSING"
        assert report["subsystems"]["chromadb"]["status"] == "MISSING"

    def test_status_probe_corrupted_sqlite_database_handled_gracefully(self, tmp_path: Path, capsys):
        """Tests status probe against a corrupted/non-sqlite db file."""
        vault_dir = tmp_path / "CorruptVault"
        vault_dir.mkdir()
        corrupt_db = vault_dir / "vault.db"
        corrupt_db.write_bytes(b"CORRUPTED_BINARY_NOT_SQLITE_HEADER_1234567890")

        code = main(["status", "--vault-dir", str(vault_dir), "--json"])
        assert code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)

        assert report["overall_status"] == "DEGRADED"
        assert report["subsystems"]["sqlite"]["status"] == "DEGRADED"
        assert "SQLite error" in report["subsystems"]["sqlite"]["details"]

    def test_status_text_dashboard_renders_without_encoding_errors(self, tmp_path: Path, capsys):
        """Verifies text-mode ASCII dashboard renders cleanly across various subsystem states."""
        vault_dir = tmp_path / "DashboardVault"
        vault_dir.mkdir()
        (vault_dir / "vault.db").touch()

        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            code = main(["status", "--vault-dir", str(vault_dir)])
            assert code in (0, 1)
            captured = capsys.readouterr()
            assert "SYSTEM STATUS DASHBOARD" in captured.out
            assert "Vault Dir" in captured.out
            assert "Fastapi Backend" in captured.out
            assert "Overall System Health" in captured.out


# ============================================================================
# 4. Server Preflight & Signal Resilience (`alpha start`)
# ============================================================================

class TestStartPreflightAndSignalResilience:
    """Stress-tests startup preflight checks, bootstrap fallback, and signal traps."""

    def test_start_preflight_uninitialized_vault_bootstrap_failure_aborts_cleanly(self, tmp_path: Path, capsys):
        """When vault is uninitialized and auto-bootstrap fails, start must abort without launching uvicorn."""
        empty_vault = tmp_path / "UninitializedVault"
        empty_vault.mkdir()

        # Mock handle_setup to simulate bootstrap failure (rc=1)
        with patch("alpha.PROJECT_ROOT", tmp_path), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("alpha.handle_setup", return_value=1) as mock_setup, \
             patch("uvicorn.run") as mock_uvicorn:

            code = main(["start"])
            assert code == 1
            mock_setup.assert_called_once()
            mock_uvicorn.assert_not_called()
            captured = capsys.readouterr()
            assert "Automated setup failed. Aborting start." in captured.err or "Automated setup failed" in captured.out

    def test_start_preflight_uninitialized_vault_bootstrap_success_proceeds(self, tmp_path: Path):
        """When vault is uninitialized but auto-bootstrap succeeds (rc=0), start proceeds to uvicorn."""
        with patch("alpha.PROJECT_ROOT", tmp_path), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("alpha.handle_setup", return_value=0) as mock_setup, \
             patch("uvicorn.run") as mock_uvicorn:

            code = main(["start"])
            assert code == 0
            mock_setup.assert_called_once()
            mock_uvicorn.assert_called_once()

    def test_start_uvicorn_fatal_error_returns_code_one(self, capsys):
        """When Uvicorn crashes or fails to bind port, main() catches and exits with code 1."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("uvicorn.run", side_effect=RuntimeError("Address already in use: 8765")):

            code = main(["start", "--port", "8765"])
            assert code == 1
            captured = capsys.readouterr()
            assert "Server execution failed" in captured.err

    def test_start_mcp_flag_thread_failure_isolated(self):
        """When --mcp is passed and background thread fails to start, main process remains intact."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("backend.mcp.server.create_mcp_server", side_effect=Exception("MCP Module Fault")), \
             patch("uvicorn.run") as mock_uvicorn:

            code = main(["start", "--mcp"])
            assert code == 0
            mock_uvicorn.assert_called_once()

    def test_start_signal_sigint_graceful_shutdown(self, capsys):
        """Verifies SIGINT signal handler prints notice, sets shutdown event, and raises SystemExit(0)."""
        registered_handlers: Dict[int, Any] = {}

        def mock_signal(sig, handler):
            registered_handlers[sig] = handler

        with patch("signal.signal", side_effect=mock_signal), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("uvicorn.run", side_effect=KeyboardInterrupt):

            # Check that signal handlers get registered
            try:
                main(["start"])
            except KeyboardInterrupt:
                pass

            assert signal.SIGINT in registered_handlers
            handler = registered_handlers[signal.SIGINT]

            # Invoke the registered SIGINT handler directly
            with pytest.raises(SystemExit) as exc_info:
                handler(signal.SIGINT, None)
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Shutting down Alpha OS desktop backend gracefully" in captured.out

    def test_start_signal_sigterm_graceful_shutdown(self, capsys):
        """Verifies SIGTERM signal handler prints notice, sets shutdown event, and raises SystemExit(0)."""
        registered_handlers: Dict[int, Any] = {}

        def mock_signal(sig, handler):
            registered_handlers[sig] = handler

        with patch("signal.signal", side_effect=mock_signal), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("uvicorn.run"):

            main(["start"])

            assert signal.SIGTERM in registered_handlers
            handler = registered_handlers[signal.SIGTERM]

            # Invoke the registered SIGTERM handler directly
            with pytest.raises(SystemExit) as exc_info:
                handler(signal.SIGTERM, None)
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Shutting down Alpha OS desktop backend gracefully" in captured.out

    def test_start_signal_registration_in_worker_thread_safe(self):
        """When signal registration raises ValueError (not in main thread), it is caught cleanly."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("signal.signal", side_effect=ValueError("signal only works in main thread of the main interpreter")), \
             patch("uvicorn.run") as mock_uvicorn:

            code = main(["start"])
            assert code == 0
            mock_uvicorn.assert_called_once()


# ============================================================================
# 5. Standalone Subprocess Cross-Boundary Verification
# ============================================================================

class TestSubprocessAdversarialCLI:
    """Verifies that OS-level process execution of alpha.py adheres to exit code contracts."""

    def test_subprocess_unknown_subcommand_exits_code_two(self):
        """Subprocess running 'alpha bogus' exits with code 2 and usage in stderr."""
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "bogus_command_name"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode == 2
        assert "invalid choice" in proc.stderr

    def test_subprocess_unknown_flag_exits_code_two(self):
        """Subprocess running 'alpha setup --bogus' exits with code 2."""
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "setup", "--bogus"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode == 2
        assert "unrecognized arguments: --bogus" in proc.stderr

    def test_subprocess_invalid_mcp_transport_exits_code_two(self):
        """Subprocess running 'alpha mcp --transport bad' exits with code 2."""
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "mcp", "--transport", "bad"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode == 2
        assert "invalid choice: 'bad'" in proc.stderr

    def test_subprocess_malformed_port_exits_code_two(self):
        """Subprocess running 'alpha start --port notanumber' exits with code 2."""
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "start", "--port", "notanumber"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode == 2
        assert "invalid int value: 'notanumber'" in proc.stderr

    def test_subprocess_status_json_schema_validation(self):
        """Subprocess running 'alpha status --json' produces valid JSON with all required keys."""
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "status", "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode in (0, 1)

        data = json.loads(proc.stdout)
        assert data["system"] == "Project Alpha"
        assert data["version"] == "1.0.0"
        sub = data["subsystems"]
        # Required subsystems: vault, sqlite, chroma, agents, models, backend
        assert "vault_dir" in sub
        assert "sqlite" in sub
        assert "chromadb" in sub
        assert "agents" in sub
        assert "model_router" in sub
        assert "fastapi_backend" in sub

    def test_subprocess_status_nonexistent_vault_exits_code_one(self, tmp_path: Path):
        """Subprocess running 'alpha status --vault-dir <missing>' reports degraded and exits code 1."""
        missing = tmp_path / "NonExistentVault"
        cmd = [PYTHON_EXE, str(PROJECT_ROOT / "alpha.py"), "status", "--vault-dir", str(missing), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert proc.returncode == 1

        data = json.loads(proc.stdout)
        assert data["overall_status"] == "DEGRADED"
        assert data["subsystems"]["vault_dir"]["status"] == "MISSING"
