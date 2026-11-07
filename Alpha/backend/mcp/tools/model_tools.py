"""backend/mcp/tools/model_tools.py - Alpha MCP Model Routing Tool Handler.

Implements MCP tool for cost-aware and complexity-based model routing:
- model_route: Resolve the optimal AI model for a task based on complexity tier,
  enforcing CAO agent overrides and zero-cost-first optimization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.model_router.router import ModelRouter

logger = logging.getLogger("alpha.mcp.tools.model")


# ============================================================================
# Pydantic Input Schemas
# ============================================================================

class ModelRouteInput(BaseModel):
    """Input schema for model_route MCP tool."""
    model_config = ConfigDict(extra="ignore")

    task_type: str = Field(..., description="Task classification, e.g. 'technical_spec', 'draft_copy', 'audit'")
    complexity: int = Field(..., ge=1, le=5, description="Complexity tier rating from 1 (simple) to 5 (advanced)")
    agent_id: str = Field(..., description="Calling agent ID (e.g. 'CEO', 'CTO', 'CAO-Claude')")
    prefer_free: bool = Field(default=True, description="Prioritize free and local Ollama tiers when feasible")

    @field_validator("task_type", "agent_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


# ============================================================================
# Tool Handlers
# ============================================================================

def model_route(
    task_type: str,
    complexity: int,
    agent_id: str,
    prefer_free: bool = True,
    model_router: Optional[ModelRouter] = None,
) -> Dict[str, Any]:
    """Get the recommended AI model for a task based on complexity, task type, and calling agent.

    Enforces:
    1. Mandatory CAO overrides (CAO-Claude -> Claude 3.5 Sonnet, CAO-ChatGPT -> GPT-4o).
    2. Zero-cost-first tier routing (Tiers 1-4 free: Ollama, Groq, Gemini).
    3. Tier 5 premium routing for high-complexity architecture or legal tasks.

    Args:
        task_type: Functional task type (e.g. 'architecture_design', 'draft_copy').
        complexity: Difficulty rating (1 to 5).
        agent_id: Requesting agent ID.
        prefer_free: Flag prioritizing free tiers.
        model_router: Optional ModelRouter instance.

    Returns:
        Structured response dictionary containing model routing decision.
    """
    clean_task = task_type.strip()
    clean_agent = agent_id.strip()

    try:
        raw_comp = int(complexity)
        if raw_comp < 1 or raw_comp > 5:
            raise ValueError(f"complexity must be between 1 and 5, got {complexity}")
    except (TypeError, ValueError) as ve:
        raise ValueError(f"complexity must be between 1 and 5, got {complexity}") from ve

    # Inviolable CAO Audit Gate Override Rules
    if clean_agent in ("CAO", "CAO-C", "CAO-Claude"):
        return {
            "success": True,
            "agent_id": clean_agent,
            "task_type": clean_task,
            "complexity": raw_comp,
            "recommended_model": "claude-3-5-sonnet",
            "model": "claude-3-5-sonnet",
            "provider": "anthropic",
            "tier": 5,
            "is_free": False,
            "model_string": "anthropic/claude-3-5-sonnet",
            "context_window": 200000,
            "cost_per_m": {"input_usd": 3.0, "output_usd": 15.0},
            "message": "Enforced Tier 5 Claude 3.5 Sonnet for CAO-Claude audit gate.",
        }
    elif clean_agent in ("CAO-G", "CAO-ChatGPT"):
        return {
            "success": True,
            "agent_id": clean_agent,
            "task_type": clean_task,
            "complexity": raw_comp,
            "recommended_model": "gpt-4o",
            "model": "gpt-4o",
            "provider": "openai",
            "tier": 5,
            "is_free": False,
            "model_string": "openai/gpt-4o",
            "context_window": 128000,
            "cost_per_m": {"input_usd": 2.5, "output_usd": 10.0},
            "message": "Enforced Tier 5 GPT-4o for CAO-ChatGPT audit gate.",
        }

    try:
        mr = model_router or ModelRouter()
        try:
            config = mr.route(
                task_type=clean_task,
                complexity=raw_comp,
                agent_id=clean_agent,
                prefer_free=prefer_free,
            )
        except TypeError:
            config = mr.route(
                task_type=clean_task,
                complexity=raw_comp,
                agent_role=clean_agent,
            )

        return {
            "success": True,
            "task_type": clean_task,
            "complexity": raw_comp,
            "agent_id": clean_agent,
            "prefer_free": prefer_free,
            "recommended_model": config.model,
            "model": config.model,
            "provider": config.provider,
            "tier": config.tier,
            "is_free": config.is_free,
            "model_string": f"{config.provider}/{config.model}",
            "context_window": getattr(config, "context_window", 8192),
            "cost_per_m": {
                "input_usd": getattr(config, "cost_per_m_in", 0.0),
                "output_usd": getattr(config, "cost_per_m_out", 0.0),
            },
            "message": f"Routed '{clean_task}' (complexity {raw_comp}) to {config.provider}/{config.model} (Tier {config.tier}).",
        }
    except Exception as e:
        logger.error("Unexpected error in model_route: %s", e, exc_info=True)
        return {
            "success": False,
            "task_type": task_type,
            "agent_id": agent_id,
            "error": f"Internal error during model_route: {str(e)}",
        }
