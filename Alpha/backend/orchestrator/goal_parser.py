"""backend/orchestrator/goal_parser.py - Project Alpha Goal Parser.

Converts natural language founder directives into structured, validated
project briefs, workstream tasks, dependency definitions, and agent assignments.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.orchestrator.goal_parser")


class GoalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class WorkstreamTask(BaseModel):
    """Atomic task unit decomposed from user directive."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    task_id: str = Field(description="Unique task identifier, e.g. T-01")
    title: str = Field(description="Concise task title")
    description: str = Field(description="Detailed scope and requirements")
    lead_agent: str = Field(description="Responsible executive role, e.g. CTO, CPO, CDO")
    dependencies: List[str] = Field(default_factory=list, description="IDs of prerequisite tasks")
    estimated_duration_hours: float = Field(default=2.0, ge=0.1, description="Estimated duration in hours")
    deliverable_type: str = Field(default="general_spec", description="Expected output artifact type")
    is_parallelizable: bool = Field(default=True, description="Whether task can run concurrently")
    priority: GoalPriority = Field(default=GoalPriority.MEDIUM, description="Task execution priority")


class ParsedGoal(BaseModel):
    """Complete structured representation of parsed user directive."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    goal_id: str = Field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(default_factory=lambda: f"proj_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}")
    project_title: str = Field(description="Professional business/technical project title")
    description: str = Field(description="Cleaned, expanded goal description")
    complexity: int = Field(default=3, ge=1, le=5, description="Complexity tier 1 (simple) to 5 (enterprise)")
    priority: GoalPriority = Field(default=GoalPriority.MEDIUM, description="Overall project priority")
    required_agents: List[str] = Field(default_factory=list, description="List of assigned C-Suite roles")
    workstreams: List[WorkstreamTask] = Field(default_factory=list, description="Ordered workstream tasks")
    estimated_duration_hours: float = Field(default=8.0, ge=0.1, description="Total project critical path or work duration")
    suggested_model_tier: int = Field(default=3, ge=1, le=5, description="Recommended default model tier")
    founder_objectives: List[str] = Field(default_factory=list, description="High-signal key outcomes")
    key_risks: List[str] = Field(default_factory=list, description="Identified technical/operational risks")
    brief_markdown: str = Field(default="", description="Executive project brief in Markdown")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("required_agents", mode="before")
    @classmethod
    def normalize_agents(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            res = []
            for a in v:
                s = str(a).strip()
                if s.upper() == "CAO-CLAUDE":
                    res.append("CAO-Claude")
                elif s.upper() == "CAO-CHATGPT":
                    res.append("CAO-ChatGPT")
                else:
                    res.append(s.upper())
            return res
        return ["CEO", "CTO", "COO"]


class GoalParser:
    """Natural language directive parser for Project Alpha."""

    ROLE_TAXONOMY: Dict[str, List[str]] = {
        "CTO": ["tech", "architecture", "code", "backend", "frontend", "api", "database", "infrastructure", "security", "diagram", "docker", "python", "flutter"],
        "CMO": ["marketing", "growth", "branding", "copy", "advertising", "market", "campaign", "persona", "gtm", "seo"],
        "CPO": ["product", "prd", "feature", "user story", "roadmap", "requirements", "mvp", "spec", "flow"],
        "CDO": ["design", "ui", "ux", "wireframe", "styling", "visual", "tokens", "oled", "canvas", "theme"],
        "CFO": ["finance", "budget", "cost", "token", "roi", "pricing", "financial", "unit economics"],
        "COO": ["operations", "timeline", "schedule", "execution", "pep", "resource", "bottleneck", "milestone"],
        "CHRO": ["hr", "hire", "personnel", "recruiting", "team", "lifecycle"],
        "CIO": ["vault", "data", "schema", "storage", "governance", "backup"],
        "CSO": ["strategy", "okr", "vision", "alignment", "long-term", "positioning"],
        "CLO": ["legal", "license", "compliance", "gdpr", "contract", "terms", "ip", "patent"],
        "CAO-Claude": ["audit", "review", "rubric", "quality", "verification", "correctness"],
        "CAO-ChatGPT": ["code audit", "alternatives", "edge cases", "stress test"],
    }

    def __init__(
        self,
        model_router: Optional[ModelRouter] = None,
        vault_manager: Optional[VaultManager] = None,
    ) -> None:
        self.model_router = model_router
        self.vault_manager = vault_manager

    def parse(
        self,
        directive: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> ParsedGoal:
        """Parse raw directive into structured ParsedGoal."""
        if not directive or not str(directive).strip():
            raise ValueError("Directive cannot be empty or whitespace.")

        clean_text = str(directive).strip()
        resolved_pid = project_id or f"proj_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        parsed_goal: Optional[ParsedGoal] = None

        if self.model_router is not None:
            try:
                parsed_goal = self._parse_with_model(clean_text, resolved_pid)
            except Exception as e:
                logger.warning("Model-based goal parsing failed: %s. Falling back to heuristic parsing.", e)

        if parsed_goal is None:
            parsed_goal = self._parse_with_heuristics(clean_text, resolved_pid)

        # Generate markdown brief if not present
        if not parsed_goal.brief_markdown:
            parsed_goal.brief_markdown = self._format_brief_markdown(parsed_goal)

        # Persist brief to Vault if available
        if self.vault_manager is not None:
            try:
                self._persist_to_vault(parsed_goal)
            except Exception as e:
                logger.debug("Failed to persist parsed goal to Vault: %s", e)

        return parsed_goal

    def parse_goal(
        self,
        goal: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Adapter returning dictionary payload for orchestrator pipeline compatibility."""
        parsed = self.parse(directive=goal, project_id=project_id)
        return {
            "project_id": parsed.project_id,
            "project_title": parsed.project_title,
            "description": parsed.description,
            "complexity": parsed.complexity,
            "priority": parsed.priority.value,
            "required_agents": parsed.required_agents,
            "workstreams": [t.model_dump() for t in parsed.workstreams],
            "estimated_duration_hours": parsed.estimated_duration_hours,
            "parsed_goal": parsed,
        }

    def _parse_with_model(self, directive: str, project_id: str) -> Optional[ParsedGoal]:
        prompt = (
            f"You are the Alpha Executive Goal Intake Parser.\n"
            f"Analyze the following founder directive and decompose it into a structured business and engineering plan:\n\n"
            f"Directive: \"{directive}\"\n\n"
            f"Available C-Suite Agents: CEO, CTO, CMO, CPO, CDO, CFO, COO, CHRO, CIO, CSO, CLO, CAO-Claude, CAO-ChatGPT.\n\n"
            f"Respond ONLY with a valid JSON object matching this schema:\n"
            f"{{\n"
            f'  "project_title": "Concise Business Title",\n'
            f'  "description": "Expanded goal description",\n'
            f'  "complexity": 1-5,\n'
            f'  "priority": "low" | "medium" | "high" | "urgent",\n'
            f'  "required_agents": ["CEO", "CTO", ...],\n'
            f'  "founder_objectives": ["Obj 1", "Obj 2"],\n'
            f'  "key_risks": ["Risk 1", "Risk 2"],\n'
            f'  "estimated_duration_hours": 12.0,\n'
            f'  "workstreams": [\n'
            f'    {{\n'
            f'      "task_id": "T-01",\n'
            f'      "title": "Task title",\n'
            f'      "description": "Details",\n'
            f'      "lead_agent": "CPO",\n'
            f'      "dependencies": [],\n'
            f'      "estimated_duration_hours": 2.0,\n'
            f'      "deliverable_type": "product_prd",\n'
            f'      "is_parallelizable": true,\n'
            f'      "priority": "medium"\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )

        response_text = ""
        if hasattr(self.model_router, "invoke"):
            resp = self.model_router.invoke(
                prompt=prompt,
                system_prompt="You are a strict JSON-emitting executive parser for Project Alpha. Do not write preamble or markdown fences.",
                complexity=4,
                task_type="strategic_planning",
            )
            response_text = resp.content
        elif hasattr(self.model_router, "call"):
            response_text = self.model_router.call(
                prompt=prompt,
                system="Emit valid JSON only.",
                complexity=4,
                task_type="strategic_planning",
            )

        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(0))
        data["project_id"] = project_id
        return ParsedGoal(**data)

    def _parse_with_heuristics(self, directive: str, project_id: str) -> ParsedGoal:
        lower = directive.lower()

        # Priority detection
        priority = GoalPriority.MEDIUM
        if any(w in lower for w in ["urgent", "asap", "emergency", "critical", "p0", "immediately", "mission critical"]):
            priority = GoalPriority.URGENT
        elif any(w in lower for w in ["high priority", "important", "p1", "soon", "priority", "high"]):
            priority = GoalPriority.HIGH
        elif any(w in lower for w in ["low priority", "nice to have", "someday", "trivial", "low"]):
            priority = GoalPriority.LOW

        # Complexity inference
        word_count = len(directive.split())
        complexity = 3
        if word_count < 8:
            complexity = 1 if word_count < 5 else 2
        elif any(w in lower for w in ["enterprise", "microservices", "scalable", "distributed", "kubernetes", "audit", "security", "compiler", "operating system"]):
            complexity = 5
        elif any(w in lower for w in ["architecture", "refactor", "database", "full-stack", "system", "saas", "platform", "multi-agent", "orchestration"]):
            complexity = 4
        elif word_count > 30:
            complexity = 4

        # Department identification
        assigned = set(["CEO", "COO"])
        for role, keywords in self.ROLE_TAXONOMY.items():
            if role.startswith("CAO"):
                continue
            if any(kw in lower for kw in keywords):
                assigned.add(role)

        if "CTO" not in assigned and any(w in lower for w in ["build", "make", "create", "app", "site", "web", "platform", "system", "service"]):
            assigned.add("CTO")
        if "CPO" not in assigned and ("CTO" in assigned or "CDO" in assigned):
            assigned.add("CPO")

        # Always include CAO audit if complexity >= 4
        if complexity >= 4:
            assigned.add("CAO-Claude")
            assigned.add("CAO-ChatGPT")

        required_agents = sorted(list(assigned))

        # Generate sequential workstream tasks
        workstreams: List[WorkstreamTask] = []
        tid_counter = 1

        if "CPO" in required_agents:
            workstreams.append(WorkstreamTask(
                task_id=f"T-{tid_counter:02d}",
                title="Product Requirements & Scope Definition",
                description=f"Draft formal PRD and user stories for: {directive[:80]}",
                lead_agent="CPO",
                dependencies=[],
                estimated_duration_hours=2.0,
                deliverable_type="product_prd",
                is_parallelizable=True,
                priority=priority,
            ))
            tid_counter += 1

        if "CMO" in required_agents:
            workstreams.append(WorkstreamTask(
                task_id=f"T-{tid_counter:02d}",
                title="Market Positioning & Audience Definition",
                description="Determine target market, positioning, and key messaging.",
                lead_agent="CMO",
                dependencies=[],
                estimated_duration_hours=1.5,
                deliverable_type="marketing_brief",
                is_parallelizable=True,
                priority=priority,
            ))
            tid_counter += 1

        prd_dep = ["T-01"] if any(t.lead_agent == "CPO" for t in workstreams) else []

        if "CTO" in required_agents:
            cto_tid = f"T-{tid_counter:02d}"
            workstreams.append(WorkstreamTask(
                task_id=cto_tid,
                title="Technical Architecture & System Specification",
                description="Design components, data models, APIs, and Archify system diagrams.",
                lead_agent="CTO",
                dependencies=list(prd_dep),
                estimated_duration_hours=3.0,
                deliverable_type="technical_spec",
                is_parallelizable=False,
                priority=priority,
            ))
            tid_counter += 1

        if "CDO" in required_agents:
            workstreams.append(WorkstreamTask(
                task_id=f"T-{tid_counter:02d}",
                title="UI/UX Design System & Layout Tokens",
                description="Produce OLED Dark visual hierarchy and design tokens.",
                lead_agent="CDO",
                dependencies=list(prd_dep),
                estimated_duration_hours=2.0,
                deliverable_type="design_system",
                is_parallelizable=True,
                priority=priority,
            ))
            tid_counter += 1

        if "CFO" in required_agents:
            workstreams.append(WorkstreamTask(
                task_id=f"T-{tid_counter:02d}",
                title="Financial Feasibility & Budget Analysis",
                description="Assess token infrastructure cost and unit economics.",
                lead_agent="CFO",
                dependencies=list(prd_dep),
                estimated_duration_hours=1.0,
                deliverable_type="financial_plan",
                is_parallelizable=True,
                priority=priority,
            ))
            tid_counter += 1

        # Audit gate if complex
        if "CAO-Claude" in required_agents or "CAO-ChatGPT" in required_agents:
            prior_ids = [t.task_id for t in workstreams]
            workstreams.append(WorkstreamTask(
                task_id=f"T-{tid_counter:02d}",
                title="Dual CAO 5-Axis Quality Audit",
                description="Conduct rigorous architectural and security verification.",
                lead_agent="CAO-Claude",
                dependencies=prior_ids,
                estimated_duration_hours=1.5,
                deliverable_type="audit_report",
                is_parallelizable=False,
                priority=GoalPriority.HIGH,
            ))
            tid_counter += 1

        # Final release/synthesis task
        all_ids = [t.task_id for t in workstreams]
        workstreams.append(WorkstreamTask(
            task_id=f"T-{tid_counter:02d}",
            title="Executive Delivery & Founder Synthesis",
            description="Consolidate all departmental deliverables into executive briefing.",
            lead_agent="CEO",
            dependencies=all_ids,
            estimated_duration_hours=1.0,
            deliverable_type="executive_briefing",
            is_parallelizable=False,
            priority=priority,
        ))

        total_hours = sum(t.estimated_duration_hours for t in workstreams)
        title_words = directive.strip().split()[:6]
        project_title = " ".join(title_words).title()

        return ParsedGoal(
            project_id=project_id,
            project_title=f"Project {project_title}",
            description=directive,
            complexity=complexity,
            priority=priority,
            required_agents=required_agents,
            workstreams=workstreams,
            estimated_duration_hours=total_hours,
            suggested_model_tier=complexity,
            founder_objectives=[f"Deliver validated result for: {directive}"],
            key_risks=["Cross-departmental dependency delays", "Scope expansion beyond MVP"],
        )

    def _format_brief_markdown(self, goal: ParsedGoal) -> str:
        tasks_md = "\n".join(
            f"- **[{t.task_id}] {t.title}** (`{t.lead_agent}`): {t.description} (Est: {t.estimated_duration_hours}h, Deps: {t.dependencies or 'None'})"
            for t in goal.workstreams
        )
        return (
            f"# Project Brief: {goal.project_title}\n\n"
            f"**Project ID:** `{goal.project_id}`  \n"
            f"**Priority:** `{goal.priority.value.upper()}` | **Complexity:** `{goal.complexity}/5` | **Duration:** `~{goal.estimated_duration_hours}h`  \n"
            f"**Assigned C-Suite Agents:** {', '.join(goal.required_agents)}\n\n"
            f"## Strategic Directive\n{goal.description}\n\n"
            f"## Key Objectives\n" + "\n".join(f"- {o}" for o in goal.founder_objectives) + "\n\n"
            f"## Decomposed Workstreams & Execution Tasks\n{tasks_md}\n\n"
            f"## Key Risk Considerations\n" + "\n".join(f"- {r}" for r in goal.key_risks) + "\n"
        )

    def _persist_to_vault(self, goal: ParsedGoal) -> None:
        if self.vault_manager is None:
            return
        brief_path = f"projects/{goal.project_id}/brief.md"
        if hasattr(self.vault_manager, "write"):
            self.vault_manager.write(brief_path, {"markdown": goal.brief_markdown}, agent_id="CEO")
            manifest_path = f"projects/{goal.project_id}/manifest"
            manifest = {
                "project_id": goal.project_id,
                "project_title": goal.project_title,
                "description": goal.description,
                "status": "planning",
                "complexity": goal.complexity,
                "priority": goal.priority.value,
                "required_agents": goal.required_agents,
                "estimated_duration_hours": goal.estimated_duration_hours,
                "created_at": goal.created_at,
            }
            self.vault_manager.write(manifest_path, manifest, agent_id="CEO")
