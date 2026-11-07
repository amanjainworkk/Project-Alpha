"""backend/api/auth.py - Local Token Authentication Subsystem for Project Alpha.

Verifies ALPHA_TOKEN for REST endpoints and WebSocket handshakes.
Provides constant-time token comparison, header-based REST authentication,
WebSocket query parameter authentication, and dev test integration.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("alpha.api.auth")

DEFAULT_DEV_TOKEN = "test_alpha_bearer_token_secret_xyz789"
security_scheme = HTTPBearer(auto_error=False)


def get_expected_token(request: Optional[Request] = None) -> str:
    """Resolve expected authentication token from app state, environment, or default fallback."""
    if request is not None and hasattr(request.app.state, "auth_token") and request.app.state.auth_token:
        return str(request.app.state.auth_token)
    return os.environ.get("ALPHA_TOKEN", DEFAULT_DEV_TOKEN)


def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> str:
    """Verify Bearer token from Authorization header (or X-Alpha-Token header)."""
    if os.environ.get("ALPHA_AUTH_DISABLED") == "1":
        return "auth_disabled"

    token: Optional[str] = None

    if credentials is not None:
        # RFC 6750 Case-Sensitivity: Scheme MUST be exact 'Bearer'
        if credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = credentials.credentials
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # Check Authorization header if HTTPBearer did not parse it
        raw_auth = request.headers.get("authorization")
        if raw_auth:
            parts = raw_auth.strip().split(" ", 1)
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Custom header fallback (e.g. X-Alpha-Token)
            # Query parameter fallback removed for REST endpoints to prevent credential leakage (OWASP API3:2023)
            x_token = request.headers.get("x-alpha-token")
            if x_token:
                token = x_token

    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected = get_expected_token(request)
    if not secrets.compare_digest(token.strip(), expected.strip()):
        logger.warning("Authentication failure: provided token does not match ALPHA_TOKEN.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def verify_ws_token(websocket: WebSocket) -> bool:
    """Validate token during WebSocket handshake via query param or Authorization header."""
    if os.environ.get("ALPHA_AUTH_DISABLED") == "1":
        return True

    expected = os.environ.get("ALPHA_TOKEN", DEFAULT_DEV_TOKEN)
    if hasattr(websocket.app.state, "auth_token") and websocket.app.state.auth_token:
        expected = str(websocket.app.state.auth_token)

    # 1. Query parameter (permitted for WebSocket handshakes due to browser API constraints)
    token = websocket.query_params.get("token")

    # 2. Header fallback
    if not token:
        raw_auth = websocket.headers.get("authorization") or websocket.headers.get("sec-websocket-protocol")
        if raw_auth:
            parts = raw_auth.strip().split(" ")
            token = parts[1] if len(parts) == 2 and parts[0] == "Bearer" else parts[0]

    if not token or not secrets.compare_digest(token.strip(), expected.strip()):
        logger.warning("WebSocket authentication failed. Closing connection with code 1008.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: Invalid token")
        return False

    return True
