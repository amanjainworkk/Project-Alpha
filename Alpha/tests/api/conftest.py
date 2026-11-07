"""tests/api/conftest.py - Shared Pytest Fixtures for FastAPI & WebSocket Test Suite.

Compatible with Starlette TestClient, httpx.AsyncClient, and Alpha's master conftest.py.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from tests.conftest import (
    TEST_TOKEN,
    ContractAPIClient,
    ContractArchifyEngine,
    ContractDualCAO,
    ContractMCPClient,
    ContractModelRouter,
    ContractVaultManager,
)

from backend.api.main import create_app
from backend.api.websocket import ConnectionManager


@pytest.fixture
def test_token() -> str:
    """Canonical test bearer token."""
    return TEST_TOKEN


@pytest.fixture
def auth_headers(test_token: str) -> Dict[str, str]:
    """Standard Bearer authentication headers for REST testing."""
    return {"Authorization": f"Bearer {test_token}"}


@pytest.fixture
def temp_api_vault_dir() -> Generator[Path, None, None]:
    """Provide isolated temporary directory for Vault tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_api_vault_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def api_vault(temp_api_vault_dir: Path) -> ContractVaultManager:
    """Isolated contract vault manager for API testing."""
    return ContractVaultManager(str(temp_api_vault_dir))


@pytest.fixture
def api_router() -> ContractModelRouter:
    """Deterministic model router for API testing."""
    return ContractModelRouter()


@pytest.fixture
def api_cao() -> ContractDualCAO:
    """Dual CAO audit gate for API testing."""
    return ContractDualCAO()


@pytest.fixture
def connection_manager(test_token: str):
    """Isolated WebSocket ConnectionManager."""
    return ConnectionManager(auth_token=test_token)


@pytest.fixture
def app(
    api_vault: ContractVaultManager,
    api_router: ContractModelRouter,
    connection_manager: Any,
    test_token: str,
) -> FastAPI:
    """Construct fully configured FastAPI application with test fixtures."""
    os.environ["ALPHA_TOKEN"] = test_token
    return create_app(
        vault_manager=api_vault,
        model_router=api_router,
        token=test_token,
        connection_manager=connection_manager,
    )


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Synchronous FastAPI TestClient with WebSocket support."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Asynchronous HTTPX client with ASGI in-memory transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
