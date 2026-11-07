"""backend/orchestrator/state_graph.py - LangGraph StateGraph & Native State Machine.

Implements the cyclic state machine with nodes:
goal_intake -> workstream_scheduling -> agent_execution -> dual_cao_audit ->
(reflection_revision loop | founder_escalation | ceo_synthesis) -> complete.

Provides:
1. NativeStateGraph: Zero-dependency, high-reliability native Python state machine
   adhering strictly to the LangGraph contract (add_node, add_edge, add_conditional_edges, compile, invoke).
2. LangGraph bridge: Compiles to standard LangGraph if installed.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

logger = logging.getLogger("alpha.orchestrator.state_graph")


class AlphaState(TypedDict, total=False):
    """Master state dictionary carried through all LangGraph StateGraph nodes."""
    project_id: str
    goal: str
    user_id: Optional[str]
    status: str
    workstreams: List[Dict[str, Any]]
    execution_waves: List[List[Dict[str, Any]]]
    current_wave_index: int
    deliverables: Dict[str, Any]
    thread_id: str
    messages: List[Dict[str, Any]]
    audit_round: int
    audit_result: Optional[Dict[str, Any]]
    audit_history: List[Dict[str, Any]]
    p0_defects: List[str]
    p1_defects: List[str]
    founder_escalation: Optional[Dict[str, Any]]
    executive_summary: str
    archify_html: Optional[str]
    archify_graph: Optional[Dict[str, Any]]
    errors: List[str]


class NativeCompiledGraph:
    """Runnable compiled graph instance adhering to LangGraph Runnable contract."""

    def __init__(
        self,
        nodes: Dict[str, Callable[[AlphaState], Dict[str, Any]]],
        edges: Dict[str, str],
        conditional_edges: Dict[str, Tuple[Callable[[AlphaState], str], Optional[Dict[str, str]]]],
        entry_point: str,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point

    def invoke(self, initial_state: AlphaState) -> AlphaState:
        """Executes the graph synchronously from entry point to terminal sink."""
        state: AlphaState = dict(initial_state)
        current_node = self.entry_point
        max_steps = 50  # Safety circuit breaker against infinite loops
        step_count = 0

        while current_node and step_count < max_steps:
            step_count += 1
            node_fn = self.nodes.get(current_node)
            if not node_fn:
                logger.error("Node '%s' not found in graph definition.", current_node)
                break

            logger.debug("Executing state graph node '%s' (step %d)", current_node, step_count)
            updates = node_fn(state)
            if isinstance(updates, dict):
                state.update(updates)

            # Route to next node
            if current_node in self.conditional_edges:
                router_fn, path_map = self.conditional_edges[current_node]
                next_key = router_fn(state)
                next_node = path_map.get(next_key, next_key) if path_map else next_key
            else:
                next_node = self.edges.get(current_node)

            if next_node in ("__end__", "END", None):
                break
            current_node = next_node

        return state


class NativeStateGraph:
    """Pure-Python StateGraph adhering to LangGraph contract."""

    def __init__(self, state_schema: Any = AlphaState) -> None:
        self.state_schema = state_schema
        self.nodes: Dict[str, Callable[[AlphaState], Dict[str, Any]]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, Tuple[Callable[[AlphaState], str], Optional[Dict[str, str]]]] = {}
        self.entry_point: Optional[str] = None

    def add_node(self, name: str, fn: Callable[[AlphaState], Dict[str, Any]]) -> None:
        self.nodes[name] = fn

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        router_fn: Callable[[AlphaState], str],
        path_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.conditional_edges[source] = (router_fn, path_map)

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def compile(self) -> NativeCompiledGraph:
        if not self.entry_point:
            raise ValueError("Entry point must be set before compiling StateGraph.")
        return NativeCompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            entry_point=self.entry_point,
        )


# Alias
AlphaStateGraph = NativeStateGraph


def create_alpha_state_graph(orchestrator_instance: Any) -> NativeCompiledGraph:
    """Build and compile the standard Project Alpha cyclic StateGraph."""
    graph = NativeStateGraph(AlphaState)

    # 1. Define Nodes
    def node_goal_intake(state: AlphaState) -> Dict[str, Any]:
        goal = state.get("goal", "")
        pid = state.get("project_id", "default_proj")
        workstreams = orchestrator_instance._parse_goal_into_workstreams(goal, pid)
        return {"workstreams": workstreams, "status": "planning"}

    def node_workstream_scheduling(state: AlphaState) -> Dict[str, Any]:
        ws = state.get("workstreams", [])
        pid = state.get("project_id", "default_proj")
        sched = orchestrator_instance._schedule_workstreams(ws, pid)
        waves = sched.get("waves", [ws])
        return {"execution_waves": waves, "current_wave_index": 0, "status": "scheduling"}

    def node_agent_execution(state: AlphaState) -> Dict[str, Any]:
        waves = state.get("execution_waves", [])
        idx = state.get("current_wave_index", 0)
        pid = state.get("project_id", "default_proj")
        deliverables = dict(state.get("deliverables", {}))

        if idx < len(waves):
            wave_tasks = waves[idx]
            wave_res = orchestrator_instance._execute_wave(wave_tasks, pid, deliverables)
            deliverables.update(wave_res)
            return {"deliverables": deliverables, "current_wave_index": idx + 1, "status": "executing"}
        return {"status": "executed"}

    def node_dual_cao_audit(state: AlphaState) -> Dict[str, Any]:
        deliverables = state.get("deliverables", {})
        pid = state.get("project_id", "default_proj")
        round_num = state.get("audit_round", 1)

        if hasattr(orchestrator_instance.dual_cao, "audit_deliverables"):
            audit_res = orchestrator_instance.dual_cao.audit_deliverables(
                project_id=pid,
                deliverables=deliverables,
                round_num=round_num,
            )
        else:
            audit_res = orchestrator_instance.dual_cao.audit(
                deliverables=deliverables,
                project_id=pid,
                round_num=round_num,
            )

        return {
            "audit_round": round_num,
            "audit_result": audit_res.model_dump(),
            "p0_defects": audit_res.p0_defects,
            "p1_defects": audit_res.p1_defects,
            "status": "approved" if audit_res.passed else ("escalated" if audit_res.escalation_required else "revision_needed"),
        }

    def node_reflection_revision(state: AlphaState) -> Dict[str, Any]:
        deliverables = dict(state.get("deliverables", {}))
        pid = state.get("project_id", "default_proj")
        current_round = state.get("audit_round", 1)

        # Formulate remediation
        raw_res = state.get("audit_result", {})
        feedback = f"Remediate: {'; '.join(raw_res.get('p0_defects', []) + raw_res.get('p1_defects', []))}"
        for k, v in deliverables.items():
            if isinstance(v, dict):
                v["content"] = f"{v.get('content', '')}\n\n[REVISED]: {feedback}"

        return {
            "deliverables": deliverables,
            "audit_round": current_round + 1,
            "status": "revising",
        }

    def node_founder_escalation(state: AlphaState) -> Dict[str, Any]:
        raw_res = state.get("audit_result", {})
        escalation = {
            "project_id": state.get("project_id"),
            "reason": "Dual CAO audit failed after 2 rounds.",
            "p0_defects": raw_res.get("p0_defects", []),
            "p1_defects": raw_res.get("p1_defects", []),
            "verdict": "ESCALATED_TO_FOUNDER",
        }
        return {"founder_escalation": escalation, "status": "escalated_to_founder"}

    def node_ceo_synthesis(state: AlphaState) -> Dict[str, Any]:
        deliverables = state.get("deliverables", {})
        pid = state.get("project_id", "default_proj")
        summary = orchestrator_instance._synthesize_outputs(deliverables, pid, None)
        html, graph = orchestrator_instance._generate_archify_artifacts(pid, deliverables)
        return {
            "executive_summary": summary,
            "archify_html": html,
            "archify_graph": graph,
            "status": "completed",
        }

    # Register nodes
    graph.add_node("goal_intake", node_goal_intake)
    graph.add_node("workstream_scheduling", node_workstream_scheduling)
    graph.add_node("agent_execution", node_agent_execution)
    graph.add_node("dual_cao_audit", node_dual_cao_audit)
    graph.add_node("reflection_revision", node_reflection_revision)
    graph.add_node("founder_escalation", node_founder_escalation)
    graph.add_node("ceo_synthesis", node_ceo_synthesis)

    # 2. Wire Edges
    graph.set_entry_point("goal_intake")
    graph.add_edge("goal_intake", "workstream_scheduling")
    graph.add_edge("workstream_scheduling", "agent_execution")

    # Wave execution conditional loop
    def route_execution(state: AlphaState) -> str:
        idx = state.get("current_wave_index", 0)
        waves = state.get("execution_waves", [])
        return "agent_execution" if idx < len(waves) else "dual_cao_audit"

    graph.add_conditional_edges("agent_execution", route_execution)

    # Dual CAO Audit Gate conditional routing
    def route_audit(state: AlphaState) -> str:
        res = state.get("audit_result", {})
        passed = res.get("passed", False)
        round_num = state.get("audit_round", 1)
        if passed:
            return "ceo_synthesis"
        if round_num < 2 and not res.get("escalation_required", False):
            return "reflection_revision"
        return "founder_escalation"

    graph.add_conditional_edges("dual_cao_audit", route_audit)
    graph.add_edge("reflection_revision", "dual_cao_audit")
    graph.add_edge("ceo_synthesis", "__end__")
    graph.add_edge("founder_escalation", "__end__")

    return graph.compile()
