"""backend/api/__init__.py - Project Alpha FastAPI Desktop Backend & WebSocket Engine.

Exposes application factory create_app() and core components for Milestone 8.
"""

from backend.api.main import create_app

__all__ = ["create_app"]
