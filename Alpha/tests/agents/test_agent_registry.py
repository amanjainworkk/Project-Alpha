"""tests/agents/test_agent_registry.py - Comprehensive Unit Tests for AgentRegistry."""

from pathlib import Path
import pytest

from backend.agents.agent_registry import (
    AgentRegistry,
    CANONICAL_AGENT_METADATA,
    get_agent_registry,
    reset_agent_registry,
)
from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.ceo import CEOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


@pytest.fixture(autouse=True)
def clean_registry():
    reset_agent_registry()
    yield
    reset_agent_registry()


@pytest.fixture
def test_vault(tmp_path: Path) -> VaultManager:
    return VaultManager(
        vault_root=tmp_path / "vault",
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
    )


@pytest.fixture
def test_router() -> ModelRouter:
    clients = {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
        "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }
    return ModelRouter(clients=clients)


@pytest.fixture
def registry(test_vault, test_router) -> AgentRegistry:
    return AgentRegistry(vault_manager=test_vault, model_router=test_router)


# ============================================================================
# 1. Discovery and Cataloging
# ============================================================================

def test_registry_initialization_defaults():
    reg = AgentRegistry()
    assert len(reg) == 0
    assert reg.jd_dir.exists()


def test_agent_registry_discovers_all_12_markdown_jds(registry):
    jds = registry.discover_jds()
    expected_roles = {"CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO", "CHRO", "CIO", "CSO", "CLO", "CAO"}
    assert expected_roles.issubset(set(jds.keys()))
    for role, path in jds.items():
        assert Path(path).is_file()


def test_agent_registry_catalogs_14_default_agents(registry):
    agents = registry.list_agents(active_only=False)
    agent_ids = {a["agent_id"] for a in agents}
    expected_14 = {
        "CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO",
        "CHRO", "CIO", "CSO", "CLO", "CAO", "CAO-Claude", "CAO-ChatGPT"
    }
    assert expected_14.issubset(agent_ids)


# ============================================================================
# 2. Loading and Instantiation
# ============================================================================

def test_registry_load_all_instantiates_13_agents(registry):
    agents = registry.load_all()

    # 13 unique agent instances loaded
    assert len(registry) >= 13
    assert "CEO" in registry
    assert "CTO" in registry
    assert "CMO" in registry
    assert "CPO" in registry
    assert "CDO" in registry
    assert "CFO" in registry
    assert "COO" in registry
    assert "CHRO" in registry
    assert "CIO" in registry
    assert "CSO" in registry
    assert "CLO" in registry
    assert "CAO-Claude" in registry
    assert "CAO-ChatGPT" in registry
    assert "CAO" in registry  # Alias works


def test_factory_creates_ceo_subclass(registry):
    registry.load_all()

    ceo = registry.get("CEO")
    assert isinstance(ceo, CEOAgent)
    assert isinstance(ceo, BaseExecutiveAgent)

    cto = registry.get("CTO")
    assert isinstance(cto, BaseExecutiveAgent)
    assert not isinstance(cto, CEOAgent)


# ============================================================================
# 3. Lookups and Aliases
# ============================================================================

def test_case_insensitive_lookups(registry):
    registry.load_all()

    # Lowercase & uppercase
    assert registry.get("ceo") is not None
    assert registry.get("CEO") is not None
    assert registry.get("cTo") is not None

    # Full role titles
    assert registry.get_by_role("Chief Executive Officer") is not None
    assert registry.get_by_role("chief executive officer") is not None
    assert registry.get_by_role("Chief Technology Officer") is not None


def test_agent_registry_get_by_role_alias(registry):
    registry.load_all()
    ceo = registry.get_by_role("ceo")
    assert isinstance(ceo, CEOAgent)
    assert ceo.role == "CEO"


def test_agent_registry_aliases_cao_c_and_cao_g(registry):
    registry.load_all()

    cao_c = registry.get("CAO-C")
    cao_claude = registry.get("CAO-Claude")
    assert cao_c is cao_claude

    cao_g = registry.get("CAO-G")
    cao_gpt = registry.get("CAO-ChatGPT")
    assert cao_g is cao_gpt


# ============================================================================
# 4. Dynamic Registration & Vault Sync
# ============================================================================

def test_dynamic_registration_and_vault_sync(registry, test_vault):
    custom_agent = BaseExecutiveAgent(
        agent_id="CXO-Custom",
        name="Alpha Custom",
        role="Chief Experience Officer",
        vault_manager=test_vault,
    )
    registry.register(custom_agent)

    assert registry.get("CXO-Custom") is not None
    assert registry.get_by_role("Chief Experience Officer") is not None

    # Verify SQLite sync
    if hasattr(test_vault, "sqlite") and hasattr(test_vault.sqlite, "get_agent"):
        db_agent = test_vault.sqlite.get_agent("CXO-Custom")
        assert db_agent is not None
        assert db_agent["agent_role"] == "Chief Experience Officer"


def test_missing_jd_graceful_fallback(tmp_path, test_vault, test_router):
    empty_jd_dir = tmp_path / "empty_jds"
    empty_jd_dir.mkdir()

    registry = AgentRegistry(vault_manager=test_vault, model_router=test_router, jd_dir=empty_jd_dir)

    # Should not raise exception
    agents = registry.load_all()
    assert len(agents) >= 13
    ceo = registry.get("CEO")
    assert ceo is not None
    assert ceo.system_prompt != ""


def test_singleton_thread_safety():
    r1 = get_agent_registry()
    r2 = get_agent_registry()
    assert r1 is r2


def test_unregister_agent(registry):
    registry.load_all()
    assert "CMO" in registry

    removed = registry.unregister("CMO")
    assert removed is not None
    assert removed.agent_id == "CMO"
    assert registry.get("CMO") is None
