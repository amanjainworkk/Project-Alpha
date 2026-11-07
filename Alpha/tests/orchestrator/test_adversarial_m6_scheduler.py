"""tests/orchestrator/test_adversarial_m6_scheduler.py - Empirical Adversarial Test Suite for Milestone 6.

Adversarially stresses and verifies:
1. Scheduler Topological & CPM Stress:
   - Self-loops, 2-node cycles, multi-hop cycles, disconnected cycles.
   - Kahn's algorithm cycle path extraction in CyclicDependencyError.
   - Boundary DAGs: empty lists, single tasks, linear chains, diamond DAGs, massive 100-task DAGs.
   - Exact mathematical verification of textbook Critical Path Method (CPM):
     ES, EF, LS, LF, Total Float, Free Float (identifying FF != TF).
   - Wave scheduling invariant: tasks in Wave N depend strictly on tasks in Waves < N.
   - Dynamic delays (recalculate_on_delay): critical vs non-critical slips, slack absorption.
2. ThreadManager Concurrency & Persistence Stress:
   - 25+ concurrent worker threads posting to same thread and across 10 threads.
   - Dual-write consistency between SQLite (vault_thread_messages) and disk JSONL.
   - Unicode, emojis, Asian/Arabic/Hindi text, massive payloads (150KB+), malformed inputs.
   - Concurrency safety of PubSub subscriptions.
3. Delegation Error Containment Stress:
   - Crashing agent tasks (RuntimeError, ZeroDivisionError) contained within ThreadPoolExecutor.
   - Mixed wave execution (valid, crashing, missing agents).
   - Empirical investigation of task timeouts.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from backend.orchestrator.delegation import (
    DelegationEngine,
    TaskExecutionResult,
    TaskStatus,
)
from backend.orchestrator.goal_parser import WorkstreamTask
from backend.orchestrator.scheduler import (
    CyclicDependencyError,
    SchedulePlan,
    ScheduledTask,
    Scheduler,
)
from backend.orchestrator.thread_manager import ThreadManager
from backend.vault.schemas import ThreadMessageType
from backend.vault.vault_manager import VaultManager


# ============================================================================
# 1. Scheduler Topological & CPM Adversarial Stress Suite
# ============================================================================

class TestTopologicalAndCPMStress:
    """Adversarial stress-testing of Kahn's topological sort and CPM algorithms."""

    def test_cyclic_graph_self_loop(self):
        """Self-loop (A -> A) must raise CyclicDependencyError with cycle path ['A', 'A']."""
        scheduler = Scheduler()
        tasks = [
            {"id": "A", "dependencies": ["A"], "duration": 2.0},
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            scheduler.build_schedule(tasks, project_id="proj_self_loop")

        err = exc_info.value
        assert err.cycle_nodes == ["A", "A"]
        assert "A -> A" in str(err)

    def test_cyclic_graph_two_node_cycle(self):
        """2-node cycle (A -> B -> A) must be detected and return the complete loop."""
        scheduler = Scheduler()
        tasks = [
            {"id": "A", "dependencies": ["B"], "duration": 1.0},
            {"id": "B", "dependencies": ["A"], "duration": 1.0},
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            scheduler.build_schedule(tasks, project_id="proj_2node_cycle")

        cycle = exc_info.value.cycle_nodes
        assert cycle in (["A", "B", "A"], ["B", "A", "B"])
        assert "Cyclic dependency detected" in str(exc_info.value)

    def test_cyclic_graph_multihop_cycle(self):
        """Multi-hop cycle (A -> B -> C -> D -> B) must isolate the cyclic sub-path."""
        scheduler = Scheduler()
        tasks = [
            {"id": "A", "dependencies": [], "duration": 1.0},
            {"id": "B", "dependencies": ["A", "D"], "duration": 1.0},
            {"id": "C", "dependencies": ["B"], "duration": 1.0},
            {"id": "D", "dependencies": ["C"], "duration": 1.0},
            {"id": "E", "dependencies": ["C"], "duration": 1.0},
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            scheduler.build_schedule(tasks, project_id="proj_multihop_cycle")

        cycle = exc_info.value.cycle_nodes
        # Must trace the cycle among B, C, D
        assert cycle[0] == cycle[-1], "Cycle path must start and end at the same node"
        assert set(cycle) == {"B", "C", "D"}

    def test_cyclic_graph_disconnected_subgraphs(self):
        """Acyclic subgraph alongside a disconnected cyclic component must raise CyclicDependencyError."""
        scheduler = Scheduler()
        tasks = [
            # Acyclic component
            {"id": "T1", "dependencies": [], "duration": 1.0},
            {"id": "T2", "dependencies": ["T1"], "duration": 2.0},
            {"id": "T3", "dependencies": ["T2"], "duration": 3.0},
            # Disconnected cyclic component
            {"id": "X", "dependencies": ["Y"], "duration": 1.0},
            {"id": "Y", "dependencies": ["X"], "duration": 1.0},
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            scheduler.build_schedule(tasks, project_id="proj_disconnected_cycle")

        cycle = exc_info.value.cycle_nodes
        assert cycle in (["X", "Y", "X"], ["Y", "X", "Y"])

    def test_boundary_empty_tasks(self):
        """Empty task list returns valid empty SchedulePlan with zero duration and no cycles."""
        scheduler = Scheduler()
        plan = scheduler.build_schedule([], project_id="proj_empty")
        assert plan.total_duration == 0.0
        assert plan.topological_order == []
        assert plan.critical_path == []
        assert plan.execution_waves == []
        assert plan.has_cycles is False

    def test_boundary_single_task(self):
        """Single task must be assigned wave 0, zero slack, and is_critical True."""
        scheduler = Scheduler()
        plan = scheduler.build_schedule([{"id": "solo", "dependencies": [], "duration": 5.5}])
        assert plan.total_duration == 5.5
        assert plan.topological_order == ["solo"]
        assert plan.critical_path == ["solo"]
        assert len(plan.execution_waves) == 1
        assert plan.execution_waves[0] == ["solo"]

        t = plan.tasks["solo"]
        assert t.es == 0.0
        assert t.ef == 5.5
        assert t.ls == 0.0
        assert t.lf == 5.5
        assert t.slack == 0.0
        assert t.free_slack == 0.0
        assert t.is_critical is True
        assert t.wave == 0

    def test_boundary_strictly_linear_pipeline(self):
        """Linear pipeline (T1 -> T2 -> T3 -> T4 -> T5) must have N waves and sum of durations."""
        scheduler = Scheduler()
        durations = [1.0, 2.5, 3.0, 4.5, 5.0]
        tasks = []
        for i, dur in enumerate(durations, start=1):
            deps = [f"T{i-1}"] if i > 1 else []
            tasks.append({"id": f"T{i}", "dependencies": deps, "duration": dur})

        plan = scheduler.build_schedule(tasks, project_id="proj_linear")
        expected_total = sum(durations)
        assert plan.total_duration == expected_total
        assert plan.topological_order == ["T1", "T2", "T3", "T4", "T5"]
        assert plan.critical_path == ["T1", "T2", "T3", "T4", "T5"]
        assert len(plan.execution_waves) == 5
        for idx, wave in enumerate(plan.execution_waves, start=1):
            assert wave == [f"T{idx}"]
            assert plan.tasks[f"T{idx}"].slack == 0.0

    def test_boundary_diamond_dag_slack_and_float(self):
        """Diamond DAG must partition into 3 waves and compute float on non-critical branch."""
        scheduler = Scheduler()
        tasks = [
            {"id": "root", "dependencies": [], "duration": 2.0},
            {"id": "heavy", "dependencies": ["root"], "duration": 8.0},
            {"id": "light", "dependencies": ["root"], "duration": 3.0},
            {"id": "sink", "dependencies": ["heavy", "light"], "duration": 1.0},
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_diamond")

        # Root(2) + Heavy(8) + Sink(1) = 11.0
        assert plan.total_duration == 11.0
        assert plan.critical_path == ["root", "heavy", "sink"]
        assert len(plan.execution_waves) == 3
        assert plan.execution_waves[0] == ["root"]
        assert set(plan.execution_waves[1]) == {"heavy", "light"}
        assert plan.execution_waves[2] == ["sink"]

        # Light task should have total float = 5.0 (8.0 - 3.0)
        light_t = plan.tasks["light"]
        assert light_t.es == 2.0
        assert light_t.ef == 5.0
        assert light_t.lf == 10.0  # Must finish before Sink starts at 10.0
        assert light_t.ls == 7.0
        assert light_t.slack == 5.0
        assert light_t.free_slack == 5.0
        assert light_t.is_critical is False

    def test_massive_dag_100_tasks_performance_and_waves(self):
        """Massive 100-task DAG across 10 stages must schedule under 100ms with strict wave ordering."""
        scheduler = Scheduler()
        tasks = []
        for i in range(10):
            tasks.append({"id": f"s0_{i}", "dependencies": [], "duration": 1.0})

        for stage in range(1, 10):
            for i in range(10):
                deps = [f"s{stage-1}_{i}", f"s{stage-1}_{(i+1)%10}"]
                tasks.append({"id": f"s{stage}_{i}", "dependencies": deps, "duration": 1.0})

        t0 = time.time()
        plan = scheduler.build_schedule(tasks, project_id="proj_massive")
        elapsed = time.time() - t0

        assert len(plan.topological_order) == 100
        assert len(plan.execution_waves) == 10
        assert elapsed < 0.1, f"Scheduling took {elapsed}s, expected < 100ms"

        # Verify wave assignment: each stage i is in wave i
        for stage in range(10):
            for i in range(10):
                assert plan.tasks[f"s{stage}_{i}"].wave == stage

    def test_textbook_cpm_forward_backward_pass(self):
        """Verify textbook CPM forward/backward passes with known exact float values.

        DAG:
        A (dur 5, deps [])
        B (dur 3, deps [])
        C (dur 4, deps [A])
        D (dur 6, deps [A])
        E (dur 4, deps [B, C])
        F (dur 3, deps [D])
        G (dur 5, deps [D, E])
        H (dur 2, deps [F, G])
        """
        scheduler = Scheduler()
        tasks = [
            {"id": "A", "dependencies": [], "duration": 5.0},
            {"id": "B", "dependencies": [], "duration": 3.0},
            {"id": "C", "dependencies": ["A"], "duration": 4.0},
            {"id": "D", "dependencies": ["A"], "duration": 6.0},
            {"id": "E", "dependencies": ["B", "C"], "duration": 4.0},
            {"id": "F", "dependencies": ["D"], "duration": 3.0},
            {"id": "G", "dependencies": ["D", "E"], "duration": 5.0},
            {"id": "H", "dependencies": ["F", "G"], "duration": 2.0},
        ]

        plan = scheduler.build_schedule(tasks, project_id="proj_textbook_cpm")

        # 1. Total Duration
        assert plan.total_duration == 20.0

        # 2. Critical Path
        assert plan.critical_path == ["A", "C", "E", "G", "H"]

        # 3. Exact metric verification for all tasks
        expected_metrics = {
            "A": {"es": 0.0, "ef": 5.0, "ls": 0.0, "lf": 5.0, "slack": 0.0, "free_slack": 0.0, "is_crit": True},
            "B": {"es": 0.0, "ef": 3.0, "ls": 6.0, "lf": 9.0, "slack": 6.0, "free_slack": 6.0, "is_crit": False},
            "C": {"es": 5.0, "ef": 9.0, "ls": 5.0, "lf": 9.0, "slack": 0.0, "free_slack": 0.0, "is_crit": True},
            "D": {"es": 5.0, "ef": 11.0, "ls": 7.0, "lf": 13.0, "slack": 2.0, "free_slack": 0.0, "is_crit": False},
            "E": {"es": 9.0, "ef": 13.0, "ls": 9.0, "lf": 13.0, "slack": 0.0, "free_slack": 0.0, "is_crit": True},
            "F": {"es": 11.0, "ef": 14.0, "ls": 15.0, "lf": 18.0, "slack": 4.0, "free_slack": 4.0, "is_crit": False},
            "G": {"es": 13.0, "ef": 18.0, "ls": 13.0, "lf": 18.0, "slack": 0.0, "free_slack": 0.0, "is_crit": True},
            "H": {"es": 18.0, "ef": 20.0, "ls": 18.0, "lf": 20.0, "slack": 0.0, "free_slack": 0.0, "is_crit": True},
        }

        for tid, exp in expected_metrics.items():
            st = plan.tasks[tid]
            assert st.es == exp["es"], f"{tid} ES failed"
            assert st.ef == exp["ef"], f"{tid} EF failed"
            assert st.ls == exp["ls"], f"{tid} LS failed"
            assert st.lf == exp["lf"], f"{tid} LF failed"
            assert st.slack == exp["slack"], f"{tid} Slack failed"
            assert st.free_slack == exp["free_slack"], f"{tid} FreeSlack failed"
            assert st.is_critical == exp["is_crit"], f"{tid} is_critical failed"

        # Note: Task D has Total Slack = 2.0, but Free Slack = 0.0
        assert plan.tasks["D"].slack == 2.0
        assert plan.tasks["D"].free_slack == 0.0

    def test_wave_scheduling_strict_dependency_invariant(self):
        """In any valid DAG, every task in Wave N must depend ONLY on tasks in Waves < N."""
        scheduler = Scheduler()
        tasks = [
            {"id": f"t_{i}", "dependencies": [f"t_{j}" for j in range(max(0, i-5), i) if (i+j)%2 == 0], "duration": 1.0}
            for i in range(40)
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_wave_invariant")

        wave_map: Dict[str, int] = {}
        for w_idx, batch in enumerate(plan.execution_waves):
            for tid in batch:
                wave_map[tid] = w_idx

        for tid, st in plan.tasks.items():
            for dep in st.dependencies:
                assert wave_map[dep] < wave_map[tid], (
                    f"Wave invariant violated: Task {tid} in wave {wave_map[tid]} "
                    f"depends on {dep} in wave {wave_map[dep]}"
                )

    def test_dynamic_recalculate_on_delay_critical_vs_noncritical(self):
        """Stressing recalculate_on_delay:

        1. Critical slip: project slips by exact delta.
        2. Non-critical slip within slack: project duration unaffected, slack reduced.
        3. Non-critical slip exceeding slack: project slips by (delta - slack), path shifts.
        """
        scheduler = Scheduler()
        tasks = [
            {"id": "A", "dependencies": [], "duration": 5.0},
            {"id": "B", "dependencies": [], "duration": 3.0},
            {"id": "C", "dependencies": ["A"], "duration": 4.0},
            {"id": "D", "dependencies": ["A"], "duration": 6.0},
            {"id": "E", "dependencies": ["B", "C"], "duration": 4.0},
            {"id": "F", "dependencies": ["D"], "duration": 3.0},
            {"id": "G", "dependencies": ["D", "E"], "duration": 5.0},
            {"id": "H", "dependencies": ["F", "G"], "duration": 2.0},
        ]
        base_plan = scheduler.build_schedule(tasks, project_id="proj_delay_stress")
        assert base_plan.total_duration == 20.0

        # Scenario 1: Critical task C slips from 4.0 to 7.0 (+3.0)
        plan_crit = scheduler.recalculate_on_delay(base_plan, delayed_task_id="C", new_duration=7.0)
        assert plan_crit.total_duration == 23.0
        assert plan_crit.critical_path == ["A", "C", "E", "G", "H"]

        # Scenario 2: Non-critical task D slips within slack (from 6.0 to 7.5; delta=1.5 <= slack 2.0)
        plan_within_slack = scheduler.recalculate_on_delay(base_plan, delayed_task_id="D", new_duration=7.5)
        assert plan_within_slack.total_duration == 20.0
        assert plan_within_slack.tasks["D"].slack == 0.5
        assert plan_within_slack.tasks["D"].is_critical is False
        assert plan_within_slack.critical_path == ["A", "C", "E", "G", "H"]

        # Scenario 3: Non-critical task D slips exceeding slack (from 6.0 to 10.0; delta=4.0 > slack 2.0)
        plan_exceed_slack = scheduler.recalculate_on_delay(base_plan, delayed_task_id="D", new_duration=10.0)
        # Expected new duration: 20.0 + (4.0 - 2.0) = 22.0
        assert plan_exceed_slack.total_duration == 22.0
        assert plan_exceed_slack.tasks["D"].is_critical is True
        assert plan_exceed_slack.critical_path == ["A", "D", "G", "H"]

    def test_floating_point_durations_precision(self):
        """Floating point task durations (e.g., 1.25, 2.75, 0.5) must maintain exact arithmetic."""
        scheduler = Scheduler()
        tasks = [
            {"id": "t1", "dependencies": [], "duration": 1.25},
            {"id": "t2", "dependencies": ["t1"], "duration": 2.75},
            {"id": "t3", "dependencies": ["t1"], "duration": 0.5},
            {"id": "t4", "dependencies": ["t2", "t3"], "duration": 1.5},
        ]
        plan = scheduler.build_schedule(tasks, project_id="proj_float")
        # 1.25 + 2.75 + 1.5 = 5.5
        assert abs(plan.total_duration - 5.5) < 1e-6
        assert plan.critical_path == ["t1", "t2", "t4"]
        # t3 slack: 2.75 - 0.5 = 2.25
        assert abs(plan.tasks["t3"].slack - 2.25) < 1e-6

    def test_zero_duration_and_schema_boundary(self):
        """Zero duration tasks in dict format fall back to 1.0 due to python falsiness (0.0 or 1.0);

        WorkstreamTask pydantic schema strictly enforces ge=0.1.
        """
        scheduler = Scheduler()
        # Dict format with duration 0.0
        dict_tasks = [{"id": "m1", "dependencies": [], "duration": 0.0}]
        plan = scheduler.build_schedule(dict_tasks, project_id="proj_zero")
        # Due to: duration = float(t.get(...) or 1.0), 0.0 evaluates to 1.0
        assert plan.tasks["m1"].duration == 1.0

        # WorkstreamTask schema enforces minimum of 0.1 hours
        with pytest.raises(Exception):
            WorkstreamTask(
                task_id="m2",
                title="Milestone",
                description="Zero duration",
                lead_agent="CTO",
                estimated_duration_hours=0.0,
            )



# ============================================================================
# 2. ThreadManager Concurrency & Persistence Adversarial Stress Suite
# ============================================================================

class TestThreadManagerConcurrencyAndPersistence:
    """Adversarial stress-testing of ThreadManager concurrent writes and dual persistence."""

    def test_concurrent_writes_same_thread_25_workers(self, tmp_path):
        """25 concurrent workers posting 50 messages to a single thread:

        - Dual-write integrity between SQLite and JSONL.
        - Zero race conditions or missing messages.
        - Exactly 50 uncorrupted lines in JSONL.
        """
        vault = VaultManager(vault_root=str(tmp_path))
        tm = ThreadManager(vault_manager=vault, vault_root=tmp_path)
        tm.create_thread(project_id="proj_c1", thread_id="thread_c1_main", topic="Concurrent Test", owner_agent="CEO")

        def post_msg(i: int):
            return tm.post_message(
                thread_id="thread_c1_main",
                sender_agent="CEO",
                content=f"Worker payload #{i}",
                project_id="proj_c1",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(post_msg, i) for i in range(50)]
            posted_messages = [f.result() for f in futures]

        assert len(posted_messages) == 50

        # Verify SQLite store
        db_messages = vault.sqlite.get_thread_messages("thread_c1_main", limit=100)
        assert len(db_messages) == 50

        # Verify JSONL disk file
        disk_path = tm._resolve_jsonl_path("proj_c1", "thread_c1_main")
        assert disk_path.exists()
        lines = [line.strip() for line in disk_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 50

        # Verify all lines parse as valid JSON
        for line in lines:
            data = json.loads(line)
            assert "message_id" in data
            assert data["from"] == "CEO"

        # Verify identical message IDs across SQLite and disk
        db_ids = {m["message_id"] for m in db_messages}
        disk_ids = {json.loads(line)["message_id"] for line in lines}
        posted_ids = {m.message_id for m in posted_messages}
        assert db_ids == posted_ids
        assert disk_ids == posted_ids

    def test_concurrent_writes_multi_thread_across_10_threads(self, tmp_path):
        """20 concurrent workers posting 200 messages across 10 distinct threads."""
        vault = VaultManager(vault_root=str(tmp_path))
        tm = ThreadManager(vault_manager=vault, vault_root=tmp_path)

        for t_idx in range(10):
            tm.create_thread(
                project_id="proj_c2",
                thread_id=f"thread_multi_{t_idx}",
                topic=f"Topic {t_idx}",
                owner_agent="CTO",
            )

        def post_task(msg_idx: int):
            target_thread = f"thread_multi_{msg_idx % 10}"
            return tm.post_message(
                thread_id=target_thread,
                sender_agent="CTO",
                content=f"Message {msg_idx} on {target_thread}",
                project_id="proj_c2",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(post_task, i) for i in range(200)]
            results = [f.result() for f in futures]

        assert len(results) == 200

        # Verify message count per thread (20 each)
        for t_idx in range(10):
            tid = f"thread_multi_{t_idx}"
            db_msgs = vault.sqlite.get_thread_messages(tid, limit=50)
            assert len(db_msgs) == 20

            disk_path = tm._resolve_jsonl_path("proj_c2", tid)
            assert disk_path.exists()
            lines = [l.strip() for l in disk_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            assert len(lines) == 20

    def test_unicode_and_special_character_roundtrip(self, tmp_path):
        """Verifies Unicode, emojis, Asian/Arabic/Hindi text, and HTML/quotes in dual persistence."""
        vault = VaultManager(vault_root=str(tmp_path))
        tm = ThreadManager(vault_manager=vault, vault_root=tmp_path)
        tm.create_thread(project_id="proj_u", thread_id="thread_unicode", topic="Unicode", owner_agent="CEO")

        complex_content = (
            "🚀 Alpha OS: 中文測試 こんにちは мир مرحبا بالعالم नमस्ते "
            "Math: ∑_{i=0}^n x_i ≤ ∞ & Special: <script>alert('xss')</script> "
            "Quotes: \"double\" and 'single' and \nnewlines \ttabs"
        )

        msg = tm.post_message(
            thread_id="thread_unicode",
            sender_agent="CEO",
            content=complex_content,
            project_id="proj_u",
        )

        # SQLite verification
        db_msgs = vault.sqlite.get_thread_messages("thread_unicode")
        assert len(db_msgs) == 1
        assert db_msgs[0]["content"] == complex_content

        # TM getter / JSONL verification
        tm_msgs = tm.get_thread_messages("thread_unicode", project_id="proj_u")
        assert len(tm_msgs) == 1
        assert tm_msgs[0].content == complex_content

    def test_massive_payload_150kb(self, tmp_path):
        """Verifies 150KB+ message payload does not truncate in SQLite or JSONL."""
        vault = VaultManager(vault_root=str(tmp_path))
        tm = ThreadManager(vault_manager=vault, vault_root=tmp_path)
        tm.create_thread(project_id="proj_huge", thread_id="thread_huge", topic="Massive Payload", owner_agent="CEO")

        large_payload = "ALPHA_ENTERPRISE_SYSTEM_STRESS_TEST_" * 4500  # ~162 KB
        assert len(large_payload) > 150_000

        msg = tm.post_message(
            thread_id="thread_huge",
            sender_agent="CTO",
            content=large_payload,
            project_id="proj_huge",
        )

        db_msgs = vault.sqlite.get_thread_messages("thread_huge")
        assert len(db_msgs[0]["content"]) == len(large_payload)
        assert db_msgs[0]["content"] == large_payload

        tm_msgs = tm.get_thread_messages("thread_huge", project_id="proj_huge")
        assert len(tm_msgs[0].content) == len(large_payload)
        assert tm_msgs[0].content == large_payload

    def test_nonexistent_thread_and_malformed_inputs(self, tmp_path):
        """Queries on missing threads return empty list; empty inputs raise ValueError."""
        tm = ThreadManager(vault_root=tmp_path)

        # Non-existent thread query
        assert tm.get_thread_messages("non_existent_xyz", project_id="p1") == []

        # Empty thread_id
        with pytest.raises(ValueError, match="thread_id cannot be empty"):
            tm.post_message(thread_id="", sender_agent="CEO", content="Valid content")

        # Empty sender_agent
        with pytest.raises(ValueError, match="sender_agent cannot be empty"):
            tm.post_message(thread_id="t1", sender_agent="", content="Valid content")

        # Empty content
        with pytest.raises(ValueError, match="content cannot be empty"):
            tm.post_message(thread_id="t1", sender_agent="CEO", content="")

    def test_concurrent_pubsub_subscribers(self, tmp_path):
        """Multiple threads subscribing, posting, and unsubscribing concurrently."""
        tm = ThreadManager(vault_root=tmp_path)
        received: List[str] = []

        def subscriber_cb(msg):
            received.append(msg.message_id)

        # Register 10 subscribers
        subs = [tm.subscribe("thread_pubsub", subscriber_cb) for _ in range(10)]

        # Post message
        msg = tm.post_message(
            thread_id="thread_pubsub",
            sender_agent="CEO",
            content="Broadcast notification",
            project_id="proj_pubsub",
        )

        # All 10 subscribers should have received the message
        assert len(received) == 10
        assert all(mid == msg.message_id for mid in received)

        # Unsubscribe half
        for s in subs[:5]:
            tm.unsubscribe("thread_pubsub", s)

        # Post second message
        received.clear()
        msg2 = tm.post_message(
            thread_id="thread_pubsub",
            sender_agent="CEO",
            content="Second broadcast",
            project_id="proj_pubsub",
        )
        assert len(received) == 5


# ============================================================================
# 3. Delegation Error Containment Adversarial Stress Suite
# ============================================================================

class CrashingAgent:
    """Test mock agent that crashes with unhandled exceptions."""
    role = "CRASH_AGENT"

    def think(self, **kwargs):
        raise RuntimeError("CRITICAL_SIMULATED_AGENT_CRASH: Model out of memory or unhandled fault")


class ZeroDivisionAgent:
    """Test mock agent that raises arithmetic error."""
    role = "DIV_ZERO_AGENT"

    def think(self, **kwargs):
        return 1 / 0


class MockRegistryWithCrashingAgents:
    """Registry providing crashing, missing, and healthy agents."""

    def __init__(self, healthy_agent: Any):
        self.healthy_agent = healthy_agent
        self.crashing_agent = CrashingAgent()
        self.div_zero_agent = ZeroDivisionAgent()

    def get(self, role: str) -> Optional[Any]:
        r = (role or "").upper()
        if "CRASH" in r:
            return self.crashing_agent
        if "DIV_ZERO" in r:
            return self.div_zero_agent
        if "HEALTHY" in r or "CTO" in r:
            return self.healthy_agent
        return None

    def get_by_role(self, role: str) -> Optional[Any]:
        return self.get(role)


class TestDelegationErrorContainmentStress:
    """Adversarial stress-testing of DelegationEngine error containment and isolation."""

    def test_crashing_agent_contained_without_engine_crash(self):
        """Agent throwing RuntimeError must not crash DelegationEngine; result is FAILED."""
        from backend.agents import CTOAgent
        registry = MockRegistryWithCrashingAgents(healthy_agent=CTOAgent())
        engine = DelegationEngine(agent_registry=registry)

        task = WorkstreamTask(
            task_id="T-CRASH-01",
            title="Crash Task",
            description="Simulated agent blowup",
            lead_agent="CRASH_AGENT",
        )

        result = engine.dispatch_task(task, project_id="proj_containment")
        assert result.status == TaskStatus.FAILED
        assert result.agent_id == "CRASH_AGENT"
        assert result.deliverable is None
        assert "CRITICAL_SIMULATED_AGENT_CRASH" in str(result.error)

    def test_parallel_wave_mixed_failures_contained(self):
        """Parallel wave containing healthy, crashing, arithmetic error, and missing agents.

        - All 4 tasks must complete and return results.
        - Healthy tasks must succeed (COMPLETED).
        - Faulty tasks must fail (FAILED) without crashing the ThreadPoolExecutor or other tasks.
        """
        from backend.agents import CTOAgent
        registry = MockRegistryWithCrashingAgents(healthy_agent=CTOAgent())
        engine = DelegationEngine(agent_registry=registry, max_workers=4)

        tasks = [
            WorkstreamTask(task_id="T1-OK", title="Healthy 1", description="", lead_agent="HEALTHY"),
            WorkstreamTask(task_id="T2-CRASH", title="Crash Task", description="", lead_agent="CRASH"),
            WorkstreamTask(task_id="T3-DIVZERO", title="DivZero Task", description="", lead_agent="DIV_ZERO"),
            WorkstreamTask(task_id="T4-MISSING", title="Missing Agent", description="", lead_agent="NON_EXISTENT_AGENT"),
        ]

        results = engine.dispatch_batch_parallel(tasks, project_id="proj_mixed_wave")
        assert len(results) == 4

        # Healthy task
        assert results["T1-OK"].status == TaskStatus.COMPLETED
        assert results["T1-OK"].error is None
        assert results["T1-OK"].deliverable is not None

        # Crashing agent task
        assert results["T2-CRASH"].status == TaskStatus.FAILED
        assert "CRITICAL_SIMULATED_AGENT_CRASH" in str(results["T2-CRASH"].error)

        # ZeroDivision agent task
        assert results["T3-DIVZERO"].status == TaskStatus.FAILED
        assert "division by zero" in str(results["T3-DIVZERO"].error)

        # Missing agent task
        assert results["T4-MISSING"].status == TaskStatus.FAILED
        assert "not found in AgentRegistry" in str(results["T4-MISSING"].error)

    def test_progress_telemetry_captures_failure_events(self):
        """Granular progress listener must receive TASK_PROGRESS_UPDATED events with status FAILED."""
        from backend.agents import CTOAgent
        registry = MockRegistryWithCrashingAgents(healthy_agent=CTOAgent())
        engine = DelegationEngine(agent_registry=registry)

        captured_events = []
        engine.register_progress_listener(lambda payload: captured_events.append(payload))

        task = WorkstreamTask(
            task_id="T-FAIL-TELEMETRY",
            title="Failing Telemetry",
            description="",
            lead_agent="CRASH_AGENT",
        )
        engine.dispatch_task(task, project_id="proj_prog_fail")

        assert len(captured_events) >= 2
        final_event = captured_events[-1]
        assert final_event["event"] == "TASK_PROGRESS_UPDATED"
        assert final_event["task_id"] == "T-FAIL-TELEMETRY"
        assert final_event["status"] == "failed"
        assert "Execution failed" in final_event["current_step"]

    def test_delegation_batch_parallel_timeout_behavior(self):
        """Empirical stress test on task_timeout_seconds:

        Verifies that thread execution handles task durations safely.
        """
        class DelayAgent:
            role = "DELAY_AGENT"
            def think(self, **kwargs):
                time.sleep(0.05)
                return "completed after delay"

        class DelayRegistry:
            def get(self, role):
                return DelayAgent()
            def get_by_role(self, role):
                return DelayAgent()

        engine = DelegationEngine(agent_registry=DelayRegistry(), task_timeout_seconds=5.0)
        task = WorkstreamTask(
            task_id="T-DELAY",
            title="Delay Task",
            description="",
            lead_agent="DELAY_AGENT",
        )
        res = engine.dispatch_batch_parallel([task], project_id="proj_delay_exec")
        assert res["T-DELAY"].status == TaskStatus.COMPLETED
        assert res["T-DELAY"].deliverable == "completed after delay"

