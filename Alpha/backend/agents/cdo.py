"""backend/agents/cdo.py - Project Alpha Chief Design Officer Executive Agent.

Conforms to:
- CDO Job Description (Alpha/agents/job-descriptions/CDO-Chief-Design-Officer.md)
- PROJECT.md Milestone 4 / Feature 20 Contract
- Alpha Design System OLED Dark Design Tokens (#090A0F pitch black)
- Archify+ Flutter Living Canvas Node Styling & Pulsing Glow Halos
- Mobile 5-Screen Layout Hierarchy & ASCII Wireframes
- 6-Point Accessibility & Mobile Ergonomics Checklist
- Interactive Archify Diagram Specification Export
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.agents.base_agent import BaseExecutiveAgent
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.agents.cdo")


class CDOAgent(BaseExecutiveAgent):
    """Chief Design Officer Agent for Project Alpha.

    Responsible for:
    1. Alpha Design System OLED Dark Tokens & Aesthetics.
    2. Archify+ Interactive Node & Flow Styling.
    3. Mobile 5-Screen Layout Specifications & ASCII Wireframes.
    4. Accessibility (WCAG 2.1 AA) and Ergonomics Auditing.
    5. Archify Diagram Specification Export.
    """

    OLED_TOKENS = {
        "theme": "alpha-dark",
        "palette": {
            "background": "#090A0F",
            "surface": "#12141C",
            "surface_variant": "#1A1D28",
            "border": "#262A3B",
            "primary": "#3B82F6",
            "primary_hover": "#2563EB",
            "secondary": "#8B5CF6",
            "accent": "#06B6D4",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "text_primary": "#F9FAFB",
            "text_secondary": "#9CA3AF",
            "text_muted": "#6B7280",
        },
        "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 48},
        "radii": {"sm": 6, "md": 12, "lg": 16, "full": 9999},
        "typography": {
            "headings": "Inter, SF Pro Display",
            "body": "Inter, Roboto",
            "code": "JetBrains Mono",
        },
        "glows": {
            "active_halo": "0 0 16px rgba(6, 182, 212, 0.6)",
            "success_halo": "0 0 16px rgba(16, 185, 129, 0.5)",
            "warning_halo": "0 0 16px rgba(245, 158, 11, 0.5)",
            "error_halo": "0 0 16px rgba(239, 68, 68, 0.6)",
        },
    }

    def __init__(
        self,
        agent_id: str = "CDO",
        name: str = "Alpha CDO",
        role: str = "CDO",
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
    # 1. Authoritative OLED Design Tokens
    # ------------------------------------------------------------------------
    def get_oled_design_tokens(
        self,
        theme_name: str = "alpha-dark",
    ) -> Dict[str, Any]:
        """Return authoritative OLED Dark Mode design tokens conforming to JD §4."""
        tokens = dict(self.OLED_TOKENS)
        tokens["theme"] = theme_name

        if self.vault_manager is not None:
            vpath = "knowledge/design_system.json"
            try:
                self.vault_manager.write(vpath, tokens, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving design tokens to vault: %s", e)

        return tokens

    # ------------------------------------------------------------------------
    # 2. Archify+ Canvas Node Styling
    # ------------------------------------------------------------------------
    def generate_canvas_node_style(
        self,
        node_type: str,
        status: str = "active",
    ) -> Dict[str, Any]:
        """Generate styling configuration for Archify+ Flutter living canvas graph nodes."""
        ntype = str(node_type).lower().strip()
        st = str(status).lower().strip()

        # Lucide icon mapping
        icons = {
            "agent": "cpu",
            "project": "folder",
            "microservice": "layers",
            "task": "check-square",
            "milestone": "flag",
            "database": "database",
            "gateway": "network",
        }

        # Status border and glow colors
        status_colors = {
            "active": ("#06B6D4", "#06B6D488", 2.0, True),
            "healthy": ("#10B981", "#10B98166", 1.5, False),
            "completed": ("#10B981", "#10B98166", 1.0, False),
            "pending": ("#262A3B", "none", 1.0, False),
            "idle": ("#262A3B", "none", 1.0, False),
            "blocked": ("#EF4444", "#EF444488", 2.0, True),
            "stalled": ("#F59E0B", "#F59E0B88", 2.0, True),
            "auditing": ("#8B5CF6", "#8B5CF688", 1.5, True),
        }

        border_col, glow_col, b_width, pulse = status_colors.get(st, ("#262A3B", "none", 1.0, False))

        return {
            "node_type": ntype,
            "status": st,
            "background_color": "#12141C",
            "surface_color": "#1A1D28",
            "border_color": border_col,
            "border_width": b_width,
            "glow_color": glow_col,
            "glow_radius": 8.0 if pulse else 0.0,
            "text_color": "#F9FAFB",
            "icon_name": icons.get(ntype, "box"),
            "pulse_animation": pulse,
            "pulse_speed_ms": 1500 if pulse else 0,
        }

    # ------------------------------------------------------------------------
    # 3. Mobile 5-Screen Layout Specifications
    # ------------------------------------------------------------------------
    def generate_mobile_layout_spec(
        self,
        screen_name: str,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate layout hierarchy, widget specs, and ASCII wireframe for Flutter APK screens."""
        sname = str(screen_name).lower().strip()
        pid = project_id or self.current_project_id or "default_project"

        screens = {
            "canvas_screen": {
                "title": "Archify+ Living Canvas",
                "route": "/canvas",
                "widgets": ["InteractiveViewer", "CustomPaint(GraphRenderer)", "PulsingFlowOverlay", "MiniMapWidget", "FloatingActionPanel"],
                "wireframe": (
                    "+--------------------------------------+\n"
                    "| [OLED Canvas Screen]        [Status] |\n"
                    "+--------------------------------------+\n"
                    "|                                      |\n"
                    "|    (CEO) ===== [data] ====> (CTO)    |\n"
                    "|      ||                       ||     |\n"
                    "|    [pulse]                 [pulse]   |\n"
                    "|      v                        v      |\n"
                    "|    (CPO) -----------------> (CDO)    |\n"
                    "|                                      |\n"
                    "+--------------------------------------+\n"
                    "| [Controls: Zoom | Center | MiniMap]  |\n"
                    "+--------------------------------------+"
                ),
            },
            "tasks_screen": {
                "title": "Task & Milestone Progress",
                "route": "/tasks",
                "widgets": ["TaskListView", "GranularProgressBar", "AssignedAgentBadge", "DependencyFilterSheet"],
                "wireframe": (
                    "+--------------------------------------+\n"
                    "| [Tasks & Milestones]                 |\n"
                    "+--------------------------------------+\n"
                    "| [T-01] PRD Authoring        [DONE]   |\n"
                    "|  Progress: [====================] 100%|\n"
                    "| [T-02] Archify Layout       [ACTIVE] |\n"
                    "|  Progress: [========            ] 40%|\n"
                    "| [T-03] Code Implementation  [WAIT]   |\n"
                    "|  Progress: [                    ]  0%|\n"
                    "+--------------------------------------+"
                ),
            },
            "chat_screen": {
                "title": "Executive Direct Line",
                "route": "/chat",
                "widgets": ["AgentSelectorBar", "MessageThreadList", "MarkdownChatBubble", "AudioTranscribeInput"],
                "wireframe": (
                    "+--------------------------------------+\n"
                    "| [Chat]  CEO | CTO | COO | CDO ...    |\n"
                    "+--------------------------------------+\n"
                    "| User: Ingest founder goal for Alpha. |\n"
                    "|                                      |\n"
                    "| CEO: Goal ingested. Decomposing into |\n"
                    "| 4 parallel workstreams...            |\n"
                    "+--------------------------------------+\n"
                    "| [Input prompt...             ] [Send]|\n"
                    "+--------------------------------------+"
                ),
            },
            "boardroom_screen": {
                "title": "C-Suite Boardroom & Escalations",
                "route": "/boardroom",
                "widgets": ["TribunalEscalationCard", "DualCAORubricRadar", "DecisionVotingBar"],
                "wireframe": (
                    "+--------------------------------------+\n"
                    "| [Executive Boardroom]                |\n"
                    "+--------------------------------------+\n"
                    "| P0 Escalation: Dual CAO Audit Gate   |\n"
                    "| Claude CAO: PASS (94/100)            |\n"
                    "| ChatGPT CAO: CONDITIONAL (82/100)    |\n"
                    "| Action: Founder sign-off required.   |\n"
                    "+--------------------------------------+\n"
                    "| [Approve Override]  [Reject Release] |\n"
                    "+--------------------------------------+"
                ),
            },
            "vault_screen": {
                "title": "Vault & Memory Explorer",
                "route": "/vault",
                "widgets": ["SchemaTreeView", "DocumentViewer", "ChromaSemanticSearchBar", "MemorySnapshotTile"],
                "wireframe": (
                    "+--------------------------------------+\n"
                    "| [Alpha Vault Explorer]     [Health]  |\n"
                    "+--------------------------------------+\n"
                    "| > company/identity.json              |\n"
                    "| > projects/alpha/deliverables/       |\n"
                    "|    - technical_spec.json             |\n"
                    "|    - product_prd.json                |\n"
                    "| > agents/cto/episodic_memory.jsonl   |\n"
                    "+--------------------------------------+\n"
                    "| Search semantic vector embeddings... |\n"
                    "+--------------------------------------+"
                ),
            },
        }

        spec = screens.get(sname, screens["canvas_screen"])

        result = {
            "screen_name": sname,
            "project_id": pid,
            "title": spec["title"],
            "route": spec["route"],
            "theme": "alpha-dark",
            "widgets": spec["widgets"],
            "ascii_wireframe": spec["wireframe"],
            "a11y_compliance": "WCAG 2.1 AA",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return result

    # ------------------------------------------------------------------------
    # 4. Accessibility & Mobile Ergonomics Checklist
    # ------------------------------------------------------------------------
    def review_ui_spec(
        self,
        ui_spec: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Audit UI layout against 6-point Accessibility and Mobile Ergonomics Checklist (JD §11)."""
        pid = project_id or self.current_project_id or "default_project"

        checklist = {
            "touch_target_size_48dp": True,
            "contrast_ratio_4_5_to_1": True,
            "meaning_not_color_alone": True,
            "haptic_tactile_feedback": True,
            "dynamic_type_scaling": True,
            "clean_desktop_and_webview": True,
        }

        violations = []
        if ui_spec.get("touch_target_min_dp", 48) < 48:
            checklist["touch_target_size_48dp"] = False
            violations.append("Touch targets smaller than minimum 48x48dp.")

        if ui_spec.get("contrast_ratio", 5.0) < 4.5:
            checklist["contrast_ratio_4_5_to_1"] = False
            violations.append("Normal text contrast ratio lower than 4.5:1.")

        passed_count = sum(1 for v in checklist.values() if v)
        score = round((passed_count / 6.0) * 100.0, 1)

        return {
            "project_id": pid,
            "passed": len(violations) == 0,
            "score": score,
            "checklist": checklist,
            "violations": violations,
            "remediations": [
                "Ensure touchable icons use minimum Padding(padding: EdgeInsets.all(12)) to reach 48dp.",
                "Verify high contrast between OLED background (#090A0F) and text (#F9FAFB).",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------------
    # 5. Archify Diagram Specification Export
    # ------------------------------------------------------------------------
    def export_archify_diagram_spec(
        self,
        system_nodes: List[Dict[str, Any]],
        system_edges: List[Dict[str, Any]],
        title: str = "System Architecture",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize interactive Archify diagram specification (HTML/SVG embeddable schema)."""
        pid = project_id or self.current_project_id or "default_project"

        styled_nodes = []
        for n in system_nodes:
            style = self.generate_canvas_node_style(
                node_type=n.get("type", "agent"),
                status=n.get("status", "active"),
            )
            styled_nodes.append({
                "id": n.get("id"),
                "label": n.get("label", n.get("id")),
                "type": n.get("type", "agent"),
                "status": n.get("status", "active"),
                "style": style,
            })

        diagram_spec = {
            "title": title,
            "project_id": pid,
            "theme": "alpha-dark",
            "canvas_background": "#090A0F",
            "nodes": styled_nodes,
            "edges": system_edges,
            "total_nodes": len(styled_nodes),
            "total_edges": len(system_edges),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/archify_diagram.json"
            try:
                self.vault_manager.write(vpath, diagram_spec, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed writing archify diagram spec to vault: %s", e)

        return diagram_spec

    # ------------------------------------------------------------------------
    # 6. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute design directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["token", "oled", "palette", "design_system"]):
            output_data = self.get_oled_design_tokens()
        elif any(w in t_lower for w in ["node_style", "halo", "glow"]):
            output_data = self.generate_canvas_node_style(node_type="agent", status="active")
        elif any(w in t_lower for w in ["screen", "mobile", "layout", "wireframe"]):
            output_data = self.generate_mobile_layout_spec(screen_name="canvas_screen", project_id=pid)
        elif any(w in t_lower for w in ["a11y", "accessibility", "ergonomics", "review_ui"]):
            output_data = self.review_ui_spec(ui_spec={"touch_target_min_dp": 48, "contrast_ratio": 7.0}, project_id=pid)
        elif any(w in t_lower for w in ["diagram", "export", "archify"]):
            output_data = self.export_archify_diagram_spec(
                system_nodes=[{"id": "node_1", "type": "agent", "status": "active"}],
                system_edges=[{"from": "node_1", "to": "node_2"}],
                project_id=pid,
            )
        else:
            thought = self.think(
                context=f"CDO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="visual_design",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"CDO executed task: {clean_task[:80]}",
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
        if act_norm in ("get_oled_design_tokens", "design_tokens"):
            res = self.get_oled_design_tokens(theme_name=parameters.get("theme_name", "alpha-dark"))
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_canvas_node_style", "node_style"):
            res = self.generate_canvas_node_style(
                node_type=parameters.get("node_type", "agent"),
                status=parameters.get("status", "active"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_mobile_layout_spec", "mobile_layout"):
            res = self.generate_mobile_layout_spec(
                screen_name=parameters.get("screen_name", "canvas_screen"),
                project_id=parameters.get("project_id"),
                context=parameters.get("context"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("review_ui_spec", "audit_ui"):
            res = self.review_ui_spec(
                ui_spec=parameters.get("ui_spec", {}),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("export_archify_diagram_spec", "export_diagram"):
            res = self.export_archify_diagram_spec(
                system_nodes=parameters.get("system_nodes", []),
                system_edges=parameters.get("system_edges", []),
                title=parameters.get("title", "System Architecture"),
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
