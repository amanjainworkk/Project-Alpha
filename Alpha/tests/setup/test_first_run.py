"""tests/setup/test_first_run.py - Automated Unit & Integration Tests for First-Run Setup Wizard.

Verifies:
- Dual-mode execution (non-interactive programmatic invocation).
- Safe .env preservation (unrelated variables, comments, formatting).
- Cryptographic ALPHA_TOKEN generation and custom token preservation.
- Atomic Vault document creation and schema compliance (CompanyIdentity, UserProfile).
- Validation edge cases (empty founder/company name, invalid Ollama host).
- Idempotency and force reconfiguration.
- Simulated interactive input via mock.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from backend.setup.first_run import (
    SetupConfig,
    generate_secure_token,
    is_already_setup,
    parse_env_file,
    run_first_run,
    run_first_run_wizard,
    update_env_file,
    validate_api_key_format,
    validate_non_empty,
    validate_url,
)
from backend.vault.schemas import CompanyIdentity, UserProfile


@pytest.fixture
def temp_setup_env(tmp_path: Path):
    """Provides isolated temporary paths for .env and Alpha-Vault."""
    env_file = tmp_path / ".env"
    vault_dir = tmp_path / "Alpha-Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return env_file, vault_dir


def test_token_generation_entropy():
    """Verify generated tokens are secure, non-empty, and unique."""
    t1 = generate_secure_token(32)
    t2 = generate_secure_token(32)
    assert len(t1) >= 40
    assert len(t2) >= 40
    assert t1 != t2


def test_validation_rules():
    """Verify validation functions catch invalid inputs."""
    # Empty validation
    with pytest.raises(ValueError, match="Founder Name cannot be empty"):
        validate_non_empty("", "Founder Name")
    with pytest.raises(ValueError, match="Company Name cannot be empty"):
        validate_non_empty("   ", "Company Name")

    # URL validation
    assert validate_url("http://localhost:11434") == "http://localhost:11434"
    assert validate_url("https://ai.example.com") == "https://ai.example.com"
    with pytest.raises(ValueError, match="must begin with http://"):
        validate_url("localhost:11434", "Ollama Host")
    with pytest.raises(ValueError, match="must begin with http://"):
        validate_url("ftp://server", "Ollama Host")

    # API key formatting checks
    valid, msg = validate_api_key_format("groq", "gsk_test12345")
    assert valid is True
    valid, msg = validate_api_key_format("groq", "bad key with spaces")
    assert valid is False


def test_safe_env_file_preservation(tmp_path: Path):
    """Verify that updating .env never wipes or corrupts pre-existing unrelated variables."""
    env_file = tmp_path / ".env"
    initial_content = (
        "# Custom Database Configuration\n"
        "DATABASE_URL=postgresql://user:pass@localhost:5432/app\n"
        "DEBUG=true\n"
        "\n"
        "# Old Alpha settings\n"
        "ALPHA_TOKEN=old_token_value\n"
    )
    env_file.write_text(initial_content, encoding="utf-8")

    updates = {
        "ALPHA_TOKEN": "new_secure_token_abc123",
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "GROQ_API_KEY": "gsk_test_groq_key",
    }

    success = update_env_file(env_file, updates)
    assert success is True

    # Re-parse and verify
    raw_lines, parsed = parse_env_file(env_file)
    assert parsed["DATABASE_URL"] == "postgresql://user:pass@localhost:5432/app"
    assert parsed["DEBUG"] == "true"
    assert parsed["ALPHA_TOKEN"] == "new_secure_token_abc123"
    assert parsed["OLLAMA_HOST"] == "http://127.0.0.1:11434"
    assert parsed["GROQ_API_KEY"] == "gsk_test_groq_key"

    # Verify original comments are preserved
    full_text = env_file.read_text(encoding="utf-8")
    assert "# Custom Database Configuration" in full_text


def test_first_run_non_interactive_creates_env_and_vault(temp_setup_env):
    """Verify non-interactive setup creates valid .env and Vault documents."""
    env_file, vault_dir = temp_setup_env

    config = {
        "founder_name": "Aman Jain",
        "founder_role": "Founder & Chairman",
        "company_name": "Alpha Corp",
        "industry": "Autonomous AI",
        "vision": "Autonomous Company OS",
        "mission": "Empower founders via AI executive agents",
        "core_values": ["Speed", "Autonomy"],
        "strategic_focus_areas": ["Platform Scaling", "Mobile Interface"],
        "ollama_host": "http://localhost:11434",
        "groq_api_key": "gsk_valid_key_test",
    }

    res = run_first_run(
        config=config,
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )

    assert res["success"] is True
    assert res["already_configured"] is False
    assert res["env_updated"] is True
    assert res["vault_updated"] is True
    assert res["founder"] == "Aman Jain"
    assert res["company"] == "Alpha Corp"
    assert "ollama" in res["providers_configured"]
    assert "groq" in res["providers_configured"]

    # 1. Verify .env
    _, parsed_env = parse_env_file(env_file)
    assert parsed_env["OLLAMA_HOST"] == "http://localhost:11434"
    assert parsed_env["GROQ_API_KEY"] == "gsk_valid_key_test"
    assert len(parsed_env["ALPHA_TOKEN"]) >= 32

    # 2. Verify company/identity.json schema
    company_file = vault_dir / "company" / "identity.json"
    assert company_file.exists()
    company_data = json.loads(company_file.read_text(encoding="utf-8"))
    validated_company = CompanyIdentity.model_validate(company_data)
    assert validated_company.company_name == "Alpha Corp"
    assert validated_company.founder == "Aman Jain"
    assert validated_company.industry == "Autonomous AI"
    assert "Speed" in validated_company.core_values

    # 3. Verify user/profile.json schema
    user_file = vault_dir / "user" / "profile.json"
    assert user_file.exists()
    user_data = json.loads(user_file.read_text(encoding="utf-8"))
    validated_user = UserProfile.model_validate(user_data)
    assert validated_user.name == "Aman Jain"
    assert validated_user.role == "Founder & Chairman"
    assert "Platform Scaling" in validated_user.current_focus_areas

    # 4. Verify founder/profile.json mirror
    founder_file = vault_dir / "founder" / "profile.json"
    assert founder_file.exists()
    founder_data = json.loads(founder_file.read_text(encoding="utf-8"))
    assert founder_data["name"] == "Aman Jain"


def test_first_run_custom_token(temp_setup_env):
    """Verify custom ALPHA_TOKEN is honored when specified."""
    env_file, vault_dir = temp_setup_env
    custom_token = "my_custom_alpha_secret_token_123456789"

    res = run_first_run(
        config={"founder_name": "Test Founder", "company_name": "Test Co", "alpha_token": custom_token},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )

    assert res["success"] is True
    assert res["token"] == custom_token

    _, parsed_env = parse_env_file(env_file)
    assert parsed_env["ALPHA_TOKEN"] == custom_token


def test_idempotency_skip_without_force(temp_setup_env):
    """Verify re-running setup without force preserves existing setup without re-writing."""
    env_file, vault_dir = temp_setup_env

    # Initial setup
    res1 = run_first_run(
        config={"founder_name": "Initial Founder", "company_name": "Initial Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res1["success"] is True
    assert res1["already_configured"] is False
    assert is_already_setup(env_path=env_file, vault_dir=vault_dir) is True

    # Second run without force
    res2 = run_first_run(
        config={"founder_name": "New Founder", "company_name": "New Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
        force=False,
    )
    assert res2["success"] is True
    assert res2["already_configured"] is True
    assert res2["env_updated"] is False
    assert res2["vault_updated"] is False
    assert res2["founder"] == "Initial Founder"


def test_force_reconfiguration(temp_setup_env):
    """Verify force=True allows overwriting existing configuration."""
    env_file, vault_dir = temp_setup_env

    # Initial setup
    run_first_run(
        config={"founder_name": "Old Founder", "company_name": "Old Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )

    # Force reconfigure
    res = run_first_run(
        config={"founder_name": "New Founder", "company_name": "New Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
        force=True,
    )
    assert res["success"] is True
    assert res["already_configured"] is False
    assert res["env_updated"] is True
    assert res["founder"] == "New Founder"
    assert res["company"] == "New Co"


def test_validation_failure_handling(temp_setup_env):
    """Verify validation errors return failure response rather than uncaught crash."""
    env_file, vault_dir = temp_setup_env

    res = run_first_run(
        config={"founder_name": "", "company_name": "Test Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res["success"] is False
    assert "Founder Name cannot be empty" in res["error"]


def test_first_run_wizard_alias(temp_setup_env):
    """Verify run_first_run_wizard is a functional alias for run_first_run."""
    env_file, vault_dir = temp_setup_env
    res = run_first_run_wizard(
        config={"founder_name": "Alias Test", "company_name": "Alias Co"},
        interactive=False,
        env_file_path=env_file,
        vault_dir=vault_dir,
    )
    assert res["success"] is True
    assert res["founder"] == "Alias Test"


def test_mocked_interactive_flow(temp_setup_env):
    """Verifies interactive prompt execution using mocked stdin inputs."""
    env_file, vault_dir = temp_setup_env

    simulated_inputs = [
        "Aman Interactive",       # Founder Name
        "Founder & Chairman",     # Founder Title
        "Interactive Co",         # Company Name
        "Technology / AI",        # Industry
        "Autonomous Future",      # Vision
        "Empower builders",       # Mission
        "Speed, Autonomy",        # Core Values
        "Scale, Automate",        # Focus Areas
        "y",                      # Auto-generate secure ALPHA_TOKEN? [Y/n]
        "http://localhost:11434", # Ollama Host
        "gsk_mock_groq",          # Groq Key
        "AIza_mock_gemini",       # Gemini Key
        "sk-ant-mock_claude",     # Claude Key
        "sk-mock_openai",         # OpenAI Key
        "y",                      # Confirm apply configuration [Y/n]
    ]

    with patch("builtins.input", side_effect=simulated_inputs):
        result = run_first_run(
            interactive=True,
            env_file_path=env_file,
            vault_dir=vault_dir,
        )

    assert result["success"] is True
    company_file = vault_dir / "company" / "identity.json"
    assert company_file.exists()
    identity = json.loads(company_file.read_text(encoding="utf-8"))
    assert identity["company_name"] == "Interactive Co"
    assert identity["founder"] == "Aman Interactive"
