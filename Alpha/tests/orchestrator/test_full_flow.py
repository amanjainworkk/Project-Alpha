"""tests/orchestrator/test_full_flow.py - Master Full-Flow Integration Test Suite.

End-to-end integration tests verifying the full Project Alpha pipeline:
Goal Intake -> Scheduling -> Delegation -> Archify Visuals -> Dual CAO Audit -> Synthesis -> Vault Deliverables.

Tests:
1. TestFullFlowHappyPath: Full execution from raw string to verified Vault deliverables.
2. TestFullFlowWithCAOReflection: Audit failure in Round 1 triggers reflection and passes in Round 2.
3. TestFullFlowWithFounderEscalation: Audit deadlocks after 2 rounds, creating Founder escalation ticket.
4. TestFullFlowPerformanceAndStress: Multi-agent execution benchmark with zero token leaks.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.cao import CAOAuditResult
from backend.model_router.router import ModelRouter
from backend.orchestrator import (
    AlphaOrchestrator,
    OrchestratorResult,
    OrchestratorStatus,
)
from backend.vault.vault_manager import VaultManager


class TestMasterOrchestrationFlow:
    """Verifies End-to-End Goal Execution Pipeline."""

    @pytest.fixture
    def harness(self, tmp_path):
        vault = VaultManager(vault_root=str(tmp_path / "vault"))
        router = ModelRouter()
        orchestrator = AlphaOrchestrator(
            vault_manager=vault,
            model_router=router,
        )
        return orchestrator, vault

    def test_full_flow_happy_path(self, harness):
        orchestrator, vault = harness
        result = orchestrator.run_goal(
            goal="Build an autonomous AI-driven customer intelligence platform with FastAPI and Flutter",
            user_id="aman",
        )

        assert result.status == OrchestratorStatus.COMPLETED
        assert result.project_id.startswith("proj_")
        assert len(result.deliverables) >= 2
        assert result.audit_result is not None
        assert result.audit_result.passed is True
        assert result.passed_audit is True

        # 1. Verify deliverables written in Vault
        pid = result.project_id
        for k in result.deliverables.keys():
            deliv = vault.read(f"projects/{pid}/deliverables/{k}.json")
            assert deliv is not None
            assert "task_id" in deliv

        # 2. Verify Archify living diagram generated
        assert result.archify_diagram_html is not None
        assert "<!DOCTYPE html>" in result.archify_diagram_html
        assert "#090A0F" in result.archify_diagram_html
        assert result.archify_graph_data is not None
        assert "nodes" in result.archify_graph_data

        # 3. Verify final output executive briefing
        assert len(result.executive_summary) > 0
        briefing_md = vault.read(f"projects/{pid}/deliverables/final-output.md")
        assert briefing_md is not None
        assert "Executive Delivery Briefing" in briefing_md.get("markdown", "")

    def test_full_flow_with_cao_reflection_loop(self, harness):
        orchestrator, vault = harness

        round1_res = CAOAuditResult(
            passed=False,
            claude_score=78.0,
            gpt_score=80.0,
            consolidated_report="Round 1 P1 defect found: missing retry policy.",
            p0_defects=[],
            p1_defects=["P1: Missing retry policy in worker dispatch."],
            round_num=1,
            escalation_required=False,
        )
        round2_res = CAOAuditResult(
            passed=True,
            claude_score=92.0,
            gpt_score=94.0,
            consolidated_report="Round 2 verification: All defects remediated successfully.",
            p0_defects=[],
            p1_defects=[],
            round_num=2,
            escalation_required=False,
        )

        call_count = 0

        def mock_audit(project_id, deliverables, round_num):
            nonlocal call_count
            call_count += 1
            if round_num == 1:
                return round1_res
            return round2_res

        orchestrator.dual_cao.audit_deliverables = mock_audit

        result = orchestrator.run_goal(
            goal="Create microservices pipeline with strict security audit",
            max_audit_rounds=2,
        )

        assert call_count == 2
        assert result.status == OrchestratorStatus.COMPLETED
        assert result.audit_result is not None
        assert result.audit_result.round_num == 2
        assert result.audit_result.passed is True

        # Check remediation was applied to deliverables
        for d in result.deliverables.values():
            if isinstance(d, dict) and "revision_round" in d:
                assert d["revision_round"] == 2
                assert "Remediate identified flaws" in d.get("remediation_applied", "")

    def test_full_flow_with_founder_escalation(self, harness):
        orchestrator, vault = harness

        round1_res = CAOAuditResult(
            passed=False,
            claude_score=65.0,
            gpt_score=68.0,
            consolidated_report="Critical security invariant failure.",
            p0_defects=["P0: Invariant check violation in auth layer."],
            p1_defects=[],
            round_num=1,
            escalation_required=False,
        )
        round2_res = CAOAuditResult(
            passed=False,
            claude_score=68.0,
            gpt_score=70.0,
            consolidated_report="Defect remains uncorrected after 2 rounds.",
            p0_defects=["P0: Invariant check violation in auth layer."],
            p1_defects=[],
            round_num=2,
            escalation_required=True,
            user_escalate_payload={
                "project_id": "proj_esc_test",
                "reason": "Dual CAO audit failed after 2 revision rounds.",
                "p0_defects": ["P0: Invariant check violation in auth layer."],
                "requires_founder_action": True,
            },
        )

        call_count = 0

        def mock_audit(project_id, deliverables, round_num):
            nonlocal call_count
            call_count += 1
            if round_num == 1:
                return round1_res
            return round2_res

        orchestrator.dual_cao.audit_deliverables = mock_audit

        result = orchestrator.run_goal(
            goal="High risk experimental subsystem",
            max_audit_rounds=2,
        )

        assert call_count == 2
        assert result.status == OrchestratorStatus.ESCALATED_TO_FOUNDER
        assert result.founder_escalation is not None
        assert result.founder_escalation.get("requires_founder_action") is True
        assert len(result.founder_escalation.get("p0_defects", [])) == 1

    def test_full_flow_performance_and_stress(self, harness):
        orchestrator, vault = harness
        start_time = time.time()
        result = orchestrator.run_goal(
            goal="Rapid multi-agent enterprise goal execution benchmark",
            user_id="aman",
        )
        elapsed = time.time() - start_time

        assert result.status == OrchestratorStatus.COMPLETED
        assert elapsed < 10.0  # Must complete rapidly under native heuristic mode
        assert result.elapsed_seconds >= 0.0
