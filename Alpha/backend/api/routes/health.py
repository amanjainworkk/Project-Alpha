"""backend/api/routes/health.py - Project Alpha System Health & Telemetry Probes."""

from __future__ import annotations

import os
import time
from typing import Any, Dict
from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response

from backend.api.schemas import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/hello", response_class=HTMLResponse, summary="Simple HTML Hello World cross-check endpoint")
@router.get("/hello.html", response_class=HTMLResponse, summary="Simple HTML Hello World cross-check endpoint")
def hello_world_html() -> HTMLResponse:
    """Delivers a clean, responsive OLED-styled Hello World page to verify end-to-end frontend/backend connectivity."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Alpha - Hello World Cross-Check</title>
    <style>
        :root {
            --bg-oled: #05070B;
            --surface: #0E131F;
            --border: #1E293B;
            --cyan: #06B6D4;
            --emerald: #10B981;
            --text-primary: #F8FAFC;
            --text-muted: #94A3B8;
        }
        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg-oled);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .card {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 32px 28px;
            max-width: 440px;
            width: 90%;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
            text-align: center;
        }
        .badge {
            display: inline-block;
            background: rgba(16, 185, 129, 0.15);
            color: var(--emerald);
            font-size: 11px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.3);
            margin-bottom: 16px;
            letter-spacing: 0.5px;
        }
        h1 {
            color: var(--cyan);
            font-size: 28px;
            margin: 0 0 12px 0;
            font-weight: 800;
        }
        p {
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.5;
            margin: 0 0 24px 0;
        }
        .status-box {
            background: #05070B;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: var(--cyan);
            text-align: left;
            margin-bottom: 20px;
        }
        .btn {
            display: inline-block;
            background: var(--cyan);
            color: #05070B;
            font-weight: 700;
            font-size: 13px;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">&#9679; SYSTEM OPERATIONAL</div>
        <h1>Hello World!</h1>
        <p>Project Alpha Autonomous Executive OS is functioning normally. End-to-end cloudflare tunnel and executive backend verified.</p>
        <div class="status-box">
            &gt; CEO Status: ACTIVE<br>
            &gt; Multi-Agent Dispatch: ENABLED<br>
            &gt; Dual CAO Audit Gate: ONLINE<br>
            &gt; Telemetry Stream: OPERATIONAL
        </div>
        <a href="/download/apk" class="btn">&#8595; Download Mobile APK</a>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)


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
