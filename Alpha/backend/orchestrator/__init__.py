"""backend/orchestrator/__init__.py - Project Alpha Tri-Framework Orchestration Engine.

Exports:
- AlphaOrchestrator: Unified end-to-end goal execution pipeline.
- OrchestratorResult / FinalOutput: Result envelope.
- AlphaStateGraph / NativeStateGraph: Cyclic execution state machine.
- AlphaCrewFlow / NativeCrewFlow: CrewAI hierarchical task flow engine.
- AlphaGroupChat / NativeAG2GroupChat: AG2 conversational deliberation engine.
- GoalParser, ThreadManager, Scheduler, DelegationEngine, OutputSynthesizer, ArchifyEngine.
"""

from __future__ import annotations

from .ag2_chat import (
    AlphaGroupChat,
    GroupChatMessage,
    NativeAG2GroupChat,
    create_ag2_group_chat,
)
from .archify_engine import (
    ArchifyDiff,
    ArchifyEngine,
    EdgeDiff,
    GraphData,
    GraphEdge,
    GraphNode,
    NodeDiff,
    NodeStatus,
    NodeType,
    OLED_THEME,
)
from .crew_flows import (
    AlphaCrewFlow,
    CrewAgentRole,
    CrewTask,
    NativeCrewFlow,
    create_crew_flow,
)
from .delegation import (
    DelegationEngine,
    TaskExecutionResult,
    TaskStatus,
)
from .goal_parser import (
    GoalParser,
    GoalPriority,
    ParsedGoal,
    WorkstreamTask,
)
from .orchestrator import (
    AlphaOrchestrator,
    FinalOutput,
    OrchestratorResult,
    OrchestratorStatus,
)
from .scheduler import (
    CyclicDependencyError,
    ScheduledTask,
    SchedulePlan,
    Scheduler,
)
from .state_graph import (
    AlphaState,
    AlphaStateGraph,
    NativeCompiledGraph,
    NativeStateGraph,
    create_alpha_state_graph,
)
from .synthesizer import (
    ConflictResolution,
    FounderEscalation,
    OutputSynthesizer,
    SynthesizedDeliverable,
)
from .thread_manager import ThreadManager

__all__ = [
    # Master Pipeline
    "AlphaOrchestrator",
    "OrchestratorResult",
    "FinalOutput",
    "OrchestratorStatus",
    # StateGraph
    "AlphaState",
    "AlphaStateGraph",
    "NativeStateGraph",
    "NativeCompiledGraph",
    "create_alpha_state_graph",
    # CrewFlow
    "AlphaCrewFlow",
    "CrewAgentRole",
    "CrewTask",
    "NativeCrewFlow",
    "create_crew_flow",
    # AG2
    "AlphaGroupChat",
    "GroupChatMessage",
    "NativeAG2GroupChat",
    "create_ag2_group_chat",
    # Building Blocks
    "GoalParser",
    "ParsedGoal",
    "WorkstreamTask",
    "GoalPriority",
    "ThreadManager",
    "Scheduler",
    "ScheduledTask",
    "SchedulePlan",
    "CyclicDependencyError",
    "DelegationEngine",
    "TaskStatus",
    "TaskExecutionResult",
    "OutputSynthesizer",
    "SynthesizedDeliverable",
    "ConflictResolution",
    "FounderEscalation",
    "ArchifyEngine",
    "GraphNode",
    "GraphEdge",
    "GraphData",
    "ArchifyDiff",
    "NodeDiff",
    "EdgeDiff",
    "NodeStatus",
    "NodeType",
    "OLED_THEME",
]
