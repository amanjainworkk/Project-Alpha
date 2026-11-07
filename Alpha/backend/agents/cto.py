"""backend/agents/cto.py - Project Alpha Chief Technology Officer Executive Agent.

Conforms to:
- CTO Job Description (Alpha/agents/job-descriptions/CTO-Chief-Technology-Officer.md)
- PROJECT.md Milestone 4 / Feature 17 Contract
- ATSR 9-Dimension Scoring Rubric
- Archify Visual Graph & Standalone OLED-themed HTML Generation
- Addy Osmani TDD (Plan, Build, Red-Green-Refactor)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.agents.base_agent import BaseExecutiveAgent
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.agents.cto")


class CTOAgent(BaseExecutiveAgent):
    """Chief Technology Officer Agent for Project Alpha.

    Responsible for:
    1. Technical Architecture Design (ADD/TSD).
    2. Stack Selection via ATSR 9-dimension scoring rubric.
    3. Archify Interactive Living Canvas Graphs and Standalone HTML.
    4. Code Quality & Standards Review.
    5. Addy Osmani TDD Red-Green-Refactor Test Planning.
    """

    ATSR_DIMENSIONS: Dict[str, float] = {
        "open_source_licensing": 0.15,
        "total_cost_of_ownership": 0.15,
        "scalability_ceiling": 0.15,
        "security_track_record": 0.15,
        "community_ecosystem": 0.10,
        "learning_curve": 0.10,
        "performance_characteristics": 0.10,
        "operational_complexity": 0.05,
        "integration_compatibility": 0.05,
    }

    def __init__(
        self,
        agent_id: str = "CTO",
        name: str = "Alpha CTO",
        role: str = "CTO",
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
    # 1. Architecture Design Document & Technical Specification Generation
    # ------------------------------------------------------------------------
    def generate_architecture_spec(
        self,
        requirements: str,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        system_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Produce a formal Technical Specification Document (TSD) per CTO JD §5.3."""
        if not requirements or not str(requirements).strip():
            raise ValueError("requirements cannot be empty or whitespace.")

        clean_req = str(requirements).strip()
        pid = project_id or self.current_project_id or f"proj_{uuid.uuid4().hex[:8]}"
        spec_id = f"TSD-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:6]}"
        spec_title = title or f"Technical Architecture Specification for {pid}"

        prompt = (
            f"Generate a comprehensive Technical Specification Document (TSD) for:\n"
            f"Title: {spec_title}\n"
            f"Project ID: {pid}\n"
            f"Requirements: {clean_req}\n"
            f"Context: {json.dumps(system_context or {})}\n\n"
            f"Follow the 10-section CTO TSD structure:\n"
            f"1. Executive Summary\n2. Background & Constraints\n3. Scope (In/Out)\n"
            f"4. Functional & Non-Functional Requirements\n5. Architecture Design & Schemas\n"
            f"6. API Specification\n7. Technology Stack (with ATSR scores)\n"
            f"8. Security Considerations\n9. Performance Plan\n10. Infrastructure & CI/CD Plan.\n\n"
            f"Return structured JSON containing keys: 'summary', 'scope', 'components', "
            f"'tech_stack', 'apis', 'security_plan', 'content_md'."
        )

        thought_output = self.think(
            context=prompt,
            complexity=4,
            task_type="technical_spec",
        )

        structured_data = self._parse_spec_output(thought_output, spec_title, clean_req)

        spec_record = {
            "spec_id": spec_id,
            "project_id": pid,
            "title": spec_title,
            "requirements": clean_req,
            "status": "draft",
            "summary": structured_data.get("summary", f"Technical Architecture specification for {spec_title}."),
            "scope": structured_data.get("scope", {"in_scope": [clean_req], "out_of_scope": ["Cloud vendor lock-in"]}),
            "components": structured_data.get("components", []),
            "tech_stack": structured_data.get("tech_stack", {}),
            "apis": structured_data.get("apis", []),
            "security_plan": structured_data.get("security_plan", {}),
            "content_md": structured_data.get("content_md", thought_output),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to Vault
        if self.vault_manager is not None:
            vault_path = f"projects/{pid}/deliverables/technical_spec.json"
            try:
                self.vault_manager.write(vault_path, spec_record, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("Could not persist technical spec to %s: %s", vault_path, e)

            try:
                self.record_decision(
                    summary=f"Authored technical specification for {pid}: {spec_title}",
                    rationale=f"Specified {len(spec_record['components'])} core components aligned with Zero-Cost and Local-First principles.",
                    importance=8,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed to record decision memory: %s", e)

        return spec_record

    # ------------------------------------------------------------------------
    # 2. Technology Stack Evaluation (ATSR 9-Dimension Rubric)
    # ------------------------------------------------------------------------
    def review_tech_stack(
        self,
        proposed_stack: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate technology candidates across 9 ATSR dimensions."""
        if not proposed_stack:
            raise ValueError("proposed_stack cannot be empty.")

        pid = project_id or self.current_project_id or "default_project"
        evaluation_results: Dict[str, Any] = {}
        disqualified = False
        overall_scores: List[float] = []

        for category, tech_info in proposed_stack.items():
            tech_name = tech_info.get("name") if isinstance(tech_info, dict) else str(tech_info)
            scores = tech_info.get("scores", {}) if isinstance(tech_info, dict) else {}

            total_weighted = 0.0
            dim_details = {}
            for dim, weight in self.ATSR_DIMENSIONS.items():
                score = float(scores.get(dim, 4.0))
                # Security is dimension 4: score 1 is automatic disqualifier
                if dim == "security_track_record" and score <= 1.0:
                    disqualified = True
                total_weighted += score * weight
                dim_details[dim] = {"score": score, "weight": weight}

            # Decision threshold
            sec_score = dim_details.get("security_track_record", {}).get("score", 4.0)
            if sec_score <= 1.0:
                decision = "HOLD (SECURITY DISQUALIFIED)"
            elif total_weighted >= 4.0:
                decision = "ADOPT"
            elif total_weighted >= 3.0:
                decision = "TRIAL"
            elif total_weighted >= 2.0:
                decision = "ASSESS"
            else:
                decision = "HOLD"

            evaluation_results[category] = {
                "technology": tech_name,
                "weighted_score": round(total_weighted, 2),
                "decision": decision,
                "dimensions": dim_details,
            }
            overall_scores.append(total_weighted)

        avg_score = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0.0
        review_summary = {
            "review_id": f"atsr_{uuid.uuid4().hex[:8]}",
            "project_id": pid,
            "average_weighted_score": avg_score,
            "stack_status": "REJECTED" if disqualified else ("APPROVED" if avg_score >= 3.5 else "CONDITIONAL"),
            "evaluations": evaluation_results,
            "disqualified": disqualified,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/tech_stack_review.json"
            try:
                self.vault_manager.write(vpath, review_summary, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed to write tech stack review to %s: %s", vpath, e)

            try:
                self.record_thought(
                    thought=f"Evaluated tech stack for {pid}: status={review_summary['stack_status']}, disqualified={disqualified}",
                    importance=6,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed to record thought memory: %s", e)

        return review_summary

    # ------------------------------------------------------------------------
    # 3. Archify Interactive Graph & Standalone HTML Generation
    # ------------------------------------------------------------------------
    def generate_archify_graph(
        self,
        project_id: str,
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate Archify visual graph data and standalone OLED-themed HTML diagram."""
        if not project_id or not str(project_id).strip():
            raise ValueError("project_id cannot be empty.")

        pid = str(project_id).strip()
        comp_list = components or [
            {"id": "comp_api", "name": "FastAPI Desktop Backend", "type": "gateway", "status": "active"},
            {"id": "comp_vault", "name": "Alpha Vault (SQLite + Chroma)", "type": "storage", "status": "healthy"},
            {"id": "comp_router", "name": "5-Tier Model Router", "type": "service", "status": "active"},
            {"id": "comp_mobile", "name": "Flutter Archify+ UI", "type": "agent", "status": "idle"},
        ]

        nodes = []
        for idx, c in enumerate(comp_list):
            nodes.append({
                "id": c.get("id", f"node_{idx}"),
                "label": c.get("name", f"Component {idx}"),
                "type": c.get("type", "service"),
                "status": c.get("status", "active"),
            })

        edges = []
        if len(nodes) > 1:
            for i in range(len(nodes) - 1):
                edges.append({
                    "from": nodes[i]["id"],
                    "to": nodes[i + 1]["id"],
                    "label": "data_flow",
                    "pulsing": bool(i == 0),
                })

        graph_data = {"project_id": pid, "nodes": nodes, "edges": edges}

        # Standalone interactive OLED HTML diagram
        html = (
            f"<!DOCTYPE html>\n<html>\n<head>\n"
            f"<meta charset='utf-8'>\n<title>Archify Architecture - {pid}</title>\n"
            f"<style>\n"
            f"  body {{ background: #0A0A0F; color: #E0E0E0; font-family: monospace; margin: 0; padding: 20px; }}\n"
            f"  .canvas {{ display: flex; gap: 20px; flex-wrap: wrap; background: #13131A; border: 1px solid #262635; border-radius: 8px; padding: 20px; }}\n"
            f"  .node {{ background: #1A1A24; border: 1px solid #06B6D4; border-radius: 6px; padding: 12px 16px; color: #FFFFFF; font-weight: bold; }}\n"
            f"  .pulsing {{ box-shadow: 0 0 12px rgba(6, 182, 212, 0.6); animation: pulse 2s infinite; }}\n"
            f"  @keyframes pulse {{ 0% {{ opacity: 0.8; }} 50% {{ opacity: 1.0; }} 100% {{ opacity: 0.8; }} }}\n"
            f"</style>\n</head>\n<body>\n"
            f"<h2>Project Alpha Archify Architecture Diagram: {pid}</h2>\n"
            f"<div class='canvas' id='archify-canvas' data-project='{pid}'>\n"
        )
        for n in nodes:
            html += f"  <div class='node pulsing' id='{n['id']}'>[{n['type'].upper()}] {n['label']} ({n['status']})</div>\n"
        html += "</div>\n</body>\n</html>"

        result = {
            "project_id": pid,
            "graph_data": graph_data,
            "html": html,
            "status": "generated",
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/archify_graph.json"
            try:
                self.vault_manager.write(vpath, graph_data, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Could not write archify graph to vault: %s", e)

        return result

    # ------------------------------------------------------------------------
    # 4. Code Standards & Static Quality Review
    # ------------------------------------------------------------------------
    def review_code_standards(
        self,
        code_snippet: str,
        language: str = "python",
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify code snippet against CTO JD §3.4 quality guidelines."""
        if not code_snippet:
            return {"passed": True, "score": 100.0, "violations": [], "metrics": {}}

        lines = code_snippet.splitlines()
        violations = []

        # 1. Function length inspection (max 50 lines)
        func_starts: List[Tuple[str, int]] = []
        for i, line in enumerate(lines):
            m = re.match(r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(", line)
            if m:
                func_starts.append((m.group(1), i))

        for idx, (fname, s_line) in enumerate(func_starts):
            e_line = func_starts[idx + 1][1] if idx + 1 < len(func_starts) else len(lines)
            length = e_line - s_line
            if length > 50:
                violations.append({
                    "rule": "max_function_length",
                    "target": fname,
                    "actual": length,
                    "max_allowed": 50,
                    "severity": "HIGH",
                    "message": f"Function '{fname}' exceeds 50 lines ({length} lines).",
                })

        # 2. Approximate cyclomatic complexity
        branching_keywords = ["if ", "elif ", "for ", "while ", "except ", "and ", "or "]
        complexity_count = 1 + sum(code_snippet.count(kw) for kw in branching_keywords)
        if complexity_count > 10:
            violations.append({
                "rule": "cyclomatic_complexity",
                "actual": complexity_count,
                "max_allowed": 10,
                "severity": "MEDIUM",
                "message": f"Cyclomatic complexity is {complexity_count} (limit: 10).",
            })

        score = max(0.0, 100.0 - (len(violations) * 15.0))
        passed = len(violations) == 0

        return {
            "passed": passed,
            "score": score,
            "violations": violations,
            "metrics": {
                "total_lines": len(lines),
                "function_count": len(func_starts),
                "complexity": complexity_count,
            },
        }

    # ------------------------------------------------------------------------
    # 5. Addy Osmani TDD Integration (Red-Green-Refactor Plan)
    # ------------------------------------------------------------------------
    def generate_tdd_test_plan(
        self,
        component_name: str,
        functional_requirements: List[str],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured Addy Osmani TDD test plan."""
        if not component_name or not str(component_name).strip():
            raise ValueError("component_name cannot be empty.")

        pid = project_id or self.current_project_id or "default_project"
        clean_name = str(component_name).strip()

        tests = []
        for idx, req in enumerate(functional_requirements, 1):
            tests.append({
                "test_id": f"test_{clean_name}_{idx}",
                "description": f"Verify {req}",
                "phase": "RED (Failing Assertion)",
                "mock_boundaries": ["VaultManager", "ModelRouter"],
                "target_coverage": ">=80% unit",
            })

        plan = {
            "plan_id": f"tdd_{uuid.uuid4().hex[:8]}",
            "component": clean_name,
            "project_id": pid,
            "lifecycle": "Addy Osmani 6-Phase Engineering (Plan & Build)",
            "tests": tests,
            "coverage_target": {"unit": "80%", "integration": "60%"},
            "status": "ready_for_red_phase",
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/tdd_{clean_name}.json"
            try:
                self.vault_manager.write(vpath, plan, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed to write TDD plan to vault: %s", e)

        return plan

    # ------------------------------------------------------------------------
    # 6. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a technical task directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["architecture", "spec", "tsd", "design"]):
            output_data = self.generate_architecture_spec(requirements=clean_task, project_id=pid)
        elif any(w in t_lower for w in ["stack", "atsr", "evaluate"]):
            output_data = self.review_tech_stack(
                proposed_stack={"core": {"name": "DefaultStack", "scores": {"security_track_record": 4.0}}},
                project_id=pid,
            )
        elif any(w in t_lower for w in ["archify", "diagram", "graph"]):
            output_data = self.generate_archify_graph(project_id=pid)
        elif any(w in t_lower for w in ["code", "standards", "lint"]):
            output_data = self.review_code_standards(code_snippet=clean_task)
        elif any(w in t_lower for w in ["tdd", "test_plan", "tests"]):
            output_data = self.generate_tdd_test_plan(
                component_name="CoreEngine",
                functional_requirements=[clean_task],
                project_id=pid,
            )
        else:
            thought = self.think(
                context=f"CTO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="technical_architecture",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"CTO executed task: {clean_task[:80]}",
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
        """Hook for derived executive agent classes to implement role-specific actions."""
        act_norm = action.lower().strip()
        if act_norm in ("generate_architecture_spec", "generate_spec", "author_tsd"):
            res = self.generate_architecture_spec(
                requirements=parameters.get("requirements", ""),
                project_id=parameters.get("project_id"),
                title=parameters.get("title"),
                system_context=parameters.get("context"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("review_tech_stack", "atsr_evaluate"):
            res = self.review_tech_stack(
                proposed_stack=parameters.get("proposed_stack", {}),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_archify_graph", "archify_graph"):
            res = self.generate_archify_graph(
                project_id=parameters.get("project_id", "default_proj"),
                components=parameters.get("components"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("review_code_standards", "check_code_standards"):
            res = self.review_code_standards(
                code_snippet=parameters.get("code_snippet", ""),
                language=parameters.get("language", "python"),
                file_path=parameters.get("file_path"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_tdd_test_plan", "tdd_plan"):
            res = self.generate_tdd_test_plan(
                component_name=parameters.get("component_name", "Component"),
                functional_requirements=parameters.get("functional_requirements", []),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm == "run":
            res = self.run(
                task=parameters.get("task", ""),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        return super()._handle_custom_action(action, parameters)

    def _parse_spec_output(self, output: str, title: str, fallback_req: str) -> Dict[str, Any]:
        """Safely parse model output or synthesize default spec structure."""
        try:
            m = re.search(r"\{.*\}", output, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                if isinstance(d, dict) and "components" in d:
                    return d
        except Exception:
            pass

        return {
            "summary": f"Technical Architecture specification for {title}.",
            "scope": {"in_scope": [fallback_req], "out_of_scope": ["Cloud vendor lock-in"]},
            "components": [
                {"name": "Core Service Engine", "type": "backend", "status": "active"},
                {"name": "Local Vault Data Store", "type": "storage", "status": "healthy"},
            ],
            "tech_stack": {"backend": "Python 3.11 / FastAPI", "storage": "SQLite + ChromaDB"},
            "apis": [{"endpoint": "/v1/execute", "method": "POST"}],
            "security_plan": {"auth": "Local Token", "rbac": "Role-Based"},
            "content_md": output,
        }
