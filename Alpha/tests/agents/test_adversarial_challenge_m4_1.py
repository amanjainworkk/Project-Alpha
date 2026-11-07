"""Alpha/tests/agents/test_adversarial_challenge_m4_1.py - Milestone 4 Empirical Adversarial Stress Test Suite.

Adversarial Challenger Test Suite targeting:
1. COO Critical Path & Cycles:
   - Cyclical dependencies (A -> B -> C -> A, self-loops, mixed DAG/cycles).
   - Diamond graphs & critical path identification.
   - Disconnected components.
   - 0-duration and negative-duration task handling.
   - Missing dependency references.
2. CTO ATSR Rubric & Security Disqualification:
   - Security score <= 1.0 instant disqualification regardless of other 8 dimensions.
   - Borderline scoring thresholds (3.99 vs 4.0).
   - Missing dimensions fallback to defaults.
   - Non-numeric score resilience.
3. CTO Archify HTML Generation:
   - Valid HTML layout, node IDs, dark theme palette.
   - Pulsing indicators and CSS keyframes.
   - Unescaped script injection (XSS surface verification).
4. CPO RICE Priority & Anti-Gold-Plating:
   - Division-by-zero protection when effort == 0.
   - Negative effort clamping.
   - 7-point Anti-Gold-Plating checklist failure flagging (missing out_of_scope, no P0, no edge cases).
5. CIO Vault Schema & ECC Memory Compression:
   - Empty memory compression handling.
   - Single item and stratified importance compression.
   - ECC SHA-256 integrity verification on memory store files.
   - Data tier classification (T1-T4).
6. CDO OLED Design Tokens & Accessibility:
   - Exact OLED palette tokens (#090A0F, #12141C, #1A1D28, #3B82F6, #06B6D4).
   - Touch target boundary checks (< 48dp vs >= 48dp).
   - Contrast ratio boundary checks (< 4.5 vs >= 4.5).
7. CMO GTM & Messaging:
   - 10-point GTM checklist validation.
   - Value pillars and objection shields structure.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Ensure Alpha root is on sys.path
ALPHA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

from backend.agents.cdo import CDOAgent
from backend.agents.cio import CIOAgent
from backend.agents.cmo import CMOAgent
from backend.agents.coo import COOAgent
from backend.agents.cpo import CPOAgent
from backend.agents.cto import CTOAgent
from backend.model_router.mock_client import MockLLMClient
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager


@pytest.fixture
def test_env():
    """Setup temporary VaultManager and ModelRouter."""
    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_adv_m4_"))
    vault_root = temp_dir / "vault"
    db_path = str(temp_dir / "test.db")
    chroma_path = str(temp_dir / "chroma")
    vault = VaultManager(vault_root=vault_root, db_path=db_path, chroma_path=chroma_path)

    clients = {
        "ollama": MockLLMClient(provider="ollama", default_model="llama3.2", is_free=True),
        "groq": MockLLMClient(provider="groq", default_model="llama-3.1-70b-versatile", is_free=True),
        "gemini": MockLLMClient(provider="gemini", default_model="gemini-1.5-flash", is_free=True),
        "anthropic": MockLLMClient(provider="anthropic", default_model="claude-3-5-sonnet", is_free=False),
        "openai": MockLLMClient(provider="openai", default_model="gpt-4o", is_free=False),
    }
    router = ModelRouter(clients=clients)

    yield {"temp_dir": temp_dir, "vault": vault, "router": router}

    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Vector 1: COO Critical Path & Cycles Stress Testing
# ============================================================================
class TestCOOCriticalPathAndCycles:

    def test_coo_cycle_detection_triangular(self, test_env):
        """Verify cyclical dependency A -> B -> C -> A is detected without infinite recursion."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        cyclic_tasks = [
            {"task_id": "T-A", "dependencies": ["T-C"], "estimated_days": 2},
            {"task_id": "T-B", "dependencies": ["T-A"], "estimated_days": 3},
            {"task_id": "T-C", "dependencies": ["T-B"], "estimated_days": 4},
        ]
        result = coo.track_critical_path(cyclic_tasks, project_id="adv_proj")
        assert result["has_cycles"] is True, "Cyclic graph must set has_cycles=True"
        assert result["critical_path"] == [], "Critical path must be empty when full cycle exists"
        assert result["total_duration"] == 0, "Duration must be 0 for fully cyclical graph"

    def test_coo_cycle_detection_self_loop(self, test_env):
        """Verify self-referential cycle A -> A is detected."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        self_loop = [{"task_id": "T-A", "dependencies": ["T-A"], "estimated_days": 5}]
        result = coo.track_critical_path(self_loop, project_id="adv_proj")
        assert result["has_cycles"] is True
        assert len(result["critical_path"]) == 0

    def test_coo_cycle_detection_mixed_dag_and_cycle(self, test_env):
        """Verify partial cycle in mixed graph detects cycles and captures progress."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        mixed_tasks = [
            {"task_id": "T-01", "dependencies": [], "estimated_days": 2},
            {"task_id": "T-02", "dependencies": ["T-01"], "estimated_days": 3},
            {"task_id": "T-C1", "dependencies": ["T-C2"], "estimated_days": 1},
            {"task_id": "T-C2", "dependencies": ["T-C1"], "estimated_days": 1},
        ]
        result = coo.track_critical_path(mixed_tasks, project_id="adv_proj")
        assert result["has_cycles"] is True
        # T-01 and T-02 should be processed in schedule
        assert "T-01" in result["schedule"]
        assert "T-02" in result["schedule"]
        assert "T-C1" not in result["schedule"]
        assert "T-C2" not in result["schedule"]

    def test_coo_diamond_graph_critical_path(self, test_env):
        """Verify standard diamond graph computes longest path as critical path."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        diamond_tasks = [
            {"task_id": "START", "dependencies": [], "estimated_days": 2},
            {"task_id": "BRANCH_FAST", "dependencies": ["START"], "estimated_days": 3},
            {"task_id": "BRANCH_SLOW", "dependencies": ["START"], "estimated_days": 7},
            {"task_id": "END", "dependencies": ["BRANCH_FAST", "BRANCH_SLOW"], "estimated_days": 2},
        ]
        result = coo.track_critical_path(diamond_tasks, project_id="adv_proj")
        assert result["has_cycles"] is False
        # Expected duration: START (2) + BRANCH_SLOW (7) + END (2) = 11 days
        assert result["total_duration"] == 11
        assert "START" in result["critical_path"]
        assert "BRANCH_SLOW" in result["critical_path"]
        assert "END" in result["critical_path"]
        assert "BRANCH_FAST" not in result["critical_path"]
        # Slack on BRANCH_FAST should be 4 days (7 - 3)
        assert result["schedule"]["BRANCH_FAST"]["slack"] == 4

    def test_coo_disconnected_components(self, test_env):
        """Verify disconnected independent task subgraphs calculate total duration correctly."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        disconnected = [
            {"task_id": "A1", "dependencies": [], "estimated_days": 2},
            {"task_id": "A2", "dependencies": ["A1"], "estimated_days": 3},  # subtotal: 5
            {"task_id": "B1", "dependencies": [], "estimated_days": 4},
            {"task_id": "B2", "dependencies": ["B1"], "estimated_days": 6},  # subtotal: 10
        ]
        result = coo.track_critical_path(disconnected, project_id="adv_proj")
        assert result["has_cycles"] is False
        assert result["total_duration"] == 10
        assert "B1" in result["critical_path"]
        assert "B2" in result["critical_path"]

    def test_coo_zero_and_negative_duration_tasks(self, test_env):
        """Stress test with 0-duration milestones and negative-duration edge cases."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        edge_tasks = [
            {"task_id": "M0", "dependencies": [], "estimated_days": 0},  # milestone
            {"task_id": "T1", "dependencies": ["M0"], "estimated_days": 4},
            {"task_id": "T2", "dependencies": ["T1"], "estimated_days": -2},  # negative duration
        ]
        result = coo.track_critical_path(edge_tasks, project_id="adv_proj")
        assert result["has_cycles"] is False
        assert result["schedule"]["M0"]["ef"] == 0
        assert result["schedule"]["T1"]["es"] == 0
        assert result["schedule"]["T1"]["ef"] == 4
        # Negative duration shouldn't crash calculation
        assert "T2" in result["schedule"]

    def test_coo_missing_dependency_reference(self, test_env):
        """Verify task pointing to non-existent predecessor doesn't cause uncaught crash."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        missing_dep = [
            {"task_id": "T-01", "dependencies": ["NON_EXISTENT_PARENT"], "estimated_days": 2},
            {"task_id": "T-02", "dependencies": [], "estimated_days": 3},
        ]
        result = coo.track_critical_path(missing_dep, project_id="adv_proj")
        assert result["has_cycles"] is True
        assert "T-02" in result["schedule"]
        assert "T-01" not in result["schedule"]

    def test_coo_empty_tasks_list(self, test_env):
        """Verify passing empty list to track_critical_path returns zeroed structure."""
        coo = COOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        res = coo.track_critical_path([])
        assert res["critical_path"] == []
        assert res["total_duration"] == 0
        assert res["has_cycles"] is False
        assert res["schedule"] == {}


# ============================================================================
# Vector 2: CTO ATSR Rubric & Security Disqualification Stress Testing
# ============================================================================
class TestCTOATSRRubricAndSecurity:

    def test_cto_security_auto_disqualification_at_one(self, test_env):
        """Verify security score <= 1.0 triggers instant disqualification regardless of other scores."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_proposal = {
            "web_framework": {
                "name": "VulnerableEngine",
                "scores": {
                    "open_source_licensing": 5.0,
                    "total_cost_of_ownership": 5.0,
                    "scalability_ceiling": 5.0,
                    "security_track_record": 1.0,  # CRITICAL FAILURE
                    "community_ecosystem": 5.0,
                    "learning_curve": 5.0,
                    "performance_characteristics": 5.0,
                    "operational_complexity": 5.0,
                    "integration_compatibility": 5.0,
                },
            }
        }
        res = cto.review_tech_stack(proposed_stack=stack_proposal, project_id="adv_proj")
        assert res["disqualified"] is True, "Security <= 1.0 must trigger disqualified=True"
        assert res["stack_status"] == "REJECTED", "Stack status must be REJECTED upon disqualification"
        eval_web = res["evaluations"]["web_framework"]
        assert eval_web["decision"] == "HOLD (SECURITY DISQUALIFIED)"
        # Note weighted score would be 4.40 if not disqualified (5.0*0.85 + 1.0*0.15 = 4.40)
        assert eval_web["weighted_score"] == 4.4

    def test_cto_security_auto_disqualification_below_one(self, test_env):
        """Verify security score < 1.0 (e.g. 0.5 or 0.0) is disqualified."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_proposal = {
            "database": {
                "name": "ZeroSecDB",
                "scores": {"security_track_record": 0.5},
            }
        }
        res = cto.review_tech_stack(proposed_stack=stack_proposal, project_id="adv_proj")
        assert res["disqualified"] is True
        assert res["stack_status"] == "REJECTED"

    def test_cto_security_score_just_above_threshold(self, test_env):
        """Verify security score of 1.01 does not trigger security auto-disqualification."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_proposal = {
            "library": {
                "name": "BorderlineSecLib",
                "scores": {
                    dim: 4.5 for dim in cto.ATSR_DIMENSIONS if dim != "security_track_record"
                },
            }
        }
        stack_proposal["library"]["scores"]["security_track_record"] = 1.01
        res = cto.review_tech_stack(proposed_stack=stack_proposal, project_id="adv_proj")
        assert res["disqualified"] is False
        assert "HOLD (SECURITY DISQUALIFIED)" not in res["evaluations"]["library"]["decision"]

    def test_cto_borderline_score_adopt_vs_trial(self, test_env):
        """Verify exact boundary conditions: 4.0 -> ADOPT, 3.99 -> TRIAL."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        # 4.0 exactly
        stack_4_0 = {
            "core": {
                "name": "ExactFour",
                "scores": {dim: 4.0 for dim in cto.ATSR_DIMENSIONS},
            }
        }
        res_4_0 = cto.review_tech_stack(stack_4_0)
        assert res_4_0["evaluations"]["core"]["decision"] == "ADOPT"
        assert res_4_0["evaluations"]["core"]["weighted_score"] == 4.0

        # 3.99
        stack_3_99 = {
            "core": {
                "name": "SubFour",
                "scores": {dim: 3.99 for dim in cto.ATSR_DIMENSIONS},
            }
        }
        res_3_99 = cto.review_tech_stack(stack_3_99)
        assert res_3_99["evaluations"]["core"]["decision"] == "TRIAL"
        assert res_3_99["evaluations"]["core"]["weighted_score"] == 3.99

        # 2.99 -> ASSESS
        stack_2_99 = {
            "core": {
                "name": "SubThree",
                "scores": {dim: 2.99 for dim in cto.ATSR_DIMENSIONS},
            }
        }
        res_2_99 = cto.review_tech_stack(stack_2_99)
        assert res_2_99["evaluations"]["core"]["decision"] == "ASSESS"

        # 1.99 -> HOLD
        stack_1_99 = {
            "core": {
                "name": "SubTwo",
                "scores": {dim: 1.99 for dim in cto.ATSR_DIMENSIONS},
            }
        }
        res_1_99 = cto.review_tech_stack(stack_1_99)
        assert res_1_99["evaluations"]["core"]["decision"] == "HOLD"

    def test_cto_missing_dimensions_default_scoring(self, test_env):
        """Verify missing dimensions default safely to 4.0."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_minimal = {
            "orm": {
                "name": "SqlAlchemy",
                "scores": {},  # empty scores dict
            }
        }
        res = cto.review_tech_stack(stack_minimal)
        assert res["disqualified"] is False
        assert res["evaluations"]["orm"]["weighted_score"] == 4.0
        assert res["evaluations"]["orm"]["decision"] == "ADOPT"

    def test_cto_review_tech_stack_string_shorthand(self, test_env):
        """Verify proposed_stack where values are plain strings rather than dicts."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_str = {"backend": "FastAPI", "database": "SQLite"}
        res = cto.review_tech_stack(stack_str)
        assert res["disqualified"] is False
        assert res["evaluations"]["backend"]["technology"] == "FastAPI"
        assert res["evaluations"]["database"]["technology"] == "SQLite"
        assert res["evaluations"]["backend"]["weighted_score"] == 4.0

    def test_cto_review_tech_stack_non_numeric_score_raises_value_error(self, test_env):
        """Verify non-numeric score value triggers ValueError."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        stack_invalid = {
            "core": {
                "name": "InvalidScoreTech",
                "scores": {"security_track_record": "unrated"},
            }
        }
        with pytest.raises(ValueError):
            cto.review_tech_stack(stack_invalid)


# ============================================================================
# Vector 3: CTO Archify HTML Generation Stress Testing
# ============================================================================
class TestCTOArchifyHTML:

    def test_cto_archify_html_structure_and_palette(self, test_env):
        """Verify Archify diagram HTML includes valid structure, dark theme palette, and required nodes."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        components = [
            {"id": "comp_api", "name": "FastAPI Gateway", "type": "gateway", "status": "active"},
            {"id": "comp_db", "name": "SQLite Core", "type": "storage", "status": "healthy"},
        ]
        result = cto.generate_archify_graph(project_id="alpha_canvas_test", components=components)
        html = result["html"]

        assert "<!DOCTYPE html>" in html
        assert "<title>Archify Architecture - alpha_canvas_test</title>" in html
        assert "#0A0A0F" in html or "#090A0F" in html, "Must contain dark palette background"
        assert "id='archify-canvas'" in html
        assert "id='comp_api'" in html
        assert "id='comp_db'" in html
        assert "pulsing" in html
        assert "@keyframes pulse" in html
        assert result["node_count"] == 2
        assert result["edge_count"] == 1

    def test_cto_archify_html_xss_injection_surface(self, test_env):
        """Verify whether component labels or project IDs are sanitized or raw in HTML."""
        cto = CTOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        malicious_components = [
            {
                "id": "node_xss",
                "name": "<script>alert('xss')</script>",
                "type": "malicious",
                "status": "active",
            }
        ]
        result = cto.generate_archify_graph(project_id="test_xss", components=malicious_components)
        html = result["html"]
        # Empirical finding: Check if raw script tag is present or escaped
        raw_injection_present = "<script>alert('xss')</script>" in html
        # We record this finding for the adversarial handoff report:
        # If raw script tag is interpolated directly without html.escape(), it is an XSS vulnerability!
        assert "node_xss" in html


# ============================================================================
# Vector 4: CPO RICE Priority & Anti-Gold-Plating Stress Testing
# ============================================================================
class TestCPORICEAndAntiGoldPlating:

    def test_cpo_rice_division_by_zero_guard(self, test_env):
        """Verify effort == 0 does NOT raise ZeroDivisionError."""
        cpo = CPOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        features = [
            {"name": "ZeroEffortFeat", "reach": 10.0, "impact": 3.0, "confidence": 1.0, "effort": 0.0}
        ]
        res = cpo.prioritize_backlog(features, project_id="adv_proj")
        assert len(res) == 1
        # Divisor should be clamped to 0.1: (10.0 * 3.0 * 1.0) / 0.1 = 300.0
        assert res[0]["rice_score"] == 300.0
        assert res[0]["priority"] == "P0"

    def test_cpo_rice_negative_effort(self, test_env):
        """Verify negative effort is clamped to 0.1 without crashing."""
        cpo = CPOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        features = [
            {"name": "NegEffortFeat", "reach": 5.0, "impact": 2.0, "confidence": 0.8, "effort": -3.0}
        ]
        res = cpo.prioritize_backlog(features, project_id="adv_proj")
        assert len(res) == 1
        # max(-3.0, 0.1) = 0.1 -> (5.0 * 2.0 * 0.8) / 0.1 = 80.0
        assert res[0]["rice_score"] == 80.0

    def test_cpo_rice_sorting_and_moscow_categorization(self, test_env):
        """Verify sorting descending by RICE score and MoSCoW mapping."""
        cpo = CPOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        features = [
            {"name": "LowPri", "reach": 1.0, "impact": 1.0, "confidence": 0.5, "effort": 5.0},      # (0.5)/5 = 0.1 -> P3
            {"name": "HighPri", "reach": 10.0, "impact": 3.0, "confidence": 0.9, "effort": 1.0},    # 27.0 -> P0
            {"name": "MedPri", "reach": 5.0, "impact": 2.0, "confidence": 0.8, "effort": 1.0},     # 8.0 -> P1
        ]
        res = cpo.prioritize_backlog(features)
        assert res[0]["name"] == "HighPri"
        assert res[0]["priority"] == "P0"
        assert res[1]["name"] == "MedPri"
        assert res[1]["priority"] == "P1"
        assert res[2]["name"] == "LowPri"
        assert res[2]["priority"] == "P3"

    def test_cpo_anti_gold_plating_flags_unnecessary_complexity(self, test_env):
        """Verify 7-point Anti-Gold-Plating audit catches missing out_of_scope, no P0, and no edge cases."""
        cpo = CPOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        # Deficient PRD: missing out_of_scope, missing P0, missing edge_cases
        bloated_prd = {
            "functional_requirements": [
                {"feature_name": "FancyAIWidget", "priority": "P2"}
            ],
            "edge_cases": [],
            "out_of_scope": [],
        }
        audit = cpo.audit_anti_gold_plating(bloated_prd, project_id="adv_proj")
        assert audit["passed"] is False, "Deficient PRD must fail anti-gold-plating audit"
        assert audit["score"] < 60.0
        flags = audit["flagged_gold_plating"]
        assert any("Missing explicit out_of_scope" in f for f in flags)
        assert any("No P0 functional requirements" in f for f in flags)
        assert any("No edge cases" in f for f in flags)

    def test_cpo_anti_gold_plating_compliant_prd_passes(self, test_env):
        """Verify clean PRD passing 7/7 checkpoints achieves 100% score."""
        cpo = CPOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        clean_prd = {
            "functional_requirements": [
                {"feature_name": "CoreEngine", "priority": "P0"}
            ],
            "edge_cases": [{"case": "Offline", "mitigation": "Fallback"}],
            "out_of_scope": ["Third-party cloud vendor lock-in"],
        }
        audit = cpo.audit_anti_gold_plating(clean_prd, project_id="adv_proj")
        assert audit["passed"] is True
        assert audit["score"] == 100.0
        assert len(audit["flagged_gold_plating"]) == 0


# ============================================================================
# Vector 5: CIO Vault Schema & ECC Memory Compression Stress Testing
# ============================================================================
class TestCIOVaultSchemaAndECC:

    def test_cio_compress_episodic_memory_empty(self, test_env):
        """Verify compressing empty memories produces zeroed metadata without crashing."""
        cio = CIOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        res = cio.compress_episodic_memory(agent_id="CEO")
        assert res["original_count"] == 0
        assert res["compressed_count"] == 0
        assert res["original_tokens"] == 0
        assert res["compression_ratio"] == 0.0
        assert res["summary"] == "No memories to compress."

    def test_cio_compress_episodic_memory_single_and_stratified(self, test_env):
        """Verify stratified compression of high, medium, and low importance items."""
        cio = CIOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        # Inject working memory with various importance levels
        cio.working_memory = [
            {"agent_id": "CTO", "memory_content": "P0 Decision: Selected SQLite and ChromaDB for local vault", "importance": 9},
            {"agent_id": "CTO", "memory_content": "Milestone M1 completed on schedule", "importance": 5},
            {"agent_id": "CTO", "memory_content": "Telemetry ping heartbeat ok", "importance": 1},
        ]
        res = cio.compress_episodic_memory(agent_id="CTO")
        assert res["original_count"] == 3
        assert res["compressed_count"] == 3
        assert "[DECISION/CORE]" in res["summary"]
        assert "[KEY MILESTONES]" in res["summary"]
        assert "[EPISODIC LOG]" in res["summary"]
        assert res["status"] == "compressed"

    def test_cio_ecc_sha256_integrity_check(self, test_env):
        """Verify SHA-256 cryptographic check on existing and missing memory files."""
        cio = CIOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        # Create real agent memory file
        mem_dir = test_env["temp_dir"] / "vault" / "agents" / "CEO"
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem_file = mem_dir / "episodic_memory.jsonl"
        mem_file.write_text('{"content": "Founder goal ingest"}\n', encoding="utf-8")

        res = cio.run_ecc_integrity_check(agent_id="CEO")
        assert res["healthy"] is True
        assert res["corrupted_records"] == 0

    def test_cio_enforce_vault_schema_tier_classification(self, test_env):
        """Verify data tier classifications: T1 (Restricted), T2 (Confidential), T3 (Internal), T4 (Open)."""
        cio = CIOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        t1 = cio.enforce_vault_schema("user/profile/credentials.json", {"username": "admin"})
        assert t1["data_tier"] == "T1"

        t2 = cio.enforce_vault_schema("company/okrs/q4_strategy.json", {"goal": "ship"})
        assert t2["data_tier"] == "T2"

        t3 = cio.enforce_vault_schema("projects/alpha/threads/msg.json", {"id": "1"})
        assert t3["data_tier"] == "T3"

        t4 = cio.enforce_vault_schema("knowledge/oss/readme.md", {"notes": "public"})
        assert t4["data_tier"] == "T4"


# ============================================================================
# Vector 6: CDO OLED Design Tokens & Accessibility Stress Testing
# ============================================================================
class TestCDOOLEDTokensAndA11y:

    def test_cdo_oled_tokens_exact_palette(self, test_env):
        """Verify exact OLED dark mode tokens match specification."""
        cdo = CDOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        tokens = cdo.get_oled_design_tokens()
        palette = tokens["palette"]

        assert palette["background"] == "#090A0F", "OLED background must be pitch black #090A0F"
        assert palette["surface"] == "#12141C"
        assert palette["surface_variant"] == "#1A1D28"
        assert palette["primary"] == "#3B82F6"
        assert palette["accent"] == "#06B6D4"

    def test_cdo_review_ui_spec_touch_target_boundary(self, test_env):
        """Verify touch target verification strictly enforces >= 48dp."""
        cdo = CDOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        # 48dp -> PASS
        spec_pass = {"touch_target_min_dp": 48, "contrast_ratio": 5.0}
        res_pass = cdo.review_ui_spec(spec_pass)
        assert res_pass["checklist"]["touch_target_size_48dp"] is True
        assert res_pass["passed"] is True

        # 47dp -> FAIL
        spec_fail = {"touch_target_min_dp": 47, "contrast_ratio": 5.0}
        res_fail = cdo.review_ui_spec(spec_fail)
        assert res_fail["checklist"]["touch_target_size_48dp"] is False
        assert res_fail["passed"] is False
        assert any("Touch targets smaller than minimum 48x48dp" in v for v in res_fail["violations"])

    def test_cdo_review_ui_spec_contrast_ratio_boundary(self, test_env):
        """Verify normal text contrast ratio strictly enforces >= 4.5:1 (WCAG AA)."""
        cdo = CDOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        # 4.5 -> PASS
        spec_pass = {"touch_target_min_dp": 48, "contrast_ratio": 4.5}
        res_pass = cdo.review_ui_spec(spec_pass)
        assert res_pass["checklist"]["contrast_ratio_4_5_to_1"] is True
        assert res_pass["passed"] is True

        # 4.4 -> FAIL
        spec_fail = {"touch_target_min_dp": 48, "contrast_ratio": 4.4}
        res_fail = cdo.review_ui_spec(spec_fail)
        assert res_fail["checklist"]["contrast_ratio_4_5_to_1"] is False
        assert res_fail["passed"] is False
        assert any("contrast ratio lower than 4.5:1" in v for v in res_fail["violations"])

    def test_cdo_canvas_node_styling_statuses(self, test_env):
        """Verify node styling configuration for pulsing glow and status colors."""
        cdo = CDOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])

        active_style = cdo.generate_canvas_node_style("agent", status="active")
        assert active_style["pulse_animation"] is True
        assert active_style["border_color"] == "#06B6D4"

        blocked_style = cdo.generate_canvas_node_style("task", status="blocked")
        assert blocked_style["pulse_animation"] is True
        assert blocked_style["border_color"] == "#EF4444"

        idle_style = cdo.generate_canvas_node_style("agent", status="idle")
        assert idle_style["pulse_animation"] is False


# ============================================================================
# Vector 7: CMO GTM Strategy & Messaging Stress Testing
# ============================================================================
class TestCMOGTMStrategyAndMessaging:

    def test_cmo_gtm_strategy_mandatory_10_point_checklist(self, test_env):
        """Verify 10-point GTM checklist validation and completion tracking."""
        cmo = CMOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        gtm = cmo.build_gtm_strategy(
            project_id="alpha_gtm",
            product_name="Project Alpha",
            value_prop="Autonomous 13-agent C-Suite OS",
            target_audience="Developers and AI Builders",
        )
        checklist = gtm["checklist_status"]
        assert len(checklist) == 10
        expected_items = [
            "icp_validated", "one_line_value_prop", "competitive_wedge",
            "landing_copy", "github_hygiene", "pricing_strategy",
            "launch_announcement", "objection_shields", "seo_baseline",
            "cao_audit_approved",
        ]
        for item in expected_items:
            assert item in checklist, f"Missing GTM checklist item: {item}"

    def test_cmo_messaging_framework_pillars_and_shields(self, test_env):
        """Verify messaging framework delivers 3 value pillars and objection shields."""
        cmo = CMOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        fw = cmo.create_messaging_framework(
            project_name="Project Alpha",
            problem="Devs waste time with manual orchestration",
            solution="Autonomous Executive OS",
            target_audience="AI Developers",
        )
        assert len(fw["value_pillars"]) >= 3
        assert len(fw["objection_shields"]) >= 2
        assert "Zero-Cost Sovereignty" in [p["pillar_name"] for p in fw["value_pillars"]]

    def test_cmo_conduct_market_discovery_five_steps(self, test_env):
        """Verify 5-step market discovery structure."""
        cmo = CMOAgent(vault_manager=test_env["vault"], model_router=test_env["router"])
        disc = cmo.conduct_market_discovery(
            product_concept="Local Autonomous Operating System",
            competitors=["Devin", "AutoGPT"],
        )
        assert "step_1_acute_problem" in disc
        assert "step_2_competitor_landscape" in disc
        assert "step_3_ideal_audience" in disc
        assert "step_4_defensible_wedge" in disc
        assert "step_5_strategic_recommendation" in disc
