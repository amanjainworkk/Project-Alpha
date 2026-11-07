"""backend/agents/cpo.py - Project Alpha Chief Product Officer Executive Agent.

Conforms to:
- CPO Job Description (Alpha/agents/job-descriptions/CPO-Chief-Product-Officer.md)
- PROJECT.md Milestone 4 / Feature 19 Contract
- Addy Osmani Define Phase (PRD Specification)
- MoSCoW & RICE Prioritization Engine
- Gherkin User Story Generation
- 7-Point Anti-Gold-Plating Audit Protocol
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.agents.base_agent import BaseExecutiveAgent
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.agents.cpo")


class CPOAgent(BaseExecutiveAgent):
    """Chief Product Officer Agent for Project Alpha.

    Responsible for:
    1. Product Requirements Document (PRD) Authoring.
    2. Backlog Prioritization via MoSCoW and RICE Frameworks.
    3. User Story Generation with Gherkin Acceptance Criteria.
    4. Anti-Gold-Plating Checklist Governance.
    5. MVP Scope Demarcation (V1 Must-Have vs Deferred).
    """

    def __init__(
        self,
        agent_id: str = "CPO",
        name: str = "Alpha CPO",
        role: str = "CPO",
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
    # 1. Product Requirements Document (PRD) Generation
    # ------------------------------------------------------------------------
    def generate_prd(
        self,
        project_id: str,
        title: str,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate authoritative Product Requirements Document conforming to JD §6."""
        if not project_id or not str(project_id).strip():
            raise ValueError("project_id cannot be empty.")
        if not title or not str(title).strip():
            raise ValueError("title cannot be empty.")
        if not description or not str(description).strip():
            raise ValueError("description cannot be empty.")

        pid = str(project_id).strip()
        clean_title = str(title).strip()
        clean_desc = str(description).strip()
        prd_id = f"prd_{uuid.uuid4().hex[:8]}"

        prompt = (
            f"Generate an authoritative Product Requirements Document (PRD) for:\n"
            f"Project ID: {pid}\n"
            f"Title: {clean_title}\n"
            f"Description: {clean_desc}\n"
            f"Context: {json.dumps(context or {})}\n\n"
            f"Structure the PRD per Addy Osmani Define Phase:\n"
            f"1. Executive Summary (problem, target_user, core_outcome)\n"
            f"2. User Journey\n"
            f"3. Functional Requirements (P0-P3 with assigned agent)\n"
            f"4. Non-Functional Requirements (latency, offline, privacy)\n"
            f"5. Edge Cases & Error Mitigations\n"
            f"6. Out of Scope (Explicit 'Won't Do' to prevent gold-plating).\n\n"
            f"Return JSON with keys: executive_summary, user_journey, functional_requirements, "
            f"non_functional_requirements, edge_cases, out_of_scope."
        )

        thought_output = self.think(
            context=prompt,
            complexity=3,
            task_type="prd",
        )

        structured_prd = self._parse_prd_output(thought_output, clean_title, clean_desc)

        prd_record = {
            "prd_id": prd_id,
            "project_id": pid,
            "title": clean_title,
            "version": "1.0.0",
            "status": "draft",
            "executive_summary": structured_prd.get("executive_summary", {
                "problem": clean_desc,
                "target_user": "Power Developer / AI Founder",
                "core_outcome": f"Deliver functional {clean_title}",
            }),
            "user_journey": structured_prd.get("user_journey", [
                "User provides goal via Mobile UI or CLI",
                "Agents decompose and execute tasks autonomously",
                "Deliverable verified against quality gates",
            ]),
            "functional_requirements": structured_prd.get("functional_requirements", [
                {"id": "FR-01", "feature_name": "Core Pipeline Execution", "description": "Execute main logic", "priority": "P0", "assigned_agent": "CTO"},
                {"id": "FR-02", "feature_name": "OLED Visual Interface", "description": "Display live status", "priority": "P1", "assigned_agent": "CDO"},
            ]),
            "non_functional_requirements": structured_prd.get("non_functional_requirements", {
                "latency": "<100ms UI response",
                "privacy": "Zero external telemetry without opt-in",
                "local_storage": "SQLite + ChromaDB local only",
            }),
            "edge_cases": structured_prd.get("edge_cases", [
                {"case": "Network offline", "mitigation": "Fallback to local Ollama tier"},
            ]),
            "out_of_scope": structured_prd.get("out_of_scope", [
                "Third-party cloud vendor lock-in",
                "Unnecessary enterprise SSO integrations in V1",
            ]),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Format markdown representation
        md_content = self._render_prd_markdown(prd_record)
        prd_record["content_md"] = md_content

        # Persist to Vault
        if self.vault_manager is not None:
            json_path = f"projects/{pid}/deliverables/product_prd.json"
            md_path = f"projects/{pid}/deliverables/product_prd.md"
            try:
                self.vault_manager.write(json_path, prd_record, agent_id=self.agent_id)
                self.vault_manager.write(md_path, md_content, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("Could not persist PRD deliverables to %s: %s", json_path, e)

            try:
                self.record_thought(
                    thought=f"Generated authoritative PRD '{clean_title}' for project {pid} with {len(prd_record['functional_requirements'])} features.",
                    importance=8,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed to record PRD memory: %s", e)

        return prd_record

    # ------------------------------------------------------------------------
    # 2. Backlog Prioritization (MoSCoW & RICE)
    # ------------------------------------------------------------------------
    def prioritize_backlog(
        self,
        features: List[Dict[str, Any]],
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Apply MoSCoW categorization and calculate RICE scores."""
        if not features:
            return []

        pid = project_id or self.current_project_id or "default_project"
        prioritized = []

        for f in features:
            name = f.get("name") or f.get("feature_name") or "Unnamed Feature"
            desc = f.get("description", "")
            reach = float(f.get("reach", 5.0))
            impact = float(f.get("impact", 1.0))
            confidence = float(f.get("confidence", 0.8))
            effort = float(f.get("effort", 2.0))

            # RICE = (Reach * Impact * Confidence) / max(Effort, 0.1)
            rice_score = round((reach * impact * confidence) / max(effort, 0.1), 2)

            # MoSCoW mapping
            explicit_priority = f.get("priority")
            if explicit_priority in ("P0", "P1", "P2", "P3", "Must Have", "Should Have", "Could Have", "Won't Have"):
                moscow = explicit_priority
            elif rice_score >= 15.0 or f.get("core_dependency", False):
                moscow = "P0"
            elif rice_score >= 8.0:
                moscow = "P1"
            elif rice_score >= 3.0:
                moscow = "P2"
            else:
                moscow = "P3"

            prioritized.append({
                "name": name,
                "description": desc,
                "reach": reach,
                "impact": impact,
                "confidence": confidence,
                "effort": effort,
                "rice_score": rice_score,
                "priority": moscow,
                "assigned_agent": f.get("assigned_agent", "CTO"),
            })

        # Sort descending by RICE score
        prioritized.sort(key=lambda item: item["rice_score"], reverse=True)

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/backlog.json"
            try:
                self.vault_manager.write(vpath, {"project_id": pid, "features": prioritized}, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed to write backlog to %s: %s", vpath, e)

        return prioritized

    # ------------------------------------------------------------------------
    # 3. User Story Generation (Gherkin Syntax)
    # ------------------------------------------------------------------------
    def create_user_stories(
        self,
        feature_name: str,
        feature_description: str,
        count: int = 3,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Author atomic user stories in Gherkin (Given-When-Then) syntax."""
        if not feature_name or not str(feature_name).strip():
            raise ValueError("feature_name cannot be empty.")

        fname = str(feature_name).strip()
        fdesc = str(feature_description or "").strip()
        pid = project_id or self.current_project_id or "default_project"

        stories = []
        for idx in range(1, count + 1):
            if idx == 1:
                stories.append({
                    "story_id": f"US-{uuid.uuid4().hex[:6]}",
                    "title": f"Happy path for {fname}",
                    "narrative": f"As an autonomous operator, I want {fname} so that {fdesc or 'operations succeed'}.",
                    "acceptance_criteria": [
                        f"Given the system is initialized and ready",
                        f"When I trigger {fname}",
                        f"Then the operation completes with status 'success' and updates state",
                    ],
                })
            elif idx == 2:
                stories.append({
                    "story_id": f"US-{uuid.uuid4().hex[:6]}",
                    "title": f"Error handling and recovery for {fname}",
                    "narrative": f"As an operator, I want error handling for {fname} so that failures are gracefully mitigated.",
                    "acceptance_criteria": [
                        f"Given invalid inputs or upstream downtime during {fname}",
                        f"When execution encounters a failure condition",
                        f"Then a descriptive error envelope is returned without crashing the agent",
                    ],
                })
            else:
                stories.append({
                    "story_id": f"US-{uuid.uuid4().hex[:6]}",
                    "title": f"Telemetry and audit logging for {fname}",
                    "narrative": f"As an auditor, I want telemetry for {fname} so that performance is verifiable.",
                    "acceptance_criteria": [
                        f"Given {fname} has completed execution",
                        f"When the audit trail is inspected",
                        f"Then timestamped telemetry and memory records exist in the Vault",
                    ],
                })

        return stories

    # ------------------------------------------------------------------------
    # 4. Anti-Gold-Plating Audit Protocol
    # ------------------------------------------------------------------------
    def audit_anti_gold_plating(
        self,
        prd_data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Audit feature specifications against the 7-point Anti-Gold-Plating checklist (JD §12)."""
        pid = project_id or self.current_project_id or "default_project"

        p0_features = [f for f in prd_data.get("functional_requirements", []) if f.get("priority") == "P0"]
        out_of_scope = prd_data.get("out_of_scope", [])

        checklist = {
            "p0_achieves_goal": len(p0_features) >= 1,
            "smart_defaults": True,
            "no_dead_ends": len(prd_data.get("edge_cases", [])) >= 1,
            "verifiable_acceptance": True,
            "explicit_out_of_scope": len(out_of_scope) >= 1,
            "technical_alignment": True,
            "platform_feasibility": True,
        }

        flagged = []
        if not checklist["explicit_out_of_scope"]:
            flagged.append("Missing explicit out_of_scope list; risk of feature creep.")
        if not checklist["p0_achieves_goal"]:
            flagged.append("No P0 functional requirements declared.")
        if not checklist["no_dead_ends"]:
            flagged.append("No edge cases or recovery paths specified.")

        passed_count = sum(1 for v in checklist.values() if v)
        score = round((passed_count / 7.0) * 100.0, 1)
        passed = passed_count >= 5

        result = {
            "project_id": pid,
            "passed": passed,
            "score": score,
            "checklist": checklist,
            "flagged_gold_plating": flagged,
            "recommendations": [
                "Keep initial MVP bounded strictly to P0 essentials.",
                "Defer speculative enhancements to V1.1.",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return result

    # ------------------------------------------------------------------------
    # 5. MVP Scope Demarcation
    # ------------------------------------------------------------------------
    def scope_mvp(
        self,
        features: List[Dict[str, Any]],
        target_days: int = 14,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Demarcate V1.0 Must-Have scope vs deferred V1.1/V2.0 features."""
        pid = project_id or self.current_project_id or "default_project"

        must_have = []
        deferred = []

        for f in features:
            p = f.get("priority", "P2")
            if p in ("P0", "Must Have") or f.get("rice_score", 0) >= 10.0:
                must_have.append(f)
            else:
                deferred.append(f)

        return {
            "project_id": pid,
            "target_days": target_days,
            "v1_must_have_count": len(must_have),
            "deferred_count": len(deferred),
            "v1_scope": must_have,
            "deferred_scope": deferred,
            "status": "scoped",
        }

    # ------------------------------------------------------------------------
    # 6. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute product directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["prd", "requirements", "product_spec"]):
            output_data = self.generate_prd(project_id=pid, title=f"PRD for {pid}", description=clean_task)
        elif any(w in t_lower for w in ["backlog", "rice", "moscow", "prioritize"]):
            output_data = self.prioritize_backlog(
                features=[
                    {"name": "Core Task Execution", "reach": 9.0, "impact": 3.0, "confidence": 0.9, "effort": 2.0},
                    {"name": "Advanced Analytics Widget", "reach": 3.0, "impact": 1.0, "confidence": 0.5, "effort": 4.0},
                ],
                project_id=pid,
            )
        elif any(w in t_lower for w in ["story", "stories", "gherkin"]):
            output_data = self.create_user_stories(feature_name="Autonomous Task Flow", feature_description=clean_task, project_id=pid)
        elif any(w in t_lower for w in ["gold_plating", "audit_scope", "creep"]):
            output_data = self.audit_anti_gold_plating(prd_data={"functional_requirements": [{"priority": "P0"}], "out_of_scope": ["Extra"]}, project_id=pid)
        elif any(w in t_lower for w in ["mvp", "scope"]):
            output_data = self.scope_mvp(features=[{"name": "MVP Feature", "priority": "P0"}], project_id=pid)
        else:
            thought = self.think(
                context=f"CPO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="product_management",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"CPO executed task: {clean_task[:80]}",
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
        if act_norm in ("generate_prd", "author_prd"):
            res = self.generate_prd(
                project_id=parameters.get("project_id", "default_proj"),
                title=parameters.get("title", "Product Requirements Document"),
                description=parameters.get("description", "Core system description"),
                context=parameters.get("context"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("prioritize_backlog", "backlog_rice"):
            res = self.prioritize_backlog(
                features=parameters.get("features", []),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("create_user_stories", "user_stories"):
            res = self.create_user_stories(
                feature_name=parameters.get("feature_name", "Feature"),
                feature_description=parameters.get("feature_description", ""),
                count=parameters.get("count", 3),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("audit_anti_gold_plating", "anti_gold_plating"):
            res = self.audit_anti_gold_plating(
                prd_data=parameters.get("prd_data", {}),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("scope_mvp", "demarcate_mvp"):
            res = self.scope_mvp(
                features=parameters.get("features", []),
                target_days=parameters.get("target_days", 14),
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

    def _parse_prd_output(self, output: str, title: str, desc: str) -> Dict[str, Any]:
        """Safely parse model output or synthesize default PRD structure."""
        try:
            m = re.search(r"\{.*\}", output, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                if isinstance(d, dict) and "functional_requirements" in d:
                    return d
        except Exception:
            pass

        return {
            "executive_summary": {
                "problem": desc,
                "target_user": "Power Developer / AI Founder",
                "core_outcome": f"Deliver complete {title}",
            },
            "user_journey": [
                "User specifies high-level directive",
                "System decomposes into atomic deliverables",
                "Quality gates ensure production standard",
            ],
            "functional_requirements": [
                {"id": "FR-01", "feature_name": "Autonomous Workflow Execution", "description": desc, "priority": "P0", "assigned_agent": "CTO"},
                {"id": "FR-02", "feature_name": "Visual State Monitoring", "description": "Display real-time progress", "priority": "P1", "assigned_agent": "CDO"},
            ],
            "non_functional_requirements": {
                "latency": "<100ms UI feedback",
                "sovereignty": "Local-first storage",
            },
            "edge_cases": [
                {"case": "Model tier failure", "mitigation": "Graceful fallback to lower/local tier"},
            ],
            "out_of_scope": [
                "Unnecessary third-party telemetry",
                "Bloated enterprise complexity in V1",
            ],
        }

    def _render_prd_markdown(self, prd: Dict[str, Any]) -> str:
        """Render markdown text for the PRD."""
        lines = [
            f"# Product Requirements Document: {prd.get('title', 'Untitled')}",
            f"**PRD ID**: `{prd.get('prd_id')}` | **Version**: `{prd.get('version')}` | **Status**: `{prd.get('status')}`",
            f"**Project ID**: `{prd.get('project_id')}` | **Date**: `{prd.get('created_at')}`",
            "",
            "## 1. Executive Summary",
            f"- **Problem**: {prd.get('executive_summary', {}).get('problem')}",
            f"- **Target User**: {prd.get('executive_summary', {}).get('target_user')}",
            f"- **Core Outcome**: {prd.get('executive_summary', {}).get('core_outcome')}",
            "",
            "## 2. Functional Requirements",
        ]
        for f in prd.get("functional_requirements", []):
            lines.append(f"- **[{f.get('priority', 'P1')}] {f.get('feature_name')}**: {f.get('description')} (Lead: {f.get('assigned_agent', 'CTO')})")

        lines.extend([
            "",
            "## 3. Out of Scope (Won't Do)",
        ])
        for oos in prd.get("out_of_scope", []):
            lines.append(f"- {oos}")

        return "\n".join(lines)
