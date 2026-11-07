"""backend/orchestrator/archify_engine.py - Project Alpha Archify Living Diagram Engine.

Responsible for:
1. Transforming project architectures, agent workstreams, and data flows into interactive visual diagrams.
2. Producing standalone, zero-dependency OLED-themed HTML/SVG diagrams for web and Flutter WebView.
3. Generating typed GraphData models for direct 60 FPS rendering in Flutter CustomPainter (ArchifyCanvas).
4. Providing three canonical visual layers: System Architecture, Company Hierarchy, and Execution Flow.
5. Computing delta architecture diffs (archify diff) highlighting added, removed, and modified nodes/edges.
6. Persisting deliverables directly into Alpha-Vault/projects/{project_id}/deliverables/.

Conforms to:
- PROJECT.md Milestone 6 / Feature 38 Contract
- Master Design Doc §10 (Archify+ Living Visual Canvas)
- INTEGRATIONS-AND-SKILLS.md §2.1 (tt-a1i/archify Specification)
- CDO OLED Dark Tokens (#090A0F, #06B6D4, #3B82F6, #10B981, #F59E0B, #EF4444)
"""

from __future__ import annotations

import html
import json
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("alpha.orchestrator.archify")


# ============================================================================
# 1. Authoritative Design Tokens & Constants
# ============================================================================

OLED_THEME = {
    "background": "#090A0F",
    "surface": "#12131C",
    "surface_variant": "#1A1D28",
    "border": "#262A3B",
    "border_highlight": "#3A405A",
    "text_primary": "#F9FAFB",
    "text_secondary": "#9CA3AF",
    "text_muted": "#6B7280",
    "colors": {
        "cyan": "#06B6D4",      # Active data flow, primary telemetry
        "blue": "#3B82F6",      # Executive leadership, coordination
        "emerald": "#10B981",   # Healthy, verified, completed
        "amber": "#F59E0B",     # Warning, auditing, review in progress
        "rose": "#EF4444",      # Blocked, error, P0 veto flag
        "purple": "#8B5CF6",    # Deliberation, groupchat, AI synthesis
    },
    "glows": {
        "cyan": "0 0 16px rgba(6, 182, 212, 0.6)",
        "blue": "0 0 16px rgba(59, 130, 246, 0.6)",
        "emerald": "0 0 16px rgba(16, 185, 129, 0.6)",
        "amber": "0 0 16px rgba(245, 158, 11, 0.6)",
        "rose": "0 0 16px rgba(239, 68, 68, 0.6)",
    },
}

LUCIDE_ICONS: Dict[str, str] = {
    "ceo": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>',
    "cto": '<rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line>',
    "cmo": '<path d="m3 11 18-5v12L3 14v-3z"></path><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"></path>',
    "cpo": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path><path d="m3.3 7 8.7 5 8.7-5"></path><path d="M12 22V12"></path>',
    "cdo": '<circle cx="13.5" cy="6.5" r=".5"></circle><circle cx="17.5" cy="10.5" r=".5"></circle><circle cx="8.5" cy="7.5" r=".5"></circle><circle cx="6.5" cy="12.5" r=".5"></circle><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"></path>',
    "cfo": '<line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>',
    "coo": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>',
    "chro": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>',
    "cio": '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>',
    "cso": '<polygon points="3 11 22 2 13 21 11 13 3 11"></polygon>',
    "clo": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"></path><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"></path><path d="M7 21h10"></path><path d="M12 3v18"></path><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"></path>',
    "cao": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="m9 15 2 2 4-4"></path>',
    "vault": '<rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="12" cy="12" r="3"></circle><line x1="12" y1="6" x2="12" y2="9"></line><line x1="12" y1="15" x2="12" y2="18"></line><line x1="6" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="18" y2="12"></line>',
    "router": '<rect x="2" y="2" width="20" height="8" rx="2"></rect><rect x="2" y="14" width="20" height="8" rx="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line>',
    "mcp": '<rect x="4" y="4" width="16" height="16" rx="2"></rect><path d="M9 9h6v6H9z"></path><path d="M9 1v3"></path><path d="M15 1v3"></path><path d="M9 20v3"></path><path d="M15 20v3"></path><path d="M20 9h3"></path><path d="M20 14h3"></path><path d="M1 9h3"></path><path d="M1 14h3"></path>',
    "gateway": '<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>',
    "service": '<polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline>',
    "task": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>',
    "deliverable": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline>',
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>',
}


# ============================================================================
# 2. Pydantic Graph & Delta Diff Models
# ============================================================================

class NodeStatus(str, Enum):
    ACTIVE = "active"
    HEALTHY = "healthy"
    COMPLETED = "completed"
    IDLE = "idle"
    BLOCKED = "blocked"
    AUDITING = "auditing"
    PENDING = "pending"


class NodeType(str, Enum):
    AGENT = "agent"
    SUBSYSTEM = "subsystem"
    VAULT = "vault"
    ROUTER = "router"
    MCP = "mcp"
    TASK = "task"
    DELIVERABLE = "deliverable"
    GATEWAY = "gateway"


class GraphNode(BaseModel):
    """Visual Node representing an agent, subsystem, task, or deliverable."""
    model_config = ConfigDict(extra="ignore")

    id: str
    label: str
    type: str = "service"
    status: str = "active"
    assigned_agent: Optional[str] = None
    model_tier: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    width: float = 180.0
    height: float = 72.0
    icon: str = "box"
    pulsing: bool = False
    glow_color: str = "#06B6D4"
    border_color: str = "#262A3B"
    background_color: str = "#1A1D28"
    progress: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    diff_status: Optional[str] = None  # "added" | "removed" | "modified" | "unchanged"


class GraphEdge(BaseModel):
    """Directed connection representing data flow, delegation, or dependency."""
    model_config = ConfigDict(extra="ignore")

    id: str
    source: str
    target: str
    label: Optional[str] = None
    type: str = "data_flow"
    pulsing: bool = True
    color: str = "#06B6D4"
    stroke_width: float = 2.0
    bidirectional: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    diff_status: Optional[str] = None  # "added" | "removed" | "modified" | "unchanged"


class GraphData(BaseModel):
    """Master graph model serialized to JSON for Flutter and HTML rendering."""
    model_config = ConfigDict(extra="ignore")

    project_id: str
    title: str
    view_type: str = "system"  # "system" | "company" | "execution" | "diff"
    theme: str = "alpha-dark"
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NodeDiff(BaseModel):
    id: str
    status: str  # "added" | "removed" | "modified"
    changes: Dict[str, Any] = Field(default_factory=dict)
    node: GraphNode


class EdgeDiff(BaseModel):
    id: str
    source: str
    target: str
    status: str  # "added" | "removed" | "modified"
    edge: GraphEdge


class ArchifyDiff(BaseModel):
    """Delta comparison between two architecture graphs."""
    model_config = ConfigDict(extra="ignore")

    baseline_project_id: str
    current_project_id: str
    added_nodes: List[GraphNode] = Field(default_factory=list)
    removed_nodes: List[GraphNode] = Field(default_factory=list)
    modified_nodes: List[NodeDiff] = Field(default_factory=list)
    added_edges: List[GraphEdge] = Field(default_factory=list)
    removed_edges: List[GraphEdge] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)


# ============================================================================
# 3. Archify Living Diagram Engine
# ============================================================================

class ArchifyEngine:
    """Production-grade visual living architecture diagram generator."""

    def __init__(self, vault_manager: Optional[Any] = None) -> None:
        self.vault_manager = vault_manager

    # ------------------------------------------------------------------------
    # Graph Generation: System Architecture View
    # ------------------------------------------------------------------------
    def generate_system_graph(
        self,
        project_id: str,
        title: str = "Project System Architecture",
        components: Optional[List[Dict[str, Any]]] = None,
        data_flows: Optional[List[Dict[str, Any]]] = None,
    ) -> GraphData:
        """Construct system architecture graph (APIs, Vault, Model Router, MCP, Agents)."""
        pid = str(project_id).strip()
        comp_list = components or [
            {"id": "gateway_api", "label": "FastAPI REST / WS", "type": "gateway", "status": "active"},
            {"id": "vault_store", "label": "Alpha Vault (SQLite + Chroma)", "type": "vault", "status": "healthy"},
            {"id": "router_5tier", "label": "5-Tier Model Router", "type": "router", "status": "active"},
            {"id": "mcp_server", "label": "MCP Server (15 Tools)", "type": "mcp", "status": "active"},
            {"id": "ceo_agent", "label": "CEO Orchestrator", "type": "agent", "status": "active", "assigned_agent": "CEO"},
            {"id": "cto_agent", "label": "CTO Tech Architect", "type": "agent", "status": "active", "assigned_agent": "CTO"},
            {"id": "cao_audit", "label": "Dual CAO Audit Gate", "type": "agent", "status": "auditing", "assigned_agent": "CAO"},
            {"id": "flutter_client", "label": "Flutter Archify+ UI", "type": "subsystem", "status": "active"},
        ]

        flows = data_flows or [
            {"source": "flutter_client", "target": "gateway_api", "label": "REST / WS"},
            {"source": "gateway_api", "target": "ceo_agent", "label": "Goal Directive"},
            {"source": "ceo_agent", "target": "cto_agent", "label": "Workstream Delegation"},
            {"source": "cto_agent", "target": "router_5tier", "label": "Inference"},
            {"source": "cto_agent", "target": "vault_store", "label": "Tech Spec Persistence"},
            {"source": "cto_agent", "target": "mcp_server", "label": "Tool Invocation"},
            {"source": "cto_agent", "target": "cao_audit", "label": "Audit Gate Submission"},
            {"source": "cao_audit", "target": "ceo_agent", "label": "Consolidated Scorecard"},
        ]

        nodes = []
        for c in comp_list:
            nodes.append(self._create_node(c))

        edges = []
        for idx, f in enumerate(flows):
            edges.append(self._create_edge(f, f"edge_{idx}"))

        graph = GraphData(
            project_id=pid,
            title=title,
            view_type="system",
            nodes=nodes,
            edges=edges,
        )
        self._apply_topological_layout(graph)
        return graph

    # ------------------------------------------------------------------------
    # Graph Generation: Company View (C-Suite Hierarchy)
    # ------------------------------------------------------------------------
    def generate_company_graph(
        self,
        project_id: str,
        title: str = "Alpha Executive C-Suite Hierarchy",
    ) -> GraphData:
        """Construct company organizational view with 13 C-Suite executives and dual CAO."""
        pid = str(project_id).strip()
        agents = [
            {"id": "FOUNDER", "label": "Aman Jain (Founder)", "type": "agent", "status": "healthy", "icon": "ceo"},
            {"id": "CEO", "label": "Alpha CEO (Executive Hub)", "type": "agent", "status": "active", "icon": "ceo"},
            {"id": "CTO", "label": "CTO (Technology)", "type": "agent", "status": "active", "icon": "cto"},
            {"id": "CPO", "label": "CPO (Product)", "type": "agent", "status": "active", "icon": "cpo"},
            {"id": "CDO", "label": "CDO (Design & UX)", "type": "agent", "status": "active", "icon": "cdo"},
            {"id": "CMO", "label": "CMO (Marketing)", "type": "agent", "status": "active", "icon": "cmo"},
            {"id": "CFO", "label": "CFO (Finance)", "type": "agent", "status": "active", "icon": "cfo"},
            {"id": "COO", "label": "COO (Operations)", "type": "agent", "status": "active", "icon": "coo"},
            {"id": "CHRO", "label": "CHRO (People)", "type": "agent", "status": "idle", "icon": "chro"},
            {"id": "CIO", "label": "CIO (Vault Custodian)", "type": "agent", "status": "active", "icon": "cio"},
            {"id": "CSO", "label": "CSO (Strategy)", "type": "agent", "status": "idle", "icon": "cso"},
            {"id": "CLO", "label": "CLO (Legal Shield)", "type": "agent", "status": "idle", "icon": "clo"},
            {"id": "CAO_CLAUDE", "label": "CAO (Claude Audit)", "type": "agent", "status": "auditing", "icon": "cao"},
            {"id": "CAO_GPT", "label": "CAO (GPT Audit)", "type": "agent", "status": "auditing", "icon": "cao"},
        ]

        hierarchy = [
            {"source": "FOUNDER", "target": "CEO", "label": "Direct Mandate"},
            {"source": "CEO", "target": "CTO", "label": "Delegation"},
            {"source": "CEO", "target": "CPO", "label": "Delegation"},
            {"source": "CEO", "target": "CDO", "label": "Delegation"},
            {"source": "CEO", "target": "CMO", "label": "Delegation"},
            {"source": "CEO", "target": "CFO", "label": "Delegation"},
            {"source": "CEO", "target": "COO", "label": "Delegation"},
            {"source": "CEO", "target": "CHRO", "label": "Delegation"},
            {"source": "CEO", "target": "CIO", "label": "Delegation"},
            {"source": "CEO", "target": "CSO", "label": "Delegation"},
            {"source": "CEO", "target": "CLO", "label": "Delegation"},
            {"source": "CTO", "target": "CAO_CLAUDE", "label": "Audit Gate"},
            {"source": "CTO", "target": "CAO_GPT", "label": "Audit Gate"},
        ]

        nodes = [self._create_node(a) for a in agents]
        edges = [self._create_edge(h, f"comp_edge_{idx}") for idx, h in enumerate(hierarchy)]

        graph = GraphData(
            project_id=pid,
            title=title,
            view_type="company",
            nodes=nodes,
            edges=edges,
        )
        self._apply_hierarchical_org_layout(graph)
        return graph

    # ------------------------------------------------------------------------
    # Graph Generation: Execution Flow (Task Pipeline & CPM)
    # ------------------------------------------------------------------------
    def generate_execution_graph(
        self,
        project_id: str,
        title: str,
        tasks: List[Dict[str, Any]],
        critical_path_ids: Optional[Set[str]] = None,
    ) -> GraphData:
        """Construct task execution pipeline graph showing Kahn CPM critical path."""
        pid = str(project_id).strip()
        cp_set = critical_path_ids or set()

        nodes = []
        edges = []

        for t in tasks:
            tid = str(t.get("id") or t.get("task_id"))
            label = t.get("name") or t.get("task_name") or t.get("title") or tid
            agent = t.get("assigned_agent") or t.get("lead_agent") or "CEO"
            status = t.get("status", "pending")
            progress = t.get("progress_percent", 0.0)
            is_critical = tid in cp_set

            glow = OLED_THEME["colors"]["rose"] if is_critical else OLED_THEME["colors"]["cyan"]
            border = OLED_THEME["colors"]["rose"] if is_critical else OLED_THEME["colors"]["cyan"]

            node = GraphNode(
                id=tid,
                label=f"[{agent}] {label}",
                type="task",
                status=status,
                assigned_agent=agent,
                icon="task",
                pulsing=bool(status == "active"),
                glow_color=glow,
                border_color=border,
                progress=progress,
                metadata={"is_critical": is_critical, "duration": t.get("duration", 1.0)},
            )
            nodes.append(node)

            for dep in t.get("dependencies", []):
                edge_color = OLED_THEME["colors"]["rose"] if (is_critical and dep in cp_set) else OLED_THEME["colors"]["cyan"]
                edges.append(
                    GraphEdge(
                        id=f"dep_{dep}_{tid}",
                        source=dep,
                        target=tid,
                        label="CPM Dep",
                        pulsing=is_critical,
                        color=edge_color,
                        stroke_width=2.5 if is_critical else 1.5,
                    )
                )

        graph = GraphData(
            project_id=pid,
            title=title,
            view_type="execution",
            nodes=nodes,
            edges=edges,
        )
        self._apply_topological_layout(graph)
        return graph

    # ------------------------------------------------------------------------
    # Delta Comparison Engine (archify diff)
    # ------------------------------------------------------------------------
    def compute_diff(self, baseline: GraphData, current: GraphData) -> ArchifyDiff:
        """Compute delta changes between baseline and current graph."""
        base_nodes = {n.id: n for n in baseline.nodes}
        curr_nodes = {n.id: n for n in current.nodes}

        base_edges = {f"{e.source}->{e.target}": e for e in baseline.edges}
        curr_edges = {f"{e.source}->{e.target}": e for e in current.edges}

        added_nodes = []
        removed_nodes = []
        modified_nodes = []

        for cid, cnode in curr_nodes.items():
            if cid not in base_nodes:
                cnode.diff_status = "added"
                cnode.border_color = OLED_THEME["colors"]["emerald"]
                cnode.glow_color = OLED_THEME["colors"]["emerald"]
                added_nodes.append(cnode)
            else:
                bnode = base_nodes[cid]
                changes = {}
                if bnode.status != cnode.status:
                    changes["status"] = {"old": bnode.status, "new": cnode.status}
                if bnode.label != cnode.label:
                    changes["label"] = {"old": bnode.label, "new": cnode.label}
                if bnode.type != cnode.type:
                    changes["type"] = {"old": bnode.type, "new": cnode.type}

                if changes:
                    cnode.diff_status = "modified"
                    cnode.border_color = OLED_THEME["colors"]["amber"]
                    cnode.glow_color = OLED_THEME["colors"]["amber"]
                    modified_nodes.append(NodeDiff(id=cid, status="modified", changes=changes, node=cnode))
                else:
                    cnode.diff_status = "unchanged"

        for bid, bnode in base_nodes.items():
            if bid not in curr_nodes:
                bnode.diff_status = "removed"
                bnode.border_color = OLED_THEME["colors"]["rose"]
                bnode.glow_color = OLED_THEME["colors"]["rose"]
                removed_nodes.append(bnode)

        added_edges = []
        removed_edges = []

        for ckey, cedge in curr_edges.items():
            if ckey not in base_edges:
                cedge.diff_status = "added"
                cedge.color = OLED_THEME["colors"]["emerald"]
                added_edges.append(cedge)
            else:
                cedge.diff_status = "unchanged"

        for bkey, bedge in base_edges.items():
            if bkey not in curr_edges:
                bedge.diff_status = "removed"
                bedge.color = OLED_THEME["colors"]["rose"]
                removed_edges.append(bedge)

        diff = ArchifyDiff(
            baseline_project_id=baseline.project_id,
            current_project_id=current.project_id,
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            modified_nodes=modified_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges,
            summary={
                "added_nodes_count": len(added_nodes),
                "removed_nodes_count": len(removed_nodes),
                "modified_nodes_count": len(modified_nodes),
                "added_edges_count": len(added_edges),
                "removed_edges_count": len(removed_edges),
            },
        )
        return diff

    def generate_diff_graph(self, baseline: GraphData, current: GraphData) -> GraphData:
        """Create a merged visualization graph representing the delta diff."""
        diff = self.compute_diff(baseline, current)
        merged_nodes = []

        # Current nodes with annotated diff status
        for n in current.nodes:
            merged_nodes.append(n)

        # Append removed nodes with phantom styling
        for rn in diff.removed_nodes:
            rn.label = f"[REMOVED] {rn.label}"
            merged_nodes.append(rn)

        merged_edges = list(current.edges)
        for re_edge in diff.removed_edges:
            re_edge.label = "[REMOVED]"
            merged_edges.append(re_edge)

        graph = GraphData(
            project_id=current.project_id,
            title=f"Architecture Delta Diff: {baseline.project_id} -> {current.project_id}",
            view_type="diff",
            nodes=merged_nodes,
            edges=merged_edges,
            metadata={"diff_summary": diff.summary},
        )
        self._apply_topological_layout(graph)
        return graph

    # ------------------------------------------------------------------------
    # HTML/SVG Interactive Diagram Generator (Zero CDN Dependencies)
    # ------------------------------------------------------------------------
    def generate_html_diagram(
        self,
        graph_data: GraphData,
        diff: Optional[ArchifyDiff] = None,
    ) -> str:
        """Generate a completely self-contained, interactive OLED HTML/SVG document."""
        svg_content = self.generate_svg(graph_data)
        nodes_json = json.dumps([n.model_dump() for n in graph_data.nodes], ensure_ascii=False)
        edges_json = json.dumps([e.model_dump() for e in graph_data.edges], ensure_ascii=False)

        diff_badge_html = ""
        if diff:
            s = diff.summary
            diff_badge_html = (
                f"<div class='diff-badge'>"
                f"<span class='badge-add'>+{s.get('added_nodes_count', 0)} added</span> "
                f"<span class='badge-mod'>~{s.get('modified_nodes_count', 0)} modified</span> "
                f"<span class='badge-rem'>-{s.get('removed_nodes_count', 0)} removed</span>"
                f"</div>"
            )

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0">
  <title>Archify Living Architecture — {html.escape(graph_data.title)}</title>
  <style>
    :root {{
      --bg: #090A0F;
      --surface: #12131C;
      --surface-variant: #1A1D28;
      --border: #262A3B;
      --border-highlight: #3A405A;
      --text: #F9FAFB;
      --text-muted: #9CA3AF;
      --cyan: #06B6D4;
      --blue: #3B82F6;
      --emerald: #10B981;
      --amber: #F59E0B;
      --rose: #EF4444;
      --purple: #8B5CF6;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: rgba(18, 19, 28, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 100;
    }}
    .title-group h1 {{
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .title-group h1 span.pill {{
      font-size: 11px;
      background: rgba(6, 182, 212, 0.15);
      color: var(--cyan);
      border: 1px solid var(--cyan);
      padding: 2px 8px;
      border-radius: 999px;
      text-transform: uppercase;
    }}
    .controls {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .btn {{
      background: var(--surface-variant);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .btn:hover {{
      border-color: var(--cyan);
      box-shadow: 0 0 10px rgba(6, 182, 212, 0.3);
    }}
    .btn.active {{
      background: var(--cyan);
      color: #000;
      border-color: var(--cyan);
    }}
    .diff-badge {{
      display: flex;
      gap: 8px;
      font-size: 11px;
      font-weight: 700;
      margin-left: 12px;
    }}
    .badge-add {{ color: var(--emerald); background: rgba(16, 185, 129, 0.15); padding: 3px 8px; border-radius: 4px; }}
    .badge-mod {{ color: var(--amber); background: rgba(245, 158, 11, 0.15); padding: 3px 8px; border-radius: 4px; }}
    .badge-rem {{ color: var(--rose); background: rgba(239, 68, 68, 0.15); padding: 3px 8px; border-radius: 4px; }}
    
    #canvas-viewport {{
      flex: 1;
      width: 100%;
      height: 100%;
      position: relative;
      cursor: grab;
      user-select: none;
      touch-action: none;
    }}
    #canvas-viewport:active {{ cursor: grabbing; }}
    #diagram-svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    
    /* Neon Glow & Pulse Animations */
    .pulsing-edge {{
      stroke-dasharray: 8, 8;
      animation: dashFlow 1.5s linear infinite;
    }}
    @keyframes dashFlow {{
      to {{ stroke-dashoffset: -32; }}
    }}
    .node-group {{
      cursor: pointer;
      transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .node-group:hover rect.node-card {{
      stroke-width: 2.5px;
      filter: drop-shadow(0 0 14px rgba(6, 182, 212, 0.7));
    }}
    .node-group.selected rect.node-card {{
      stroke: var(--cyan) !important;
      stroke-width: 3px;
      filter: drop-shadow(0 0 18px rgba(6, 182, 212, 0.9));
    }}
    
    /* Inspector Card Drawer */
    #inspector {{
      position: absolute;
      top: 24px;
      right: 24px;
      width: 320px;
      background: rgba(18, 19, 28, 0.95);
      border: 1px solid var(--border-highlight);
      border-radius: 12px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(16px);
      padding: 20px;
      z-index: 200;
      transform: translateX(380px);
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    #inspector.open {{ transform: translateX(0); }}
    #inspector h2 {{ font-size: 15px; margin-bottom: 8px; color: var(--cyan); }}
    #inspector .field {{ margin-bottom: 12px; font-size: 12px; }}
    #inspector .field label {{ color: var(--text-muted); display: block; margin-bottom: 2px; font-size: 11px; text-transform: uppercase; }}
    #inspector .field value {{ color: var(--text); font-weight: 500; font-family: monospace; }}
    #inspector .close-btn {{
      position: absolute;
      top: 14px;
      right: 14px;
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 18px;
    }}
    
    /* MiniMap */
    #minimap {{
      position: absolute;
      bottom: 24px;
      left: 24px;
      width: 160px;
      height: 100px;
      background: rgba(18, 19, 28, 0.7);
      border: 1px solid var(--border);
      border-radius: 8px;
      pointer-events: none;
      opacity: 0.6;
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
          <polyline points="2 17 12 22 22 17"></polyline>
          <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
        {html.escape(graph_data.title)}
        <span class="pill">{html.escape(graph_data.view_type)}</span>
      </h1>
      {diff_badge_html}
    </div>
    <div class="controls">
      <button class="btn" id="zoom-in-btn">Zoom +</button>
      <button class="btn" id="zoom-out-btn">Zoom -</button>
      <button class="btn" id="reset-btn">Reset View</button>
    </div>
  </header>

  <div id="canvas-viewport">
    {svg_content}
    <div id="minimap"></div>
    <div id="inspector">
      <button class="close-btn" id="close-inspector">&times;</button>
      <h2 id="insp-title">Component Inspector</h2>
      <div class="field"><label>Node ID</label><value id="insp-id">-</value></div>
      <div class="field"><label>Type</label><value id="insp-type">-</value></div>
      <div class="field"><label>Status</label><value id="insp-status">-</value></div>
      <div class="field"><label>Assigned Agent</label><value id="insp-agent">-</value></div>
      <div class="field"><label>Progress</label><value id="insp-progress">-</value></div>
      <div class="field"><label>Metadata</label><value id="insp-metadata">-</value></div>
    </div>
  </div>

  <script>
    (function() {{
      const viewport = document.getElementById('canvas-viewport');
      const gGroup = document.getElementById('scene-transform-group');
      const inspector = document.getElementById('inspector');
      const nodesData = {nodes_json};
      
      let scale = 1.0;
      let panX = 0;
      let panY = 0;
      let isPanning = false;
      let startX = 0;
      let startY = 0;

      function updateTransform() {{
        if (gGroup) {{
          gGroup.setAttribute('transform', `translate(${{panX}}, ${{panY}}) scale(${{scale}})`);
        }}
      }}

      viewport.addEventListener('mousedown', (e) => {{
        if (e.target.closest('#inspector')) return;
        isPanning = true;
        startX = e.clientX - panX;
        startY = e.clientY - panY;
      }});

      window.addEventListener('mousemove', (e) => {{
        if (!isPanning) return;
        panX = e.clientX - startX;
        panY = e.clientY - startY;
        updateTransform();
      }});

      window.addEventListener('mouseup', () => {{ isPanning = false; }});

      viewport.addEventListener('wheel', (e) => {{
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.15 : 0.85;
        scale = Math.min(Math.max(0.35, scale * factor), 4.0);
        updateTransform();
      }}, {{ passive: false }});

      document.getElementById('zoom-in-btn').onclick = () => {{ scale = Math.min(4.0, scale * 1.25); updateTransform(); }};
      document.getElementById('zoom-out-btn').onclick = () => {{ scale = Math.max(0.35, scale * 0.8); updateTransform(); }};
      document.getElementById('reset-btn').onclick = () => {{ scale = 1.0; panX = 0; panY = 0; updateTransform(); }};
      document.getElementById('close-inspector').onclick = () => {{ inspector.classList.remove('open'); }};

      // Node selection & inspection
      document.querySelectorAll('.node-group').forEach(el => {{
        el.addEventListener('click', (e) => {{
          e.stopPropagation();
          const nodeId = el.getAttribute('data-id');
          const node = nodesData.find(n => n.id === nodeId);
          if (!node) return;

          document.querySelectorAll('.node-group').forEach(n => n.classList.remove('selected'));
          el.classList.add('selected');

          document.getElementById('insp-title').innerText = node.label;
          document.getElementById('insp-id').innerText = node.id;
          document.getElementById('insp-type').innerText = node.type.toUpperCase();
          document.getElementById('insp-status').innerText = node.status.toUpperCase();
          document.getElementById('insp-agent').innerText = node.assigned_agent || 'N/A';
          document.getElementById('insp-progress').innerText = node.progress !== null ? `${{node.progress}}%` : 'N/A';
          document.getElementById('insp-metadata').innerText = JSON.stringify(node.metadata || {{}}, null, 2);

          inspector.classList.add('open');
        }});
      }});
    }})();
  </script>
</body>
</html>"""
        return html_template

    # ------------------------------------------------------------------------
    # SVG Vector Generator
    # ------------------------------------------------------------------------
    def generate_svg(
        self,
        graph_data: GraphData,
        width: int = 1400,
        height: int = 900,
    ) -> str:
        """Render pure SVG string containing glowing filters, nodes, and pulsing edges."""
        defs = f"""<defs>
    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
    <filter id="glow-blue" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
    <filter id="glow-emerald" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
    <filter id="glow-rose" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
    <marker id="arrow-cyan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{OLED_THEME['colors']['cyan']}" />
    </marker>
    <marker id="arrow-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{OLED_THEME['colors']['rose']}" />
    </marker>
  </defs>"""

        node_map = {n.id: n for n in graph_data.nodes}
        edges_svg = []

        for e in graph_data.edges:
            src = node_map.get(e.source)
            tgt = node_map.get(e.target)
            if not src or not tgt:
                continue

            x1 = src.x + (src.width / 2.0)
            y1 = src.y + (src.height / 2.0)
            x2 = tgt.x + (tgt.width / 2.0)
            y2 = tgt.y + (tgt.height / 2.0)

            # Curved cubic Bezier control points
            dx = x2 - x1
            c1x = x1 + dx * 0.45
            c1y = y1
            c2x = x2 - dx * 0.45
            c2y = y2

            path_d = f"M {x1} {y1} C {c1x} {c1y}, {c2x} {c2y}, {x2} {y2}"
            pulse_cls = "pulsing-edge" if e.pulsing else ""
            marker = "url(#arrow-rose)" if e.color == OLED_THEME["colors"]["rose"] else "url(#arrow-cyan)"

            edges_svg.append(
                f'<path d="{path_d}" fill="none" stroke="{e.color}" stroke-width="{e.stroke_width}" '
                f'class="{pulse_cls}" marker-end="{marker}" opacity="0.85" />'
            )

        nodes_svg = []
        for n in graph_data.nodes:
            icon_key = n.icon.lower()
            if icon_key not in LUCIDE_ICONS:
                icon_key = "box"
            icon_svg = LUCIDE_ICONS.get(icon_key, "")

            # Progress bar SVG sub-element
            progress_bar = ""
            if n.progress is not None:
                pw = max(0.0, min(140.0, (n.progress / 100.0) * 140.0))
                progress_bar = (
                    f'<rect x="{n.x + 20}" y="{n.y + 54}" width="140" height="4" rx="2" fill="#262A3B" />'
                    f'<rect x="{n.x + 20}" y="{n.y + 54}" width="{pw}" height="4" rx="2" fill="{n.glow_color}" />'
                )

            diff_stroke_dash = 'stroke-dasharray="6,4"' if n.diff_status in ("added", "modified") else ""

            nodes_svg.append(
                f'<g class="node-group" data-id="{n.id}" id="node_{n.id}">'
                f'  <rect class="node-card" x="{n.x}" y="{n.y}" width="{n.width}" height="{n.height}" rx="10" '
                f'        fill="{n.background_color}" stroke="{n.border_color}" stroke-width="1.5" {diff_stroke_dash} />'
                f'  <g transform="translate({n.x + 14}, {n.y + 14}) scale(0.85)" stroke="{n.glow_color}" fill="none" stroke-width="2">'
                f'    {icon_svg}'
                f'  </g>'
                f'  <text x="{n.x + 44}" y="{n.y + 26}" fill="#F9FAFB" font-size="12" font-weight="700" font-family="monospace">{html.escape(n.label[:20])}</text>'
                f'  <text x="{n.x + 44}" y="{n.y + 42}" fill="#9CA3AF" font-size="10" font-family="sans-serif">{html.escape(n.status.upper())} | {html.escape(n.type)}</text>'
                f'  {progress_bar}'
                f'</g>'
            )

        svg = (
            f'<svg id="diagram-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">\n'
            f'{defs}\n'
            f'<g id="scene-transform-group">\n'
            f'  <g id="edges-layer">\n' + "\n".join(edges_svg) + '\n  </g>\n'
            f'  <g id="nodes-layer">\n' + "\n".join(nodes_svg) + '\n  </g>\n'
            f'</g>\n'
            f'</svg>'
        )
        return svg

    # ------------------------------------------------------------------------
    # Persistence Engine (Alpha's Vault Deliverable Writer)
    # ------------------------------------------------------------------------
    def save_diagram(
        self,
        project_id: str,
        graph_data: GraphData,
        diff: Optional[ArchifyDiff] = None,
        vault_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, str]:
        """Save both standalone HTML and JSON GraphData into Vault deliverables directory."""
        pid = str(project_id).strip()

        # Determine target deliverables directory
        if self.vault_manager and hasattr(self.vault_manager, "vault_root"):
            out_dir = Path(self.vault_manager.vault_root) / "projects" / pid / "deliverables"
        elif vault_root:
            out_dir = Path(vault_root) / "projects" / pid / "deliverables"
        else:
            out_dir = Path("Alpha-Vault") / "projects" / pid / "deliverables"

        out_dir.mkdir(parents=True, exist_ok=True)

        html_file = out_dir / "architecture-diagram.html"
        json_file = out_dir / "architecture-diagram.json"

        # 1. Generate and save HTML
        html_content = self.generate_html_diagram(graph_data, diff)
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Save JSON GraphData
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(graph_data.model_dump(), f, indent=2, ensure_ascii=False)

        # 3. Synchronize with VaultManager KV / SQLite store if present
        if self.vault_manager:
            try:
                self.vault_manager.write(
                    f"projects/{pid}/deliverables/architecture_graph.json",
                    graph_data.model_dump(),
                    agent_id="CTO",
                )
            except Exception as e:
                logger.debug("Vault write fallback: %s", e)

        return {
            "html_path": str(html_file),
            "json_path": str(json_file),
            "project_id": pid,
            "status": "saved",
        }

    # ------------------------------------------------------------------------
    # Orchestrator Compatibility Facades
    # ------------------------------------------------------------------------
    def generate_diagram(
        self,
        project_id: str,
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Compatibility method returning interactive HTML string."""
        graph = self.generate_system_graph(project_id=project_id, components=components)
        return self.generate_html_diagram(graph)

    def generate_graph_data(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """Compatibility method returning GraphData dictionary."""
        graph = self.generate_system_graph(project_id=project_id)
        return graph.model_dump()

    # ------------------------------------------------------------------------
    # Internal Helpers & Automatic Layout
    # ------------------------------------------------------------------------
    def _create_node(self, d: Dict[str, Any]) -> GraphNode:
        nid = d.get("id", f"node_{uuid.uuid4().hex[:6]}")
        label = d.get("label", nid)
        ntype = d.get("type", "service")
        status = d.get("status", "active")
        agent = d.get("assigned_agent")
        icon = d.get("icon") or (agent.lower() if agent else ntype)

        color_map = {
            "active": OLED_THEME["colors"]["cyan"],
            "healthy": OLED_THEME["colors"]["emerald"],
            "completed": OLED_THEME["colors"]["emerald"],
            "auditing": OLED_THEME["colors"]["amber"],
            "blocked": OLED_THEME["colors"]["rose"],
            "idle": OLED_THEME["colors"]["blue"],
            "pending": OLED_THEME["border"],
        }
        glow = color_map.get(status, OLED_THEME["colors"]["cyan"])

        return GraphNode(
            id=nid,
            label=label,
            type=ntype,
            status=status,
            assigned_agent=agent,
            icon=icon,
            pulsing=bool(status == "active"),
            glow_color=glow,
            border_color=glow if status != "pending" else OLED_THEME["border"],
            progress=d.get("progress"),
            metadata=d.get("metadata", {}),
        )

    def _create_edge(self, d: Dict[str, Any], default_id: str) -> GraphEdge:
        src = d.get("source") or d.get("from")
        tgt = d.get("target") or d.get("to")
        color = OLED_THEME["colors"]["cyan"]
        if "audit" in str(d.get("label", "")).lower():
            color = OLED_THEME["colors"]["amber"]

        return GraphEdge(
            id=d.get("id", default_id),
            source=src,
            target=tgt,
            label=d.get("label"),
            type=d.get("type", "data_flow"),
            pulsing=d.get("pulsing", True),
            color=color,
            stroke_width=2.0,
        )

    def _apply_topological_layout(self, graph: GraphData, canvas_width: int = 1400) -> None:
        """Assign coordinates by topological rank layers."""
        in_degrees: Dict[str, int] = {n.id: 0 for n in graph.nodes}
        adj: Dict[str, List[str]] = {n.id: [] for n in graph.nodes}

        for e in graph.edges:
            if e.source in adj and e.target in in_degrees:
                adj[e.source].append(e.target)
                in_degrees[e.target] += 1

        queue = [nid for nid, deg in in_degrees.items() if deg == 0]
        ranks: Dict[str, int] = {nid: 0 for nid in queue}

        # Longest path rank assignment
        visited = set(queue)
        while queue:
            curr = queue.pop(0)
            curr_rank = ranks[curr]
            for neighbor in adj[curr]:
                ranks[neighbor] = max(ranks.get(neighbor, 0), curr_rank + 1)
                in_degrees[neighbor] -= 1
                if in_degrees[neighbor] == 0:
                    queue.append(neighbor)
                    visited.add(neighbor)

        # Handle cycles / disconnected nodes
        for n in graph.nodes:
            if n.id not in ranks:
                ranks[n.id] = 0

        # Group nodes by rank
        tier_map: Dict[int, List[GraphNode]] = {}
        for n in graph.nodes:
            r = ranks[n.id]
            tier_map.setdefault(r, []).append(n)

        # Space out coordinates
        tier_y_start = 100.0
        tier_y_gap = 160.0

        for r, nodes_in_tier in tier_map.items():
            total_tier_w = len(nodes_in_tier) * 220.0
            start_x = max(60.0, (canvas_width - total_tier_w) / 2.0)
            for idx, node in enumerate(nodes_in_tier):
                node.x = start_x + (idx * 230.0)
                node.y = tier_y_start + (r * tier_y_gap)

    def _apply_hierarchical_org_layout(self, graph: GraphData) -> None:
        """Assign clean executive hierarchy positions (Founder -> CEO -> C-Suite -> CAO)."""
        node_map = {n.id: n for n in graph.nodes}

        # Layer 0: Founder
        if "FOUNDER" in node_map:
            node_map["FOUNDER"].x = 610.0
            node_map["FOUNDER"].y = 60.0

        # Layer 1: CEO
        if "CEO" in node_map:
            node_map["CEO"].x = 610.0
            node_map["CEO"].y = 190.0

        # Layer 2: Core C-Suite Agents
        c_suite_order = ["CTO", "CPO", "CDO", "CMO", "CFO", "COO", "CHRO", "CIO", "CSO", "CLO"]
        start_x = 40.0
        gap_x = 135.0
        for idx, cid in enumerate(c_suite_order):
            if cid in node_map:
                node_map[cid].x = start_x + (idx * gap_x)
                node_map[cid].y = 350.0

        # Layer 3: Dual CAO Audit Gate
        if "CAO_CLAUDE" in node_map:
            node_map["CAO_CLAUDE"].x = 480.0
            node_map["CAO_CLAUDE"].y = 520.0
        if "CAO_GPT" in node_map:
            node_map["CAO_GPT"].x = 740.0
            node_map["CAO_GPT"].y = 520.0
