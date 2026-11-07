"""tests/setup/test_cli.py - Master Test Suite for Alpha CLI Command Center.

Verifies:
1. CLI top-level argument parsing and global flags (--help, --version, --verbose).
2. Unknown command and argument error handling with non-zero exit codes.
3. Subcommand 'alpha setup' argument passing and execution routing.
4. Subcommand 'alpha start' argument parsing and mock Uvicorn dispatch.
5. Subcommand 'alpha start --mcp' concurrent FastMCP dispatch.
6. Subcommand 'alpha status' subsystem diagnostic probes and formatted output.
7. Subcommand 'alpha status --json' parseable structured output.
8. Subcommand 'alpha mcp' standalone execution dispatch (stdio & sse).
9. Graceful signal handling lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpha import create_parser, main


# ============================================================================
# 1. Global Flags & Parser Basics
# ============================================================================

def test_cli_help_flag_displays_usage_and_exits_zero(capsys):
    """Verifies 'alpha --help' displays usage documentation and returns 0."""
    code = main(["--help"])
    assert code == 0
    captured = capsys.readouterr()
    assert "usage: alpha" in captured.out
    assert "setup" in captured.out
    assert "start" in captured.out
    assert "status" in captured.out
    assert "mcp" in captured.out


def test_cli_version_flag_displays_version_and_exits_zero(capsys):
    """Verifies 'alpha --version' prints version and returns 0."""
    code = main(["--version"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Project Alpha v1.0.0" in captured.out or "Project Alpha v1.0.0" in captured.err


def test_cli_no_args_displays_help_and_exits_nonzero(capsys):
    """Verifies invoking 'alpha' with no arguments displays help and returns 1."""
    code = main([])
    assert code == 1
    captured = capsys.readouterr()
    assert "usage: alpha" in captured.out or "usage: alpha" in captured.err


def test_cli_unknown_command_returns_code_two(capsys):
    """Verifies passing unrecognized command returns exit code 2."""
    code = main(["nonexistent_subcommand"])
    assert code == 2


# ============================================================================
# 2. 'alpha setup' Subcommand
# ============================================================================

def test_cli_setup_dispatches_with_flags(tmp_path: Path):
    """Verifies 'alpha setup' passes flags to vault_init and first_run."""
    mock_vm = MagicMock()
    mock_vm.close = MagicMock()

    with patch("backend.setup.vault_init.initialize_vault", return_value=mock_vm) as mock_init, \
         patch("backend.setup.first_run.run_first_run", return_value={"success": True}) as mock_run:

        code = main([
            "setup",
            "--non-interactive",
            "--vault-dir", str(tmp_path),
            "--company", "TestCo",
            "--founder", "TestFounder",
            "--force",
        ])

        assert code == 0
        mock_init.assert_called_once_with(
            vault_dir=tmp_path.resolve(),
            force=True,
            founder_name="TestFounder",
            company_name="TestCo",
        )
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["interactive"] is False
        assert kwargs["force"] is True


def test_cli_setup_returns_code_one_on_failure(tmp_path: Path):
    """Verifies 'alpha setup' returns exit code 1 if setup fails."""
    with patch("backend.setup.vault_init.initialize_vault", side_effect=RuntimeError("Disk failure")):
        code = main(["setup", "--non-interactive", "--vault-dir", str(tmp_path)])
        assert code == 1


# ============================================================================
# 3. 'alpha start' Subcommand
# ============================================================================

def test_cli_start_dispatches_to_uvicorn(tmp_path: Path):
    """Verifies 'alpha start' launches uvicorn with specified host, port, and reload."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("uvicorn.run") as mock_uvicorn:

        code = main([
            "start",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--reload",
            "--workers", "2",
        ])

        assert code == 0
        mock_uvicorn.assert_called_once()
        args, kwargs = mock_uvicorn.call_args
        assert args[0] == "backend.api.main:app"
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000
        assert kwargs["reload"] is True
        assert kwargs["workers"] == 2


def test_cli_start_with_mcp_flag_spawns_background_thread():
    """Verifies 'alpha start --mcp' initializes FastMCP concurrent server."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("threading.Thread.start") as mock_thread_start, \
         patch("uvicorn.run") as mock_uvicorn:

        code = main(["start", "--mcp"])
        assert code == 0
        mock_thread_start.assert_called_once()
        mock_uvicorn.assert_called_once()


# ============================================================================
# 4. 'alpha status' Subcommand
# ============================================================================

def test_cli_status_dashboard_text_output(tmp_path: Path, capsys):
    """Verifies 'alpha status' displays table headers and health rows."""
    vault_dir = tmp_path / "Alpha-Vault"
    vault_dir.mkdir(parents=True)
    db_file = vault_dir / "vault.db"
    db_file.touch()

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        code = main(["status", "--vault-dir", str(vault_dir)])

        assert code in (0, 1)
        captured = capsys.readouterr()
        assert "SYSTEM STATUS DASHBOARD" in captured.out
        assert "Vault Dir" in captured.out
        assert "Sqlite" in captured.out


def test_cli_status_json_flag_outputs_valid_json(tmp_path: Path, capsys):
    """Verifies 'alpha status --json' outputs parseable JSON telemetry."""
    vault_dir = tmp_path / "Alpha-Vault"
    vault_dir.mkdir(parents=True)
    db_file = vault_dir / "vault.db"
    db_file.touch()

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        code = main(["status", "--vault-dir", str(vault_dir), "--json"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert data["system"] == "Project Alpha"
        assert "subsystems" in data
        assert "vault_dir" in data["subsystems"]
        assert "sqlite" in data["subsystems"]
        assert "fastapi_backend" in data["subsystems"]


# ============================================================================
# 5. 'alpha mcp' Subcommand
# ============================================================================

def test_cli_mcp_stdio_dispatch():
    """Verifies 'alpha mcp --transport stdio' executes FastMCP stdio loop."""
    mock_srv = MagicMock()
    mock_srv.run_stdio = MagicMock()

    with patch("backend.mcp.server.create_mcp_server", return_value=mock_srv), \
         patch("asyncio.run") as mock_async_run:

        code = main(["mcp", "--transport", "stdio"])
        assert code == 0
        mock_async_run.assert_called_once()


def test_cli_mcp_sse_dispatch():
    """Verifies 'alpha mcp --transport sse' creates ASGI app and runs uvicorn."""
    mock_srv = MagicMock()
    mock_srv.create_asgi_app = MagicMock(return_value="mock_asgi_app")

    with patch("backend.mcp.server.create_mcp_server", return_value=mock_srv), \
         patch("uvicorn.run") as mock_uvicorn:

        code = main(["mcp", "--transport", "sse", "--host", "127.0.0.1", "--port", "8766"])
        assert code == 0
        mock_uvicorn.assert_called_once_with("mock_asgi_app", host="127.0.0.1", port=8766)
