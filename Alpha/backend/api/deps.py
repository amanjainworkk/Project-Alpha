"""backend/api/deps.py - FastAPI Dependency Providers for Subsystem Injection.

Supports production dependency resolution from app.state as well as
isolated mock overrides via app.dependency_overrides in test suites.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import Request

from backend.agents.agent_registry import AgentRegistry
from backend.model_router.router import ModelRouter
from backend.orchestrator.orchestrator import AlphaOrchestrator
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.api.deps")


def get_vault_manager(request: Request) -> VaultManager:
    """Dependency provider returning active VaultManager instance."""
    vm = getattr(request.app.state, "vault_manager", None)
    if vm is not None:
        return vm
    return VaultManager()


def get_agent_registry(request: Request) -> Any:
    """Dependency provider returning active AgentRegistry instance."""
    ar = getattr(request.app.state, "agent_registry", None)
    if ar is not None:
        return ar
    vm = get_vault_manager(request)
    mr = get_model_router(request)
    try:
        reg = AgentRegistry(vault_manager=vm, model_router=mr)
        reg.load_all()
        return reg
    except Exception as e:
        logger.debug("AgentRegistry dependency fallback notice: %s", e)
        return None


def get_orchestrator(request: Request) -> Any:
    """Dependency provider returning active AlphaOrchestrator instance."""
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        return orch
    vm = get_vault_manager(request)
    mr = get_model_router(request)
    ar = get_agent_registry(request)
    try:
        return AlphaOrchestrator(vault_manager=vm, agent_registry=ar, model_router=mr)
    except Exception as e:
        logger.debug("AlphaOrchestrator dependency fallback notice: %s", e)
        return None


def get_model_router(request: Request) -> ModelRouter:
    """Dependency provider returning active ModelRouter instance."""
    mr = getattr(request.app.state, "model_router", None)
    if mr is not None:
        return mr
    return ModelRouter()


def get_connection_manager(request: Request) -> Any:
    """Dependency provider returning active WebSocket ConnectionManager instance."""
    return getattr(request.app.state, "connection_manager", None)
