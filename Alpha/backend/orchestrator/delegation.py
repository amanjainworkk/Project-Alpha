"""backend/orchestrator/delegation.py - Project Alpha Delegation Engine.

Executes CEO workstream delegations, runs independent tasks concurrently in
parallel thread workers, monitors status, captures deliverables, and safely handles agent failures.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.agents.agent_registry import AgentRegistry
from backend.agents.base_agent import BaseExecutiveAgent
from backend.orchestrator.goal_parser import WorkstreamTask
from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.schemas import ThreadMessageType
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.orchestrator.delegation")


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskExecutionResult(BaseModel):
    """Execution telemetry and output deliverable from an assigned agent."""
    model_config = ConfigDict(extra="ignore")

    task_id: str
    project_id: str
    agent_id: str
    status: TaskStatus
    deliverable: Optional[Any] = None
    deliverable_path: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    retry_count: int = 0


class DelegationEngine:
    """CEO Executive Dispatch & Parallel Workstream Concurrency Engine."""

    def __init__(
        self,
        agent_registry: Optional[AgentRegistry] = None,
        thread_manager: Optional[ThreadManager] = None,
        vault_manager: Optional[VaultManager] = None,
        max_workers: int = 4,
        task_timeout_seconds: float = 180.0,
    ) -> None:
        self.vault_manager = vault_manager
        self.registry = agent_registry or AgentRegistry(vault_manager=vault_manager)
        if hasattr(self.registry, "load_all") and not self.registry.get("CEO"):
            self.registry.load_all()
        self.thread_manager = thread_manager
        self.max_workers = max_workers
        self.task_timeout_seconds = task_timeout_seconds

        self._task_results: Dict[str, TaskExecutionResult] = {}
        self._progress_listeners: List[Callable[[Dict[str, Any]], Any]] = []

    def register_progress_listener(self, listener: Callable[[Dict[str, Any]], Any]) -> None:
        """Register a callback for granular progress updates (e.g. for Flutter APK)."""
        self._progress_listeners.append(listener)

    def _emit_progress(self, task_id: str, project_id: str, agent_id: str, percent: int, step: str, status: TaskStatus) -> None:
        payload = {
            "event": "TASK_PROGRESS_UPDATED",
            "task_id": task_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "progress_percent": percent,
            "current_step": step,
            "status": status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for l in self._progress_listeners:
            try:
                l(payload)
            except Exception as e:
                logger.debug("Progress listener error: %s", e)

    # ------------------------------------------------------------------------
    # 1. Single Task Dispatch
    # ------------------------------------------------------------------------

    def dispatch_task(
        self,
        task: Union[WorkstreamTask, Dict[str, Any]],
        project_id: str,
        thread_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskExecutionResult:
        """Execute a single workstream task through its assigned agent."""
        if isinstance(task, dict):
            task_obj = WorkstreamTask(
                task_id=str(task.get("task_id") or task.get("id")),
                title=task.get("title") or task.get("name") or "Task",
                description=task.get("description", ""),
                lead_agent=task.get("lead_agent") or task.get("assigned_agent") or "CTO",
                dependencies=task.get("dependencies", []),
                estimated_duration_hours=float(task.get("duration") or task.get("estimated_duration_hours") or 2.0),
                deliverable_type=task.get("deliverable_type", "general_spec"),
            )
        else:
            task_obj = task

        tid = task_obj.task_id
        lead = task_obj.lead_agent
        resolved_thread = thread_id or f"thread_{project_id}_main"

        result = TaskExecutionResult(
            task_id=tid,
            project_id=project_id,
            agent_id=lead,
            status=TaskStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._task_results[tid] = result
        self._emit_progress(tid, project_id, lead, 10, f"Dispatching brief to {lead}", TaskStatus.IN_PROGRESS)

        # Notify thread of delegation
        if self.thread_manager:
            self.thread_manager.post_message(
                thread_id=resolved_thread,
                sender_agent="CEO",
                to_agents=[lead],
                message_type=ThreadMessageType.DELEGATION,
                subject=f"Delegation Brief: [{tid}] {task_obj.title}",
                content=f"TASK: {task_obj.title}\nSCOPE: {task_obj.description}\nDELIVERABLE: {task_obj.deliverable_type}",
                project_id=project_id,
            )

        start_time = time.time()
        agent = self.registry.get(lead) if self.registry else None
        if not agent and self.registry:
            agent = self.registry.get_by_role(lead)

        if not agent:
            err_msg = f"Agent '{lead}' not found in AgentRegistry."
            logger.error(err_msg)
            result.status = TaskStatus.FAILED
            result.error = err_msg
            result.completed_at = datetime.now(timezone.utc).isoformat()
            self._emit_progress(tid, project_id, lead, 100, "Failed: Agent not found", TaskStatus.FAILED)
            return result

        try:
            self._emit_progress(tid, project_id, lead, 35, f"{lead} analyzing requirements", TaskStatus.IN_PROGRESS)
            deliverable, tokens, cost = self._execute_agent_action(agent, task_obj, project_id, context)

            elapsed_ms = (time.time() - start_time) * 1000
            result.status = TaskStatus.COMPLETED
            result.deliverable = deliverable
            result.tokens_used = tokens
            result.cost_usd = cost
            result.latency_ms = elapsed_ms
            result.completed_at = datetime.now(timezone.utc).isoformat()

            # Persist deliverable to Vault
            deliv_path = self._persist_deliverable(project_id, task_obj, deliverable)
            result.deliverable_path = deliv_path

            self._emit_progress(tid, project_id, lead, 100, f"Completed deliverable for {tid}", TaskStatus.COMPLETED)

            # Post deliverable to thread
            if self.thread_manager:
                content_preview = str(deliverable)
                if isinstance(deliverable, dict):
                    content_preview = json.dumps(deliverable, indent=2)
                elif len(content_preview) > 500:
                    content_preview = content_preview[:500] + "... [Deliverable saved to Vault]"

                self.thread_manager.post_message(
                    thread_id=resolved_thread,
                    sender_agent=lead,
                    to_agents=["CEO", "thread"],
                    message_type=ThreadMessageType.DELIVERABLE,
                    subject=f"Deliverable: [{tid}] {task_obj.title}",
                    content=content_preview,
                    attachments=[deliv_path] if deliv_path else [],
                    tokens_used=tokens,
                    latency_ms=int(elapsed_ms),
                    project_id=project_id,
                )

        except Exception as e:
            logger.exception("Error executing task %s on agent %s: %s", tid, lead, e)
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.latency_ms = (time.time() - start_time) * 1000
            result.completed_at = datetime.now(timezone.utc).isoformat()
            self._emit_progress(tid, project_id, lead, 100, f"Execution failed: {e}", TaskStatus.FAILED)

        return result

    def _execute_agent_action(
        self,
        agent: Any,
        task: WorkstreamTask,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, int, float]:
        """Call role-specific method on agent or general think operation."""
        ctx_dict = context or {}
        role = getattr(agent, "role", "AGENT").upper()

        initial_tokens = getattr(getattr(agent, "telemetry", None), "total_tokens", getattr(agent, "total_tokens_used", 0))
        initial_cost = getattr(getattr(agent, "telemetry", None), "total_cost_usd", getattr(agent, "total_cost_usd", 0.0))

        deliverable: Any = None

        # 1. Specialized C-Suite API calls
        if "CTO" in role and hasattr(agent, "generate_architecture_spec"):
            deliverable = agent.generate_architecture_spec(
                requirements=f"{task.title}: {task.description}",
                project_id=project_id,
            )
        elif "COO" in role and hasattr(agent, "create_pep"):
            deliverable = agent.create_pep(
                project_id=project_id,
                founder_goal=f"{task.title}: {task.description}",
            )
        elif "CPO" in role and hasattr(agent, "create_prd"):
            deliverable = agent.create_prd(
                product_vision=f"{task.title}: {task.description}",
                project_id=project_id,
            )
        elif "CDO" in role and hasattr(agent, "generate_design_system"):
            deliverable = agent.generate_design_system(
                product_context=f"{task.title}: {task.description}",
                project_id=project_id,
            )
        elif "CAO" in role and hasattr(agent, "audit"):
            deliverable = agent.audit(
                project_id=project_id,
                deliverables=[ctx_dict.get("deliverables", {})],
            )
        elif hasattr(agent, "think"):
            prompt = (
                f"Workstream Task ID: {task.task_id}\n"
                f"Task Title: {task.title}\n"
                f"Description: {task.description}\n"
                f"Deliverable Type: {task.deliverable_type}\n"
                f"Context: {json.dumps(ctx_dict)}\n\n"
                f"Execute your responsibilities and produce the complete deliverable."
            )
            deliverable = agent.think(
                context=prompt,
                complexity=3,
                task_type=task.deliverable_type,
            )
        else:
            deliverable = f"Deliverable completed for {task.title} by {role}."

        final_tokens = getattr(getattr(agent, "telemetry", None), "total_tokens", getattr(agent, "total_tokens_used", 0))
        final_cost = getattr(getattr(agent, "telemetry", None), "total_cost_usd", getattr(agent, "total_cost_usd", 0.0))

        tokens_delta = max(0, final_tokens - initial_tokens)
        cost_delta = max(0.0, final_cost - initial_cost)

        return deliverable, tokens_delta, cost_delta

    def _persist_deliverable(self, project_id: str, task: WorkstreamTask, deliverable: Any) -> Optional[str]:
        """Save completed deliverable artifact into Vault deliverables/."""
        if not self.vault_manager or not hasattr(self.vault_manager, "write"):
            return None

        clean_type = re.sub(r"[^A-Za-z0-9_-]+", "_", task.deliverable_type.lower())
        rel_path = f"projects/{project_id}/deliverables/{task.task_id.lower()}_{clean_type}.json"

        data_payload: Dict[str, Any] = {
            "task_id": task.task_id,
            "project_id": project_id,
            "title": task.title,
            "lead_agent": task.lead_agent,
            "deliverable_type": task.deliverable_type,
            "output": deliverable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            write_agent = "CEO" if "CAO" in (task.lead_agent or "").upper() else task.lead_agent
            self.vault_manager.write(rel_path, data_payload, agent_id=write_agent)
            return rel_path
        except Exception as e:
            logger.warning("Could not persist deliverable to %s: %s", rel_path, e)
            return None

    # ------------------------------------------------------------------------
    # 2. Parallel Batch Execution
    # ------------------------------------------------------------------------

    def dispatch_batch_parallel(
        self,
        tasks: List[Union[WorkstreamTask, Dict[str, Any]]],
        project_id: str,
        thread_id: Optional[str] = None,
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, TaskExecutionResult]:
        """Execute a wave of independent tasks concurrently across thread pool."""
        if not tasks:
            return {}

        task_objs = [
            t if isinstance(t, WorkstreamTask) else WorkstreamTask(
                task_id=str(t.get("task_id") or t.get("id")),
                title=t.get("title") or t.get("name") or "Task",
                description=t.get("description", ""),
                lead_agent=t.get("lead_agent") or t.get("assigned_agent") or "CTO",
                dependencies=t.get("dependencies", []),
                estimated_duration_hours=float(t.get("duration") or t.get("estimated_duration_hours") or 2.0),
                deliverable_type=t.get("deliverable_type", "general_spec"),
            )
            for t in tasks
        ]

        results: Dict[str, TaskExecutionResult] = {}
        effective_workers = min(self.max_workers, len(task_objs))

        with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_to_task = {
                executor.submit(
                    self.dispatch_task,
                    task,
                    project_id,
                    thread_id,
                    shared_context,
                ): task.task_id
                for task in task_objs
            }

            for future in concurrent.futures.as_completed(future_to_task):
                tid = future_to_task[future]
                try:
                    res = future.result(timeout=self.task_timeout_seconds)
                    results[tid] = res
                except concurrent.futures.TimeoutError:
                    logger.error("Task %s timed out after %ss", tid, self.task_timeout_seconds)
                    results[tid] = TaskExecutionResult(
                        task_id=tid,
                        project_id=project_id,
                        agent_id=next((t.lead_agent for t in task_objs if t.task_id == tid), "UNKNOWN"),
                        status=TaskStatus.FAILED,
                        error=f"Task timed out after {self.task_timeout_seconds} seconds",
                    )
                except Exception as e:
                    logger.error("Parallel execution exception on task %s: %s", tid, e)
                    results[tid] = TaskExecutionResult(
                        task_id=tid,
                        project_id=project_id,
                        agent_id=next((t.lead_agent for t in task_objs if t.task_id == tid), "UNKNOWN"),
                        status=TaskStatus.FAILED,
                        error=str(e),
                    )

        return results

    def execute_workstreams(
        self,
        project_id: str,
        workstreams: List[Dict[str, Any]],
        fail_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience method for executing workstreams with optional injected failure."""
        results: Dict[str, Any] = {}
        for ws in workstreams:
            wid = str(ws.get("id") or ws.get("task_id"))
            agent = ws.get("assigned_agent") or ws.get("lead_agent") or "CEO"
            if agent == fail_agent:
                results[wid] = {"status": "failed", "error": f"Agent {agent} failed safely."}
            else:
                res = self.dispatch_task(ws, project_id=project_id)
                results[wid] = {
                    "status": res.status.value,
                    "deliverable": res.deliverable,
                    "error": res.error,
                }
        return results

    def get_task_result(self, task_id: str) -> Optional[TaskExecutionResult]:
        return self._task_results.get(task_id)

    def list_results(self) -> List[TaskExecutionResult]:
        return list(self._task_results.values())
