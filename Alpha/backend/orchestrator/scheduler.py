"""backend/orchestrator/scheduler.py - Project Alpha Critical Path & Wave Scheduler.

Implements Kahn's topological sorting algorithm, cyclic dependency detection,
Critical Path Method (CPM) with forward and backward passes (ES, EF, LS, LF, total/free slack),
and execution wave partitioning for parallel multi-agent dispatch.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.orchestrator.goal_parser import WorkstreamTask
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.orchestrator.scheduler")


class CyclicDependencyError(Exception):
    """Raised when the task graph contains one or more dependency cycles."""

    def __init__(self, cycle_nodes: List[str], message: Optional[str] = None) -> None:
        self.cycle_nodes = cycle_nodes
        msg = message or f"Cyclic dependency detected among tasks: {' -> '.join(cycle_nodes)}"
        super().__init__(msg)


class ScheduledTask(BaseModel):
    """Task decorated with critical path schedule metrics."""
    model_config = ConfigDict(extra="ignore")

    task_id: str
    title: str
    lead_agent: str
    dependencies: List[str] = Field(default_factory=list)
    duration: float = Field(default=1.0, ge=0.0)
    es: float = Field(default=0.0, description="Earliest Start time")
    ef: float = Field(default=0.0, description="Earliest Finish time")
    ls: float = Field(default=0.0, description="Latest Start time")
    lf: float = Field(default=0.0, description="Latest Finish time")
    slack: float = Field(default=0.0, description="Total Float (LF - EF)")
    free_slack: float = Field(default=0.0, description="Free Float")
    is_critical: bool = Field(default=False)
    wave: int = Field(default=0, description="Execution batch index")


class SchedulePlan(BaseModel):
    """Complete project critical path and wave schedule plan."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    tasks: Dict[str, ScheduledTask]
    topological_order: List[str]
    critical_path: List[str]
    total_duration: float
    execution_waves: List[List[str]] = Field(description="Batches of task IDs runnable in parallel")
    has_cycles: bool = False
    cycle_path: Optional[List[str]] = None


class Scheduler:
    """Dependency resolution and Kahn's CPM Critical Path Engine."""

    def __init__(self, vault_manager: Optional[VaultManager] = None) -> None:
        self.vault_manager = vault_manager

    def build_schedule(
        self,
        tasks: List[Union[WorkstreamTask, Dict[str, Any]]],
        project_id: str = "default_project",
    ) -> SchedulePlan:
        """Construct full topological CPM schedule plan or raise CyclicDependencyError."""
        if not tasks:
            return SchedulePlan(
                project_id=project_id,
                tasks={},
                topological_order=[],
                critical_path=[],
                total_duration=0.0,
                execution_waves=[],
            )

        # 1. Normalize input task dictionaries
        task_map: Dict[str, Dict[str, Any]] = {}
        for t in tasks:
            if isinstance(t, WorkstreamTask):
                task_map[t.task_id] = {
                    "task_id": t.task_id,
                    "title": t.title,
                    "lead_agent": t.lead_agent,
                    "dependencies": list(t.dependencies),
                    "duration": float(t.estimated_duration_hours),
                }
            elif isinstance(t, dict):
                tid = str(t.get("task_id") or t.get("id"))
                task_map[tid] = {
                    "task_id": tid,
                    "title": t.get("title") or t.get("name") or tid,
                    "lead_agent": t.get("lead_agent") or t.get("assigned_agent") or "AGENT",
                    "dependencies": list(t.get("dependencies", [])),
                    "duration": float(t.get("estimated_duration_hours") or t.get("estimated_days") or t.get("duration") or 1.0),
                }

        # 2. Build Adjacency and In-Degree structures
        adj: Dict[str, List[str]] = {tid: [] for tid in task_map}
        in_degree: Dict[str, int] = {tid: 0 for tid in task_map}

        for tid, data in task_map.items():
            for dep in data["dependencies"]:
                if dep in adj:
                    adj[dep].append(tid)
                    in_degree[tid] += 1
                else:
                    logger.debug("Dependency %s not found in current task map.", dep)

        # 3. Kahn's Algorithm for Topological Sort & Cycle Detection
        queue: deque[str] = deque([tid for tid, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []

        es: Dict[str, float] = {tid: 0.0 for tid in task_map}
        ef: Dict[str, float] = {}

        while queue:
            curr = queue.popleft()
            topo_order.append(curr)

            curr_deps = task_map[curr]["dependencies"]
            curr_es = max([ef[d] for d in curr_deps if d in ef], default=0.0)
            es[curr] = curr_es
            ef[curr] = curr_es + task_map[curr]["duration"]

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Detect cycle
        if len(topo_order) < len(task_map):
            cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
            cycle_path = self._find_cycle_path(adj, cycle_nodes)
            raise CyclicDependencyError(cycle_nodes=cycle_path or cycle_nodes)

        total_duration = max(ef.values(), default=0.0)

        # 4. Backward Pass: Latest Finish (LF) and Latest Start (LS)
        lf: Dict[str, float] = {tid: total_duration for tid in topo_order}
        ls: Dict[str, float] = {}

        for curr in reversed(topo_order):
            successors = adj[curr]
            if successors:
                lf[curr] = min(ls[s] for s in successors if s in ls)
            ls[curr] = lf[curr] - task_map[curr]["duration"]

        # 5. Critical Path & Float Calculation
        critical_path: List[str] = []
        scheduled_tasks: Dict[str, ScheduledTask] = {}

        for tid in topo_order:
            total_float = round(lf[tid] - ef[tid], 4)
            # Free float = min(ES of successors) - EF of current
            succ_es = [es[s] for s in adj[tid] if s in es]
            free_float = round(min(succ_es) - ef[tid], 4) if succ_es else total_float

            is_crit = abs(total_float) < 1e-6
            if is_crit:
                critical_path.append(tid)

            scheduled_tasks[tid] = ScheduledTask(
                task_id=tid,
                title=task_map[tid]["title"],
                lead_agent=task_map[tid]["lead_agent"],
                dependencies=task_map[tid]["dependencies"],
                duration=task_map[tid]["duration"],
                es=es[tid],
                ef=ef[tid],
                ls=ls[tid],
                lf=lf[tid],
                slack=total_float,
                free_slack=free_float,
                is_critical=is_crit,
                wave=0,
            )

        # 6. Compute Execution Waves (Parallel Batches)
        waves = self._compute_execution_waves(task_map, topo_order)
        for wave_idx, batch in enumerate(waves):
            for tid in batch:
                if tid in scheduled_tasks:
                    scheduled_tasks[tid].wave = wave_idx

        plan = SchedulePlan(
            project_id=project_id,
            tasks=scheduled_tasks,
            topological_order=topo_order,
            critical_path=critical_path,
            total_duration=total_duration,
            execution_waves=waves,
            has_cycles=False,
        )

        # Persist schedule timeline to Vault
        if self.vault_manager and hasattr(self.vault_manager, "write"):
            try:
                self.vault_manager.write(
                    f"projects/{project_id}/timelines.json",
                    plan.model_dump(),
                    agent_id="COO",
                )
            except Exception as e:
                logger.debug("Could not write timelines to Vault: %s", e)

        return plan

    def schedule(
        self,
        tasks: List[Union[WorkstreamTask, Dict[str, Any]]],
        project_id: str = "default_project",
    ) -> Dict[str, Any]:
        """Convenience method returning waves and critical path for orchestrators."""
        plan = self.build_schedule(tasks, project_id)
        # Convert task IDs in waves to actual task dictionaries if inputs were dicts
        task_dict_lookup: Dict[str, Dict[str, Any]] = {}
        for t in tasks:
            if isinstance(t, WorkstreamTask):
                task_dict_lookup[t.task_id] = t.model_dump()
            elif isinstance(t, dict):
                tid = str(t.get("task_id") or t.get("id"))
                task_dict_lookup[tid] = t

        waves_as_tasks: List[List[Dict[str, Any]]] = []
        for wave in plan.execution_waves:
            wave_tasks = [task_dict_lookup.get(tid, {"task_id": tid}) for tid in wave]
            waves_as_tasks.append(wave_tasks)

        return {
            "execution_order": plan.topological_order,
            "critical_path": plan.critical_path,
            "total_duration": plan.total_duration,
            "waves": waves_as_tasks,
            "execution_waves": plan.execution_waves,
            "plan": plan,
        }

    def _compute_execution_waves(
        self,
        task_map: Dict[str, Dict[str, Any]],
        topo_order: List[str],
    ) -> List[List[str]]:
        """Group tasks into independent execution waves for parallel execution."""
        task_wave: Dict[str, int] = {}
        waves: List[List[str]] = []

        for tid in topo_order:
            deps = task_map[tid]["dependencies"]
            if not deps:
                wave = 0
            else:
                wave = max([task_wave[d] for d in deps if d in task_wave], default=-1) + 1
            task_wave[tid] = wave

            while len(waves) <= wave:
                waves.append([])
            waves[wave].append(tid)

        return waves

    def _find_cycle_path(self, adj: Dict[str, List[str]], cycle_nodes: List[str]) -> Optional[List[str]]:
        """DFS traversal to extract exact loop path among cyclic nodes."""
        cycle_set = set(cycle_nodes)
        visited: Set[str] = set()
        stack: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            if node in stack:
                cycle_start = stack.index(node)
                return stack[cycle_start:] + [node]
            if node in visited:
                return None
            visited.add(node)
            stack.append(node)
            for neighbor in adj.get(node, []):
                if neighbor in cycle_set:
                    res = dfs(neighbor)
                    if res:
                        return res
            stack.pop()
            return None

        for n in cycle_nodes:
            path = dfs(n)
            if path:
                return path
        return cycle_nodes

    def recalculate_on_delay(
        self,
        current_plan: SchedulePlan,
        delayed_task_id: str,
        new_duration: float,
    ) -> SchedulePlan:
        """Dynamic schedule update when a running task takes longer than estimated."""
        tasks = []
        for tid, st in current_plan.tasks.items():
            dur = new_duration if tid == delayed_task_id else st.duration
            tasks.append({
                "task_id": st.task_id,
                "title": st.title,
                "lead_agent": st.lead_agent,
                "dependencies": st.dependencies,
                "duration": dur,
            })
        return self.build_schedule(tasks, project_id=current_plan.project_id)
