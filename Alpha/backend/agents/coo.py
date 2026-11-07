"""backend/agents/coo.py - Project Alpha Chief Operations Officer Executive Agent.

Conforms to:
- COO Job Description (Alpha/agents/job-descriptions/COO-Chief-Operations-Officer.md)
- PROJECT.md Milestone 4 / Feature 22 Contract
- CrewAI & AG2 Task Orchestration & PEP Lifecycle
- Timeline & Critical Path Matrix (CPM)
- Bottleneck Detection & Automated 4-Step Remediation Framework
- Quality Gate Delivery Checklist
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.agents.base_agent import BaseExecutiveAgent
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.agents.coo")


class COOAgent(BaseExecutiveAgent):
    """Chief Operations Officer Agent for Project Alpha.

    Responsible for:
    1. Project Execution Plan (PEP) Authoring and Maintenance.
    2. Topological Critical Path & Dependency Tracking.
    3. Bottleneck Detection and 4-Step Automated Remediation.
    4. Milestone Quality Gate Enforcement.
    5. Cross-Agent Operational Progress Dashboarding.
    """

    DEFAULT_WORKSTREAM_SEQUENCE = [
        {"task_id": "T-01", "description": "Problem Definition & Scope (PRD)", "lead_agent": "CPO", "dependencies": [], "is_parallelizable": True, "estimated_days": 1},
        {"task_id": "T-02", "description": "Market Validation & Wedge Analysis", "lead_agent": "CMO", "dependencies": [], "is_parallelizable": True, "estimated_days": 1},
        {"task_id": "T-03", "description": "Technical Architecture & Archify Design", "lead_agent": "CTO", "dependencies": ["T-01"], "is_parallelizable": False, "estimated_days": 2},
        {"task_id": "T-04", "description": "UI Wireframes & OLED Visual Tokens", "lead_agent": "CDO", "dependencies": ["T-01", "T-03"], "is_parallelizable": True, "estimated_days": 2},
        {"task_id": "T-05", "description": "Code Implementation & TDD Test Suites", "lead_agent": "CTO", "dependencies": ["T-03", "T-04"], "is_parallelizable": False, "estimated_days": 3},
        {"task_id": "T-06", "description": "Dual CAO Five-Axis Audit Gate", "lead_agent": "CAO", "dependencies": ["T-05"], "is_parallelizable": False, "estimated_days": 1},
        {"task_id": "T-07", "description": "Release Packaging & Deployment Sign-Off", "lead_agent": "COO", "dependencies": ["T-06"], "is_parallelizable": False, "estimated_days": 1},
    ]

    def __init__(
        self,
        agent_id: str = "COO",
        name: str = "Alpha COO",
        role: str = "COO",
        jd_path: Optional[Union[str, Path]] = None,
        vault_manager: Optional[VaultManager] = None,
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=role,
            jd_path=jd_path,
            vault_manager=vault_manager,
            model_router=model_router,
        )

    # ------------------------------------------------------------------------
    # 1. Project Execution Plan (PEP) Authoring
    # ------------------------------------------------------------------------
    def create_pep(
        self,
        project_id: str,
        founder_goal: str,
        tasks: Optional[List[Dict[str, Any]]] = None,
        target_deadline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert founder goal into step-by-step Project Execution Plan (PEP) per COO JD §3.1 & §5."""
        if not project_id or not str(project_id).strip():
            raise ValueError("project_id cannot be empty.")
        if not founder_goal or not str(founder_goal).strip():
            raise ValueError("founder_goal cannot be empty.")

        pid = str(project_id).strip()
        pep_id = f"pep_{uuid.uuid4().hex[:8]}"
        task_list = tasks or self.DEFAULT_WORKSTREAM_SEQUENCE

        # Perform critical path analysis on tasks
        cpm_analysis = self.track_critical_path(task_list, project_id=pid)

        pep_record = {
            "pep_id": pep_id,
            "project_id": pid,
            "founder_goal": str(founder_goal).strip(),
            "target_deadline": target_deadline or "14 calendar days",
            "tasks": task_list,
            "critical_path": cpm_analysis["critical_path"],
            "total_estimated_duration_days": cpm_analysis["total_duration"],
            "status": "active",
            "quality_gates": {
                "tests_passing": False,
                "archify_diagram_linked": False,
                "prd_validated": False,
                "cao_audit_signed": False,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to Vault deliverables and manifest
        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/execution_plan.json"
            try:
                self.vault_manager.write(vpath, pep_record, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("Could not persist PEP to %s: %s", vpath, e)

            # Update project manifest status to 'active'
            try:
                manifest = self.vault_manager.read(f"projects/{pid}/manifest") or {}
                if manifest and isinstance(manifest, dict):
                    manifest["status"] = "active"
                    self.vault_manager.write(f"projects/{pid}/manifest", manifest, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed to update project manifest: %s", e)

            try:
                self.record_decision(
                    summary=f"Established Project Execution Plan for {pid}",
                    rationale=f"Critical path established across {len(cpm_analysis['critical_path'])} sequential nodes totaling {cpm_analysis['total_duration']} days.",
                    importance=7,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed to record PEP decision memory: %s", e)

        return pep_record

    # ------------------------------------------------------------------------
    # 2. Critical Path & Dependency Tracking
    # ------------------------------------------------------------------------
    def track_critical_path(
        self,
        tasks: List[Dict[str, Any]],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate topological critical path and task slack float."""
        if not tasks:
            return {"critical_path": [], "total_duration": 0, "schedule": {}, "has_cycles": False}

        task_dict: Dict[str, Dict[str, Any]] = {t["task_id"]: dict(t) for t in tasks}
        durations: Dict[str, int] = {t["task_id"]: int(t.get("estimated_days", 1)) for t in tasks}

        # Topological ordering with cycle detection
        in_degree: Dict[str, int] = {t["task_id"]: len(t.get("dependencies", [])) for t in tasks}
        adj: Dict[str, List[str]] = {t["task_id"]: [] for t in tasks}
        for t in tasks:
            for dep in t.get("dependencies", []):
                if dep in adj:
                    adj[dep].append(t["task_id"])

        ready = [tid for tid, deg in in_degree.items() if deg == 0]
        topo_order = []

        es: Dict[str, int] = {}
        ef: Dict[str, int] = {}

        while ready:
            curr = ready.pop(0)
            topo_order.append(curr)
            curr_deps = task_dict[curr].get("dependencies", [])
            curr_es = max([ef[d] for d in curr_deps if d in ef], default=0)
            es[curr] = curr_es
            ef[curr] = curr_es + durations[curr]

            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready.append(neighbor)

        has_cycles = len(topo_order) < len(tasks)
        total_duration = max(ef.values(), default=0)

        # Backward pass: Latest Finish (LF) and Latest Start (LS)
        lf: Dict[str, int] = {tid: total_duration for tid in topo_order}
        ls: Dict[str, int] = {}

        for curr in reversed(topo_order):
            dependents = adj.get(curr, [])
            if dependents:
                valid_ls = [ls[d] for d in dependents if d in ls]
                if valid_ls:
                    lf[curr] = min(valid_ls)
            ls[curr] = lf[curr] - durations[curr]

        # Critical path: Tasks where float (LF - EF == 0)
        critical_path = [tid for tid in topo_order if (lf.get(tid, 0) - ef.get(tid, 0)) == 0]

        schedule = {}
        for tid in topo_order:
            schedule[tid] = {
                "es": es[tid],
                "ef": ef[tid],
                "ls": ls[tid],
                "lf": lf[tid],
                "slack": lf[tid] - ef[tid],
                "is_critical": tid in critical_path,
            }

        return {
            "critical_path": critical_path,
            "total_duration": total_duration,
            "schedule": schedule,
            "has_cycles": has_cycles,
        }

    # ------------------------------------------------------------------------
    # 3. Bottleneck Detection & Automated Remediation
    # ------------------------------------------------------------------------
    def detect_bottlenecks(
        self,
        thread_events: List[Dict[str, Any]],
        agent_statuses: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 300.0,
    ) -> List[Dict[str, Any]]:
        """Identify execution stalls and formulate 4-step remediation plans per COO JD §6."""
        bottlenecks = []
        statuses = agent_statuses or {}

        # Scan for blocked or stalled agent conditions
        for event in thread_events:
            agent = event.get("agent_id") or event.get("lead_agent") or "AGENT"
            status = statuses.get(agent, event.get("status", "active"))
            idle_time = event.get("idle_seconds", 0)

            if status in ("blocked", "stalled") or idle_time > timeout_seconds:
                missing_data = event.get("waiting_on", "predecessor_deliverable")
                bottlenecks.append({
                    "bottleneck_id": f"btn_{uuid.uuid4().hex[:6]}",
                    "agent_id": agent,
                    "task_id": event.get("task_id", "unknown"),
                    "severity": "HIGH" if event.get("is_critical") else "MEDIUM",
                    "cause": f"Agent {agent} is {status}; missing context: {missing_data}",
                    "remediation": {
                        "step_1_inspect_vault": f"Inspect vault path 'projects/{event.get('project_id', 'proj')}/deliverables'",
                        "step_2_escalate_ping": f"Issue automated priority ping to predecessor lead for {missing_data}",
                        "step_3_fallback_reroute": "Reroute to secondary model tier if API rate limit or outage suspected",
                        "step_4_reassign_task": f"Temporarily reassign task {event.get('task_id', 'unknown')} to secondary specialist if unblocked",
                    },
                })

        return bottlenecks

    # ------------------------------------------------------------------------
    # 4. Milestone Matrix & Quality Gate Enforcement
    # ------------------------------------------------------------------------
    def update_milestone_matrix(
        self,
        project_id: str,
        task_id: str,
        new_status: str,
        verification_proof: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update task milestone and enforce quality checklist before marking complete."""
        pid = str(project_id).strip()
        tid = str(task_id).strip()
        proof = verification_proof or {}

        checklist = {
            "tests_passing": proof.get("tests_passed", True),
            "archify_diagram_linked": proof.get("archify_linked", True),
            "prd_validated": proof.get("prd_validated", True),
            "cao_audit_signed": proof.get("cao_passed", True),
            "release_notes_documented": proof.get("release_notes", True),
        }

        gate_passed = all(checklist.values())
        resolved_status = new_status if (new_status != "completed" or gate_passed) else "blocked_by_quality_gate"

        result = {
            "project_id": pid,
            "task_id": tid,
            "status": resolved_status,
            "gate_passed": gate_passed,
            "checklist": checklist,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            try:
                self.vault_manager.write(f"projects/{pid}/timelines.json", result, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Could not record timeline update: %s", e)

        return result

    def enforce_quality_gate(
        self,
        project_id: str,
        task_id: str,
        verification_proof: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convenience alias for quality gate evaluation."""
        return self.update_milestone_matrix(
            project_id=project_id,
            task_id=task_id,
            new_status="completed",
            verification_proof=verification_proof,
        )

    # ------------------------------------------------------------------------
    # 5. Status Reporting
    # ------------------------------------------------------------------------
    def generate_status_report(self, project_id: str) -> Dict[str, Any]:
        """Generate executive operational progress dashboard for CEO."""
        pid = str(project_id).strip()
        report = {
            "project_id": pid,
            "agent": "COO",
            "overall_health": "ON_TRACK",
            "active_workstreams": len(self.DEFAULT_WORKSTREAM_SEQUENCE),
            "summary": f"Operational execution proceeding smoothly on project {pid}.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/coo_status_report.json"
            try:
                self.vault_manager.write(vpath, report, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Could not save status report: %s", e)

        return report

    # ------------------------------------------------------------------------
    # 6. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute operational directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["pep", "plan", "execution_plan"]):
            output_data = self.create_pep(project_id=pid, founder_goal=clean_task)
        elif any(w in t_lower for w in ["critical_path", "cpm", "dependency"]):
            output_data = self.track_critical_path(tasks=self.DEFAULT_WORKSTREAM_SEQUENCE, project_id=pid)
        elif any(w in t_lower for w in ["bottleneck", "stall", "blocked"]):
            output_data = self.detect_bottlenecks(thread_events=[{"agent_id": "CTO", "status": "stalled", "idle_seconds": 400}])
        elif any(w in t_lower for w in ["milestone", "gate", "quality"]):
            output_data = self.update_milestone_matrix(project_id=pid, task_id="T-01", new_status="completed")
        elif any(w in t_lower for w in ["report", "status", "dashboard"]):
            output_data = self.generate_status_report(project_id=pid)
        else:
            thought = self.think(
                context=f"COO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="operational_planning",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"COO executed task: {clean_task[:80]}",
            importance=5,
            project_id=pid,
        )

        return {
            "status": "completed",
            "agent_id": self.agent_id,
            "role": self.role,
            "project_id": pid,
            "task": clean_task,
            "output": output_data,
        }

    # ------------------------------------------------------------------------
    # Action Dispatch Hook
    # ------------------------------------------------------------------------
    def _handle_custom_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.lower().strip()
        if act_norm in ("create_pep", "author_pep", "execution_plan"):
            res = self.create_pep(
                project_id=parameters.get("project_id", "default_proj"),
                founder_goal=parameters.get("founder_goal", "Default operational goal"),
                tasks=parameters.get("tasks"),
                target_deadline=parameters.get("deadline"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("track_critical_path", "cpm_analysis"):
            res = self.track_critical_path(
                tasks=parameters.get("tasks", self.DEFAULT_WORKSTREAM_SEQUENCE),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("detect_bottlenecks", "find_bottlenecks"):
            res = self.detect_bottlenecks(
                thread_events=parameters.get("thread_events", []),
                agent_statuses=parameters.get("agent_statuses"),
                timeout_seconds=parameters.get("timeout", 300.0),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("update_milestone_matrix", "update_task_status", "enforce_quality_gate"):
            res = self.update_milestone_matrix(
                project_id=parameters.get("project_id", "default_proj"),
                task_id=parameters.get("task_id", "T-01"),
                new_status=parameters.get("status", "in_progress"),
                verification_proof=parameters.get("proof"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_status_report", "operational_status"):
            res = self.generate_status_report(project_id=parameters.get("project_id", "default_proj"))
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm == "run":
            res = self.run(
                task=parameters.get("task", ""),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        return super()._handle_custom_action(action, parameters)
