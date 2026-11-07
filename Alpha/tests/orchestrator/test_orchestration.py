"""tests/orchestrator/test_orchestration.py - Master Subsystem Test Suite for Milestone 6.

Validates all 9 core subsystems of the Tri-Framework Orchestration Engine:
1. GoalParser (NLP Parsing, Complexity, Priority, Agent Selection)
2. Scheduler (Kahn's CPM Algorithm, Cyclic Dependency Detection, Slack)
3. ThreadManager (Dual Persistence in SQLite & JSONL, PubSub, WebSocket Broadcasts)
4. DelegationEngine (CEO Dispatch, Dependency Resolution, Parallel Execution, Error Containment)
5. Synthesizer (Multi-Agent Deliverable Synthesis, Contradiction Resolution, 3-Tier Matrix)
6. StateGraph (Cyclic State Transitions, Reflection Loops, Escalation Caps)
7. CrewFlows (Hierarchical Manager Process, Task Context Chaining)
8. AG2Chat (Multi-Agent Deliberation, Dynamic Turn-taking, Consensus Termination)
9. ArchifyEngine (OLED Tokens, Standalone HTML/SVG, Delta Diff Generation)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.orchestrator import (
    AlphaCrewFlow,
    AlphaGroupChat,
    AlphaOrchestrator,
    AlphaState,
    AlphaStateGraph,
    ArchifyDiff,
    ArchifyEngine,
    ConflictResolution,
    CrewAgentRole,
    CrewTask,
    CyclicDependencyError,
    DelegationEngine,
    FounderEscalation,
    GoalParser,
    GoalPriority,
    GraphData,
    GraphEdge,
    GraphNode,
    GroupChatMessage,
    NativeAG2GroupChat,
    NativeCrewFlow,
    NativeStateGraph,
    OLED_THEME,
    OutputSynthesizer,
    ParsedGoal,
    SchedulePlan,
    ScheduledTask,
    Scheduler,
    SynthesizedDeliverable,
    TaskExecutionResult,
    TaskStatus,
    ThreadManager,
    WorkstreamTask,
    create_ag2_group_chat,
    create_alpha_state_graph,
    create_crew_flow,
)
from backend.vault.schemas import ThreadMessageType
from backend.vault.vault_manager import VaultManager


# ============================================================================
# 1. GoalParser Subsystem Tests
# ============================================================================

class TestGoalParser:
    """Verifies Natural Language Goal Decomposition and Workstream Planning."""

    def test_goal_parser_standard_decomposition(self):
        parser = GoalParser()
        result = parser.parse("Build an autonomous SaaS market intelligence platform with FastAPI and Flutter")

        assert result.project_title.startswith("Project")
        assert result.complexity in (3, 4)
        assert result.priority == GoalPriority.MEDIUM
        assert "CEO" in result.required_agents
        assert "CTO" in result.required_agents
        assert len(result.workstreams) >= 2
        assert any(t.lead_agent == "CTO" for t in result.workstreams)
        assert result.estimated_duration_hours > 0

    def test_goal_parser_priority_and_complexity_escalation(self):
        parser = GoalParser()
        result = parser.parse("URGENT: Architect enterprise distributed multi-agent operating system immediately")

        assert result.priority == GoalPriority.URGENT
        assert result.complexity == 5
        assert "CAO-Claude" in result.required_agents or "CAO-ChatGPT" in result.required_agents
        assert result.estimated_duration_hours >= 4.0

    def test_goal_parser_empty_input_validation(self):
        parser = GoalParser()
        with pytest.raises(ValueError, match="Directive cannot be empty or whitespace"):
            parser.parse("   ")

    def test_goal_parser_parse_goal_adapter(self):
        parser = GoalParser()
        res_dict = parser.parse_goal("Build design system for mobile app", project_id="proj_custom_001")
        assert res_dict["project_id"] == "proj_custom_001"
        assert len(res_dict["workstreams"]) >= 1
        assert "parsed_goal" in res_dict


# ============================================================================
# 2. Scheduler & Kahn CPM Subsystem Tests
# ============================================================================

class TestScheduler:
    """Verifies Kahn's Topological Sorting and Critical Path Method (CPM)."""

    def test_kahn_topological_sort_linear(self):
        scheduler = Scheduler()
        tasks = [
            {"id": "t1", "dependencies": [], "duration": 2.0},
            {"id": "t2", "dependencies": ["t1"], "duration": 3.0},
            {"id": "t3", "dependencies": ["t2"], "duration": 1.0},
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_sched_1")
        assert plan.topological_order == ["t1", "t2", "t3"]
        assert plan.total_duration == 6.0
        assert plan.critical_path == ["t1", "t2", "t3"]
        assert len(plan.execution_waves) == 3

    def test_kahn_topological_sort_parallel_branches(self):
        scheduler = Scheduler()
        tasks = [
            {"id": "root", "dependencies": [], "duration": 1.0},
            {"id": "branch_a", "dependencies": ["root"], "duration": 4.0},
            {"id": "branch_b", "dependencies": ["root"], "duration": 2.0},
            {"id": "merge", "dependencies": ["branch_a", "branch_b"], "duration": 1.0},
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_sched_2")
        assert plan.topological_order[0] == "root"
        assert plan.topological_order[-1] == "merge"
        assert plan.total_duration == 6.0  # root(1) + branch_a(4) + merge(1)
        assert "branch_a" in plan.critical_path
        # Wave 0: root; Wave 1: branch_a, branch_b; Wave 2: merge
        assert len(plan.execution_waves) == 3
        assert set(plan.execution_waves[1]) == {"branch_a", "branch_b"}

    def test_scheduler_detects_cyclic_dependency(self):
        scheduler = Scheduler()
        tasks = [
            {"id": "a", "dependencies": ["c"]},
            {"id": "b", "dependencies": ["a"]},
            {"id": "c", "dependencies": ["b"]},
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            scheduler.build_schedule(tasks, project_id="proj_cycle")
        assert exc_info.value.cycle_nodes is not None

    def test_recalculate_on_delay(self):
        scheduler = Scheduler()
        tasks = [
            {"id": "t1", "dependencies": [], "duration": 2.0},
            {"id": "t2", "dependencies": ["t1"], "duration": 3.0},
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_sched_delay")
        assert plan.total_duration == 5.0

        # Delay t1 by 3 extra hours (duration = 5.0)
        updated = scheduler.recalculate_on_delay(plan, delayed_task_id="t1", new_duration=5.0)
        assert updated.total_duration == 8.0
        assert updated.tasks["t1"].duration == 5.0


# ============================================================================
# 3. ThreadManager Subsystem Tests
# ============================================================================

class TestThreadManager:
    """Verifies Inter-Agent Discussion Threads and Dual Persistence."""

    def test_thread_posting_and_jsonl_persistence(self, tmp_path):
        mgr = ThreadManager(vault_root=tmp_path)
        mgr.create_thread(project_id="proj_001", thread_id="thread_proj_001_main", topic="Architecture Alignment")

        msg1 = mgr.post_message(
            thread_id="thread_proj_001_main",
            sender_agent="CEO",
            content="Produce Tech Spec",
            to_agents=["CTO"],
            message_type=ThreadMessageType.DELEGATION,
            project_id="proj_001",
        )
        msg2 = mgr.post_message(
            thread_id="thread_proj_001_main",
            sender_agent="CTO",
            content="Tech Spec Completed",
            to_agents=["CEO"],
            message_type=ThreadMessageType.DELIVERABLE,
            project_id="proj_001",
        )

        history = mgr.get_thread_messages("thread_proj_001_main", project_id="proj_001")
        assert len(history) == 2
        assert history[0].type == "DELEGATION"
        assert history[1].type == "DELIVERABLE"

        # Check JSONL file exists and is valid
        disk_file = tmp_path / "projects" / "proj_001" / "threads" / "thread_proj_001_main.jsonl"
        assert disk_file.exists()
        lines = disk_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["from"] == "CEO"

    def test_subscriber_pubsub_notifications(self, tmp_path):
        mgr = ThreadManager(vault_root=tmp_path)
        received_messages = []

        sub_id = mgr.subscribe("thread_sub_test", lambda m: received_messages.append(m))
        mgr.post_message(
            thread_id="thread_sub_test",
            sender_agent="CEO",
            content="Broadcast notification",
            project_id="proj_sub",
        )

        assert len(received_messages) == 1
        assert received_messages[0].content == "Broadcast notification"

        # Unsubscribe test
        mgr.unsubscribe("thread_sub_test", sub_id)
        mgr.post_message(
            thread_id="thread_sub_test",
            sender_agent="CEO",
            content="Second message after unsub",
            project_id="proj_sub",
        )
        assert len(received_messages) == 1

    def test_websocket_envelope_formatting(self, tmp_path):
        mgr = ThreadManager(vault_root=tmp_path)
        msg = mgr.post_message(
            thread_id="thread_ws_test",
            sender_agent="CTO",
            content="Status check",
            project_id="proj_ws",
        )
        payload = mgr.format_websocket_payload(msg, event_type="THREAD_MESSAGE_POSTED")
        assert payload["event"] == "THREAD_MESSAGE_POSTED"
        assert payload["project_id"] == "proj_ws"
        assert payload["payload"]["from"] == "CTO"
        assert "timestamp" in payload


# ============================================================================
# 4. DelegationEngine Subsystem Tests
# ============================================================================

class TestDelegationEngine:
    """Verifies CEO Workstream Dispatch, Parallel Management, and Error Containment."""

    def test_delegation_executes_successfully(self, tmp_path):
        engine = DelegationEngine()
        task = WorkstreamTask(
            task_id="T-01",
            title="Technical Architecture",
            description="Produce FastAPI spec",
            lead_agent="CTO",
        )
        result = engine.dispatch_task(task, project_id="proj_del_1")
        assert result.status == TaskStatus.COMPLETED
        assert result.agent_id == "CTO"
        assert result.deliverable is not None

    def test_delegation_batch_parallel(self):
        engine = DelegationEngine(max_workers=2)
        tasks = [
            WorkstreamTask(task_id="T-01", title="Spec A", description="Scope A", lead_agent="CTO"),
            WorkstreamTask(task_id="T-02", title="Spec B", description="Scope B", lead_agent="CMO"),
        ]
        results = engine.dispatch_batch_parallel(tasks, project_id="proj_del_batch")
        assert len(results) == 2
        assert results["T-01"].status == TaskStatus.COMPLETED
        assert results["T-02"].status == TaskStatus.COMPLETED

    def test_delegation_contains_agent_failure(self):
        engine = DelegationEngine()
        workstreams = [
            {"id": "w1", "name": "Architecture Spec", "assigned_agent": "CTO"},
            {"id": "w2", "name": "Budget Model", "assigned_agent": "NON_EXISTENT_AGENT_XYZ"},
        ]
        results = engine.execute_workstreams("proj_fail_test", workstreams, fail_agent="NON_EXISTENT_AGENT_XYZ")
        assert results["w1"]["status"] == "completed"
        assert results["w2"]["status"] == "failed"
        assert "failed safely" in results["w2"]["error"]


# ============================================================================
# 5. OutputSynthesizer Subsystem Tests
# ============================================================================

class TestSynthesizer:
    """Verifies Multi-Agent Deliverable Synthesis and Contradiction Resolution."""

    def test_synthesizer_produces_executive_markdown(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path))
        synth = OutputSynthesizer(vault_manager=vault)
        deliverables = {
            "Technical Spec (CTO)": "FastAPI + SQLite + ChromaDB backend.",
            "Design Tokens (CDO)": "OLED deep black theme (#090A0F) with cyan accents.",
        }
        res = synth.synthesize("proj_synth_1", deliverables)
        assert isinstance(res, SynthesizedDeliverable)
        assert "Executive Delivery Briefing" in res.final_output_markdown
        assert "Technical Architecture" in res.final_output_markdown
        assert len(res.action_items) > 0

    def test_synthesizer_conflict_detection_and_escalation(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path))
        synth = OutputSynthesizer(vault_manager=vault)
        deliverables = [
            {"lead_agent": "CTO", "title": "Infrastructure Spec", "output": "Infrastructure costs will cause a budget overrun and expensive GPU allocations."},
            {"lead_agent": "COO", "title": "Timeline Plan", "output": "Dependencies on design tokens will cause a delay in timeline."},
        ]
        res = synth.synthesize("proj_conflict_test", deliverables)
        assert len(res.conflicts_resolved) >= 2
        # Critical budget conflict triggers Tier 3 Founder Escalation
        assert res.founder_escalation is not None
        assert res.founder_escalation.severity == "P0_CRITICAL"


# ============================================================================
# 6. StateGraph & Reflection Subsystem Tests
# ============================================================================

class TestStateGraph:
    """Verifies Cyclic State Transitions, Reflection Loops, and Escalation Caps."""

    def test_state_graph_happy_path(self):
        graph = NativeStateGraph(AlphaState)

        def node_intake(s: AlphaState) -> Dict[str, Any]:
            return {"status": "planning"}

        def node_audit(s: AlphaState) -> Dict[str, Any]:
            return {"status": "approved", "audit_result": {"passed": True}}

        def node_synthesis(s: AlphaState) -> Dict[str, Any]:
            return {"status": "completed"}

        graph.add_node("goal_intake", node_intake)
        graph.add_node("dual_cao_audit", node_audit)
        graph.add_node("ceo_synthesis", node_synthesis)

        graph.set_entry_point("goal_intake")
        graph.add_edge("goal_intake", "dual_cao_audit")

        def route_audit(s: AlphaState) -> str:
            res = s.get("audit_result", {})
            return "ceo_synthesis" if res.get("passed") else "__end__"

        graph.add_conditional_edges("dual_cao_audit", route_audit)
        graph.add_edge("ceo_synthesis", "__end__")

        compiled = graph.compile()
        final_state = compiled.invoke({"goal": "Test goal", "project_id": "p1"})
        assert final_state["status"] == "completed"

    def test_state_graph_reflection_loop_recovery(self):
        graph = NativeStateGraph(AlphaState)

        def node_audit(s: AlphaState) -> Dict[str, Any]:
            round_num = s.get("audit_round", 1)
            # Pass on round 2
            passed = bool(round_num >= 2)
            return {"audit_round": round_num, "audit_result": {"passed": passed}}

        def node_revise(s: AlphaState) -> Dict[str, Any]:
            return {"audit_round": s.get("audit_round", 1) + 1, "status": "revised"}

        def node_complete(s: AlphaState) -> Dict[str, Any]:
            return {"status": "completed"}

        graph.add_node("audit", node_audit)
        graph.add_node("revise", node_revise)
        graph.add_node("complete", node_complete)

        graph.set_entry_point("audit")

        def route_audit(s: AlphaState) -> str:
            res = s.get("audit_result", {})
            return "complete" if res.get("passed") else "revise"

        graph.add_conditional_edges("audit", route_audit)
        graph.add_edge("revise", "audit")
        graph.add_edge("complete", "__end__")

        compiled = graph.compile()
        final_state = compiled.invoke({"audit_round": 1})
        assert final_state["status"] == "completed"
        assert final_state["audit_round"] == 2

    def test_state_graph_escalation_cap_triggers_founder_escalation(self):
        graph = NativeStateGraph(AlphaState)

        def node_audit(s: AlphaState) -> Dict[str, Any]:
            round_num = s.get("audit_round", 1)
            return {"audit_round": round_num, "audit_result": {"passed": False}}

        def node_revise(s: AlphaState) -> Dict[str, Any]:
            return {"audit_round": s.get("audit_round", 1) + 1}

        def node_escalate(s: AlphaState) -> Dict[str, Any]:
            return {"status": "escalated_to_founder"}

        graph.add_node("audit", node_audit)
        graph.add_node("revise", node_revise)
        graph.add_node("escalate", node_escalate)

        graph.set_entry_point("audit")

        def route_audit(s: AlphaState) -> str:
            round_num = s.get("audit_round", 1)
            if round_num >= 2:
                return "escalate"
            return "revise"

        graph.add_conditional_edges("audit", route_audit)
        graph.add_edge("revise", "audit")
        graph.add_edge("escalate", "__end__")

        compiled = graph.compile()
        final_state = compiled.invoke({"audit_round": 1})
        assert final_state["status"] == "escalated_to_founder"
        assert final_state["audit_round"] == 2


# ============================================================================
# 7. CrewFlows & AG2Chat Subsystem Tests
# ============================================================================

class TestCrewFlowsAndAG2Chat:
    """Verifies CrewAI Hierarchical Flow and AG2 Deliberation Protocol."""

    def test_crew_hierarchical_manager_flow(self):
        flow = NativeCrewFlow(
            manager_agent=None,
            agents={},
            tasks=[
                CrewTask(task_id="t1", description="Scope Product", expected_output="PRD", agent_role="CPO"),
                CrewTask(task_id="t2", description="Architecture", expected_output="Tech Spec", agent_role="CTO", dependencies=["t1"]),
            ],
            project_id="proj_crew_test",
        )
        res = flow.kickoff()
        assert len(res) >= 2
        assert "t1" in res
        assert "t2" in res

        # Check compatibility helper
        compat_res = flow.run_flow(manager="CEO", tasks=["Define Scope", "Architecture"])
        assert compat_res["tasks_executed"] == 2
        assert "Manager CEO" in compat_res["execution_log"][0]

    def test_ag2_chat_consensus_termination(self):
        chat = NativeAG2GroupChat(
            agents={},
            moderator_role="CEO",
            max_turns=5,
            project_id="proj_ag2_test",
        )
        res = chat.deliberate(participants=["CEO", "CTO", "CPO"], max_turns=5)
        assert res["consensus_reached"] is True
        assert res["turns"] >= 2


# ============================================================================
# 8. ArchifyEngine Subsystem Tests
# ============================================================================

class TestArchifyEngine:
    """Verifies Living Canvas Generator, OLED Theme Tokens, and Delta Diffs."""

    def test_archify_engine_generates_valid_system_graph(self):
        engine = ArchifyEngine()
        graph = engine.generate_system_graph("proj_test_001", title="System Architecture Test")

        assert graph.project_id == "proj_test_001"
        assert len(graph.nodes) >= 6
        assert len(graph.edges) >= 5
        assert graph.nodes[0].x > 0.0
        assert graph.nodes[0].y > 0.0

    def test_archify_engine_generates_company_graph(self):
        engine = ArchifyEngine()
        graph = engine.generate_company_graph("proj_test_comp", title="Company Hierarchy")
        assert graph.view_type == "company"
        assert any(n.id == "FOUNDER" for n in graph.nodes)
        assert any(n.id == "CEO" for n in graph.nodes)
        assert any(n.id == "CTO" for n in graph.nodes)

    def test_archify_engine_generates_execution_graph(self):
        engine = ArchifyEngine()
        tasks = [
            {"id": "t1", "name": "PRD", "lead_agent": "CPO", "dependencies": [], "duration": 1.0},
            {"id": "t2", "name": "Architecture", "lead_agent": "CTO", "dependencies": ["t1"], "duration": 2.0},
        ]
        graph = engine.generate_execution_graph("proj_test_exec", title="Execution CPM", tasks=tasks, critical_path_ids={"t1", "t2"})
        assert graph.view_type == "execution"
        assert len(graph.nodes) == 2
        assert graph.nodes[0].metadata.get("is_critical") is True

    def test_archify_engine_generates_standalone_html(self):
        engine = ArchifyEngine()
        graph = engine.generate_system_graph("proj_test_002")
        html_out = engine.generate_html_diagram(graph)

        # Zero CDN dependencies check
        assert "<script src=\"http" not in html_out
        assert "<link rel=\"stylesheet\" href=\"http" not in html_out
        assert "http://" not in html_out.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in html_out
        assert "<!DOCTYPE html>" in html_out
        assert "#090A0F" in html_out  # OLED dark background token
        assert "#06B6D4" in html_out  # Neon cyan token
        assert 'svg id="diagram-svg"' in html_out

    def test_archify_engine_delta_diff_computation(self):
        engine = ArchifyEngine()
        baseline = engine.generate_system_graph("proj_baseline")

        # Modify current graph by adding a new node
        current = engine.generate_system_graph("proj_current")
        new_node = GraphNode(
            id="auth_service",
            label="OAuth2 Service",
            type="service",
            status="active",
        )
        current.nodes.append(new_node)
        # Remove an existing node
        current.nodes = [n for n in current.nodes if n.id != "flutter_client"]

        diff = engine.compute_diff(baseline, current)
        assert diff.summary["added_nodes_count"] == 1
        assert diff.summary["removed_nodes_count"] == 1
        assert diff.added_nodes[0].id == "auth_service"
        assert diff.removed_nodes[0].id == "flutter_client"

    def test_archify_engine_vault_persistence(self, tmp_path):
        engine = ArchifyEngine()
        graph = engine.generate_system_graph("proj_persist_001")
        saved = engine.save_diagram("proj_persist_001", graph, vault_root=tmp_path)

        html_path = Path(saved["html_path"])
        json_path = Path(saved["json_path"])

        assert html_path.exists()
        assert json_path.exists()
        assert html_path.stat().st_size > 500

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["project_id"] == "proj_persist_001"
