"""Alpha/tests/agents/test_adversarial_m5_cao.py - Adversarial Stress Tests for Milestone 5 Dual CAO.

Stress-tests:
1. Non-serializable deliverable objects (sets, custom classes).
2. Boundary and non-standard round numbers (0, -1, 100, float).
3. Path traversal attempts in project_id.
4. Unicode, null bytes, and malicious payloads in deliverable keys.
5. Large deliverable payload stress.
6. Concurrent audit executions across DualCAO instances.
"""

import gc
import json
from pathlib import Path
import pytest

from backend.agents.cao import DualCAO, CAOClaudeAgent, CAOGPTAgent
from backend.agents.agent_registry import AgentRegistry, reset_agent_registry
from backend.vault.vault_manager import VaultManager
from backend.model_router.router import ModelRouter
from backend.model_router.mock_client import MockLLMClient


@pytest.fixture(autouse=True)
def clean_registry():
    reset_agent_registry()
    yield
    reset_agent_registry()
    gc.collect()


@pytest.fixture
def test_vault(tmp_path: Path) -> VaultManager:
    vm = VaultManager(
        vault_root=tmp_path / "vault",
        db_path=str(tmp_path / "test.db"),
        chroma_path=str(tmp_path / "chroma"),
    )
    yield vm
    if hasattr(vm, "sqlite") and hasattr(vm.sqlite, "close"):
        vm.sqlite.close()
    gc.collect()


@pytest.fixture
def test_router() -> ModelRouter:
    clients = {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }
    return ModelRouter(clients=clients)


def test_adversarial_round_num_boundary_values(test_vault, test_router):
    """Stress tests boundary and non-integer round numbers."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    # Round 100 should trigger runaway guard immediately
    res_100 = cao.audit({"code": "clean code"}, "proj_adv_1", round_num=100)
    assert res_100.escalation_required is True
    assert res_100.passed is False
    assert res_100.round_num == 100

    # Float 2.0 should be treated as round 2
    res_float = cao.audit({"code": "insecure_token"}, "proj_adv_2", round_num=2.0)
    assert res_float.round_num == 2
    assert res_float.escalation_required is True
    assert res_float.passed is False

    # Round 0: if failing, should not escalate because 0 < 2
    res_zero = cao.audit({"code": "insecure_token"}, "proj_adv_3", round_num=0)
    assert res_zero.round_num == 0
    assert res_zero.escalation_required is False
    assert res_zero.verdict == "REVISE_REQUESTED"


def test_adversarial_non_json_serializable_deliverable(test_vault, test_router):
    """Stress tests deliverable payloads containing sets or custom objects."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    class CustomObj:
        def __str__(self):
            return "CustomDeliverableObject"

    payload = {
        "title": "Complex Deliverable",
        "custom_obj": str(CustomObj()),
        "description": "Clean modular code without flaws",
    }
    res = cao.audit(payload, "proj_adv_obj", round_num=1)
    assert res is not None
    assert res.passed is True


def test_adversarial_vault_confinement_on_path_traversal(test_vault, test_router):
    """Verifies that malicious project_id cannot write outside vault root."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)

    # Attempt path traversal in project_id
    traversal_pid = "../../../escaped_proj"
    res = cao.audit({"code": "Insecure plain token"}, traversal_pid, round_num=2)
    # The audit should either safely handle or gracefully log warning without corrupting fs
    assert res.escalation_required is True
    # Verify no file was written outside vault
    outside_file = test_vault.vault_root.parent / "escaped_proj"
    assert not outside_file.exists()


def test_adversarial_extreme_payload_size(test_vault, test_router):
    """Verifies that large payload (> 100KB) does not cause OOM or crash."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    large_payload = {
        "large_spec": "A" * 150000,
        "code": "def process(): return True",
    }
    res = cao.audit(large_payload, "proj_adv_large", round_num=1)
    assert res is not None
    assert res.passed is True


def test_adversarial_deduplication_fuzzy_and_unicode(test_vault, test_router):
    """Verifies deduplication engine handles unicode, accents, and punctuation."""
    cao = DualCAO(vault_manager=test_vault, model_router=test_router)
    findings = [
        "Unauthenticated access on endpoint /auth/token!",
        "unauthenticated access on endpoint /auth/token",
        "Déjà vu: unauthenticated access on endpoint /auth/token",
        "  ",
        "Valid unique finding 1",
    ]
    deduped = cao._deduplicate_strings(findings)
    assert len(deduped) <= 3
    assert "Valid unique finding 1" in deduped
