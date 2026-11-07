"""Alpha/tests/agents/adversarial_challenge_m3_r2.py - Milestone 3 Round 2 Empirical Adversarial Challenge.

Empirical verification harness targeting:
1. Multi-Breach Simultaneous Adjudication: 2, 3, and 4 simultaneous critical breaches.
2. Domain Conflict Detection Surface: Verification of non-CFO/non-CLO critical blocker detection (CTO architecture, CMO security).
3. Fault-Tolerant Delegation: delegate_task(task_type, None), (None, None), ("", {}), (None, {}), and malformed types.
4. Extreme Input Stress: ingest_goal with 120k+ chars, whitespace, None; synthesize with 100k+ char payloads and malformed report structures.
5. Binary Founder Options Preservation: verification of discrete founder_escalations, composite founder_escalation, and unified_briefing_md formatting.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure Alpha root is on sys.path
ALPHA_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALPHA_ROOT))
os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

from backend.agents.base_agent import BaseExecutiveAgent
from backend.agents.ceo import CEOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


class AdversarialTestResult:
    def __init__(self, name: str, passed: bool, bug_detected: bool, details: str, elapsed_ms: float = 0.0):
        self.name = name
        self.passed = passed
        self.bug_detected = bug_detected
        self.details = details
        self.elapsed_ms = elapsed_ms


class AdversarialChallengeM3R2:
    def __init__(self):
        self.results: List[AdversarialTestResult] = []
        self.temp_dir: Optional[Path] = None
        self.vault: Optional[VaultManager] = None
        self.router: Optional[ModelRouter] = None

    def setup(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="alpha_adv_m3_r2_"))
        vault_root = self.temp_dir / "vault"
        db_path = str(self.temp_dir / "test.db")
        chroma_path = str(self.temp_dir / "chroma")
        self.vault = VaultManager(vault_root=vault_root, db_path=db_path, chroma_path=chroma_path)

        clients = {
            "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
            "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
            "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
            "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
            "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
        }
        self.router = ModelRouter(clients=clients)

    def teardown(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def record(self, name: str, passed: bool, bug_detected: bool, details: str, elapsed_ms: float = 0.0):
        res = AdversarialTestResult(name, passed, bug_detected, details, elapsed_ms)
        self.results.append(res)
        tag = "[BUG DETECTED]" if bug_detected else ("[PASS]" if passed else "[FAIL]")
        print(f"{tag:14s} | {name} | {details}")

    def run_all(self):
        print("=" * 80)
        print("EMPIRICAL ADVERSARIAL CHALLENGE HARNESS — MILESTONE 3 ITERATION 2")
        print("Target: CEOAgent (Alpha/backend/agents/ceo.py)")
        print("=" * 80)

        # Category 1: Simultaneous Multi-Breach Adjudication (2, 3, 4 Breaches)
        self.test_multi_breach_2_departments()
        self.test_multi_breach_3_departments_detected()
        self.test_multi_breach_4_departments_detected()

        # Category 2: Domain Conflict Detection Surface (CTO Architecture, CMO Brand Security)
        self.test_domain_conflict_detection_cto_cmo()

        # Category 3: Fault-Tolerant Delegation
        self.test_delegate_task_none_context()
        self.test_delegate_task_none_none()
        self.test_delegate_task_empty_dict()
        self.test_delegate_task_non_dict_context()
        self.test_delegate_task_custom_override()

        # Category 4: Extreme Input Stress
        self.test_ingest_goal_empty_and_whitespace()
        self.test_ingest_goal_none()
        self.test_ingest_goal_massive_payload()
        self.test_synthesize_massive_reports()
        self.test_synthesize_empty_and_malformed_reports()

        # Category 5: Founder Escalation Presentation & Options Integrity
        self.test_founder_briefing_markdown_structure()

        print("=" * 80)
        passed_count = sum(1 for r in self.results if r.passed)
        bugs_count = sum(1 for r in self.results if r.bug_detected)
        failed_count = sum(1 for r in self.results if not r.passed and not r.bug_detected)
        total = len(self.results)
        print(f"SUMMARY: {total} tests executed. {passed_count} PASSED, {bugs_count} BUGS DETECTED, {failed_count} FAILED.")
        print("=" * 80)

    # ========================================================================
    # Category 1: Simultaneous Multi-Breach Adjudication
    # ========================================================================

    def test_multi_breach_2_departments(self):
        """Test 2 simultaneous critical breaches: CFO budget overrun + CLO legal blocker."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        reports = [
            {"role": "CTO", "summary": "Core infrastructure functional."},
            {
                "role": "CFO",
                "summary": "Monthly cloud infrastructure spending audit.",
                "budget_breach": True,
                "status": "over_budget",
                "breach_details": "Critical budget overrun: $15,000 spent against $10,000 allocated monthly budget.",
            },
            {
                "role": "CLO",
                "summary": "Third-party dependency license audit.",
                "risk": "critical",
                "license_violation": True,
                "risk_details": "Critical legal blocker: GPL-3.0 license contamination identified in core distribution.",
            },
        ]
        res = ceo.synthesize(reports, project_id="proj_adv_2breaches")
        elapsed = (time.perf_counter() - t0) * 1000

        # Assertions
        status_ok = res.get("status") == "escalation_required"
        conflicts_count = len(res.get("conflicts_detected", [])) == 2
        f_escs = res.get("founder_escalations", [])
        escs_count = len(f_escs) == 2
        depts_in_escs = {e.get("department") for e in f_escs}
        depts_ok = depts_in_escs == {"CFO", "CLO"}

        comp_esc = res.get("founder_escalation") or {}
        comp_issue = comp_esc.get("issue", "")
        both_issues_in_comp = "$15,000" in comp_issue and "GPL-3.0" in comp_issue
        both_in_departments = set(comp_esc.get("departments", [])) == {"CFO", "CLO"}

        md = res.get("unified_briefing_md", "")
        md_has_both = "$15,000" in md and "GPL-3.0" in md
        md_has_blockers = "Critical Blocker 1" in md and "Critical Blocker 2" in md
        md_has_options = "Options for Founder (Aman Jain)" in md

        all_ok = (status_ok and conflicts_count and escs_count and depts_ok and 
                  both_issues_in_comp and both_in_departments and md_has_both and md_has_blockers and md_has_options)

        bug = not (both_issues_in_comp and escs_count and md_has_both)
        self.record(
            "Multi-Breach (2 depts: CFO + CLO)",
            all_ok,
            bug,
            f"Escalations: {len(f_escs)}, Comp issue preserved both: {both_issues_in_comp}, MD blockers formatted: {md_has_blockers}",
            elapsed,
        )

    def test_multi_breach_3_departments_detected(self):
        """Test 3 simultaneous critical breaches across 3 departments (CFO budget overrun, CLO licensing blocker, CTO compute budget breach)."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        reports = [
            {
                "role": "CFO",
                "summary": "Compute spending spiked.",
                "budget_breach": True,
                "breach_details": "CFO: Unbudgeted cloud infrastructure costs exceeded monthly runway by $45,000.",
            },
            {
                "role": "CLO",
                "summary": "Patent infringement warning received.",
                "risk": "critical",
                "license_violation": True,
                "risk_details": "CLO: Cease and desist letter received regarding vector quantization patents.",
            },
            {
                "role": "CTO",
                "summary": "Dedicated GPU server budget overrun.",
                "budget": True,
                "budget_breach": True,
                "breach_details": "CTO: High-throughput cluster cluster provisioning overrun by $30,000.",
            },
        ]
        res = ceo.synthesize(reports, project_id="proj_adv_3breaches")
        elapsed = (time.perf_counter() - t0) * 1000

        f_escs = res.get("founder_escalations", [])
        escs_count = len(f_escs) == 3
        depts_in_escs = {e.get("department") for e in f_escs}
        depts_ok = depts_in_escs == {"CFO", "CLO", "CTO"}

        comp_esc = res.get("founder_escalation") or {}
        comp_issue = comp_esc.get("issue", "")
        all_in_comp = "$45,000" in comp_issue and "Cease and desist" in comp_issue and "$30,000" in comp_issue

        md = res.get("unified_briefing_md", "")
        md_has_all = "Critical Blocker 1" in md and "Critical Blocker 2" in md and "Critical Blocker 3" in md
        md_options_count = md.count("Options for Founder (Aman Jain)")

        all_ok = escs_count and depts_ok and all_in_comp and md_has_all and (md_options_count >= 3)
        bug = not (escs_count and all_in_comp)
        self.record(
            "Multi-Breach (3 depts: CFO + CLO + CTO)",
            all_ok,
            bug,
            f"Escalations: {len(f_escs)}/3, All 3 in composite: {all_in_comp}, 3 MD blocker sections: {md_has_all}",
            elapsed,
        )

    def test_multi_breach_4_departments_detected(self):
        """Test 4 simultaneous critical breaches across 4 departments (CFO + CLO + CTO + CMO)."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        reports = [
            {
                "role": "CFO",
                "summary": "Runway alert.",
                "budget_breach": True,
                "breach_details": "CFO: Monthly operating runway depleted below emergency threshold ($50,000 breach).",
            },
            {
                "role": "CLO",
                "summary": "Regulatory enforcement action.",
                "risk": "critical",
                "license_violation": True,
                "risk_details": "CLO: Regulatory audit order served alleging unauthorized autonomous trading execution.",
            },
            {
                "role": "CTO",
                "summary": "Database cluster cost spike.",
                "budget": True,
                "budget_breach": True,
                "breach_details": "CTO: Emergency failover instance costs exceeded monthly limits by $20,000.",
            },
            {
                "role": "CMO",
                "summary": "Paid ad campaign copyright infringement notice.",
                "legal": True,
                "risk": "critical",
                "risk_details": "CMO: DMCA takedown issued on active international launch advertising assets.",
            },
        ]
        res = ceo.synthesize(reports, project_id="proj_adv_4breaches")
        elapsed = (time.perf_counter() - t0) * 1000

        f_escs = res.get("founder_escalations", [])
        escs_count = len(f_escs) == 4
        depts_in_escs = {e.get("department") for e in f_escs}
        depts_ok = depts_in_escs == {"CFO", "CLO", "CTO", "CMO"}

        comp_esc = res.get("founder_escalation") or {}
        comp_issue = comp_esc.get("issue", "")
        all_in_comp = ("runway" in comp_issue.lower() and "regulatory" in comp_issue.lower() and 
                       "$20,000" in comp_issue.lower() and "dmca" in comp_issue.lower())

        md = res.get("unified_briefing_md", "")
        md_has_4_blockers = all(f"Critical Blocker {i}" in md for i in range(1, 5))
        md_has_all_depts = all(f"[{d}]" in md for d in ["CFO", "CLO", "CTO", "CMO"])

        # Check binary options for all 4 departments in composite
        comp_opts = comp_esc.get("decision_options", [])
        opts_count_ok = len(comp_opts) == 8

        all_ok = escs_count and depts_ok and all_in_comp and md_has_4_blockers and md_has_all_depts and opts_count_ok
        bug = not (escs_count and all_in_comp)
        self.record(
            "Multi-Breach (4 depts: CFO + CLO + CTO + CMO)",
            all_ok,
            bug,
            f"Escalations: {len(f_escs)}/4, 4 in composite: {all_in_comp}, 8 composite options: {len(comp_opts)}==8, 4 MD blockers: {md_has_4_blockers}",
            elapsed,
        )

    # ========================================================================
    # Category 2: Domain Conflict Detection Surface (CTO Architecture, CMO Brand Security)
    # ========================================================================

    def test_domain_conflict_detection_cto_cmo(self):
        """Stress-test _detect_conflicts with non-budget/non-legal domain blockers (CTO architecture, CMO brand security)."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        reports = [
            {
                "role": "CTO",
                "summary": "Technical architecture blocker.",
                "risk": "critical",
                "risk_details": "CTO: Zero-day RCE vulnerability in gateway requires immediate founder shutdown authorization.",
            },
            {
                "role": "CMO",
                "summary": "Brand security blocker.",
                "risk": "critical",
                "risk_details": "CMO: Executive social media account hijacked broadcasting unauthorized market statements.",
            },
        ]
        conflicts = ceo._detect_conflicts(reports)
        res = ceo.synthesize(reports, project_id="proj_adv_domain_blockers")
        elapsed = (time.perf_counter() - t0) * 1000

        detected_roles = {c.get("source") for c in conflicts}
        # Evaluation: In CEOAgent._detect_conflicts (lines 443-482), critical conflict detection is hardcoded to:
        # `if role == "CFO" or "budget" in r` and `if role == "CLO" or "legal" in r`.
        # When CTO and CMO report critical domain blockers without specifying "budget" or "legal",
        # they are NOT detected by _detect_conflicts and are silently dropped from synthesis.
        detected = len(conflicts) == 2 and detected_roles == {"CTO", "CMO"}
        details = (
            f"Detected: {len(conflicts)}/2 conflicts (roles: {detected_roles}). "
            "Note: _detect_conflicts currently limits critical checks to CFO/budget and CLO/legal; "
            "CTO/CMO domain blockers without 'budget' or 'legal' keys are not evaluated."
        )
        # We record this as an empirical observation: passed=False if not detected, but bug_detected=False
        # because the current project contract for CEOAgent Feature 16 specifically specifies CFO budget and CLO legal vetoes.
        self.record("Domain Detection: CTO Architecture & CMO Brand Security", detected, False, details, elapsed)

    # ========================================================================
    # Category 3: Fault-Tolerant Delegation
    # ========================================================================

    def test_delegate_task_none_context(self):
        """Test delegate_task(task_type, None) - must not raise AttributeError or unhandled exception."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        try:
            res = ceo.delegate_task("technical_architecture", None)
            passed = (isinstance(res, dict) and 
                      res.get("target_agent") == "CTO" and 
                      res.get("status") == "dispatched" and 
                      "formatted_brief" in res and
                      res.get("project_id") == "default_project")
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('CTO_task', None)", passed, not passed, f"Returned valid brief for {res.get('target_agent')}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('CTO_task', None)", False, True, f"Raised exception: {e}", elapsed)

    def test_delegate_task_none_none(self):
        """Test delegate_task(None, None) - both arguments None."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        try:
            res = ceo.delegate_task(None, None)
            passed = (isinstance(res, dict) and 
                      res.get("target_agent") == "COO" and 
                      res.get("status") == "dispatched" and 
                      "formatted_brief" in res)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task(None, None)", passed, not passed, f"Gracefully defaulted to {res.get('target_agent')}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task(None, None)", False, True, f"Raised exception: {e}", elapsed)

    def test_delegate_task_empty_dict(self):
        """Test delegate_task('', {}) - empty string task_type and empty dict context."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        try:
            res = ceo.delegate_task("", {})
            passed = (isinstance(res, dict) and 
                      res.get("target_agent") == "COO" and 
                      res.get("status") == "dispatched")
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('', {})", passed, not passed, f"Gracefully routed to {res.get('target_agent')}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('', {})", False, True, f"Raised exception: {e}", elapsed)

    def test_delegate_task_non_dict_context(self):
        """Test delegate_task('gtm_marketing', 'invalid_string_context') - non-dict context object."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        try:
            res = ceo.delegate_task("gtm_marketing", "invalid_context_type")  # type: ignore
            passed = (isinstance(res, dict) and 
                      res.get("target_agent") == "CMO" and 
                      res.get("status") == "dispatched")
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('gtm', str)", passed, not passed, f"Gracefully handled non-dict context, routed to {res.get('target_agent')}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Fault-Tolerant Delegation: delegate_task('gtm', str)", False, True, f"Raised exception: {e}", elapsed)

    def test_delegate_task_custom_override(self):
        """Test determine_department with target_role override."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        try:
            dept = ceo.determine_department("financial_budget", {"target_role": "CHRO"})
            passed = dept == "CHRO"
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Department Determination: target_role override", passed, not passed, f"Target role override correctly honored: {dept}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Department Determination: target_role override", False, True, f"Raised exception: {e}", elapsed)

    # ========================================================================
    # Category 4: Extreme Input Stress
    # ========================================================================

    def test_ingest_goal_empty_and_whitespace(self):
        """Test ingest_goal with empty string and whitespace variations - must raise ValueError."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        passed_all = True
        for invalid_input in ["", "   ", "\t\n  \r\n"]:
            try:
                ceo.ingest_goal(invalid_input)
                passed_all = False
                break
            except ValueError:
                pass
            except Exception:
                passed_all = False
                break
        elapsed = (time.perf_counter() - t0) * 1000
        self.record("Input Validation: ingest_goal('', '  ', '\\t\\n')", passed_all, not passed_all, "Strictly rejected empty/whitespace goals with ValueError", elapsed)

    def test_ingest_goal_none(self):
        """Test ingest_goal(None) - must raise ValueError."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        passed = False
        try:
            ceo.ingest_goal(None)  # type: ignore
        except ValueError:
            passed = True
        except Exception:
            passed = False
        elapsed = (time.perf_counter() - t0) * 1000
        self.record("Input Validation: ingest_goal(None)", passed, not passed, "Strictly rejected None goal with ValueError", elapsed)

    def test_ingest_goal_massive_payload(self):
        """Test ingest_goal with 120,000+ characters payload."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        massive_text = "Deploy comprehensive AI executive system " + ("Enterprise directive token padding " * 3500)
        assert len(massive_text) > 120_000

        try:
            res = ceo.ingest_goal(massive_text, project_id="proj_adv_massive_goal")
            passed = (isinstance(res, dict) and 
                      res.get("status") == "ingested" and 
                      "goal_id" in res and 
                      len(res.get("objectives", [])) >= 1 and 
                      len(res.get("assigned_roles", [])) >= 1)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Extreme Input Stress: ingest_goal(120k+ chars)", passed, not passed, f"Successfully parsed {len(res.get('assigned_roles', []))} roles, goal_id: {res.get('goal_id')}", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Extreme Input Stress: ingest_goal(120k+ chars)", False, True, f"Failed with exception: {e}", elapsed)

    def test_synthesize_massive_reports(self):
        """Test synthesize with massive report contents (100k+ chars in report summaries)."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        huge_summary = "Detailed architectural deliverable specifications: " + ("Component analysis and test benchmarks " * 3000)
        assert len(huge_summary) > 100_000

        reports = [
            {"role": "CTO", "summary": huge_summary},
            {"role": "CFO", "summary": "Zero cost maintenance approved."},
        ]
        try:
            res = ceo.synthesize(reports, project_id="proj_adv_huge_synth")
            passed = (isinstance(res, dict) and 
                      res.get("status") == "completed" and 
                      res.get("reports_analyzed") == 2 and 
                      "unified_briefing_md" in res and
                      len(res.get("unified_briefing_md", "")) > 1000)
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Extreme Input Stress: synthesize(100k+ chars)", passed, not passed, f"Synthesized without memory failure. Briefing length: {len(res.get('unified_briefing_md', ''))} chars", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record("Extreme Input Stress: synthesize(100k+ chars)", False, True, f"Failed with exception: {e}", elapsed)

    def test_synthesize_empty_and_malformed_reports(self):
        """Test synthesize with empty list and malformed reports (missing role, missing summary, irregular dicts)."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)

        # 1. Empty list
        res_empty = ceo.synthesize([], project_id="proj_empty")
        empty_ok = (res_empty.get("status") == "completed" and 
                    res_empty.get("reports_analyzed") == 0 and 
                    res_empty.get("founder_escalation") is None and 
                    res_empty.get("founder_escalations") == [])

        # 2. Malformed report list (missing keys, non-standard types)
        malformed_reports = [
            {},  # empty dict
            {"irregular_key": "some_value"},  # missing role and summary
            {"role": None, "summary": None},  # None values
            {"agent_id": "CUSTOM_AGENT", "data": {"nested": "value"}},  # non-standard structure
        ]
        res_malformed = ceo.synthesize(malformed_reports, project_id="proj_malformed")
        malformed_ok = (res_malformed.get("status") == "completed" and 
                        res_malformed.get("reports_analyzed") == 4 and 
                        "unified_briefing_md" in res_malformed)

        passed = empty_ok and malformed_ok
        elapsed = (time.perf_counter() - t0) * 1000
        self.record("Malformed & Empty Inputs: synthesize([], [{}...])", passed, not passed, f"Empty list handled: {empty_ok}, Malformed reports handled: {malformed_ok}", elapsed)

    # ========================================================================
    # Category 5: Founder Escalation Presentation & Options Integrity
    # ========================================================================

    def test_founder_briefing_markdown_structure(self):
        """Verify unified_briefing_md formats every blocker with binary options for Founder Aman Jain."""
        t0 = time.perf_counter()
        ceo = CEOAgent(vault_manager=self.vault, model_router=self.router)
        reports = [
            {
                "role": "CFO",
                "summary": "Infrastructure spend audit.",
                "budget_breach": True,
                "breach_details": "Budget exceeded: $25k on $10k allocation.",
            },
            {
                "role": "CLO",
                "summary": "Licensing review.",
                "risk": "critical",
                "license_violation": True,
                "risk_details": "AGPL-3.0 copyleft code detected in proprietary binary.",
            },
        ]
        res = ceo.synthesize(reports, project_id="proj_briefing_formatting")
        elapsed = (time.perf_counter() - t0) * 1000

        md = res.get("unified_briefing_md", "")
        checks = [
            ("Founder Escalation Header", "## ⚠️ Founder Escalation Required (Tier 3 Decision)" in md),
            ("Breach Count Banner", "**Total Critical Breaches Detected:** 2" in md),
            ("Blocker 1 Header", "### Critical Blocker 1: [CFO]" in md),
            ("Blocker 1 Issue", "Budget exceeded: $25k on $10k allocation." in md),
            ("Blocker 1 Recommendation", "**CEO Recommendation:**" in md),
            ("Blocker 1 Options Header", "**Options for Founder (Aman Jain) - CFO:**" in md),
            ("Blocker 1 Option A", "  - [CFO-A]" in md),
            ("Blocker 1 Option B", "  - [CFO-B]" in md),
            ("Blocker 2 Header", "### Critical Blocker 2: [CLO]" in md),
            ("Blocker 2 Issue", "AGPL-3.0 copyleft code detected in proprietary binary." in md),
            ("Blocker 2 Options Header", "**Options for Founder (Aman Jain) - CLO:**" in md),
            ("Blocker 2 Option A", "  - [CLO-A]" in md),
            ("Blocker 2 Option B", "  - [CLO-B]" in md),
            ("Sign-off Footer", "*Synthesized by Alpha CEO | Audit Status: PENDING_CAO_AUDIT*" in md),
        ]

        passed = all(check[1] for check in checks)
        missing = [check[0] for check in checks if not check[1]]
        details = "All 14 markdown structural checkpoints verified" if passed else f"Missing checkpoints: {missing}"
        self.record("Founder Presentation: Briefing Markdown Structure", passed, not passed, details, elapsed)


if __name__ == "__main__":
    harness = AdversarialChallengeM3R2()
    harness.setup()
    try:
        harness.run_all()
    finally:
        harness.teardown()
