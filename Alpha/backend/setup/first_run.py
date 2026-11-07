"""backend/setup/first_run.py - Interactive First-Run Setup Wizard for Project Alpha.

Dual-Mode Architecture:
1. Interactive Mode: Rich terminal UI with step-by-step guided onboarding, defaults,
   validation, and review/confirmation.
2. Non-Interactive Mode: Programmatic and CLI-driven configuration for automated CI/CD
   and reproducible testing (run_first_run / run_first_run_wizard).

Handles:
- Founder profile and company identity collection.
- LLM Provider preferences and API key setup (Ollama, Groq, Gemini, Anthropic, OpenAI).
- Cryptographic ALPHA_TOKEN generation and management (secure 32-byte hex/urlsafe token).
- Safe, non-destructive .env preservation and merging (preserves existing variables and comments).
- Atomic Vault document writing (user/profile.json, founder/profile.json, company/identity.json).
- Idempotency checks and graceful keyboard interrupt (Ctrl+C) handling.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Optional Rich formatting with standard fallback
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.theme import Theme

    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "accent": "bold magenta",
        "highlight": "cyan bold",
    })
    console = Console(theme=custom_theme)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

logger = logging.getLogger("alpha.setup.first_run")


# ============================================================================
# Configuration Data Models
# ============================================================================

@dataclass
class SetupConfig:
    """Master configuration payload for Project Alpha setup."""
    # Founder Information
    founder_name: str = "Aman Jain"
    founder_role: str = "Founder & Chairman"
    communication_style: str = "direct, bulleted"
    working_hours: str = "flexible"

    # Company Identity
    company_name: str = "Alpha OS"
    vision: str = "Autonomous AI Executive OS delivering end-to-end company goals"
    mission: str = "Master and deploy autonomous AI C-suite agents with zero marginal cost"
    industry: str = "Technology / Autonomous AI"
    current_stage: str = "early-stage"
    core_values: List[str] = field(default_factory=lambda: ["Autonomy", "Speed", "Excellence", "Integrity"])
    strategic_focus_areas: List[str] = field(default_factory=lambda: [
        "Autonomous Operations",
        "Free-First Intelligence",
        "Cross-Platform Architecture",
    ])
    working_style: str = "autonomous, high-velocity"

    # Security & Authentication
    alpha_token: Optional[str] = None

    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8765
    vault_dir: Optional[str] = None

    # LLM Providers & API Keys
    ollama_host: str = "http://localhost:11434"
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetupConfig":
        """Instantiate SetupConfig from arbitrary dictionary, ignoring extraneous keys."""
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields and v is not None}
        return cls(**filtered)


# ============================================================================
# Token Generation & Cryptography
# ============================================================================

def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure authentication token."""
    return secrets.token_hex(nbytes)


# ============================================================================
# Safe .env Parsing & Non-Destructive Merging
# ============================================================================

def parse_env_file(env_path: Path) -> Tuple[List[str], Dict[str, str]]:
    """Parse existing .env file preserving exact lines and extracting key-value pairs.

    Returns:
        Tuple of (raw_lines, parsed_dict)
    """
    if not env_path.exists():
        return [], {}

    raw_lines: List[str] = []
    parsed: Dict[str, str] = {}

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                raw_lines.append(line)
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, val = stripped.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip surrounding single or double quotes
                    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                        val = val[1:-1]
                    parsed[key] = val
    except Exception as e:
        logger.warning("Error reading existing .env file at %s: %s", env_path, e)

    return raw_lines, parsed


def format_env_value(val: str) -> str:
    """Format value for .env output, wrapping with double quotes if needed."""
    if not val:
        return ""
    if any(c in val for c in (' ', '\t', '#', '"', "'", '\n', '$')):
        escaped = val.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return val


def update_env_file(
    env_path: Path,
    updates: Dict[str, Optional[str]],
    backup: bool = True,
) -> bool:
    """Safely and atomically update .env file without wiping existing unrelated variables.

    - Modifies existing keys in-place, preserving their order and comments.
    - Appends newly added keys under a designated header.
    - Uses temporary file and atomic replace to guarantee integrity.
    """
    env_path = Path(env_path).resolve()
    env_dir = env_path.parent
    env_dir.mkdir(parents=True, exist_ok=True)

    raw_lines, existing_dict = parse_env_file(env_path)

    # Optional backup of original .env
    if backup and env_path.exists():
        try:
            bak_path = env_path.with_suffix(".env.bak")
            with open(env_path, "r", encoding="utf-8") as src, open(bak_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        except Exception as e:
            logger.debug("Failed to create .env.bak: %s", e)

    updated_keys: set[str] = set()
    new_lines: List[str] = []

    # Process existing lines, modifying matching keys in place
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_val = updates[k]
                if new_val is not None:
                    new_lines.append(f"{k}={format_env_value(str(new_val))}\n")
                else:
                    new_lines.append(line)  # Preserve original if update is None
                updated_keys.add(k)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append new keys that were not present in existing file
    unseen_keys = {k: v for k, v in updates.items() if k not in updated_keys and v is not None}
    if unseen_keys:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("\n")

        new_lines.append("# --- Project Alpha Configuration ---\n")
        for k, v in unseen_keys.items():
            new_lines.append(f"{k}={format_env_value(str(v))}\n")

    # Atomic write via temporary file
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=str(env_dir), delete=False, encoding="utf-8") as tf:
            temp_file = tf.name
            tf.writelines(new_lines)

        # Retry loop for Windows NTFS file locking
        max_retries = 5
        backoff = 0.05
        for attempt in range(max_retries):
            try:
                os.replace(temp_file, str(env_path))
                temp_file = None
                break
            except (PermissionError, OSError) as pe:
                if attempt == max_retries - 1:
                    raise pe
                time.sleep(backoff)
                backoff *= 2
        return True
    except Exception as e:
        logger.error("Failed to write .env file atomically at %s: %s", env_path, e)
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        return False


# ============================================================================
# Validation Functions
# ============================================================================

def validate_non_empty(val: Optional[str], field_name: str) -> str:
    """Validate that a string value is not empty or whitespace-only."""
    if not val or not val.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    return val.strip()


def validate_url(url: Optional[str], field_name: str = "URL") -> str:
    """Validate that a URL starts with http:// or https://."""
    if not url or not url.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    cleaned = url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError(f"{field_name} must begin with http:// or https:// (got '{cleaned}').")
    return cleaned


def validate_api_key_format(provider: str, key: Optional[str]) -> Tuple[bool, str]:
    """Validate API key format conventions.

    Returns:
        (is_valid, warning_or_error_message)
    """
    if not key or not key.strip():
        return True, ""  # Optional keys are valid when empty

    cleaned = key.strip()
    if any(c.isspace() for c in cleaned):
        return False, f"{provider} API key must not contain whitespace."

    if provider == "groq" and not cleaned.startswith("gsk_"):
        return True, "Notice: Groq API keys typically begin with 'gsk_'."
    if provider == "anthropic" and not cleaned.startswith("sk-ant-"):
        return True, "Notice: Anthropic API keys typically begin with 'sk-ant-'."
    if provider == "openai" and not (cleaned.startswith("sk-") or cleaned.startswith("sk-proj-")):
        return True, "Notice: OpenAI API keys typically begin with 'sk-'."
    if provider == "gemini" and not cleaned.startswith("AIza"):
        return True, "Notice: Google Gemini API keys typically begin with 'AIza'."

    return True, ""


# ============================================================================
# Idempotency & Status Check
# ============================================================================

def is_already_setup(
    env_path: Optional[Path] = None,
    vault_dir: Optional[Path] = None,
) -> bool:
    """Check if Project Alpha has already been configured."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    target_env = env_path or (base_dir / ".env")
    target_vault = vault_dir or (base_dir / "Alpha-Vault")

    if not target_env.exists():
        return False

    _, parsed = parse_env_file(target_env)
    token = parsed.get("ALPHA_TOKEN")
    if not token or not token.strip():
        return False

    company_id = target_vault / "company" / "identity.json"
    user_prof = target_vault / "user" / "profile.json"
    founder_prof = target_vault / "founder" / "profile.json"

    # Must have identity and at least one user/founder profile
    has_identity = company_id.exists()
    has_profile = user_prof.exists() or founder_prof.exists()

    return has_identity and has_profile


def load_existing_config(
    env_path: Optional[Path] = None,
    vault_dir: Optional[Path] = None,
) -> SetupConfig:
    """Load configuration from existing .env and Vault files."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    target_env = env_path or (base_dir / ".env")
    target_vault = vault_dir or (base_dir / "Alpha-Vault")

    config = SetupConfig()

    if target_env.exists():
        _, parsed = parse_env_file(target_env)
        config.alpha_token = parsed.get("ALPHA_TOKEN")
        config.ollama_host = parsed.get("OLLAMA_HOST", config.ollama_host)
        config.groq_api_key = parsed.get("GROQ_API_KEY")
        config.gemini_api_key = parsed.get("GEMINI_API_KEY") or parsed.get("GOOGLE_API_KEY")
        config.anthropic_api_key = parsed.get("ANTHROPIC_API_KEY")
        config.openai_api_key = parsed.get("OPENAI_API_KEY")
        config.host = parsed.get("ALPHA_HOST", config.host)
        if "ALPHA_PORT" in parsed:
            try:
                config.port = int(parsed["ALPHA_PORT"])
            except ValueError:
                pass

    company_id_file = target_vault / "company" / "identity.json"
    if company_id_file.exists():
        try:
            with open(company_id_file, "r", encoding="utf-8") as f:
                c_data = json.load(f)
            config.company_name = c_data.get("company_name", config.company_name)
            config.founder_name = c_data.get("founder", config.founder_name)
            config.vision = c_data.get("vision", config.vision)
            config.mission = c_data.get("mission", config.mission)
            config.industry = c_data.get("industry", config.industry)
            config.core_values = c_data.get("core_values", config.core_values)
            config.strategic_focus_areas = c_data.get("primary_goals", config.strategic_focus_areas)
        except Exception as e:
            logger.debug("Failed loading existing company identity: %s", e)

    user_prof_file = target_vault / "user" / "profile.json"
    if not user_prof_file.exists():
        user_prof_file = target_vault / "founder" / "profile.json"

    if user_prof_file.exists():
        try:
            with open(user_prof_file, "r", encoding="utf-8") as f:
                u_data = json.load(f)
            config.founder_name = u_data.get("name", config.founder_name)
            config.founder_role = u_data.get("role", config.founder_role)
            config.communication_style = u_data.get("communication_style", config.communication_style)
        except Exception as e:
            logger.debug("Failed loading existing user profile: %s", e)

    return config


# ============================================================================
# Interactive Terminal Prompts
# ============================================================================

def prompt_text(prompt_msg: str, default: str) -> str:
    """Prompt user for text with default, supporting Rich and plain fallback."""
    if HAS_RICH and sys.stdout.isatty():
        return Prompt.ask(f"[bold cyan]{prompt_msg}[/]", default=default)
    else:
        resp = input(f"{prompt_msg} [{default}]: ").strip()
        return resp if resp else default


def prompt_secret(prompt_msg: str, default: Optional[str] = None) -> Optional[str]:
    """Prompt user for sensitive API keys (optional)."""
    default_hint = " (Press Enter to keep existing / leave blank)" if not default else " [Set/Masked]"
    if HAS_RICH and sys.stdout.isatty():
        resp = Prompt.ask(f"[bold yellow]{prompt_msg}[/]{default_hint}", default=default or "", password=False)
        return resp.strip() if resp.strip() else default
    else:
        resp = input(f"{prompt_msg}{default_hint}: ").strip()
        return resp if resp else default


def prompt_interactive_wizard(default_config: Optional[SetupConfig] = None) -> SetupConfig:
    """Run interactive terminal onboarding wizard collecting full configuration."""
    cfg = default_config or SetupConfig()

    if HAS_RICH and sys.stdout.isatty():
        console.print(Panel(
            "[bold cyan]PROJECT ALPHA — FIRST-RUN SETUP WIZARD[/]\n"
            "[dim]Autonomous AI Executive Operating System[/]\n\n"
            "This wizard will configure your Founder Profile, Company Identity,\n"
            "Security Token, and LLM Provider API keys.",
            border_style="cyan",
            title="[bold green]Welcome[/]",
            subtitle="[dim]Milestone 9[/]",
        ))
    else:
        print("=" * 60)
        print("PROJECT ALPHA — FIRST-RUN SETUP WIZARD")
        print("=" * 60)

    # ------------------------------------------------------------------------
    # Step 1: Founder & Company Profile
    # ------------------------------------------------------------------------
    if HAS_RICH and sys.stdout.isatty():
        console.print("\n[bold green]Step 1: Founder & Company Profile[/]")
    else:
        print("\n--- Step 1: Founder & Company Profile ---")

    cfg.founder_name = prompt_text("Founder Full Name", cfg.founder_name)
    cfg.founder_role = prompt_text("Founder Title/Role", cfg.founder_role)
    cfg.company_name = prompt_text("Company / Organization Name", cfg.company_name)
    cfg.industry = prompt_text("Industry / Focus", cfg.industry)
    cfg.vision = prompt_text("Primary Vision Statement", cfg.vision)
    cfg.mission = prompt_text("Primary Mission Statement", cfg.mission)

    raw_values = prompt_text("Core Values (comma-separated)", ", ".join(cfg.core_values))
    cfg.core_values = [v.strip() for v in raw_values.split(",") if v.strip()]

    raw_focus = prompt_text("Strategic Focus Areas / Goals (comma-separated)", ", ".join(cfg.strategic_focus_areas))
    cfg.strategic_focus_areas = [f.strip() for f in raw_focus.split(",") if f.strip()]

    # ------------------------------------------------------------------------
    # Step 2: Authentication & Security Token
    # ------------------------------------------------------------------------
    if HAS_RICH and sys.stdout.isatty():
        console.print("\n[bold green]Step 2: Authentication & Security[/]")
        console.print("[dim]ALPHA_TOKEN secures the FastAPI REST backend and WebSocket telemetry stream.[/]")
    else:
        print("\n--- Step 2: Authentication & Security ---")

    if not cfg.alpha_token:
        generated_token = generate_secure_token()
        use_auto = True
        if HAS_RICH and sys.stdout.isatty():
            use_auto = Confirm.ask(
                f"Auto-generate a cryptographically secure 256-bit ALPHA_TOKEN?",
                default=True,
            )
        else:
            resp = input("Auto-generate secure ALPHA_TOKEN? [Y/n]: ").strip().lower()
            use_auto = resp not in ("n", "no")

        if use_auto:
            cfg.alpha_token = generated_token
        else:
            custom_token = prompt_text("Enter Custom ALPHA_TOKEN", generated_token)
            cfg.alpha_token = custom_token
    else:
        if HAS_RICH and sys.stdout.isatty():
            console.print(f"[dim]Existing ALPHA_TOKEN detected: {cfg.alpha_token[:8]}...[/]")
            regen = Confirm.ask("Regenerate a new secure token?", default=False)
        else:
            resp = input(f"Existing ALPHA_TOKEN detected ({cfg.alpha_token[:8]}...). Regenerate? [y/N]: ").strip().lower()
            regen = resp in ("y", "yes")
        if regen:
            cfg.alpha_token = generate_secure_token()

    # ------------------------------------------------------------------------
    # Step 3: LLM Providers & API Keys
    # ------------------------------------------------------------------------
    if HAS_RICH and sys.stdout.isatty():
        console.print("\n[bold green]Step 3: LLM Providers & Free-First Routing[/]")
        console.print("[dim]Project Alpha routes tasks through Ollama (free local) and Groq/Gemini (free cloud) first.[/]")
    else:
        print("\n--- Step 3: LLM Providers & Free-First Routing ---")

    cfg.ollama_host = prompt_text("Ollama Base URL", cfg.ollama_host)
    cfg.groq_api_key = prompt_secret("Groq API Key (Tier 3 Fast Cloud)", cfg.groq_api_key)
    cfg.gemini_api_key = prompt_secret("Google Gemini API Key (Tier 4 High-Context)", cfg.gemini_api_key)
    cfg.anthropic_api_key = prompt_secret("Anthropic API Key (Tier 5 & CAO-Claude Audit)", cfg.anthropic_api_key)
    cfg.openai_api_key = prompt_secret("OpenAI API Key (Tier 5 & CAO-ChatGPT Audit)", cfg.openai_api_key)

    # ------------------------------------------------------------------------
    # Step 4: Review & Confirmation
    # ------------------------------------------------------------------------
    if HAS_RICH and sys.stdout.isatty():
        summary_table = Table(title="Configuration Summary", border_style="cyan")
        summary_table.add_column("Parameter", style="cyan bold")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Founder Name", cfg.founder_name)
        summary_table.add_row("Founder Title", cfg.founder_role)
        summary_table.add_row("Company Name", cfg.company_name)
        summary_table.add_row("Industry", cfg.industry)
        summary_table.add_row("Core Values", ", ".join(cfg.core_values))
        summary_table.add_row("Strategic Focus", ", ".join(cfg.strategic_focus_areas))
        summary_table.add_row("Ollama Host", cfg.ollama_host)
        summary_table.add_row("Groq Key", "Configured" if cfg.groq_api_key else "[dim]Not Set[/]")
        summary_table.add_row("Gemini Key", "Configured" if cfg.gemini_api_key else "[dim]Not Set[/]")
        summary_table.add_row("Anthropic Key", "Configured" if cfg.anthropic_api_key else "[dim]Not Set[/]")
        summary_table.add_row("OpenAI Key", "Configured" if cfg.openai_api_key else "[dim]Not Set[/]")
        summary_table.add_row("ALPHA_TOKEN", f"{cfg.alpha_token[:12]}... (Masked)")

        console.print("\n")
        console.print(summary_table)

        confirmed = Confirm.ask("\n[bold green]Apply this configuration to Project Alpha?[/]", default=True)
    else:
        print("\n=== Review Configuration ===")
        print(f"Founder:      {cfg.founder_name} ({cfg.founder_role})")
        print(f"Company:      {cfg.company_name} ({cfg.industry})")
        print(f"Ollama Host:  {cfg.ollama_host}")
        print(f"Groq Key:     {'Configured' if cfg.groq_api_key else 'Not Set'}")
        print(f"Gemini Key:   {'Configured' if cfg.gemini_api_key else 'Not Set'}")
        print(f"Anthropic:    {'Configured' if cfg.anthropic_api_key else 'Not Set'}")
        print(f"OpenAI:       {'Configured' if cfg.openai_api_key else 'Not Set'}")
        print(f"ALPHA_TOKEN:  {cfg.alpha_token[:12]}...")

        resp = input("\nApply this configuration? [Y/n]: ").strip().lower()
        confirmed = resp not in ("n", "no")

    if not confirmed:
        raise KeyboardInterrupt("Configuration discarded by user.")

    return cfg


# ============================================================================
# Core Configuration Execution: apply_setup
# ============================================================================

def apply_setup(
    config: SetupConfig,
    env_path: Optional[Path] = None,
    vault_dir: Optional[Path] = None,
    vault_manager: Optional[Any] = None,
) -> Dict[str, Any]:
    """Apply the setup configuration: write/update .env and Vault documents."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    target_env = Path(env_path) if env_path else (base_dir / ".env")
    target_vault = Path(vault_dir) if vault_dir else (base_dir / "Alpha-Vault")

    # 1. Validate mandatory fields
    validate_non_empty(config.founder_name, "Founder Name")
    validate_non_empty(config.company_name, "Company Name")
    validate_url(config.ollama_host, "Ollama Host")

    # Auto-generate token if missing
    token = config.alpha_token or generate_secure_token()
    config.alpha_token = token

    written_files: List[str] = []

    # 2. Update .env file safely
    env_updates: Dict[str, Optional[str]] = {
        "ALPHA_TOKEN": token,
        "OLLAMA_HOST": config.ollama_host,
    }
    if config.groq_api_key is not None:
        env_updates["GROQ_API_KEY"] = config.groq_api_key
    if config.gemini_api_key is not None:
        env_updates["GEMINI_API_KEY"] = config.gemini_api_key
    if config.anthropic_api_key is not None:
        env_updates["ANTHROPIC_API_KEY"] = config.anthropic_api_key
    if config.openai_api_key is not None:
        env_updates["OPENAI_API_KEY"] = config.openai_api_key
    if config.host:
        env_updates["ALPHA_HOST"] = config.host
    if config.port:
        env_updates["ALPHA_PORT"] = str(config.port)
    if config.vault_dir:
        env_updates["ALPHA_VAULT_DIR"] = str(config.vault_dir)

    env_success = update_env_file(target_env, env_updates)
    if env_success:
        written_files.append(str(target_env))
    else:
        raise OSError(f"Failed to safely update .env file at {target_env}")

    # 3. Prepare Vault directory structure
    for sub in ["company", "user", "founder", "agents", "projects", "knowledge", "backups"]:
        (target_vault / sub).mkdir(parents=True, exist_ok=True)

    # 4. Prepare Company Identity payload conforming to CompanyIdentity schema
    company_data: Dict[str, Any] = {
        "company_name": config.company_name,
        "founder": config.founder_name,
        "founded_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "vision": config.vision,
        "mission": config.mission,
        "core_values": config.core_values,
        "industry": config.industry,
        "current_stage": config.current_stage,
        "primary_goals": config.strategic_focus_areas,
        "working_style": config.working_style,
        "preferred_communication": config.communication_style,
        "timezone": "UTC",
        "language": "en",
        "alpha_version": "1.0.0",
    }

    # 5. Prepare User Profile payload conforming to UserProfile schema
    user_data: Dict[str, Any] = {
        "name": config.founder_name,
        "role": config.founder_role,
        "communication_style": config.communication_style,
        "decision_making": "autonomous with review",
        "working_hours": config.working_hours,
        "output_preferences": {
            "length": "concise",
            "format": "bullet",
            "include_reasoning": True,
        },
        "auto_approve_routine": True,
        "escalation_threshold": "critical_only",
        "current_focus_areas": config.strategic_focus_areas,
        "long_term_goals": config.strategic_focus_areas,
        "projects_completed": 0,
        "total_goals_given": 0,
    }

    # 6. Write via VaultManager if available, otherwise direct atomic JSON file write
    if vault_manager is not None and hasattr(vault_manager, "write"):
        try:
            vault_manager.write("company/identity.json", company_data, agent_id="admin")
            vault_manager.write("user/profile.json", user_data, agent_id="admin")
            vault_manager.write("founder/profile.json", user_data, agent_id="admin")
            written_files.extend([
                str(target_vault / "company" / "identity.json"),
                str(target_vault / "user" / "profile.json"),
                str(target_vault / "founder" / "profile.json"),
            ])
        except Exception as e:
            logger.warning("VaultManager.write encountered issue, falling back to disk write: %s", e)
            _write_json_atomic(target_vault / "company" / "identity.json", company_data)
            _write_json_atomic(target_vault / "user" / "profile.json", user_data)
            _write_json_atomic(target_vault / "founder" / "profile.json", user_data)
            written_files.extend([
                str(target_vault / "company" / "identity.json"),
                str(target_vault / "user" / "profile.json"),
                str(target_vault / "founder" / "profile.json"),
            ])
    else:
        _write_json_atomic(target_vault / "company" / "identity.json", company_data)
        _write_json_atomic(target_vault / "user" / "profile.json", user_data)
        _write_json_atomic(target_vault / "founder" / "profile.json", user_data)
        written_files.extend([
            str(target_vault / "company" / "identity.json"),
            str(target_vault / "user" / "profile.json"),
            str(target_vault / "founder" / "profile.json"),
        ])

    providers_configured = ["ollama"]
    if config.groq_api_key:
        providers_configured.append("groq")
    if config.gemini_api_key:
        providers_configured.append("gemini")
    if config.anthropic_api_key:
        providers_configured.append("anthropic")
    if config.openai_api_key:
        providers_configured.append("openai")

    return {
        "success": True,
        "already_configured": False,
        "env_updated": True,
        "vault_updated": True,
        "token": token,
        "founder": config.founder_name,
        "company": config.company_name,
        "providers_configured": providers_configured,
        "written_files": written_files,
    }


def _write_json_atomic(target_path: Path, data: Dict[str, Any]) -> None:
    """Write JSON data to disk atomically with retry on Windows NTFS contention."""
    target_path = Path(target_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=str(target_path.parent), delete=False, encoding="utf-8") as tf:
            temp_file = tf.name
            json.dump(data, tf, indent=2, ensure_ascii=False)

        max_retries = 5
        backoff = 0.02
        for attempt in range(max_retries):
            try:
                os.replace(temp_file, str(target_path))
                temp_file = None
                break
            except (PermissionError, OSError) as pe:
                if attempt == max_retries - 1:
                    raise pe
                time.sleep(backoff)
                backoff *= 2
    except Exception as e:
        logger.error("Failed writing atomic json to %s: %s", target_path, e)
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        raise e


# ============================================================================
# Main Entrypoint: run_first_run & run_first_run_wizard
# ============================================================================

def run_first_run(
    config: Optional[Union[Dict[str, Any], SetupConfig]] = None,
    interactive: bool = False,
    env_file_path: Optional[Union[str, Path]] = None,
    vault_dir: Optional[Union[str, Path]] = None,
    vault_manager: Optional[Any] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Execute First-Run Setup Wizard.

    Args:
        config: Optional pre-constructed SetupConfig or dictionary of parameters.
        interactive: If True, prompt user via interactive terminal wizard.
                     If False, execute non-interactively using config/defaults.
        env_file_path: Optional custom path to .env file.
        vault_dir: Optional custom path to Alpha-Vault directory.
        vault_manager: Optional existing VaultManager instance.
        force: If True, overwrite existing configuration without prompting.

    Returns:
        Summary dictionary with execution results and status.
    """
    target_env = Path(env_file_path).resolve() if env_file_path else None
    target_vault = Path(vault_dir).resolve() if vault_dir else None

    # Check existing setup for idempotency
    already_done = is_already_setup(env_path=target_env, vault_dir=target_vault)
    if already_done and not force:
        if not interactive:
            logger.info("Project Alpha is already configured. Idempotent skip.")
            existing_cfg = load_existing_config(env_path=target_env, vault_dir=target_vault)
            return {
                "success": True,
                "already_configured": True,
                "env_updated": False,
                "vault_updated": False,
                "token": existing_cfg.alpha_token,
                "founder": existing_cfg.founder_name,
                "company": existing_cfg.company_name,
                "providers_configured": ["ollama"],
                "written_files": [],
            }
        else:
            # Interactive re-configuration prompt
            existing_cfg = load_existing_config(env_path=target_env, vault_dir=target_vault)
            if HAS_RICH and sys.stdout.isatty():
                console.print(Panel(
                    f"[bold yellow]Project Alpha is already configured for '{existing_cfg.company_name}'.[/]\n"
                    f"Founder: [cyan]{existing_cfg.founder_name}[/]\n"
                    f"Token:   [dim]{(existing_cfg.alpha_token or '')[:12]}...[/]",
                    border_style="yellow",
                    title="[bold yellow]Existing Setup Detected[/]",
                ))
                reconfig = Confirm.ask("Do you want to reconfigure Project Alpha?", default=False)
            else:
                resp = input(
                    f"Project Alpha already configured for '{existing_cfg.company_name}'. Reconfigure? [y/N]: "
                ).strip().lower()
                reconfig = resp in ("y", "yes")

            if not reconfig:
                if HAS_RICH and sys.stdout.isatty():
                    console.print("[green]Setup aborted. Existing configuration preserved.[/]")
                else:
                    print("Setup aborted. Existing configuration preserved.")
                return {
                    "success": True,
                    "already_configured": True,
                    "env_updated": False,
                    "vault_updated": False,
                    "token": existing_cfg.alpha_token,
                    "founder": existing_cfg.founder_name,
                    "company": existing_cfg.company_name,
                    "providers_configured": ["ollama"],
                    "written_files": [],
                }

    try:
        # Determine SetupConfig
        final_cfg: SetupConfig
        if interactive:
            existing = load_existing_config(env_path=target_env, vault_dir=target_vault)
            if config:
                if isinstance(config, SetupConfig):
                    existing = config
                elif isinstance(config, dict):
                    existing = SetupConfig.from_dict(config)
            final_cfg = prompt_interactive_wizard(existing)
        else:
            if isinstance(config, SetupConfig):
                final_cfg = config
            elif isinstance(config, dict):
                final_cfg = SetupConfig.from_dict(config)
            else:
                final_cfg = SetupConfig()

        # Apply configuration
        result = apply_setup(
            config=final_cfg,
            env_path=target_env,
            vault_dir=target_vault,
            vault_manager=vault_manager,
        )

        # Print success panel in interactive mode
        if interactive:
            token_display = result.get("token", "")
            if HAS_RICH and sys.stdout.isatty():
                console.print(Panel(
                    f"[bold green]Project Alpha Setup Successfully Completed![/]\n\n"
                    f"Company:      [cyan]{result['company']}[/]\n"
                    f"Founder:      [cyan]{result['founder']}[/]\n"
                    f"ALPHA_TOKEN:  [bold yellow]{token_display}[/]\n\n"
                    f"[bold white]Next Steps:[/] Run [bold cyan]python alpha.py start[/] to boot desktop backend.",
                    border_style="green",
                    title="[bold green]Success[/]",
                ))
            else:
                print("\n" + "=" * 60)
                print("Project Alpha Setup Successfully Completed!")
                print(f"Company:     {result['company']}")
                print(f"Founder:     {result['founder']}")
                print(f"ALPHA_TOKEN: {token_display}")
                print("Run 'python alpha.py start' to boot desktop backend.")
                print("=" * 60 + "\n")

        return result

    except KeyboardInterrupt:
        if HAS_RICH and sys.stdout.isatty():
            console.print("\n[bold red][Setup cancelled by user. No modifications applied.][/]")
        else:
            print("\n[Setup cancelled by user. No modifications applied.]")
        return {
            "success": False,
            "error": "KeyboardInterrupt: Setup cancelled by user.",
            "already_configured": already_done,
        }
    except Exception as e:
        logger.error("Setup failed: %s", e, exc_info=True)
        if HAS_RICH and sys.stdout.isatty():
            console.print(f"\n[bold red]Error during setup:[/] {e}")
        else:
            print(f"\nError during setup: {e}")
        return {
            "success": False,
            "error": str(e),
            "already_configured": already_done,
        }


# Canonical Alias for programmatic callers
run_first_run_wizard = run_first_run


# ============================================================================
# CLI Entrypoint for Standalone Invocation
# ============================================================================

def main() -> int:
    """CLI entrypoint when run as `python -m backend.setup.first_run`."""
    parser = argparse.ArgumentParser(
        prog="first_run",
        description="Project Alpha First-Run Setup Wizard",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in automated non-interactive mode without stdin prompts",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing configuration without confirmation",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to .env file (default: Alpha/.env)",
    )
    parser.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Path to Alpha-Vault directory (default: Alpha/Alpha-Vault)",
    )
    parser.add_argument("--founder", type=str, default=None, help="Founder Name")
    parser.add_argument("--company", type=str, default=None, help="Company Name")
    parser.add_argument("--industry", type=str, default=None, help="Industry / Domain")
    parser.add_argument("--token", type=str, default=None, help="Custom ALPHA_TOKEN")
    parser.add_argument("--ollama-host", type=str, default=None, help="Ollama Host URL")
    parser.add_argument("--groq-key", type=str, default=None, help="Groq API Key")
    parser.add_argument("--gemini-key", type=str, default=None, help="Gemini API Key")
    parser.add_argument("--anthropic-key", type=str, default=None, help="Anthropic API Key")
    parser.add_argument("--openai-key", type=str, default=None, help="OpenAI API Key")

    args = parser.parse_args()

    cli_config: Dict[str, Any] = {}
    if args.founder:
        cli_config["founder_name"] = args.founder
    if args.company:
        cli_config["company_name"] = args.company
    if args.industry:
        cli_config["industry"] = args.industry
    if args.token:
        cli_config["alpha_token"] = args.token
    if args.ollama_host:
        cli_config["ollama_host"] = args.ollama_host
    if args.groq_key:
        cli_config["groq_api_key"] = args.groq_key
    if args.gemini_key:
        cli_config["gemini_api_key"] = args.gemini_key
    if args.anthropic_key:
        cli_config["anthropic_api_key"] = args.anthropic_key
    if args.openai_key:
        cli_config["openai_api_key"] = args.openai_key

    is_interactive = not args.non-interactive and sys.stdin.isatty()

    res = run_first_run(
        config=cli_config if cli_config else None,
        interactive=is_interactive,
        env_file_path=Path(args.env_file) if args.env_file else None,
        vault_dir=Path(args.vault_dir) if args.vault_dir else None,
        force=args.force,
    )

    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
