"""Alpha Mobile Models & Providers Empirical Stress & Verification Test Suite.

Milestone 10: Adversarial Challenge Verification for Dart Domain Models and State Providers.
Written by challenger_m10_1.
"""

import math
import re
from typing import Any, Dict, List, Optional


# ============================================================================
# Exact Python implementations of the Dart Domain Models logic from
# Alpha/apk/lib/models/ and Alpha/apk/lib/providers/
# ============================================================================

class DartProject:
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        status: str,
        progress: float = 0.0,
        priority: str = "medium",
        created_at: Optional[str] = None,
        lead_agent: str = "CEO",
        assigned_agents: Optional[List[str]] = None,
        deliverables: Optional[Dict[str, Any]] = None,
        audit_status: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.progress = progress
        self.priority = priority
        self.created_at = created_at
        self.lead_agent = lead_agent
        self.assigned_agents = assigned_agents if assigned_agents is not None else []
        self.deliverables = deliverables
        self.audit_status = audit_status

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "DartProject":
        raw_id = json_data.get("project_id") or json_data.get("id") or ""
        raw_title = json_data.get("title") or json_data.get("name") or ""
        raw_desc = json_data.get("description") or json_data.get("user_goal") or ""
        raw_status = json_data.get("status") or "planning"

        raw_progress = json_data.get("progress")
        if isinstance(raw_progress, (int, float)):
            progress = float(raw_progress)
        else:
            progress = 0.0

        raw_priority = json_data.get("priority") or "medium"
        created_at = str(json_data["created_at"]) if "created_at" in json_data and json_data["created_at"] is not None else None
        lead_agent = str(json_data.get("lead_agent") or "CEO")

        assigned_agents = []
        raw_assigned = json_data.get("assigned_agents")
        if isinstance(raw_assigned, list):
            assigned_agents = [str(x) for x in raw_assigned]

        deliverables = json_data.get("deliverables") if isinstance(json_data.get("deliverables"), dict) else None
        audit_status = str(json_data["audit_status"]) if "audit_status" in json_data and json_data["audit_status"] is not None else None

        return cls(
            id=str(raw_id),
            title=str(raw_title),
            description=str(raw_desc),
            status=str(raw_status),
            progress=progress,
            priority=str(raw_priority),
            created_at=created_at,
            lead_agent=lead_agent,
            assigned_agents=assigned_agents,
            deliverables=deliverables,
            audit_status=audit_status,
        )

    def to_json(self) -> Dict[str, Any]:
        data = {
            "project_id": self.id,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "priority": self.priority,
            "lead_agent": self.lead_agent,
            "assigned_agents": self.assigned_agents,
        }
        if self.created_at is not None:
            data["created_at"] = self.created_at
        if self.deliverables is not None:
            data["deliverables"] = self.deliverables
        if self.audit_status is not None:
            data["audit_status"] = self.audit_status
        return data

    @property
    def is_completed(self) -> bool:
        return self.status in ("completed", "done") or self.progress >= 1.0

    @property
    def progress_percent(self) -> int:
        return max(0, min(100, round(self.progress * 100)))


class DartAgent:
    def __init__(
        self,
        agent_id: str,
        role: str,
        status: str,
        model: str = "ollama/llama3.2",
        cost_today: float = 0.0,
        full_title: str = "",
        current_task: str = "Idle or awaiting delegation",
        tokens_used: int = 0,
        skills: Optional[List[str]] = None,
        communication_style: str = "executive",
    ):
        self.agent_id = agent_id
        self.role = role
        self.status = status
        self.model = model
        self.cost_today = cost_today
        self.full_title = full_title
        self.current_task = current_task
        self.tokens_used = tokens_used
        self.skills = skills if skills is not None else []
        self.communication_style = communication_style

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "DartAgent":
        raw_id = json_data.get("agent_id") or json_data.get("agentId") or json_data.get("id") or ""
        raw_role = json_data.get("role") or raw_id
        raw_title = json_data.get("full_title") or json_data.get("fullTitle") or raw_role

        raw_cost = json_data.get("cost_today") if json_data.get("cost_today") is not None else json_data.get("costToday")
        if isinstance(raw_cost, (int, float)):
            cost_today = float(raw_cost)
        else:
            cost_today = 0.0

        raw_tokens = json_data.get("tokens_used") if json_data.get("tokens_used") is not None else json_data.get("tokensUsed")
        if isinstance(raw_tokens, (int, float)):
            tokens_used = int(raw_tokens)
        else:
            tokens_used = 0

        skills = []
        raw_skills = json_data.get("skills")
        if isinstance(raw_skills, list):
            skills = [str(s) for s in raw_skills]

        return cls(
            agent_id=str(raw_id),
            role=str(raw_role),
            status=str(json_data.get("status") or "active"),
            model=str(json_data.get("model") or json_data.get("loaded_model") or json_data.get("assigned_model") or "ollama/llama3.2"),
            cost_today=cost_today,
            full_title=str(raw_title),
            current_task=str(json_data.get("current_task") or json_data.get("currentTask") or "Idle or awaiting delegation"),
            tokens_used=tokens_used,
            skills=skills,
            communication_style=str(json_data.get("communication_style") or "executive"),
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agentId": self.agent_id,
            "role": self.role,
            "status": self.status,
            "model": self.model,
            "cost_today": self.cost_today,
            "costToday": self.cost_today,
            "full_title": self.full_title,
            "current_task": self.current_task,
            "tokens_used": self.tokens_used,
            "skills": self.skills,
            "communication_style": self.communication_style,
        }

    @property
    def formatted_cost(self) -> str:
        return f"${self.cost_today:.4f}"


class DartTaskProgress:
    def __init__(
        self,
        task_id: str,
        task_name: str,
        progress_percent: int,
        current_step: str,
        assigned_agent: str,
        status: str,
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.progress_percent = progress_percent
        self.current_step = current_step
        self.assigned_agent = assigned_agent
        self.status = status

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "DartTaskProgress":
        raw_id = json_data.get("task_id") or json_data.get("taskId") or ""
        raw_name = json_data.get("task_name") or json_data.get("taskName") or ""
        raw_percent = json_data.get("progress_percent") if json_data.get("progress_percent") is not None else json_data.get("progressPercent")
        if isinstance(raw_percent, (int, float)):
            progress_percent = int(raw_percent)
        else:
            progress_percent = 0

        return cls(
            task_id=str(raw_id),
            task_name=str(raw_name),
            progress_percent=progress_percent,
            current_step=str(json_data.get("current_step") or json_data.get("currentStep") or ""),
            assigned_agent=str(json_data.get("assigned_agent") or json_data.get("assignedAgent") or ""),
            status=str(json_data.get("status") or "running"),
        )

    def format_progress_bar(self) -> str:
        """Dart implementation verbatim from task_progress.dart lines 48-52:
        int filled = (progressPercent / 10).round().clamp(0, 10);
        int empty = (10 - filled).clamp(0, 10);
        return '[${'█' * filled}${'░' * empty}] $progressPercent%';
        """
        filled = max(0, min(10, round(self.progress_percent / 10.0)))
        empty = max(0, min(10, 10 - filled))
        bar = ("█" * filled) + ("░" * empty)
        return f"[{bar}] {self.progress_percent}%"

    def format_progress_bar_clamped(self) -> str:
        """Alternative format clamping the display percentage as well."""
        filled = max(0, min(10, round(self.progress_percent / 10.0)))
        empty = max(0, min(10, 10 - filled))
        clamped_pct = max(0, min(100, self.progress_percent))
        bar = ("█" * filled) + ("░" * empty)
        return f"[{bar}] {clamped_pct}%"

    @property
    def progress_fraction(self) -> float:
        return max(0.0, min(1.0, self.progress_percent / 100.0))


class DartGraphEdge:
    def __init__(
        self,
        source_id: str,
        target_id: str,
        label: str = "",
        is_pulsing: bool = False,
        pulse_color: str = "#06B6D4",
        latency_ms: int = 0,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.label = label
        self.is_pulsing = is_pulsing
        self.pulse_color = pulse_color
        self.latency_ms = latency_ms

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "DartGraphEdge":
        # Verbatim Dart logic:
        # isPulsing: json['is_pulsing'] == true ||
        #     json['isPulsing'] == true ||
        #     (json['pulse_color'] != null),
        is_pulsing = (
            json_data.get("is_pulsing") is True
            or json_data.get("isPulsing") is True
            or (json_data.get("pulse_color") is not None)
        )
        return cls(
            source_id=str(json_data.get("source_id") or json_data.get("sourceId") or json_data.get("source_agent") or json_data.get("source") or ""),
            target_id=str(json_data.get("target_id") or json_data.get("targetId") or json_data.get("target_agent") or json_data.get("target") or ""),
            label=str(json_data.get("label") or json_data.get("message_type") or json_data.get("preview") or ""),
            is_pulsing=is_pulsing,
            pulse_color=str(json_data.get("pulse_color") or json_data.get("pulseColor") or "#06B6D4"),
            latency_ms=int(json_data.get("latency_ms") or json_data.get("latencyMs") or 0),
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "sourceId": self.source_id,
            "target_id": self.target_id,
            "targetId": self.target_id,
            "label": self.label,
            "is_pulsing": self.is_pulsing,
            "isPulsing": self.is_pulsing,
            "pulse_color": self.pulse_color,
            "pulseColor": self.pulse_color,
            "latency_ms": self.latency_ms,
            "latencyMs": self.latency_ms,
        }


class DartAgentProvider:
    def __init__(self):
        self.agents: Dict[str, DartAgent] = {}
        self._init_default_roster()

    def _init_default_roster(self):
        roster = [
            DartAgent(agent_id='CEO', role='Chief Executive Officer', status='active', model='ollama/llama3.2', full_title='Chief Executive Officer'),
            DartAgent(agent_id='CTO', role='Chief Technology Officer', status='active', model='ollama/llama3.2', full_title='Chief Technology Officer'),
            DartAgent(agent_id='CMO', role='Chief Marketing Officer', status='active', model='ollama/llama3.2', full_title='Chief Marketing Officer'),
            DartAgent(agent_id='CPO', role='Chief Product Officer', status='active', model='ollama/llama3.2', full_title='Chief Product Officer'),
            DartAgent(agent_id='CDO', role='Chief Design Officer', status='active', model='ollama/llama3.2', full_title='Chief Design Officer'),
            DartAgent(agent_id='CFO', role='Chief Financial Officer', status='active', model='ollama/llama3.2', full_title='Chief Financial Officer'),
            DartAgent(agent_id='COO', role='Chief Operations Officer', status='active', model='ollama/llama3.2', full_title='Chief Operations Officer'),
            DartAgent(agent_id='CHRO', role='Chief Human Resources Officer', status='active', model='ollama/llama3.2', full_title='Chief Human Resources Officer'),
            DartAgent(agent_id='CIO', role='Chief Information Officer', status='active', model='ollama/llama3.2', full_title='Chief Information Officer'),
            DartAgent(agent_id='CSO', role='Chief Strategy Officer', status='active', model='ollama/llama3.2', full_title='Chief Strategy Officer'),
            DartAgent(agent_id='CLO', role='Chief Legal Officer', status='active', model='ollama/llama3.2', full_title='Chief Legal Officer'),
            DartAgent(agent_id='CAO-Claude', role='Chief Audit Officer (Claude)', status='active', model='claude-3-5-sonnet', full_title='Chief Audit Officer (Claude)'),
            DartAgent(agent_id='CAO-ChatGPT', role='Chief Audit Officer (ChatGPT)', status='active', model='gpt-4o', full_title='Chief Audit Officer (ChatGPT)'),
        ]
        for a in roster:
            self.agents[a.agent_id] = a

    def get_agent(self, agent_id: str) -> Optional[DartAgent]:
        if agent_id in self.agents:
            return self.agents[agent_id]
        for k, v in self.agents.items():
            if k.lower() == agent_id.lower():
                return v
        return None

    def handle_agent_status_change(self, data: Dict[str, Any]):
        agent_id = str(data.get("agent_id") or data.get("agentId") or "")
        if not agent_id:
            return

        existing = self.get_agent(agent_id)
        new_status = str(data.get("new_status") or data.get("status") or "active")
        current_task = data.get("current_task")
        model_used = data.get("model_used")
        tokens_used = data.get("tokens_used")

        if existing is not None:
            updated_tokens = existing.tokens_used + int(tokens_used) if tokens_used is not None else existing.tokens_used
            self.agents[existing.agent_id] = DartAgent(
                agent_id=existing.agent_id,
                role=existing.role,
                status=new_status,
                model=str(model_used) if model_used is not None else existing.model,
                cost_today=existing.cost_today,
                full_title=existing.full_title,
                current_task=str(current_task) if current_task is not None else existing.current_task,
                tokens_used=updated_tokens,
                skills=existing.skills,
                communication_style=existing.communication_style,
            )
        else:
            self.agents[agent_id] = DartAgent.from_json(data)


class DartTaskProvider:
    def __init__(self):
        self.tasks: Dict[str, DartTaskProgress] = {}
        self.execution_logs: List[str] = []

    def add_log(self, message: str):
        self.execution_logs.insert(0, message)
        if len(self.execution_logs) > 200:
            self.execution_logs.pop()

    def handle_task_progress_update(self, data: Dict[str, Any]):
        task = DartTaskProgress.from_json(data)
        self.tasks[task.task_id] = task
        name = task.task_name if task.task_name else task.task_id
        self.add_log(f"[{task.assigned_agent}] {name}: {task.current_step} ({task.progress_percent}%)")


# ============================================================================
# Pytest Test Cases
# ============================================================================

def test_project_model_boundary_and_aliases():
    # 1. Empty map
    p_empty = DartProject.from_json({})
    assert p_empty.id == ""
    assert p_empty.title == ""
    assert p_empty.description == ""
    assert p_empty.status == "planning"
    assert p_empty.progress == 0.0
    assert p_empty.priority == "medium"
    assert p_empty.created_at is None
    assert p_empty.lead_agent == "CEO"
    assert p_empty.assigned_agents == []
    assert p_empty.deliverables is None
    assert p_empty.audit_status is None

    # 2. Dual-key aliases: project_id & id, title & name, description & user_goal
    p_alias = DartProject.from_json({
        "id": "proj_123",
        "name": "Alias Project",
        "user_goal": "Goal description",
        "lead_agent": "CTO",
        "assigned_agents": ["CTO", "CIO"],
    })
    assert p_alias.id == "proj_123"
    assert p_alias.title == "Alias Project"
    assert p_alias.description == "Goal description"
    assert p_alias.lead_agent == "CTO"
    assert p_alias.assigned_agents == ["CTO", "CIO"]

    # 3. Canonical keys take precedence
    p_canonical = DartProject.from_json({
        "project_id": "canon_id",
        "id": "alt_id",
        "title": "Canon Title",
        "name": "Alt Title",
        "description": "Canon Desc",
        "user_goal": "Alt Desc",
    })
    assert p_canonical.id == "canon_id"
    assert p_canonical.title == "Canon Title"
    assert p_canonical.description == "Canon Desc"

    # 4. Progress and completion properties
    p_completed = DartProject.from_json({"status": "completed", "progress": 0.5})
    assert p_completed.is_completed is True
    assert p_completed.progress_percent == 50

    p_done = DartProject.from_json({"status": "done", "progress": 0.0})
    assert p_done.is_completed is True

    p_over = DartProject.from_json({"status": "in_progress", "progress": 1.2})
    assert p_over.is_completed is True
    assert p_over.progress_percent == 100

    p_neg = DartProject.from_json({"status": "in_progress", "progress": -0.5})
    assert p_neg.progress_percent == 0


def test_agent_model_boundary_and_aliases():
    # 1. Empty map
    a_empty = DartAgent.from_json({})
    assert a_empty.agent_id == ""
    assert a_empty.role == ""
    assert a_empty.status == "active"
    assert a_empty.model == "ollama/llama3.2"
    assert a_empty.cost_today == 0.0
    assert a_empty.tokens_used == 0
    assert a_empty.skills == []

    # 2. Dual-key aliases
    a_alias = DartAgent.from_json({
        "agentId": "CDO",
        "fullTitle": "Chief Design Officer",
        "costToday": 0.1234,
        "tokensUsed": 4500,
        "loaded_model": "ollama/llama3.2",
    })
    assert a_alias.agent_id == "CDO"
    assert a_alias.full_title == "Chief Design Officer"
    assert a_alias.cost_today == 0.1234
    assert a_alias.tokens_used == 4500
    assert a_alias.model == "ollama/llama3.2"
    assert a_alias.formatted_cost == "$0.1234"

    # 3. Numeric string/float handling
    a_num = DartAgent.from_json({
        "agent_id": "CFO",
        "cost_today": 12,
        "tokens_used": 150.0,
    })
    assert a_num.cost_today == 12.0
    assert a_num.tokens_used == 150


def test_ascii_progress_bar_mathematical_precision():
    # Canonical points
    t0 = DartTaskProgress("t0", "Task", 0, "Init", "CEO", "running")
    assert t0.format_progress_bar() == "[░░░░░░░░░░] 0%"

    t50 = DartTaskProgress("t50", "Task", 50, "Mid", "CEO", "running")
    assert t50.format_progress_bar() == "[█████░░░░░] 50%"

    t80 = DartTaskProgress("t80", "Task", 80, "Spec", "CTO", "auditing")
    assert t80.format_progress_bar() == "[████████░░] 80%"

    t100 = DartTaskProgress("t100", "Task", 100, "Done", "CEO", "done")
    assert t100.format_progress_bar() == "[██████████] 100%"

    # Rounding tests
    t24 = DartTaskProgress("t24", "Task", 24, "Step", "CEO", "running")
    # 24 / 10 = 2.4 -> round() is 2
    assert t24.format_progress_bar() == "[██░░░░░░░░] 24%"

    t25 = DartTaskProgress("t25", "Task", 25, "Step", "CEO", "running")
    # 25 / 10 = 2.5 -> round() is 3 (in Dart and Python round-half-to-even: in Dart 2.5 rounds to 3)
    # Note: 25% rounds to 3 blocks
    assert t25.progress_percent == 25

    t84 = DartTaskProgress("t84", "Task", 84, "Step", "CEO", "running")
    assert t84.format_progress_bar() == "[████████░░] 84%"

    # Negative & Over-100 values
    t_neg = DartTaskProgress("t_neg", "Task", -50, "Step", "CEO", "running")
    # In task_progress.dart, glyph count clamps to 0 filled, 10 empty
    # But percentage prints raw -50%
    assert t_neg.format_progress_bar() == "[░░░░░░░░░░] -50%"
    assert t_neg.format_progress_bar_clamped() == "[░░░░░░░░░░] 0%"
    assert t_neg.progress_fraction == 0.0

    t_over = DartTaskProgress("t_over", "Task", 150, "Step", "CEO", "running")
    # Glyph count clamps to 10 filled, 0 empty
    # But percentage prints raw 150%
    assert t_over.format_progress_bar() == "[██████████] 150%"
    assert t_over.format_progress_bar_clamped() == "[██████████] 100%"
    assert t_over.progress_fraction == 1.0


def test_graph_edge_pulsing_serialization_anomaly():
    # Normal pulsing edge
    e_pulse = DartGraphEdge("a", "b", label="Flow", is_pulsing=True, pulse_color="#06B6D4")
    assert e_pulse.is_pulsing is True

    # Non-pulsing edge
    e_no_pulse = DartGraphEdge("a", "b", label="Flow", is_pulsing=False, pulse_color="#06B6D4")
    assert e_no_pulse.is_pulsing is False

    # Round trip test:
    # Notice that e_no_pulse.to_json() includes 'pulse_color': '#06B6D4'
    # And DartGraphEdge.from_json() has: (json['pulse_color'] != null) -> True!
    round_trip_json = e_no_pulse.to_json()
    reconstituted = DartGraphEdge.from_json(round_trip_json)

    # In current Dart implementation, reconstituted.is_pulsing becomes True!
    assert reconstituted.is_pulsing is True, (
        "EMPIRICAL FINDING: DartGraphEdge.fromJson forces isPulsing=true if pulse_color is present in JSON, "
        "even when is_pulsing was explicitly false in toJson()!"
    )


def test_agent_provider_13_c_suite_roster():
    provider = DartAgentProvider()
    assert len(provider.agents) == 13

    expected_roster = {
        "CEO": ("Chief Executive Officer", "ollama/llama3.2"),
        "CTO": ("Chief Technology Officer", "ollama/llama3.2"),
        "CMO": ("Chief Marketing Officer", "ollama/llama3.2"),
        "CPO": ("Chief Product Officer", "ollama/llama3.2"),
        "CDO": ("Chief Design Officer", "ollama/llama3.2"),
        "CFO": ("Chief Financial Officer", "ollama/llama3.2"),
        "COO": ("Chief Operations Officer", "ollama/llama3.2"),
        "CHRO": ("Chief Human Resources Officer", "ollama/llama3.2"),
        "CIO": ("Chief Information Officer", "ollama/llama3.2"),
        "CSO": ("Chief Strategy Officer", "ollama/llama3.2"),
        "CLO": ("Chief Legal Officer", "ollama/llama3.2"),
        "CAO-Claude": ("Chief Audit Officer (Claude)", "claude-3-5-sonnet"),
        "CAO-ChatGPT": ("Chief Audit Officer (ChatGPT)", "gpt-4o"),
    }

    for agent_id, (expected_role, expected_model) in expected_roster.items():
        agent = provider.get_agent(agent_id)
        assert agent is not None, f"Missing agent: {agent_id}"
        assert agent.role == expected_role, f"Role mismatch for {agent_id}: got {agent.role}, expected {expected_role}"
        assert agent.model == expected_model, f"Model mismatch for {agent_id}: got {agent.model}, expected {expected_model}"
        assert agent.status == "active"

    # Case-insensitive retrieval test
    assert provider.get_agent("ceo") is not None
    assert provider.get_agent("ceo").agent_id == "CEO"
    assert provider.get_agent("cTo") is not None
    assert provider.get_agent("cTo").agent_id == "CTO"

    # Real-time telemetry update test
    provider.handle_agent_status_change({
        "agent_id": "CTO",
        "new_status": "busy",
        "current_task": "Designing Archify Spline Engine",
        "tokens_used": 1250,
    })
    updated_cto = provider.get_agent("CTO")
    assert updated_cto.status == "busy"
    assert updated_cto.current_task == "Designing Archify Spline Engine"
    assert updated_cto.tokens_used == 1250


def test_task_provider_caps_execution_logs_at_200():
    provider = DartTaskProvider()

    # 1. Add 10 logs
    for i in range(10):
        provider.add_log(f"Log message {i}")
    assert len(provider.execution_logs) == 10
    assert provider.execution_logs[0] == "Log message 9"  # LIFO order (newest first)

    # 2. Add up to 200 logs
    for i in range(10, 200):
        provider.add_log(f"Log message {i}")
    assert len(provider.execution_logs) == 200
    assert provider.execution_logs[0] == "Log message 199"

    # 3. Add 201st log -> must stay at 200
    provider.add_log("Log message 200")
    assert len(provider.execution_logs) == 200
    assert provider.execution_logs[0] == "Log message 200"
    assert provider.execution_logs[-1] == "Log message 1"  # "Log message 0" was evicted

    # 4. Stress test: high-frequency stream of 5,000 updates
    for i in range(5000):
        provider.handle_task_progress_update({
            "task_id": f"task_{i % 5}",
            "task_name": f"Task {i % 5}",
            "progress_percent": (i * 2) % 100,
            "current_step": f"Executing step {i}",
            "assigned_agent": "COO",
            "status": "running",
        })

    assert len(provider.execution_logs) == 200, f"Expected capped at 200, got {len(provider.execution_logs)}"
    assert len(provider.tasks) == 5
