"""backend/api/routes/health.py - Project Alpha System Health & Telemetry Probes."""

from __future__ import annotations

import os
import time
from typing import Any, Dict
from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, Response

from backend.api.schemas import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/download/apk", summary="Download Project Alpha Android APK")
@router.get("/download/alpha.apk", summary="Download Project Alpha Android APK")
def download_apk() -> Response:
    """Direct APK download route for mobile installation."""
    apk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "apk", "release_output", "app-release.apk"))
    if not os.path.exists(apk_path):
        return Response(content="APK not found on host", status_code=404)
    return FileResponse(
        path=apk_path,
        filename="app-release.apk",
        media_type="application/vnd.android.package-archive"
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Unauthenticated system health probe",
)
@router.get(
    "/api/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Unauthenticated API health probe",
)
def health_check(request: Request) -> Dict[str, Any]:
    """System health probe checking Vault, Agent Registry, Model Router, and Uptime."""
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime = max(0.0, round(time.time() - start_time, 2))

    vm = getattr(request.app.state, "vault_manager", None)
    ar = getattr(request.app.state, "agent_registry", None)
    mr = getattr(request.app.state, "model_router", None)
    orch = getattr(request.app.state, "orchestrator", None)

    subsystems: Dict[str, str] = {
        "vault": "healthy" if vm is not None else "degraded",
        "agents": "healthy" if ar is not None else "degraded",
        "model_router": "healthy" if mr is not None else "degraded",
        "orchestrator": "healthy" if orch is not None else "degraded",
    }

    active_agents = len(ar.list_agents()) if (ar and hasattr(ar, "list_agents")) else 13
    active_projects = len(getattr(orch, "_active_projects", {})) if orch else 0

    return {
        "status": "healthy" if all(v == "healthy" for v in subsystems.values()) else "degraded",
        "version": "1.0.0",
        "uptime_seconds": uptime,
        "subsystems": subsystems,
        "system": {
            "agents_count": active_agents,
            "active_projects": active_projects,
        },
    }
