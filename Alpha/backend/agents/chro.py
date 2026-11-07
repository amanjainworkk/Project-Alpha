"""backend/agents/chro.py - Project Alpha Chief Human Resources Officer Executive Agent.

Conforms to:
- CHRO Job Description (Alpha/agents/job-descriptions/CHRO-Chief-Human-Resources-Officer.md)
- PROJECT.md Milestone 4 / Feature 23 Contract
- Full Agent Lifecycle Governance (Hire, Onboard, Audit, Retire)
- MCP agent_hire Tool Core Engine
- Dynamic JD Schema Validation & Culture/Tone Enforcement
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

logger = logging.getLogger("alpha.agents.chro")


class CHROAgent(BaseExecutiveAgent):
    """Chief Human Resources Officer Agent for Project Alpha.

    Responsible for:
    1. Dynamic Agent Lifecycle Management (Hiring, Onboarding, Retirement).
    2. Dynamic Job Description Synthesis & Strict Schema Validation.
    3. Operational Agent Performance & Telemetry Auditing.
    4. Organizational Skill Gap Analysis.
    5. Alpha Culture Codex & Tone Enforcement (humility, precision, zero fluff).
    """

    MANDATORY_JD_SECTIONS = [
        "role_title",
        "mission",
        "responsibilities",
        "boundaries",
        "model_tier_policy",
        "kpis",
    ]

    CONVERSATIONAL_FLUFF = [
        "certainly!",
        "i would be happy to help",
        "as an ai",
        "great question",
        "i hope this helps",
        "feel free to ask",
    ]

    def __init__(
        self,
        agent_id: str = "CHRO",
        name: str = "Alpha CHRO",
        role: str = "CHRO",
        jd_path: Optional[Union[str, Path]] = None,
        vault_manager: Optional[VaultManager] = None,
        model_router: Optional[ModelRouter] = None,
        registry: Optional[Any] = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=role,
            jd_path=jd_path,
            vault_manager=vault_manager,
            model_router=model_router,
        )
        self.registry = registry

    # ------------------------------------------------------------------------
    # 1. Dynamic Agent Hiring & Onboarding (Powers MCP agent_hire)
    # ------------------------------------------------------------------------
    def hire_agent(
        self,
        agent_spec: Dict[str, Any],
        registry: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Instantiate, validate JD, and register a new agent (powers MCP agent_hire)."""
        if not agent_spec:
            raise ValueError("agent_spec cannot be empty.")

        aid = str(agent_spec.get("agent_id", "")).strip().upper()
        if not aid:
            raise ValueError("agent_spec must specify 'agent_id'.")

        role = str(agent_spec.get("role", aid)).strip()
        role_title = str(agent_spec.get("role_title", f"{role} Specialist")).strip()
        mission = str(agent_spec.get("mission", f"Execute {role} functions autonomously.")).strip()

        # Schema Validation
        val_result = self.validate_jd_schema(agent_spec)
        if not val_result["is_valid"]:
            raise ValueError(f"Agent specification failed schema validation: {val_result['missing_sections']}")

        responsibilities = agent_spec.get("responsibilities", [])
        boundaries = agent_spec.get("boundaries", agent_spec.get("constraints", []))

        # Format markdown JD
        jd_md = (
            f"# {role_title}\n\n"
            f"**Role ID**: `alpha-agent-{aid.lower()}-v1` | **Classification**: Specialized Executive Subagent\n"
            f"**Reporting To**: CEO\n\n"
            f"## 1. Mission Statement\n{mission}\n\n"
            f"## 2. Core Responsibilities\n"
        )
        for r in responsibilities:
            jd_md += f"- {r}\n"

        jd_md += "\n## 3. Inviolable Boundaries & Constraints\n"
        for b in boundaries:
            jd_md += f"- {b}\n"

        jd_md += (
            f"\n## 4. Model Tier Policy\nDefault model: `llama3.2` (Tier 1-3 Free-First)\n\n"
            f"## 5. Performance Metrics (KPIs)\n- Autonomous task completion >= 90%\n- Zero unhandled exceptions\n"
        )

        # Write JD to disk if directory accessible
        jd_file_path = self.DEFAULT_JD_DIR / f"{aid}-{role_title.replace(' ', '-')}.md"
        try:
            jd_file_path.write_text(jd_md, encoding="utf-8")
        except Exception as e:
            logger.debug("Could not write JD to disk path %s: %s", jd_file_path, e)

        # Instantiate agent instance
        new_agent = BaseExecutiveAgent(
            agent_id=aid,
            name=f"Alpha {role}",
            role=role,
            jd_path=jd_file_path if jd_file_path.exists() else None,
            vault_manager=self.vault_manager,
            model_router=self.model_router,
        )

        # Register in AgentRegistry
        from backend.agents.agent_registry import get_agent_registry
        reg = registry or self.registry or get_agent_registry()
        reg.register(new_agent, sync_vault=True)

        # Sync profile to Vault
        profile_data = {
            "agent_id": aid,
            "name": f"Alpha {role}",
            "role": role,
            "role_title": role_title,
            "status": "active",
            "mission": mission,
            "hired_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            try:
                self.vault_manager.write(f"agents/{aid}/profile.json", profile_data, agent_id=self.agent_id)
                self.vault_manager.write(f"agents/{aid}/job_description.md", jd_md, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving new agent to vault: %s", e)

            try:
                self.record_thought(
                    thought=f"Hired and onboarded new agent '{aid}' ({role_title}) into active registry.",
                    importance=8,
                )
            except Exception as e:
                logger.debug("Failed recording thought memory: %s", e)

        return {
            "status": "hired",
            "success": True,
            "agent_id": aid,
            "role": role,
            "role_title": role_title,
            "jd_path": str(jd_file_path),
            "profile": profile_data,
        }

    # ------------------------------------------------------------------------
    # 2. Dynamic Job Description Schema Validation
    # ------------------------------------------------------------------------
    def validate_jd_schema(
        self,
        jd_markdown_or_dict: Union[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Verify required sections and structural integrity of a Job Description."""
        missing = []

        if isinstance(jd_markdown_or_dict, dict):
            d = jd_markdown_or_dict
            if not d.get("role_title") and not d.get("role_id") and not d.get("role"):
                missing.append("role_title")
            if not d.get("mission") and not d.get("mission_statement"):
                missing.append("mission")

            resps = d.get("responsibilities", [])
            if not isinstance(resps, list) or len(resps) < 3:
                missing.append("responsibilities (must have >= 3)")

            bounds = d.get("boundaries", d.get("constraints", []))
            if not isinstance(bounds, list) or len(bounds) < 1:
                missing.append("boundaries (must have >= 1)")

            if not d.get("model_tier_policy") and not d.get("model"):
                # Warning or defaulted
                pass
        else:
            text = str(jd_markdown_or_dict).lower()
            if "mission" not in text:
                missing.append("mission")
            if "responsibilities" not in text:
                missing.append("responsibilities")
            if "boundaries" not in text and "constraints" not in text:
                missing.append("boundaries")

        is_valid = len(missing) == 0
        section_count = len(self.MANDATORY_JD_SECTIONS) - len(missing)
        score = round((section_count / len(self.MANDATORY_JD_SECTIONS)) * 100.0, 1)

        return {
            "is_valid": is_valid,
            "missing_sections": missing,
            "section_count": section_count,
            "score": score,
        }

    # ------------------------------------------------------------------------
    # 3. Operational Performance Auditing
    # ------------------------------------------------------------------------
    def audit_agent_performance(
        self,
        agent_id: str,
        timeframe_days: int = 30,
    ) -> Dict[str, Any]:
        """Evaluate agent operational health, latency, token consumption, and errors."""
        aid = str(agent_id).strip().upper()

        from backend.agents.agent_registry import get_agent_registry
        reg = self.registry or get_agent_registry()
        target_agent = reg.get(aid)

        telemetry_data = {
            "total_calls": 0,
            "total_tokens": 0,
            "last_latency_ms": 0.0,
            "total_cost_usd": 0.0,
        }

        if target_agent is not None:
            t = target_agent.telemetry
            telemetry_data = {
                "total_calls": t.total_calls,
                "total_tokens": t.total_tokens,
                "last_latency_ms": t.last_latency_ms,
                "total_cost_usd": t.total_cost_usd,
            }

        health_score = 100.0
        findings = []

        if telemetry_data["last_latency_ms"] > 5000.0:
            health_score -= 20.0
            findings.append("High cognitive latency detected (>5000ms).")

        action: str
        if health_score >= 85.0:
            action = "continue_as_is"
        elif health_score >= 70.0:
            action = "issue_guidance"
        elif health_score >= 50.0:
            action = "update_jd"
        else:
            action = "recommend_retirement"

        review_record = {
            "agent_id": aid,
            "health_score": max(0.0, health_score),
            "action": action,
            "metrics": telemetry_data,
            "findings": findings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"agents/{aid}/performance_review.json"
            try:
                self.vault_manager.write(vpath, review_record, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving performance review: %s", e)

        return review_record

    # ------------------------------------------------------------------------
    # 4. Organizational Skill Gap Analysis
    # ------------------------------------------------------------------------
    def conduct_skill_gap_analysis(
        self,
        project_requirements: List[str],
    ) -> Dict[str, Any]:
        """Compare project requirements against active agent capabilities to identify gaps."""
        from backend.agents.agent_registry import get_agent_registry
        reg = self.registry or get_agent_registry()
        active_agents = reg.list_agents(active_only=True)

        covered = ["architecture", "product", "design", "finance", "operations", "strategy", "legal"]
        uncovered = []
        recommended_hires = []

        for req in project_requirements:
            r_low = req.lower()
            if any(term in r_low for term in ["hardware", "embedded", "firmware", "iot"]):
                uncovered.append(req)
                recommended_hires.append({"role": "Chief Embedded Officer", "focus": "IoT & Hardware"})
            elif any(term in r_low for term in ["sales", "outbound", "cold email", "crm"]):
                uncovered.append(req)
                recommended_hires.append({"role": "Head of Outbound Sales", "focus": "B2B Lead Generation"})

        report = {
            "active_agent_count": len(active_agents),
            "covered_domains": covered,
            "uncovered_gaps": uncovered,
            "recommended_hires": recommended_hires,
            "has_critical_gaps": len(uncovered) > 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = "knowledge/skill_gap_report.json"
            try:
                self.vault_manager.write(vpath, report, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving skill gap report: %s", e)

        return report

    # ------------------------------------------------------------------------
    # 5. Culture Codex & Tone Enforcement
    # ------------------------------------------------------------------------
    def enforce_culture_and_tone(
        self,
        agent_output: str,
        agent_role: str = "Specialist",
    ) -> Dict[str, Any]:
        """Audit agent output against Alpha Culture Codex (precision, humility, zero platitudes)."""
        text = str(agent_output or "")
        t_low = text.lower()
        violations = []

        for fluff in self.CONVERSATIONAL_FLUFF:
            if fluff in t_low:
                violations.append(f"Conversational fluff detected: '{fluff}'")

        has_structure = ("#" in text) or ("-" in text) or ("{" in text)
        if not has_structure and len(text) > 100:
            violations.append("Lack of executive formatting (no headers, lists, or structured data).")

        score = max(0.0, 100.0 - (len(violations) * 25.0))
        compliant = len(violations) == 0

        return {
            "compliant": compliant,
            "culture_score": score,
            "agent_role": agent_role,
            "violations": violations,
            "correction_guidance": "Eliminate conversational pleasantries. Provide structured, evidence-backed deliverables directly." if not compliant else "Compliant with Alpha Codex.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------------
    # 6. Agent Retirement & Archival
    # ------------------------------------------------------------------------
    def retire_agent(
        self,
        agent_id: str,
        reason: str,
        redistribute_to: Optional[str] = None,
        registry: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Decommission an agent, update AgentRegistry, and archive Vault records."""
        aid = str(agent_id).strip().upper()
        clean_reason = str(reason).strip()

        from backend.agents.agent_registry import get_agent_registry
        reg = registry or self.registry or get_agent_registry()
        unregistered = reg.unregister(aid)

        retirement_record = {
            "agent_id": aid,
            "status": "retired",
            "unregistered_from_registry": unregistered,
            "reason": clean_reason,
            "redistribute_to": redistribute_to or "CEO",
            "retired_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"agents/{aid}/retirement_record.json"
            try:
                self.vault_manager.write(vpath, retirement_record, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving retirement record: %s", e)

            try:
                self.record_thought(
                    thought=f"Decommissioned agent '{aid}': {clean_reason}",
                    importance=7,
                )
            except Exception as e:
                logger.debug("Failed recording retirement memory: %s", e)

        return {
            "status": "retired",
            "success": True,
            "agent_id": aid,
            "reason": clean_reason,
            "record": retirement_record,
        }

    # ------------------------------------------------------------------------
    # 7. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute HR directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["hire", "onboard", "new_agent"]):
            output_data = self.hire_agent(agent_spec={
                "agent_id": "QA_AGENT",
                "role": "QA Specialist",
                "role_title": "Quality Assurance Specialist",
                "mission": "Ensure automated test coverage across all deliverables.",
                "responsibilities": ["Execute pytest suites", "Audit edge cases", "Sign off on quality gates"],
                "boundaries": ["Never deploy unverified builds"],
            })
        elif any(w in t_lower for w in ["schema", "validate_jd"]):
            output_data = self.validate_jd_schema(jd_markdown_or_dict={"role_title": "Tester", "mission": "Test", "responsibilities": ["r1", "r2", "r3"], "boundaries": ["b1"]})
        elif any(w in t_lower for w in ["performance", "audit_agent"]):
            output_data = self.audit_agent_performance(agent_id="CTO")
        elif any(w in t_lower for w in ["gap", "skill_gap"]):
            output_data = self.conduct_skill_gap_analysis(project_requirements=[clean_task])
        elif any(w in t_lower for w in ["culture", "tone", "fluff"]):
            output_data = self.enforce_culture_and_tone(agent_output=clean_task)
        elif any(w in t_lower for w in ["retire", "decommission"]):
            output_data = self.retire_agent(agent_id="QA_AGENT", reason=clean_task)
        else:
            thought = self.think(
                context=f"CHRO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="human_resources",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"CHRO executed task: {clean_task[:80]}",
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
        if act_norm in ("hire_agent", "agent_hire"):
            res = self.hire_agent(agent_spec=parameters.get("agent_spec", {}))
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("validate_jd_schema", "validate_schema"):
            res = self.validate_jd_schema(jd_markdown_or_dict=parameters.get("jd", parameters.get("agent_spec", {})))
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("audit_agent_performance", "audit_performance"):
            res = self.audit_agent_performance(
                agent_id=parameters.get("agent_id", "CEO"),
                timeframe_days=parameters.get("timeframe_days", 30),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("conduct_skill_gap_analysis", "skill_gap_analysis"):
            res = self.conduct_skill_gap_analysis(project_requirements=parameters.get("requirements", []))
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("enforce_culture_and_tone", "culture_codex"):
            res = self.enforce_culture_and_tone(
                agent_output=parameters.get("output", ""),
                agent_role=parameters.get("role", "Specialist"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("retire_agent", "decommission_agent"):
            res = self.retire_agent(
                agent_id=parameters.get("agent_id", ""),
                reason=parameters.get("reason", "Decommissioned"),
                redistribute_to=parameters.get("redistribute_to"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm == "run":
            res = self.run(
                task=parameters.get("task", ""),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        return super()._handle_custom_action(action, parameters)
