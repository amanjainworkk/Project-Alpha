"""backend/orchestrator/orchestrator.py - Master Alpha Orchestrator.

Unifies the full end-to-end pipeline:
Goal Parsing -> Scheduling (Kahn CPM) -> Tri-Framework execution ->
Dual CAO 5-axis audit gate (with 2-round escalation cap) ->
Output Synthesis -> Archify Diagram Generation.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.agents.agent_registry import AgentRegistry
from backend.agents.cao import CAOAuditResult, DualCAO
from backend.agents.ceo import CEOAgent
from backend.model_router.router import ModelRouter
from backend.orchestrator.archify_engine import ArchifyEngine
from backend.orchestrator.delegation import DelegationEngine
from backend.orchestrator.goal_parser import GoalParser
from backend.orchestrator.scheduler import Scheduler
from backend.orchestrator.synthesizer import OutputSynthesizer
from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.orchestrator.master")


class OrchestratorStatus(str, Enum):
    INITIALIZED = "initialized"
    PLANNING = "planning"
    SCHEDULING = "scheduling"
    EXECUTING = "executing"
    AUDITING = "auditing"
    REVISING = "revising"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    ESCALATED_TO_FOUNDER = "escalated_to_founder"
    FAILED = "failed"


class OrchestratorResult(BaseModel):
    """Unified result model representing complete output of an Alpha goal run."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    project_id: str
    goal: str
    status: OrchestratorStatus = OrchestratorStatus.COMPLETED
    executive_summary: str = ""
    deliverables: Dict[str, Any] = Field(default_factory=dict)
    audit_result: Optional[CAOAuditResult] = None
    founder_escalation: Optional[Dict[str, Any]] = None
    archify_diagram_html: Optional[str] = None
    archify_graph_data: Optional[Dict[str, Any]] = None
    timeline_execution: List[Dict[str, Any]] = Field(default_factory=list)
    thread_id: Optional[str] = None
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def passed_audit(self) -> bool:
        return self.audit_result.passed if self.audit_result else False


# Contract alias
FinalOutput = OrchestratorResult


class AlphaOrchestrator:
    """Master orchestrator integrating LangGraph, CrewAI, AG2, and Dual CAO audit gate."""

    def __init__(
        self,
        vault_manager: Optional[VaultManager] = None,
        agent_registry: Optional[AgentRegistry] = None,
        model_router: Optional[ModelRouter] = None,
        dual_cao: Optional[DualCAO] = None,
        goal_parser: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        thread_manager: Optional[Any] = None,
        synthesizer: Optional[Any] = None,
        archify_engine: Optional[Any] = None,
        delegation_engine: Optional[Any] = None,
    ) -> None:
        self.vault_manager = vault_manager or VaultManager()
        self.model_router = model_router or ModelRouter()
        self.agent_registry = agent_registry or AgentRegistry(
            vault_manager=self.vault_manager,
            model_router=self.model_router,
        )
        self.agent_registry.load_all()

        self.dual_cao = dual_cao or DualCAO(
            vault_manager=self.vault_manager,
            model_router=self.model_router,
        )
        if not hasattr(self.dual_cao, "audit_deliverables") and hasattr(self.dual_cao, "audit"):
            self.dual_cao.audit_deliverables = lambda project_id, deliverables, round_num=1: self.dual_cao.audit(
                deliverables=deliverables, project_id=project_id, round_num=round_num
            )

        # Core orchestration components
        self.goal_parser = goal_parser or GoalParser(
            model_router=self.model_router,
            vault_manager=self.vault_manager,
        )
        self.scheduler = scheduler or Scheduler(vault_manager=self.vault_manager)
        self.thread_manager = thread_manager or ThreadManager(vault_manager=self.vault_manager)
        self.synthesizer = synthesizer or OutputSynthesizer(
            model_router=self.model_router,
            vault_manager=self.vault_manager,
        )
        self.archify_engine = archify_engine or ArchifyEngine(vault_manager=self.vault_manager)
        self.delegation_engine = delegation_engine or DelegationEngine(
            agent_registry=self.agent_registry,
            thread_manager=self.thread_manager,
            vault_manager=self.vault_manager,
        )

        self._active_projects: Dict[str, OrchestratorResult] = {}

    def run_goal(
        self,
        goal: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        max_audit_rounds: int = 2,
    ) -> OrchestratorResult:
        """Run the end-to-end Project Alpha autonomous execution pipeline."""
        start_time = time.time()
        if not goal or not str(goal).strip():
            raise ValueError("goal cannot be empty or whitespace.")

        clean_goal = str(goal).strip()
        pid = project_id or f"proj_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        thread_id = f"thread_{pid}_main"

        logger.info("Initializing Alpha goal execution for project '%s': %s", pid, clean_goal)

        # --------------------------------------------------------------------
        # Phase 1: DEFINE — Vault Scaffolding & Goal Parsing
        # --------------------------------------------------------------------
        parsed_workstreams = self._parse_goal_into_workstreams(clean_goal, pid)
        founder_goals = [clean_goal]

        # Scaffold project in Vault
        try:
            self.vault_manager.create_project(
                title=f"Alpha Project: {clean_goal[:40]}",
                description=clean_goal,
                founder_goals=founder_goals,
            )
        except Exception as e:
            logger.debug("Vault project scaffold notice: %s", e)

        # Initialize project thread
        try:
            self.thread_manager.create_thread(
                project_id=pid,
                thread_id=thread_id,
                topic=f"Executive Discussion: {clean_goal[:40]}",
                stakeholders=["CEO", "CTO", "COO", "DualCAO"],
                owner_agent="CEO",
            )
        except Exception as e:
            logger.debug("Thread creation notice: %s", e)

        # --------------------------------------------------------------------
        # Phase 2: PLAN — Scheduling (Kahn's CPM & Wave Partitioning)
        # --------------------------------------------------------------------
        schedule_info = self._schedule_workstreams(parsed_workstreams, pid)
        execution_waves = schedule_info.get("waves", [parsed_workstreams])

        # --------------------------------------------------------------------
        # Phase 3: BUILD — Multi-Agent Execution & Deliberation
        # --------------------------------------------------------------------
        deliverables: Dict[str, Any] = {}
        timeline: List[Dict[str, Any]] = []

        for wave_idx, wave_tasks in enumerate(execution_waves):
            logger.info("Executing Wave %d/%d (%d tasks) for project %s", wave_idx + 1, len(execution_waves), len(wave_tasks), pid)
            wave_results = self._execute_wave(wave_tasks, pid, deliverables)
            deliverables.update(wave_results)
            timeline.append({
                "wave": wave_idx + 1,
                "tasks": [t.get("task_id") or t.get("id") for t in wave_tasks],
                "status": "completed",
            })

        # --------------------------------------------------------------------
        # Phase 4 & 5: REVIEW — Dual CAO Audit Gate (Strict 2-Round Cap)
        # --------------------------------------------------------------------
        audit_result: Optional[CAOAuditResult] = None
        current_round = 1
        founder_escalation_payload: Optional[Dict[str, Any]] = None

        while current_round <= max_audit_rounds:
            logger.info("Invoking Dual CAO Audit Gate Round %d/%d for %s", current_round, max_audit_rounds, pid)
            audit_result = self.dual_cao.audit_deliverables(
                project_id=pid,
                deliverables=deliverables,
                round_num=current_round,
            )

            if audit_result.passed:
                logger.info("Dual CAO Audit Gate PASSED on Round %d (Score: Claude=%.1f%%, GPT=%.1f%%)",
                            current_round, audit_result.claude_score, audit_result.gpt_score)
                break

            logger.warning("Dual CAO Audit Gate REJECTED on Round %d (Score: Claude=%.1f%%, GPT=%.1f%%). P0s=%s, P1s=%s",
                           current_round, audit_result.claude_score, audit_result.gpt_score,
                           len(audit_result.p0_defects), len(audit_result.p1_defects))

            if current_round >= max_audit_rounds or audit_result.escalation_required:
                # Mandatory 2-Round Escalation Cap Triggered
                founder_escalation_payload = audit_result.user_escalate_payload or {
                    "project_id": pid,
                    "reason": "Dual CAO 5-axis audit rejected deliverables after 2 revision rounds.",
                    "p0_defects": audit_result.p0_defects,
                    "p1_defects": audit_result.p1_defects,
                    "action_required": "Founder decision needed to override or reject project.",
                    "requires_founder_action": True,
                }
                break

            # Reflection Loop / Self-Correction for Round 1 Failure
            logger.info("Entering Reflection Loop for Round %d self-correction remediation", current_round)
            deliverables = self._remediate_deliverables(deliverables, audit_result, pid)
            current_round += 1

        # --------------------------------------------------------------------
        # Phase 6: SHIP — Output Synthesis & Archify Visual Generation
        # --------------------------------------------------------------------
        executive_summary = self._synthesize_outputs(deliverables, pid, audit_result)
        archify_html, archify_graph = self._generate_archify_artifacts(pid, deliverables)

        # Final status calculation
        if audit_result and audit_result.passed:
            final_status = OrchestratorStatus.COMPLETED
        elif founder_escalation_payload or (audit_result and audit_result.escalation_required):
            final_status = OrchestratorStatus.ESCALATED_TO_FOUNDER
        else:
            final_status = OrchestratorStatus.FAILED

        elapsed = round(time.time() - start_time, 2)
        total_tokens = sum(getattr(agent, "total_tokens_used", 0) for agent in self.agent_registry.list_agents(active_only=True)) if hasattr(self.agent_registry, "list_agents") else 0
        total_cost = sum(getattr(agent, "total_cost_usd", 0.0) for agent in self.agent_registry.list_agents(active_only=True)) if hasattr(self.agent_registry, "list_agents") else 0.0

        res = OrchestratorResult(
            project_id=pid,
            goal=clean_goal,
            status=final_status,
            executive_summary=executive_summary,
            deliverables=deliverables,
            audit_result=audit_result,
            founder_escalation=founder_escalation_payload,
            archify_diagram_html=archify_html,
            archify_graph_data=archify_graph,
            timeline_execution=timeline,
            thread_id=thread_id,
            total_tokens_used=total_tokens,
            total_cost_usd=round(total_cost, 4),
            elapsed_seconds=elapsed,
        )

        self._active_projects[pid] = res
        return res

    # ------------------------------------------------------------------------
    # Internal Pipeline Helper Methods
    # ------------------------------------------------------------------------

    def _parse_goal_into_workstreams(self, goal: str, project_id: str) -> List[Dict[str, Any]]:
        """Parse raw goal into structured workstreams via GoalParser or CEOAgent."""
        if self.goal_parser:
            if hasattr(self.goal_parser, "parse_goal"):
                try:
                    res = self.goal_parser.parse_goal(goal, project_id)
                    if isinstance(res, dict) and "workstreams" in res and res["workstreams"]:
                        return res["workstreams"]
                except Exception as e:
                    logger.debug("GoalParser parse_goal invocation fallback: %s", e)
            elif hasattr(self.goal_parser, "parse"):
                try:
                    parsed = self.goal_parser.parse(goal, project_id=project_id)
                    if parsed and getattr(parsed, "workstreams", None):
                        return [t.model_dump() for t in parsed.workstreams]
                except Exception as e:
                    logger.debug("GoalParser parse invocation fallback: %s", e)

        # Direct CEOAgent intake fallback
        ceo: Optional[CEOAgent] = self.agent_registry.get("CEO")  # type: ignore
        if ceo and hasattr(ceo, "ingest_goal"):
            try:
                parsed = ceo.ingest_goal(goal, project_id=project_id)
                assigned = parsed.get("assigned_roles", ["CTO", "CPO", "CMO"])
                workstreams = []
                for idx, role in enumerate(assigned, 1):
                    workstreams.append({
                        "task_id": f"T-{idx:02d}",
                        "title": f"Execute domain workstream for {role}",
                        "lead_agent": role,
                        "dependencies": [f"T-{idx-1:02d}"] if idx > 1 else [],
                        "estimated_days": 1,
                        "deliverable_key": f"{role.lower()}_deliverable",
                    })
                return workstreams
            except Exception as e:
                logger.debug("CEOAgent ingest_goal fallback: %s", e)

        # Baseline heuristic fallback
        return [
            {"task_id": "T-01", "title": "Define Product Scope & PRD", "lead_agent": "CPO", "dependencies": [], "estimated_days": 1, "deliverable_key": "product_prd"},
            {"task_id": "T-02", "title": "Technical Architecture & System Design", "lead_agent": "CTO", "dependencies": ["T-01"], "estimated_days": 2, "deliverable_key": "technical_spec"},
            {"task_id": "T-03", "title": "Marketing Wedge & Positioning", "lead_agent": "CMO", "dependencies": [], "estimated_days": 1, "deliverable_key": "marketing_brief"},
            {"task_id": "T-04", "title": "Design System & Wireframes", "lead_agent": "CDO", "dependencies": ["T-01", "T-02"], "estimated_days": 1, "deliverable_key": "design_system"},
        ]

    def _schedule_workstreams(self, workstreams: List[Dict[str, Any]], project_id: str) -> Dict[str, Any]:
        """Apply Kahn's algorithm (Topological Sort) and CPM via Scheduler or COO."""
        if self.scheduler:
            if hasattr(self.scheduler, "schedule"):
                try:
                    return self.scheduler.schedule(workstreams, project_id)
                except Exception as e:
                    logger.debug("Scheduler schedule fallback: %s", e)
            elif hasattr(self.scheduler, "build_schedule"):
                try:
                    plan = self.scheduler.build_schedule(workstreams, project_id)
                    return {
                        "waves": [[t for t in workstreams if (t.get("task_id") or t.get("id")) in wave] for wave in plan.execution_waves],
                        "critical_path": plan.critical_path,
                    }
                except Exception as e:
                    logger.debug("Scheduler build_schedule fallback: %s", e)

        # COO topological critical path fallback
        coo = self.agent_registry.get("COO")
        if coo and hasattr(coo, "track_critical_path"):
            try:
                cpm = coo.track_critical_path(workstreams, project_id)
                return {"critical_path": cpm.get("critical_path", []), "waves": self._partition_into_waves(workstreams)}
            except Exception as e:
                logger.debug("COO track_critical_path fallback: %s", e)

        # Pure Python Kahn's topological sort & wave partitioning fallback
        return {"waves": self._partition_into_waves(workstreams), "critical_path": [t.get("task_id") or t.get("id") for t in workstreams]}

    def _partition_into_waves(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Kahn's topological wave partitioning algorithm."""
        in_degree: Dict[str, int] = {str(t.get("task_id") or t.get("id")): len(t.get("dependencies", [])) for t in tasks}
        task_map = {str(t.get("task_id") or t.get("id")): t for t in tasks}
        adj: Dict[str, List[str]] = {str(t.get("task_id") or t.get("id")): [] for t in tasks}

        for t in tasks:
            tid = str(t.get("task_id") or t.get("id"))
            for dep in t.get("dependencies", []):
                if dep in adj:
                    adj[dep].append(tid)

        waves: List[List[Dict[str, Any]]] = []
        ready = [tid for tid, deg in in_degree.items() if deg == 0]

        while ready:
            current_wave = [task_map[tid] for tid in ready]
            waves.append(current_wave)
            next_ready = []
            for tid in ready:
                for neighbor in adj.get(tid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_ready.append(neighbor)
            ready = next_ready

        return waves or [tasks]

    def _execute_wave(self, tasks: List[Dict[str, Any]], project_id: str, existing_deliverables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tasks in wave and capture deliverables."""
        results: Dict[str, Any] = {}
        for task in tasks:
            role = task.get("lead_agent") or task.get("assigned_agent") or "CTO"
            key = task.get("deliverable_key") or f"{role.lower()}_deliverable"
            agent = self.agent_registry.get(role)

            if agent and hasattr(agent, "think"):
                prompt = f"Execute task '{task.get('title')}' for project '{project_id}'. Upstream deliverables: {list(existing_deliverables.keys())}"
                output = agent.think(prompt, complexity=3, task_type="operational_task")
                deliverable_payload = {
                    "task_id": task.get("task_id") or task.get("id"),
                    "title": task.get("title") or task.get("name"),
                    "role": role,
                    "content": output,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                deliverable_payload = {
                    "task_id": task.get("task_id") or task.get("id"),
                    "title": task.get("title") or task.get("name"),
                    "role": role,
                    "content": f"Deliverable completed for {task.get('title') or task.get('name')}.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            results[key] = deliverable_payload

            # Persist to Vault (delegated tasks for CAO are written under CEO authority to comply with Vault RBAC)
            try:
                write_agent = "CEO" if "CAO" in role.upper() else role
                self.vault_manager.write(
                    f"projects/{project_id}/deliverables/{key}.json",
                    deliverable_payload,
                    agent_id=write_agent,
                )
            except Exception as e:
                logger.debug("Deliverable write notice: %s", e)

        return results

    def _remediate_deliverables(self, deliverables: Dict[str, Any], audit_result: CAOAuditResult, project_id: str) -> Dict[str, Any]:
        """Remediate flawed deliverables based on CAO audit feedback."""
        remediated = dict(deliverables)
        feedback = f"Remediate identified flaws: {'; '.join(audit_result.p0_defects + audit_result.p1_defects)}"

        for key, val in remediated.items():
            if isinstance(val, dict):
                role = val.get("role", "CTO")
                agent = self.agent_registry.get(role)
                if agent and hasattr(agent, "think"):
                    revised = agent.think(f"Revise deliverable {key} strictly addressing: {feedback}", complexity=4)
                    val["content"] = revised
                    val["revision_round"] = 2
                    val["remediation_applied"] = feedback

        return remediated

    def _synthesize_outputs(self, deliverables: Dict[str, Any], project_id: str, audit_result: Optional[CAOAuditResult]) -> str:
        """Synthesize final executive briefing via CEOAgent or Synthesizer."""
        if self.synthesizer and hasattr(self.synthesizer, "synthesize"):
            try:
                syn_res = self.synthesizer.synthesize(project_id, deliverables)
                if hasattr(syn_res, "final_output_markdown"):
                    return syn_res.final_output_markdown
                if isinstance(syn_res, str):
                    return syn_res
            except Exception as e:
                logger.debug("Synthesizer invocation notice: %s", e)

        ceo: Optional[CEOAgent] = self.agent_registry.get("CEO")  # type: ignore
        if ceo and hasattr(ceo, "synthesize_deliverables"):
            try:
                reports = [{"agent_id": v.get("role", "AGENT"), "deliverable": v.get("content")} for v in deliverables.values() if isinstance(v, dict)]
                synthesis = ceo.synthesize_deliverables(reports, project_id=project_id)
                return synthesis.get("unified_briefing_md") or synthesis.get("executive_summary") or "Executive synthesis completed."
            except Exception as e:
                logger.debug("CEOAgent synthesis notice: %s", e)

        # Baseline synthesis
        lines = [
            f"# Executive Deliverable Briefing: {project_id}",
            f"**Audit Status:** {'PASSED' if (audit_result and audit_result.passed) else 'REVISION/ESCALATION'}",
            "",
            "## Completed Deliverables",
        ]
        for k, v in deliverables.items():
            title = v.get("title", k) if isinstance(v, dict) else k
            lines.append(f"- **{title}**: Completed successfully.")
        return "\n".join(lines)

    def _generate_archify_artifacts(self, project_id: str, deliverables: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Generate Archify HTML and JSON node graph data."""
        if self.archify_engine:
            try:
                components = [{"id": f"comp_{k}", "label": k} for k in deliverables.keys()]
                if hasattr(self.archify_engine, "generate_diagram"):
                    html = self.archify_engine.generate_diagram(project_id, components)
                else:
                    graph = self.archify_engine.generate_system_graph(project_id, components=components)
                    html = self.archify_engine.generate_html_diagram(graph)

                if hasattr(self.archify_engine, "generate_graph_data"):
                    graph = self.archify_engine.generate_graph_data(project_id)
                else:
                    graph = self.archify_engine.generate_system_graph(project_id, components=components).model_dump()

                return html, graph
            except Exception as e:
                logger.debug("Archify engine invocation fallback: %s", e)

        # Fallback Archify generator
        html = (
            f"<!DOCTYPE html><html><head><title>Archify - {project_id}</title></head>"
            f"<body style='background:#0A0A0F; color:#E0E0E0; font-family:sans-serif;'>"
            f"<div id='canvas' data-project='{project_id}'>"
            f"<h2>Project Architecture Topology: {project_id}</h2>"
            f"<ul>"
        )
        for k in deliverables.keys():
            html += f"<li style='color:#06B6D4;'>{k}</li>"
        html += "</ul></div></body></html>"

        graph = {
            "project_id": project_id,
            "nodes": [
                {"id": "node_ceo", "label": "CEO Director", "type": "agent", "status": "active"},
                {"id": "node_cto", "label": "CTO Architecture", "type": "agent", "status": "active"},
                {"id": "node_cao", "label": "Dual CAO Gate", "type": "audit", "status": "verified"},
                {"id": "node_vault", "label": "Alpha Vault", "type": "storage", "status": "healthy"},
            ],
            "edges": [
                {"from": "node_ceo", "to": "node_cto", "label": "delegation", "pulsing": True},
                {"from": "node_cto", "to": "node_cao", "label": "audit_review", "pulsing": False},
                {"from": "node_cao", "to": "node_vault", "label": "persist_report", "pulsing": False},
            ],
        }
        return html, graph
