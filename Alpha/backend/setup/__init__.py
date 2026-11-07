"""backend/setup/__init__.py - Project Alpha Vault & System Initialization Package.

Milestone 9: CLI Entrypoint & Vault Initializer.
"""

from backend.setup.vault_init import (
    DEFAULT_EXECUTIVE_ROSTER,
    initialize_vault,
    bootstrap_directory_tree,
    bootstrap_sqlite_database,
    bootstrap_chroma_collections,
    seed_company_files,
    seed_agent_registry,
)
from backend.setup.first_run import (
    SetupConfig,
    run_first_run,
    run_first_run_wizard,
    apply_setup,
    generate_secure_token,
    is_already_setup,
    load_existing_config,
    parse_env_file,
    update_env_file,
)

__all__ = [
    "DEFAULT_EXECUTIVE_ROSTER",
    "initialize_vault",
    "bootstrap_directory_tree",
    "bootstrap_sqlite_database",
    "bootstrap_chroma_collections",
    "seed_company_files",
    "seed_agent_registry",
    "SetupConfig",
    "run_first_run",
    "run_first_run_wizard",
    "apply_setup",
    "generate_secure_token",
    "is_already_setup",
    "load_existing_config",
    "parse_env_file",
    "update_env_file",
]
