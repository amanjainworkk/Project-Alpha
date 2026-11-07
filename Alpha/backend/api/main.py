"""backend/api/main.py - Project Alpha FastAPI ASGI Desktop Backend Server.

Features:
- Application factory: create_app(...)
- Modern lifespan asynccontextmanager lifecycle
- Permissive CORS for Flutter Mobile LAN client
- Comprehensive exception handlers with standardized JSON envelopes
- Route mounting for goals, projects, agents, vault, health, and websockets
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agents.agent_registry import AgentRegistry
from backend.api.deps import (
    get_agent_registry,
    get_connection_manager,
    get_model_router,
    get_orchestrator,
    get_vault_manager,
)
from backend.api.routes.agents import router as agents_router
from backend.api.routes.goals import router as goals_router
from backend.api.routes.health import router as health_router
from backend.api.routes.projects import router as projects_router
from backend.api.routes.vault import router as vault_router
from backend.api.websocket import ConnectionManager
from backend.api.websocket import router as ws_router
from backend.model_router.router import ModelRouter
from backend.orchestrator.orchestrator import AlphaOrchestrator
from backend.vault.vault_manager import AccessDeniedError, VaultManager

logger = logging.getLogger("alpha.api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager initializing and cleaning up Alpha subsystems."""
    logger.info("Initializing Project Alpha FastAPI Backend...")

    # 1. VaultManager initialization
    if getattr(app.state, "vault_manager", None) is None:
        try:
            app.state.vault_manager = VaultManager()
        except Exception as e:
            logger.warning("VaultManager startup initialization notice: %s", e)

    # 2. ModelRouter initialization
    if getattr(app.state, "model_router", None) is None:
        try:
            app.state.model_router = ModelRouter()
        except Exception as e:
            logger.warning("ModelRouter startup initialization notice: %s", e)

    # 3. AgentRegistry initialization & directory load
    if getattr(app.state, "agent_registry", None) is None:
        try:
            app.state.agent_registry = AgentRegistry(
                vault_manager=app.state.vault_manager,
                model_router=app.state.model_router,
            )
            app.state.agent_registry.load_all()
        except Exception as e:
            logger.warning("AgentRegistry startup initialization notice: %s", e)

    # 4. Master Orchestrator initialization
    if getattr(app.state, "orchestrator", None) is None:
        try:
            app.state.orchestrator = AlphaOrchestrator(
                vault_manager=app.state.vault_manager,
                agent_registry=app.state.agent_registry,
                model_router=app.state.model_router,
            )
        except Exception as e:
            logger.warning("AlphaOrchestrator startup initialization notice: %s", e)

    # 5. WebSocket ConnectionManager initialization
    if getattr(app.state, "connection_manager", None) is None:
        try:
            app.state.connection_manager = ConnectionManager(
                auth_token=getattr(app.state, "auth_token", None) or os.environ.get("ALPHA_TOKEN")
            )
            if app.state.orchestrator:
                app.state.connection_manager.attach_orchestrator(app.state.orchestrator)
        except Exception as e:
            logger.warning("ConnectionManager startup notice: %s", e)
            app.state.connection_manager = None

    if not hasattr(app.state, "start_time"):
        app.state.start_time = time.time()

    logger.info("Project Alpha Backend Subsystems initialized successfully.")
    yield

    # Clean shutdown
    logger.info("Shutting down Project Alpha FastAPI Backend...")
    vm = getattr(app.state, "vault_manager", None)
    if vm is not None and hasattr(vm, "close"):
        try:
            vm.close()
        except Exception as e:
            logger.debug("VaultManager close notice: %s", e)


def create_app(
    vault_manager: Optional[VaultManager] = None,
    agent_registry: Optional[AgentRegistry] = None,
    orchestrator: Optional[AlphaOrchestrator] = None,
    model_router: Optional[ModelRouter] = None,
    token: Optional[str] = None,
    connection_manager: Optional[Any] = None,
) -> FastAPI:
    """Create and configure the FastAPI desktop backend application."""
    app = FastAPI(
        title="Project Alpha Desktop Backend",
        description="Autonomous AI Executive Operating System REST & WebSocket API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Attach subsystem state
    app.state.vault_manager = vault_manager
    app.state.agent_registry = agent_registry
    app.state.orchestrator = orchestrator
    app.state.model_router = model_router
    app.state.auth_token = token or os.environ.get("ALPHA_TOKEN", "test_alpha_bearer_token_secret_xyz789")
    app.state.connection_manager = connection_manager
    app.state.start_time = time.time()

    # Pre-register dependency overrides for test isolation if mocks provided
    if vault_manager is not None:
        app.dependency_overrides[get_vault_manager] = lambda: vault_manager
    if agent_registry is not None:
        app.dependency_overrides[get_agent_registry] = lambda: agent_registry
    if orchestrator is not None:
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    if model_router is not None:
        app.dependency_overrides[get_model_router] = lambda: model_router
    if connection_manager is not None:
        app.dependency_overrides[get_connection_manager] = lambda: connection_manager

    # ------------------------------------------------------------------------
    # CORS Middleware (Local Flutter Mobile & Web Client)
    # ------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------------
    # Standardized Exception Handlers
    # ------------------------------------------------------------------------

    @app.exception_handler(AccessDeniedError)
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.warning("Permission/RBAC error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Forbidden",
                "code": status.HTTP_403_FORBIDDEN,
                "detail": str(exc),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("Bad Request on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Bad Request",
                "code": status.HTTP_400_BAD_REQUEST,
                "detail": str(exc),
            },
        )

    @app.exception_handler(FileNotFoundError)
    @app.exception_handler(KeyError)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "Not Found",
                "code": status.HTTP_404_NOT_FOUND,
                "detail": str(exc) if str(exc) else "Requested resource not found",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation Error",
                "code": 422,
                "detail": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        content = {
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "code": exc.status_code,
            "detail": exc.detail,
        }
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "detail": str(exc),
            },
        )

    # ------------------------------------------------------------------------
    # Router Mounts
    # ------------------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(goals_router)
    app.include_router(projects_router)
    app.include_router(agents_router)
    app.include_router(vault_router)
    app.include_router(ws_router)

    return app


# Default ASGI application instance
app = create_app()
