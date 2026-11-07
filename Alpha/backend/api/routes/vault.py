"""backend/api/routes/vault.py - Project Alpha Vault Document Access & Semantic Search REST Handlers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.auth import verify_token
from backend.api.deps import get_vault_manager
from backend.api.schemas import VaultWriteRequest, VaultWriteResponse
from backend.vault.vault_manager import AccessDeniedError, VaultManager

logger = logging.getLogger("alpha.api.routes.vault")
router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get(
    "/read",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Read structured JSON document from Alpha's Vault",
)
def read_vault_document(
    path: str = Query("", description="Vault document path (e.g. 'company/identity')"),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Read document from SQLite KV or filesystem. Defends against traversal and returns raw JSON payload."""
    clean_path = path.strip() if path else ""
    if not clean_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty path is not allowed.",
        )

    if ".." in clean_path or "\x00" in clean_path or "\0" in clean_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal or null bytes detected in path.",
        )

    try:
        content = vault_manager.read(clean_path)
    except AccessDeniedError as ade:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ade))

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault key '{clean_path}' not found.",
        )

    return content


@router.post(
    "/write",
    response_model=VaultWriteResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Write document to Vault with RBAC agent checks",
)
def write_vault_document(
    request: VaultWriteRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> Dict[str, Any]:
    """Persist structured document with schema validation and RBAC checks."""
    clean_path = request.path.strip()
    clean_agent = request.agent_id.strip() if request.agent_id else None

    if not clean_path or ".." in clean_path or "\x00" in clean_path or "\0" in clean_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal or null bytes detected in path.",
        )

    # Enforce CAO RBAC confinement: CAO agents are strictly confined to audit paths
    if clean_agent and "CAO" in clean_agent.upper() and "audit" not in clean_path.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: CAO agent '{clean_agent}' is strictly confined to audit deliverables in projects/{{id}}/audit/",
        )

    try:
        success = vault_manager.write(
            path=clean_path,
            data=request.data,
            agent_id=clean_agent,
        )
    except (AccessDeniedError, PermissionError) as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to persist document to '{clean_path}'.",
        )

    return {
        "path": clean_path,
        "success": True,
        "message": f"Document '{clean_path}' saved successfully.",
    }


@router.get(
    "/search",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_token)],
    summary="Hybrid semantic search across Vault collections",
)
def search_vault(
    query: str = Query("", description="Semantic or keyword query text"),
    top_k: int = Query(5, ge=1, le=50, description="Max search results"),
    path_prefix: Optional[str] = Query(None, description="Optional path prefix filter"),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> List[Dict[str, Any]]:
    """Perform semantic vector retrieval across knowledge, deliverables, and agent memory collections."""
    clean_query = query.strip() if query else ""
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    results = vault_manager.search(
        query=clean_query,
        n_results=top_k,
        path_prefix=path_prefix.strip() if path_prefix else None,
    )
    return results
