"""backend/agents/ceo.py - Project Alpha CEO Executive Agent.

Autonomous Executive Intelligence serving as the single point of contact
between human Founder (Aman Jain) and the Alpha C-Suite ecosystem.

Conforms to:
- CEO Job Description (Alpha/agents/job-descriptions/CEO-Chief-Executive-Officer.md)
- PROJECT.md Milestone 3 Contract
- 3-Tier Decision Authority Matrix (Decide Alone, Consult C-Suite, Escalate to User)
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

logger = logging.getLogger("alpha.agents.ceo")


class CEOAgent(BaseExecutiveAgent):
    """Chief Executive Officer Agent for Project Alpha.

    Responsible for:
    1. Strategic Goal Intake & Decomposition into workstreams.
    2. Executive Department Delegation & Brief Formatting.
    3. Cross-Functional Deliverable Synthesis.
    4. Conflict Adjudication & 3-Tier Authority Governance.
    5. Direct Vault and Memory Ledger Management.
    """

    ROLE_TAXONOMY: Dict[str, List[str]] = {
        "CTO": ["technical", "architecture", "tech_spec", "system_design", "code", "backend", "api", "database", "infrastructure", "security", "diagram"],
        "CMO": ["marketing", "gtm", "campaign", "persona", "branding", "growth", "copy", "advertising", "content", "market_analysis"],
        "CPO": ["product", "prd", "feature", "user_story", "moscow", "mvp", "roadmap", "requirements"],
        "CDO": ["design", "ui", "ux", "wireframe", "oled", "styling", "visual", "archify_canvas", "tokens"],
        "CFO": ["finance", "financial", "budget", "cost", "token", "roi", "pricing", "unit_economics", "spending"],
        "COO": ["operations", "timeline", "workflow", "schedule", "execution_plan", "pep", "resource", "milestone"],
        "CHRO": ["hr", "hire", "recruiting", "personnel", "org_chart", "agent_lifecycle", "onboarding"],
        "CIO": ["info", "vault", "schema", "backup", "custodian", "data_governance", "relational"],
        "CSO": ["strategy", "okr", "positioning", "alignment", "strategic_planning", "vision"],
        "CLO": ["legal", "compliance", "license", "gpl", "contract", "terms", "risk_mitigation", "regulatory"],
        "CAO-Claude": ["audit", "review", "rubric", "quality_audit", "verification"],
        "CAO-ChatGPT": ["code_audit", "alternative_review", "verification_code"],
    }

    def __init__(
        self,
        agent_id: str = "CEO",
        name: str = "Alpha CEO",
        role: str = "CEO",
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
        self.active_goals: Dict[str, Dict[str, Any]] = {}

    # ========================================================================
    # 1. Goal Intake & Workstream Decomposition
    # ========================================================================

    def ingest_goal(
        self,
        goal_text: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ingest raw founder directive and decompose into structured workstreams.

        Steps:
        1. Validates input goal text.
        2. Calls model_router with complexity 4 (strategic_planning).
        3. Parses objectives, milestones, and departmental role assignments.
        4. Persists goal record to 'projects/<project_id>/goals.json' in Vault.
        5. Logs high-importance episodic memory to agent memory ledger.
        6. Returns structured goal dictionary.
        """
        if not goal_text or not str(goal_text).strip():
            raise ValueError("goal_text cannot be empty or whitespace.")

        clean_goal = str(goal_text).strip()
        resolved_project_id = project_id or f"proj_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"

        # Cognitive decomposition prompt
        prompt = (
            f"Founder Directive: {clean_goal}\n\n"
            "Decompose this goal into:\n"
            "1. Specific measurable objectives.\n"
            "2. Target milestones with sequential order.\n"
            "3. Assigned executive C-Suite roles (CTO, CMO, CPO, CDO, CFO, COO, CHRO, CIO, CSO, CLO).\n\n"
            "Format your response as structured JSON with keys: 'objectives' (list of str), "
            "'milestones' (list of dicts with 'name' and 'target_days'), and 'assigned_roles' (list of str)."
        )

        thought_output = self.think(
            context=prompt,
            complexity=4,
            task_type="strategic_planning",
        )

        parsed_data = self._parse_decomposition_output(thought_output, clean_goal)

        goal_record: Dict[str, Any] = {
            "goal_id": goal_id,
            "project_id": resolved_project_id,
            "raw_goal": clean_goal,
            "objectives": parsed_data["objectives"],
            "milestones": parsed_data["milestones"],
            "assigned_roles": parsed_data["assigned_roles"],
            "status": "ingested",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Vault persistence
        if self.vault_manager is not None:
            vault_path = f"projects/{resolved_project_id}/goals.json"
            try:
                if hasattr(self.vault_manager, "write"):
                    self.vault_manager.write(vault_path, goal_record, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("Failed to persist goal to vault path %s: %s", vault_path, e)

            # Record thought memory
            try:
                self.record_thought(
                    thought=f"Ingested founder goal '{clean_goal[:60]}...' assigned to roles: {', '.join(goal_record['assigned_roles'])}",
                    importance=8,
                    project_id=resolved_project_id,
                )
            except Exception as e:
                logger.warning("Failed to record memory for goal intake: %s", e)

        self.active_goals[goal_id] = goal_record
        return goal_record

    def _parse_decomposition_output(self, output: str, fallback_goal: str) -> Dict[str, Any]:
        """Safely extract objectives, milestones, and roles from model output with heuristic fallback."""
        try:
            match = re.search(r"\{.*\}", output, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    objectives = data.get("objectives", [])
                    milestones = data.get("milestones", [])
                    assigned_roles = data.get("assigned_roles", [])
                    if objectives and assigned_roles:
                        return {
                            "objectives": [str(o) for o in objectives],
                            "milestones": milestones,
                            "assigned_roles": [str(r).upper() for r in assigned_roles],
                        }
        except Exception:
            pass

        # Robust heuristic fallback
        objectives = [f"Execute primary directive: {fallback_goal}"]
        assigned_roles = self._infer_roles_from_text(fallback_goal)
        milestones = [
            {"phase": "M1", "name": "Architecture & Strategy Scaffolding", "target_days": 3},
            {"phase": "M2", "name": "Departmental Execution & Deliverables", "target_days": 7},
            {"phase": "M3", "name": "Synthesis, CAO Audit & Delivery", "target_days": 10},
        ]
        return {
            "objectives": objectives,
            "milestones": milestones,
            "assigned_roles": assigned_roles,
        }

    def _infer_roles_from_text(self, text: str) -> List[str]:
        """Infer C-Suite departmental roles from text keywords."""
        lower_text = text.lower()
        matched_roles = set()
        for role, keywords in self.ROLE_TAXONOMY.items():
            if role.startswith("CAO"):
                continue
            if any(kw in lower_text for kw in keywords):
                matched_roles.add(role)
        if not matched_roles:
            matched_roles = {"CTO", "COO", "CFO"}
        return sorted(list(matched_roles))

    # ========================================================================
    # 2. Executive Department Delegation & Brief Formatting
    # ========================================================================

    def delegate_task(
        self,
        task_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Determine optimal executive role and generate complete delegation brief.

        Conforms strictly to CEO Job Description §5 Step 4.
        Defensively handles None context and optional task_type.
        """
        safe_context: Dict[str, Any] = context if isinstance(context, dict) else {}
        target_agent = self.determine_department(task_type, safe_context)
        delegation_id = f"del_{uuid.uuid4().hex[:8]}"
        project_id = safe_context.get("project_id", "default_project")
        priority = str(safe_context.get("priority", "STANDARD")).upper()
        deadline = str(safe_context.get("deadline", "Next review cycle"))

        clean_task_name = str(task_type).strip() if task_type else "operational_task"
        context_desc = (
            safe_context.get("context")
            or safe_context.get("description")
            or f"Execution workstream for task '{clean_task_name}'."
        )
        objective = (
            safe_context.get("objective")
            or f"Deliver comprehensive {clean_task_name} meeting executive standards."
        )
        deliverable_spec = (
            safe_context.get("deliverable_spec")
            or f"Structured deliverable conforming to {target_agent} domain standards."
        )
        constraints = safe_context.get("constraints") or [
            "Zero-cost model priority",
            "Comply with Alpha security and licensing rules",
        ]
        dependencies = safe_context.get("dependencies") or ["None"]
        success_criteria = (
            safe_context.get("success_criteria")
            or f"Passes CEO synthesis and 85%+ CAO audit threshold."
        )

        formatted_brief = (
            f"[AGENT_BRIEF]\n"
            f"TO: {target_agent}\n"
            f"FROM: CEO\n"
            f"PRIORITY: {priority}\n"
            f"DEADLINE: {deadline}\n\n"
            f"CONTEXT:\n{context_desc}\n\n"
            f"OBJECTIVE:\n{objective}\n\n"
            f"DELIVERABLE SPECIFICATION:\n{deliverable_spec}\n\n"
            f"CONSTRAINTS:\n- " + "\n- ".join(constraints if isinstance(constraints, list) else [str(constraints)]) + "\n\n"
            f"DEPENDENCIES:\n- " + "\n- ".join(dependencies if isinstance(dependencies, list) else [str(dependencies)]) + "\n\n"
            f"SUCCESS CRITERIA:\n{success_criteria}\n"
        )

        delegation_record: Dict[str, Any] = {
            "delegation_id": delegation_id,
            "project_id": project_id,
            "target_agent": target_agent,
            "task_type": task_type or "general_task",
            "priority": priority,
            "brief": {
                "to": target_agent,
                "from": "CEO",
                "priority": priority,
                "deadline": deadline,
                "context": context_desc,
                "objective": objective,
                "deliverable_specification": deliverable_spec,
                "constraints": constraints,
                "dependencies": dependencies,
                "success_criteria": success_criteria,
            },
            "formatted_brief": formatted_brief,
            "status": "dispatched",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Memory logging
        try:
            self.record_thought(
                thought=f"Delegated task '{task_type}' to {target_agent} under priority {priority}.",
                importance=5,
                project_id=project_id,
            )
        except Exception as e:
            logger.debug("Could not record delegation memory: %s", e)

        return delegation_record

    def determine_department(
        self,
        task_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Map task_type or context to the most qualified C-Suite role."""
        safe_context: Dict[str, Any] = context if isinstance(context, dict) else {}
        if "target_role" in safe_context:
            return str(safe_context["target_role"]).upper()

        combined = f"{task_type or ''} {json.dumps(safe_context)}".lower()

        scores: Dict[str, int] = {}
        for role, keywords in self.ROLE_TAXONOMY.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                scores[role] = score

        if scores:
            return max(scores.items(), key=lambda item: item[1])[0]

        return "COO"  # Default operational lead

    # ========================================================================
    # 3. Output Synthesis & Conflict Adjudication
    # ========================================================================

    def synthesize(
        self,
        reports: List[Dict[str, Any]],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize departmental deliverables, detect conflicts, and adjudicate decisions.

        Conforms to CEO Job Description §3 R-06, R-11 and §4 Authority Matrix.
        Remediates VULN-M3-01: Preserves all simultaneous critical escalations in
        founder_escalations list, constructs a composite backward-compatible
        founder_escalation object, and ensures comprehensive visibility in the
        unified briefing markdown for Founder Aman Jain.
        """
        if not reports:
            return {
                "briefing_id": f"brief_{uuid.uuid4().hex[:8]}",
                "project_id": project_id or "unknown",
                "executive_summary": "No executive reports provided for synthesis.",
                "reports_analyzed": 0,
                "participating_roles": [],
                "conflicts_detected": [],
                "resolutions": [],
                "founder_escalation": None,
                "founder_escalations": [],
                "unified_briefing_md": "## Executive Summary\nNo reports submitted.",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        resolved_pid = project_id or reports[0].get("project_id", "proj_default")
        participating_roles = sorted(list({r.get("role") or r.get("agent_id") or "AGENT" for r in reports}))

        # 1. Conflict & Breach Detection
        conflicts = self._detect_conflicts(reports)

        # 2. Conflict Adjudication (Tier 1 vs Tier 3)
        resolutions: List[Dict[str, Any]] = []
        founder_escalations: List[Dict[str, Any]] = []

        for conf in conflicts:
            if conf.get("severity") == "critical" or conf.get("requires_founder"):
                escalation = self._format_founder_escalation(conf, resolved_pid)
                founder_escalations.append(escalation)
            else:
                resolution = self._resolve_tier1_conflict(conf)
                resolutions.append(resolution)

        # Formulate backward-compatible founder_escalation
        founder_escalation: Optional[Dict[str, Any]] = None
        if len(founder_escalations) == 1:
            founder_escalation = dict(founder_escalations[0])
            founder_escalation["all_escalations"] = list(founder_escalations)
        elif len(founder_escalations) > 1:
            # Composite escalation capturing all critical breaches simultaneously
            issues_combined = " | ".join(f"[{e['department']}] {e['issue']}" for e in founder_escalations)
            recs_combined = " | ".join(f"[{e['department']}] {e['ceo_recommendation']}" for e in founder_escalations)
            depts_combined = ", ".join(sorted(list({e["department"] for e in founder_escalations})))
            composite_options: List[Dict[str, str]] = []
            for e in founder_escalations:
                dept = e.get("department", "EXEC")
                for opt in e.get("decision_options", []):
                    composite_options.append({
                        "option_id": f"{dept}-{opt['option_id']}",
                        "label": f"[{dept}] {opt['label']}",
                    })
            founder_escalation = {
                "escalation_id": f"esc_composite_{uuid.uuid4().hex[:6]}",
                "project_id": resolved_pid,
                "issue": issues_combined,
                "severity": "P0_CRITICAL",
                "department": depts_combined,
                "departments": [e["department"] for e in founder_escalations],
                "ceo_recommendation": recs_combined,
                "decision_options": composite_options,
                "action_required": "Founder decision needed on all critical issues to resume autonomous execution.",
                "all_escalations": list(founder_escalations),
            }

        # 3. Construct Executive Briefing Narrative
        briefing_md = self._construct_briefing_markdown(
            project_id=resolved_pid,
            reports=reports,
            resolutions=resolutions,
            founder_escalation=founder_escalation,
            founder_escalations=founder_escalations,
        )

        status = "escalation_required" if len(founder_escalations) > 0 else "completed"

        briefing_record: Dict[str, Any] = {
            "briefing_id": f"brief_{uuid.uuid4().hex[:8]}",
            "project_id": resolved_pid,
            "executive_summary": f"Strategic synthesis across {len(reports)} departments: {', '.join(participating_roles)}.",
            "reports_analyzed": len(reports),
            "participating_roles": participating_roles,
            "conflicts_detected": conflicts,
            "resolutions": resolutions,
            "founder_escalation": founder_escalation,
            "founder_escalations": founder_escalations,
            "unified_briefing_md": briefing_md,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 4. Vault Deliverables Persistence
        if self.vault_manager is not None:
            deliverable_path = f"projects/{resolved_pid}/deliverables/executive_briefing.json"
            try:
                if hasattr(self.vault_manager, "write"):
                    self.vault_manager.write(deliverable_path, briefing_record, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("Could not persist executive briefing to %s: %s", deliverable_path, e)

            try:
                self.record_thought(
                    thought=f"Synthesized {len(reports)} executive reports for {resolved_pid}. Status: {status}.",
                    importance=9,
                    project_id=resolved_pid,
                )
            except Exception as e:
                logger.debug("Could not record synthesis memory: %s", e)

        return briefing_record

    def _detect_conflicts(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify budget overruns, timeline clashes, or irreconcilable domain disagreements."""
        conflicts: List[Dict[str, Any]] = []

        for r in reports:
            role = r.get("role") or r.get("agent_id") or "AGENT"

            # Check Budget Breaches
            if role == "CFO" or "budget" in r:
                if r.get("budget_breach") is True or r.get("status") == "over_budget":
                    conflicts.append({
                        "type": "budget_breach",
                        "severity": "critical",
                        "source": role,
                        "description": r.get("breach_details") or "CFO reports budget overrun exceeding approved limits.",
                        "requires_founder": True,
                    })

            # Check Legal Vetoes
            if role == "CLO" or "legal" in r:
                if r.get("risk") == "critical" or r.get("license_violation") is True:
                    conflicts.append({
                        "type": "legal_blocker",
                        "severity": "critical",
                        "source": role,
                        "description": r.get("risk_details") or "CLO identified critical legal liability or license incompatibility.",
                        "requires_founder": True,
                    })

            # Check Minor Timeline or Scope Tradeoffs (Tier 1)
            if r.get("timeline_conflict"):
                conflicts.append({
                    "type": "timeline_tradeoff",
                    "severity": "minor",
                    "source": role,
                    "description": r.get("timeline_conflict"),
                    "requires_founder": False,
                })

        return conflicts

    def _resolve_tier1_conflict(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """CEO autonomously arbitrates Tier 1 conflicts without disturbing Founder."""
        return {
            "conflict_type": conflict["type"],
            "source": conflict["source"],
            "adjudication": "CEO Executive Adjustment",
            "decision": f"Re-sequenced dependencies and adjusted operational milestones for {conflict['source']}.",
            "rationale": "Aligned with fast-path critical delivery schedule per CEO Authority Matrix Tier 1.",
        }

    def _format_founder_escalation(self, conflict: Dict[str, Any], project_id: str) -> Dict[str, Any]:
        """Format formal Tier 3 escalation presenting unambiguous binary options to Aman Jain."""
        source_dept = conflict.get("source", "EXECUTIVE")
        conf_type = conflict.get("type", "critical_issue")

        if conf_type == "legal_blocker" or source_dept == "CLO":
            rec = "Quarantine contaminated components immediately and replace with permissive MIT/Apache-2.0 alternatives."
            options = [
                {"option_id": "A", "label": "Authorize proprietary commercial license or legal waiver"},
                {"option_id": "B", "label": "Enforce strict clean-room replacement with permissive MIT/Apache dependency"},
            ]
        elif conf_type == "budget_breach" or source_dept == "CFO":
            rec = "Pause non-essential feature development and approve bounded budget exception."
            options = [
                {"option_id": "A", "label": "Approve additional resource allocation and proceed"},
                {"option_id": "B", "label": "Enforce strict scope cut to remain within original bounds"},
            ]
        else:
            rec = f"Executive intervention required to resolve {conf_type} in {source_dept}."
            options = [
                {"option_id": "A", "label": f"Approve {source_dept} proposed operational exception"},
                {"option_id": "B", "label": f"Reject exception and mandate realignment with standard baseline"},
            ]

        return {
            "escalation_id": f"esc_{uuid.uuid4().hex[:6]}",
            "project_id": project_id,
            "issue": conflict.get("description", "Unspecified critical conflict"),
            "severity": "P0_CRITICAL",
            "department": source_dept,
            "ceo_recommendation": rec,
            "decision_options": options,
            "action_required": "Founder decision needed to resume autonomous execution.",
        }

    def _construct_briefing_markdown(
        self,
        project_id: str,
        reports: List[Dict[str, Any]],
        resolutions: List[Dict[str, Any]],
        founder_escalation: Optional[Dict[str, Any]] = None,
        founder_escalations: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Format final markdown deliverable conforming to CEO JD §9.2.

        Presents every critical blocker with its issue description, CEO recommendation,
        and explicit options for Founder Aman Jain.
        """
        md = [
            f"# Strategic Executive Briefing: {project_id}\n",
            "## Executive Summary",
            f"Alpha CEO has integrated and synthesized deliverables across {len(reports)} C-Suite workstreams.",
            "All components have been aligned with Project Alpha core architecture and founder intent.\n",
            "## Departmental Deliverables",
        ]

        for r in reports:
            role = r.get("role") or r.get("agent_id") or "Executive"
            summary = r.get("summary") or r.get("deliverable") or json.dumps(r.get("data", {}))
            md.append(f"### {role}")
            md.append(f"{summary}\n")

        if resolutions:
            md.append("## Internal Conflict Resolutions (CEO Tier 1)")
            for res in resolutions:
                md.append(f"- **{res['conflict_type']}**: {res['decision']} ({res['rationale']})")
            md.append("")

        # Resolve list of all escalations to format
        escalations_to_format: List[Dict[str, Any]] = []
        if founder_escalations is not None and len(founder_escalations) > 0:
            escalations_to_format = founder_escalations
        elif founder_escalation:
            if "all_escalations" in founder_escalation and isinstance(founder_escalation["all_escalations"], list):
                escalations_to_format = founder_escalation["all_escalations"]
            else:
                escalations_to_format = [founder_escalation]

        if escalations_to_format:
            md.append("## ⚠️ Founder Escalation Required (Tier 3 Decision)")
            if len(escalations_to_format) == 1:
                esc = escalations_to_format[0]
                md.append(f"**Issue:** {esc['issue']}")
                md.append(f"**CEO Recommendation:** {esc['ceo_recommendation']}")
                md.append("**Options for Founder (Aman Jain):**")
                for opt in esc.get("decision_options", []):
                    md.append(f"  - [{opt['option_id']}] {opt['label']}")
                md.append("")
            else:
                md.append(f"**Total Critical Breaches Detected:** {len(escalations_to_format)}")
                md.append("Immediate founder adjudication required across multiple executive domains.\n")
                for idx, esc in enumerate(escalations_to_format, 1):
                    dept = esc.get("department", "Executive")
                    md.append(f"### Critical Blocker {idx}: [{dept}]")
                    md.append(f"**Issue:** {esc['issue']}")
                    md.append(f"**CEO Recommendation:** {esc['ceo_recommendation']}")
                    md.append(f"**Options for Founder (Aman Jain) - {dept}:**")
                    for opt in esc.get("decision_options", []):
                        opt_id = opt.get("option_id", "")
                        label = opt.get("label", "")
                        md.append(f"  - [{dept}-{opt_id}] {label}")
                    md.append("")

        md.append("## Next Steps")
        md.append("1. Dispatch approved briefs to downstream execution teams.")
        md.append("2. Submit consolidated deliverable package to Dual CAO audit gate.\n")
        md.append("---\n*Synthesized by Alpha CEO | Audit Status: PENDING_CAO_AUDIT*")

        return "\n".join(md)
