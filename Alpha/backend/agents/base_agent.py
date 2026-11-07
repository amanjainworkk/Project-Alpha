"""backend/agents/base_agent.py - Project Alpha Base Executive Agent.

Foundational abstract class for all Project Alpha C-Suite Executive Agents.
Provides:
1. Markdown Job Description (JD) locating, parsing, and system prompt synthesis.
2. In-memory working buffer + persistent VaultManager episodic memory integration.
3. ModelRouter cognitive operations (think, think_with_metadata, act).
4. Strict token budgeting, context packing, and sliding-window overflow protection.
5. Introspection telemetry (tokens, cost, latency, call history).
"""

from __future__ import annotations

import abc
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.model_router.base_client import estimate_tokens
from backend.model_router.router import ModelRouter
from backend.model_router.schemas import ModelConfig, ModelResponse, TokenUsage
from backend.vault.schemas import AgentStatus, MemoryType
from backend.vault.vault_manager import AccessDeniedError, VaultManager

logger = logging.getLogger("alpha.agents.base_agent")


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class JDParsedData:
    """Structured extraction of markdown Job Description."""
    role_id: str
    role_title: str
    core_purpose: str
    primary_framework: str
    model_tier_policy: str
    responsibilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    kpis: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)
    raw_markdown: str = ""


@dataclass
class AgentTelemetry:
    """Cumulative operational metrics for the executive agent."""
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    last_latency_ms: float = 0.0


# ============================================================================
# Base Executive Agent Abstract Class
# ============================================================================

class BaseExecutiveAgent(abc.ABC):
    """Abstract Base Class for all Project Alpha C-Suite Executive Agents.
    
    Conforms strictly to Milestone 3 / Feature 14 specifications and Interface Contracts.
    """

    DEFAULT_JD_DIR = Path(__file__).resolve().parent.parent.parent / "agents" / "job-descriptions"

    # Context window reserve parameters
    MAX_PROMPT_BUDGET_TOKENS = 6000  # Safe ceiling for 8K models (Tier 1-3)
    SYSTEM_PROMPT_BUDGET = 2000
    MEMORY_BUDGET_TOKENS = 1500

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        jd_path: Optional[Union[str, Path]] = None,
        vault_manager: Optional[VaultManager] = None,
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        """Initialize the executive agent with identity, JD, vault, and model router."""
        self.agent_id = str(agent_id).strip()
        self.name = str(name).strip()
        self.role = str(role).strip()
        self.status = AgentStatus.ACTIVE.value

        # Dependency Injection with safe defaults
        self.vault_manager = vault_manager
        self.model_router = model_router

        # State & Ephemeral Working Memory
        self.current_project_id: Optional[str] = None
        self.current_task: Optional[str] = None
        self.working_memory: List[Dict[str, Any]] = []
        self.state: Dict[str, Any] = {}
        self.telemetry = AgentTelemetry()

        # Job Description & System Prompt
        self.jd_path = self._resolve_jd_path(jd_path)
        self.jd_data: JDParsedData = self.load_jd(self.jd_path)
        self.system_prompt: str = self.build_system_prompt(self.jd_data)

    # ------------------------------------------------------------------------
    # Telemetry Properties
    # ------------------------------------------------------------------------

    @property
    def total_tokens_used(self) -> int:
        """Total tokens accumulated across all model invocations."""
        return self.telemetry.total_tokens

    @property
    def total_cost_usd(self) -> float:
        """Total estimated cost in USD accumulated across all model invocations."""
        return self.telemetry.total_cost_usd

    @property
    def call_history(self) -> List[Any]:
        """Inference call history from attached router if available."""
        if self.model_router is not None and hasattr(self.model_router, "call_history"):
            return self.model_router.call_history
        return []

    # ------------------------------------------------------------------------
    # 1. Markdown JD Loading & Parsing
    # ------------------------------------------------------------------------

    def _resolve_jd_path(self, explicit_path: Optional[Union[str, Path]]) -> Optional[Path]:
        """Locates the JD markdown file from explicit path or default directory."""
        if explicit_path:
            p = Path(explicit_path).resolve()
            if p.is_file():
                return p

        # Check default JD directory
        if not self.DEFAULT_JD_DIR.is_dir():
            return None

        # Try matching by agent_id or role prefix (e.g. 'CEO', 'CTO', 'CAO')
        search_terms = [
            self.agent_id,
            self.agent_id.split("-")[0],  # CAO-Claude -> CAO
            self.role.split()[0] if self.role else "",
        ]

        for term in search_terms:
            if not term:
                continue
            matches = list(self.DEFAULT_JD_DIR.glob(f"{term}-*.md"))
            if matches:
                return matches[0]

        return None

    def load_jd(self, jd_path: Optional[Path]) -> JDParsedData:
        """Loads and parses the markdown job description with safe fallbacks."""
        if jd_path and jd_path.is_file():
            try:
                content = jd_path.read_text(encoding="utf-8")
                return self.parse_jd_markdown(content)
            except Exception as e:
                logger.warning("Failed to read JD file at %s: %s. Using default persona.", jd_path, e)

        return self._create_fallback_jd_data()

    def parse_jd_markdown(self, markdown_text: str, role_id: Optional[str] = None) -> JDParsedData:
        """Robust extraction of structured persona components from markdown text.
        
        Hardened against H3 sub-heading lookahead truncation, table/bullet boundary
        formats, and specialized audit architecture schemas.
        """
        # 1. Role Title & ID
        role_id_match = re.search(r"###\s*Role ID:\s*`?([^\n`]+)`?", markdown_text, re.IGNORECASE)
        resolved_role_id = role_id or (role_id_match.group(1).strip() if role_id_match else f"alpha-agent-{self.agent_id.lower()}-v1")

        role_title = None
        for line in markdown_text.splitlines():
            line_s = line.strip()
            if line_s.startswith("# "):
                clean = re.sub(r"^#\s*[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff\u2b50-\u2b55\ufe0f]*\s*", "", line_s).strip()
                if "JOB DESCRIPTION" in clean.upper() or "AGENT JOB" in clean.upper():
                    continue
                role_title = clean
                break

        if not role_title:
            role_title = self.role

        # 2. Core Purpose / Mission Statement (Section 2)
        mission = ""
        mission_section = re.search(
            r"(?:^|\n)##[ \t]+[^\n]*MISSION STATEMENT[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
            markdown_text,
            re.DOTALL | re.IGNORECASE,
        )
        if mission_section:
            raw_mission = mission_section.group(1)
            # Extract blockquote if present
            bq_match = re.search(r">\s*(.*?)(?=\n\n|\n[A-Z]|\Z)", raw_mission, re.DOTALL)
            mission = bq_match.group(1).replace(">", "").strip() if bq_match else raw_mission.strip()
        if not mission:
            mission = f"Serve as Project Alpha's {self.role}, driving excellence and accountability."

        # 3. Primary Frameworks & Principles
        framework_match = re.search(
            r"###\s*Integrated (?:Frameworks|Principles):\s*([^\n]+)",
            markdown_text,
            re.IGNORECASE,
        )
        primary_framework = framework_match.group(1).strip() if framework_match else "Autonomous Systems Engineering"

        # 4. Model Tier Policy
        model_match = re.search(
            r"(?:^|\n)##[ \t]+[^\n]*MODEL\s+(?:USAGE|POLICY|ROUTING)[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
            markdown_text,
            re.DOTALL | re.IGNORECASE,
        )
        model_policy = model_match.group(1).strip()[:300] if model_match else "Free-first zero-cost routing"

        # 5. Core Responsibilities (Section 3 or CAO Architecture/Review Protocol)
        responsibilities: List[str] = []
        resp_section = re.search(
            r"(?:^|\n)##[ \t]+[^\n]*CORE RESPONSIBILITIES[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
            markdown_text,
            re.DOTALL | re.IGNORECASE,
        )
        if resp_section:
            resp_text = resp_section.group(1)
            # Tier A: R-xx subheadings (e.g. CEO, CHRO: ### R-01: ...)
            r_headings = re.findall(r"###\s*R-\d+:\s*([^\n]+)", resp_text)
            if r_headings:
                responsibilities = [h.strip() for h in r_headings[:15]]
            else:
                # Tier B: Numbered list items (e.g. CDO, CFO, CIO, CLO, CMO, COO, CPO, CSO)
                num_items = re.findall(r"^\d+\.\s*\*\*([^*]+)\*\*", resp_text, re.MULTILINE)
                if num_items:
                    responsibilities = [n.strip().rstrip(":") for n in num_items[:15]]
                else:
                    # Tier C: Numbered subheadings (e.g. CTO: ### 3.1 Technical Architecture Design)
                    subheads = re.findall(r"###\s*(?:\d+\.)+\d+\s*([^\n]+)", resp_text)
                    if subheads:
                        responsibilities = [s.strip() for s in subheads[:15]]
                    else:
                        # Tier D: General subheadings or bold bullets
                        gen_heads = re.findall(r"###\s*([^\n]+)", resp_text)
                        if gen_heads:
                            responsibilities = [g.strip() for g in gen_heads[:15]]
                        else:
                            bullets = re.findall(r"^\s*[-*]\s+\*\*([^*]+)\*\*", resp_text, re.MULTILINE)
                            if bullets:
                                responsibilities = [b.strip().rstrip(":") for b in bullets[:15]]

        # Tier E: CAO Specialization Fallback (Audit Architecture & Five-Axis Review Protocol)
        if not responsibilities:
            arch_match = re.search(
                r"(?:^|\n)##[ \t]+[^\n]*AUDIT ARCHITECTURE[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
                markdown_text,
                re.DOTALL | re.IGNORECASE,
            )
            if arch_match:
                specs = re.findall(r"^\d+\.\s*\*\*`?([^`*]+)`?\s*(?:\([^)]+\))?:?\*\*:?\s*([^\n]+)", arch_match.group(1), re.MULTILINE)
                for name, desc in specs:
                    responsibilities.append(f"{name.strip()}: {desc.strip()}")

            rev_match = re.search(
                r"(?:^|\n)##[ \t]+[^\n]*REVIEW PROTOCOL[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
                markdown_text,
                re.DOTALL | re.IGNORECASE,
            )
            if rev_match:
                axes = re.findall(r"###\s*(Axis\s*\d+:[^\n]+)", rev_match.group(1))
                responsibilities.extend([a.strip() for a in axes])

            responsibilities = responsibilities[:15]

        # 6. Inviolable Constraints & Boundaries (Sections 12, 13, 14, 15, or 18)
        constraints: List[str] = []
        boundaries_section = re.search(
            r"(?:^|\n)##[ \t]+[^\n]*(?:BOUNDAR|NON-NEGOTIABLE|ANTI-GOALS)[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
            markdown_text,
            re.DOTALL | re.IGNORECASE,
        )
        if boundaries_section:
            sec_text = boundaries_section.group(1)
            # Format 1: Table rows (| **Boundary** | Description |)
            tbl_rows = re.findall(r"\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|\n]+)", sec_text)
            for b, desc in tbl_rows:
                b_clean = b.strip()
                desc_clean = desc.strip()
                if b_clean.lower() not in ("boundary", "constraint", "rule", "---"):
                    constraints.append(f"{b_clean}: {desc_clean}" if desc_clean else b_clean)

            # Format 2: Bullets with bold (- [❌] **Title:** Description)
            bullets = re.findall(r"[-*]\s*(?:❌\s*)?\*\*([^*]+)\*\*[:\s—\-]*([^\n]*)", sec_text)
            for b, desc in bullets:
                b_clean = b.strip().rstrip(":")
                desc_clean = desc.strip()
                if b_clean:
                    constraints.append(f"{b_clean}: {desc_clean}" if desc_clean else b_clean)

            # Format 3: Numbered bold items (1. **Title:** Description)
            numbered = re.findall(r"^\d+\.\s*\*\*([^*]+)\*\*[:\s—\-]*([^\n]*)", sec_text, re.MULTILINE)
            for b, desc in numbered:
                b_clean = b.strip().rstrip(":")
                desc_clean = desc.strip()
                if b_clean:
                    constraints.append(f"{b_clean}: {desc_clean}" if desc_clean else b_clean)

            # Format 4: Emoji bullets (❌ Description or 🚫 Description)
            if not constraints:
                emojis = re.findall(r"^[ \t]*[❌🚫]\s*([^\n]+)", sec_text, re.MULTILINE)
                for e in emojis:
                    e_clean = e.strip()
                    if e_clean:
                        constraints.append(e_clean)

            # Format 5: Raw bullets fallback (- Description)
            if not constraints:
                raw_bullets = re.findall(r"^\s*[-*]\s+([^\n]+)", sec_text, re.MULTILINE)
                for r in raw_bullets:
                    r_clean = r.strip()
                    if r_clean:
                        constraints.append(r_clean)

        # 7. KPIs & Performance Metrics
        kpis: List[str] = []
        perf_section = re.search(
            r"(?:^|\n)##[ \t]+[^\n]*(?:PERFORMANCE METRIC|KPIS?)[^\n]*\n+(.*?)(?=\n##(?!\#)|\Z)",
            markdown_text,
            re.DOTALL | re.IGNORECASE,
        )
        if perf_section:
            p_text = perf_section.group(1)
            # Table format (| Metric | Target |)
            rows = re.findall(r"\|\s*([^|\n]+)\s*\|\s*([^|\n]+)\s*\|", p_text)
            for r in rows:
                name, target = r[0].strip(), r[1].strip()
                if name.lower() not in ("metric", "criterion", "dimension", "kpi", "area", "category", "success metric") and not name.startswith("---"):
                    if target and not target.startswith("---"):
                        kpis.append(f"{name}: {target}")
            # Bullet format (- **Metric:** Target)
            if not kpis:
                p_bullets = re.findall(r"[-*]\s*\*\*([^*]+)\*\*[:\s]*([^\n]*)", p_text)
                for b in p_bullets:
                    name, target = b[0].strip().rstrip(":"), b[1].strip()
                    if name:
                        kpis.append(f"{name}: {target}" if target else name)

        return JDParsedData(
            role_id=resolved_role_id,
            role_title=role_title,
            core_purpose=mission,
            primary_framework=primary_framework,
            model_tier_policy=model_policy,
            responsibilities=responsibilities,
            constraints=constraints[:10],
            kpis=kpis[:8],
            raw_markdown=markdown_text,
        )

    def _create_fallback_jd_data(self) -> JDParsedData:
        """Provides safe fallback persona if JD markdown file is missing."""
        return JDParsedData(
            role_id=f"alpha-agent-{self.agent_id.lower()}-v1",
            role_title=self.role or f"{self.agent_id} Executive",
            core_purpose=f"Execute {self.role} duties autonomously within Project Alpha.",
            primary_framework="Direct Execution & Structured Synthesis",
            model_tier_policy="Zero-cost-first tiered routing",
            responsibilities=["Execute domain tasks", "Log decisions in Vault", "Maintain quality standards"],
            constraints=["Never fabricate data", "Respect role-based access limits", "Escalate unresolvable conflicts"],
            kpis=["Task completion rate > 95%", "Zero unhandled exceptions"],
        )

    def build_system_prompt(self, parsed: JDParsedData) -> str:
        """Synthesizes a token-efficient system prompt (target: ~1,800 tokens)."""
        prompt_parts = [
            f"# YOU ARE THE {parsed.role_title.upper()} OF PROJECT ALPHA",
            f"Agent ID: {self.agent_id} | Role ID: {parsed.role_id}",
            f"Role: {self.role} | Full Title: {parsed.role_title}",
            "",
            "## 1. CORE PURPOSE & MISSION",
            parsed.core_purpose,
            "",
            "## 2. OPERATING FRAMEWORKS & PRINCIPLES",
            f"- Primary Doctrine: {parsed.primary_framework}",
            f"- Model Tier Policy: {parsed.model_tier_policy[:200]}",
            "",
            "## 3. CORE RESPONSIBILITIES",
        ]
        if parsed.responsibilities:
            for r in parsed.responsibilities:
                prompt_parts.append(f"- {r}")
        else:
            prompt_parts.append(f"- Oversee all {self.role} operations for Project Alpha.")

        prompt_parts.extend(["", "## 4. INVIOLABLE CONSTRAINTS & BOUNDARIES"])
        if parsed.constraints:
            for c in parsed.constraints:
                prompt_parts.append(f"- {c}")
        else:
            prompt_parts.append("- Never fabricate facts or deliver unverified assumptions.")
            prompt_parts.append("- Never write to vault paths outside your authorized RBAC domain.")

        prompt_parts.extend([
            "",
            "## 5. OUTPUT STANDARDS",
            "- Deliver clear, actionable, executive-grade outputs.",
            "- Structure responses with clear headings, bullet points, and data tables where suitable.",
            "- Adhere strictly to the Free-First token budget and local-first architecture.",
        ])

        return "\n".join(prompt_parts)

    # ------------------------------------------------------------------------
    # 2. Memory & Vault Integration
    # ------------------------------------------------------------------------

    def record_thought(
        self,
        thought: str,
        importance: int = 1,
        project_id: Optional[str] = None,
    ) -> str:
        """Records an internal thought/observation to working memory and Vault."""
        if importance < 1 or importance > 10:
            raise ValueError(f"importance must be between 1 and 10, got {importance}")

        pid = project_id or self.current_project_id
        thought_entry = {
            "type": MemoryType.OBSERVATION.value,
            "content": thought,
            "importance": importance,
            "project_id": pid,
            "agent_id": self.agent_id,
            "timestamp": time.time(),
        }
        self.working_memory.append(thought_entry)

        # Evict oldest working memory if buffer exceeds 50 items
        if len(self.working_memory) > 50:
            self.working_memory.pop(0)

        # Persist to Vault if available
        if self.vault_manager is not None:
            try:
                return self.vault_manager.append_memory(
                    agent_id=self.agent_id,
                    memory_type=MemoryType.OBSERVATION.value,
                    content=thought,
                    importance=importance,
                    project_id=pid,
                )
            except Exception as e:
                logger.warning("Failed to persist thought to Vault: %s", e)

        return f"mem_{self.agent_id}_local_{len(self.working_memory)}"

    def record_decision(
        self,
        summary: str,
        rationale: str = "",
        importance: int = 5,
        project_id: Optional[str] = None,
    ) -> str:
        """Records a formal executive decision into episodic memory and Vault."""
        if importance < 1 or importance > 10:
            raise ValueError(f"importance must be between 1 and 10, got {importance}")

        pid = project_id or self.current_project_id
        content = f"DECISION: {summary}"
        if rationale:
            content += f" | RATIONALE: {rationale}"

        decision_entry = {
            "type": MemoryType.DECISION.value,
            "content": content,
            "importance": importance,
            "project_id": pid,
            "agent_id": self.agent_id,
            "timestamp": time.time(),
        }
        self.working_memory.append(decision_entry)

        if len(self.working_memory) > 50:
            self.working_memory.pop(0)

        if self.vault_manager is not None:
            try:
                return self.vault_manager.append_memory(
                    agent_id=self.agent_id,
                    memory_type=MemoryType.DECISION.value,
                    content=content,
                    importance=importance,
                    project_id=pid,
                )
            except Exception as e:
                logger.warning("Failed to record decision in Vault: %s", e)

        return f"mem_{self.agent_id}_decision_{len(self.working_memory)}"

    def get_recent_memories(self, n: int = 10, min_importance: int = 1) -> List[Dict[str, Any]]:
        """Retrieves recent memories from SQLite store, contract store, or local working memory."""
        # 1. Try real VaultManager with SQLite
        if self.vault_manager is not None and hasattr(self.vault_manager, "sqlite") and hasattr(self.vault_manager.sqlite, "query_memories"):
            try:
                memories = self.vault_manager.sqlite.query_memories(
                    agent_id=self.agent_id,
                    limit=n,
                    min_importance=min_importance,
                    project_id=self.current_project_id,
                )
                if memories:
                    return memories
            except Exception as e:
                logger.debug("Vault SQLite query_memories failed: %s. Trying fallback.", e)

        # 2. Try in-memory ContractVaultManager from conftest
        if self.vault_manager is not None and hasattr(self.vault_manager, "memories"):
            matching = [
                m for m in self.vault_manager.memories
                if m.get("agent_id") == self.agent_id and m.get("importance", 1) >= min_importance
            ]
            if matching:
                return matching[-n:]

        # 3. Fallback to local in-memory buffer
        filtered = [
            m for m in self.working_memory
            if m.get("importance", 1) >= min_importance
        ]
        return filtered[-n:]

    def search_memory(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Semantic search across episodic memories in ChromaDB / Vault."""
        if self.vault_manager is not None:
            prefix = f"agents/{self.agent_id}"
            return self.vault_manager.search(query=query, n_results=n_results, path_prefix=prefix)
        return []

    # ------------------------------------------------------------------------
    # 3. Cognitive Operations: Think & Act
    # ------------------------------------------------------------------------

    def think(
        self,
        context: str,
        complexity: Optional[int] = None,
        task_type: str = "general",
        **kwargs: Any,
    ) -> str:
        """Executes a cognitive reasoning cycle through the ModelRouter."""
        response = self.think_with_metadata(
            context=context,
            complexity=complexity,
            task_type=task_type,
            **kwargs,
        )
        return response.content

    def think_with_metadata(
        self,
        context: str,
        complexity: Optional[int] = None,
        task_type: str = "general",
        **kwargs: Any,
    ) -> ModelResponse:
        """Executes reasoning returning full telemetry envelope and accounting metrics."""
        packed_prompt = self.pack_context(context)
        comp = complexity or 2

        if self.model_router is None:
            # Graceful fallback when running in headless mode without a model router
            content = f"[{self.role}] Fallback thought output: {context[:120]}"
            prompt_tokens = estimate_tokens(packed_prompt)
            completion_tokens = estimate_tokens(content)
            total_tokens = prompt_tokens + completion_tokens
            response = ModelResponse(
                content=content,
                model="fallback",
                provider="local",
                tier=comp,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=1.0,
                cost_usd=0.0,
            )
            setattr(response, "token_usage", response.usage or response.total_tokens)
            return response

        # Check whether router supports invoke() or standard call()
        if hasattr(self.model_router, "invoke"):
            response = self.model_router.invoke(
                prompt=packed_prompt,
                system_prompt=self.system_prompt,
                complexity=comp,
                task_type=task_type,
                agent_role=self.role,
                agent_id=self.agent_id,
                **kwargs,
            )
        else:
            # ContractModelRouter or generic mock router
            content = self.model_router.call(
                prompt=packed_prompt,
                system=self.system_prompt,
                task_type=task_type,
                complexity=comp,
                agent_role=self.role,
                **kwargs,
            )
            prompt_tokens = estimate_tokens(packed_prompt)
            completion_tokens = estimate_tokens(content)
            total_tokens = prompt_tokens + completion_tokens
            response = ModelResponse(
                content=content,
                model="contract-model",
                provider="mock",
                tier=comp,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=5.0,
                cost_usd=0.0,
            )

        # Ensure token_usage attribute exists on response
        setattr(response, "token_usage", response.usage or response.total_tokens)

        # Update cumulative telemetry
        self.telemetry.total_calls += 1
        self.telemetry.total_prompt_tokens += response.prompt_tokens
        self.telemetry.total_completion_tokens += response.completion_tokens
        self.telemetry.total_tokens += response.total_tokens
        self.telemetry.total_cost_usd += response.cost_usd
        self.telemetry.last_latency_ms = response.latency_ms

        # Record thought trace to working memory
        preview = response.content[:120].replace("\n", " ")
        self.record_thought(f"Inference output for '{task_type}': {preview}...", importance=1)

        return response

    def act(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Executes an action with standardized error handling and telemetry dispatch."""
        action_name = str(action).lower().strip()
        try:
            if action_name in ("record_thought", "record_memory"):
                content = parameters.get("thought") or parameters.get("content", "")
                importance = parameters.get("importance", 1)
                mid = self.record_thought(
                    thought=content,
                    importance=importance,
                    project_id=parameters.get("project_id"),
                )
                return {"status": "success", "success": True, "action": action, "memory_id": mid}

            elif action_name == "record_decision":
                summary = parameters.get("summary") or parameters.get("content", "")
                rationale = parameters.get("rationale", "")
                importance = parameters.get("importance", 5)
                mid = self.record_decision(
                    summary=summary,
                    rationale=rationale,
                    importance=importance,
                    project_id=parameters.get("project_id"),
                )
                return {
                    "status": "success",
                    "success": True,
                    "action": action,
                    "decision_id": mid,
                    "memory_id": mid,
                }

            elif action_name == "read_vault":
                if not self.vault_manager:
                    return {"status": "error", "success": False, "error": "VaultManager not attached"}
                data = self.vault_manager.read(parameters["path"])
                return {"status": "success", "success": True, "path": parameters["path"], "data": data}

            elif action_name == "write_vault":
                if not self.vault_manager:
                    return {"status": "error", "success": False, "error": "VaultManager not attached"}
                ok = self.vault_manager.write(
                    path=parameters["path"],
                    data=parameters["data"],
                    agent_id=self.agent_id,
                )
                return {
                    "status": "success" if ok else "error",
                    "success": ok,
                    "path": parameters["path"],
                }

            elif action_name == "search_vault":
                if not self.vault_manager:
                    return {"status": "error", "success": False, "error": "VaultManager not attached"}
                results = self.vault_manager.search(
                    query=parameters["query"],
                    n_results=parameters.get("top_k", 5),
                    path_prefix=parameters.get("path_prefix"),
                )
                return {"status": "success", "success": True, "results": results}

            return self._handle_custom_action(action_name, parameters)

        except AccessDeniedError as ade:
            logger.warning("Agent '%s' access denied during action '%s': %s", self.agent_id, action, ade)
            return {"status": "error", "success": False, "action": action, "error": f"Access Denied: {ade}"}
        except Exception as e:
            logger.error("Error executing action '%s' for agent '%s': %s", action, self.agent_id, e)
            return {"status": "error", "success": False, "action": action, "error": str(e)}

    def _handle_custom_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Hook for derived executive agent classes to implement role-specific actions."""
        return {"status": "error", "success": False, "action": action, "error": f"Unknown action: '{action}'"}

    # ------------------------------------------------------------------------
    # 4. Context Packing & Token Window Protection
    # ------------------------------------------------------------------------

    def pack_context(
        self,
        task_input: str,
        project_id: Optional[str] = None,
        max_input_tokens: Optional[int] = None,
    ) -> str:
        """Packs memory and task context within strict token budgets to prevent overflow."""
        budget = max_input_tokens or self.MAX_PROMPT_BUDGET_TOKENS

        # 1. Truncate task input if it alone exceeds budget
        task_tokens = estimate_tokens(task_input)
        if task_tokens > budget:
            return self.prune_context(task_input, max_tokens=budget)

        # 2. Extract recent memories within memory budget
        memory_budget = min(self.MEMORY_BUDGET_TOKENS, budget - task_tokens)
        recent_mems = self.get_recent_memories(n=5)
        mem_snippets: List[str] = []
        cur_mem_tokens = 0

        for m in recent_mems:
            snippet = f"- [{m.get('memory_type', m.get('type', 'observation'))}]: {m.get('memory_content') or m.get('content', '')}"
            snip_tokens = estimate_tokens(snippet)
            if cur_mem_tokens + snip_tokens > memory_budget:
                break
            mem_snippets.append(snippet)
            cur_mem_tokens += snip_tokens

        # Assemble packed context
        packed = []
        if mem_snippets:
            packed.append("## RELEVANT AGENT MEMORY:")
            packed.extend(mem_snippets)
            packed.append("")

        packed.append("## TASK INPUT:")
        packed.append(task_input)

        return "\n".join(packed)

    def prune_context(self, text: str, max_tokens: int) -> str:
        """Sliding-window middle pruning to strictly protect context windows."""
        total_tokens = estimate_tokens(text)
        if total_tokens <= max_tokens:
            return text

        # Preserve top 60% and bottom 30% of allowed token budget
        head_tokens = int(max_tokens * 0.60)
        tail_tokens = int(max_tokens * 0.30)

        # Approximate character slice positions (1 token ~= 4 chars)
        head_chars = head_tokens * 4
        tail_chars = tail_tokens * 4

        head_part = text[:head_chars]
        tail_part = text[-tail_chars:] if tail_chars > 0 else ""

        omitted_tokens = total_tokens - (head_tokens + tail_tokens)
        separator = f"\n\n[... {omitted_tokens} tokens omitted to prevent context window overflow ...]\n\n"

        return head_part + separator + tail_part

    # ------------------------------------------------------------------------
    # 5. Serialization & Introspection
    # ------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current agent state and telemetry."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "current_project_id": self.current_project_id,
            "current_task": self.current_task,
            "working_memory_count": len(self.working_memory),
            "telemetry": {
                "total_calls": self.telemetry.total_calls,
                "total_tokens": self.telemetry.total_tokens,
                "total_cost_usd": round(self.telemetry.total_cost_usd, 6),
                "last_latency_ms": round(self.telemetry.last_latency_ms, 2),
            },
        }

    def reset_telemetry(self) -> None:
        """Resets accumulated telemetry metrics."""
        self.telemetry = AgentTelemetry()
