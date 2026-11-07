"""Alpha Milestone 10 Iteration 2 Adversarial Stress & Verification Test Suite.

Authored by challenger_m10_r2_2 (Empirical Challenger).
Stress-tests:
1. GraphEdge round-trip serialization/deserialization fidelity (100+ randomized instances, mutation detection).
2. TaskProgress formatProgressBar() boundary clamping (-1M to +1M sweep, regex format validation).
3. Dart AST and delimiter integrity across all 23 Dart files in Alpha/apk/.
4. Test suite anti-cheat and authentic production model import verification.
"""

import glob
import math
import os
import random
import re
import string
from typing import Any, Dict, List, Optional, Tuple
import pytest

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APK_DIR = os.path.join(BASE_DIR, "apk")


# ==============================================================================
# Exact Dart Model Implementations (Parsed and Mirrored from lib/models/)
# ==============================================================================

class DartGraphEdgeModel:
    """Exact behavioral replica of Alpha/apk/lib/models/graph_edge.dart."""
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
    def from_json(cls, json_data: Dict[str, Any]) -> "DartGraphEdgeModel":
        # Dart line 23:
        source_id = str(
            json_data.get("source_id")
            if json_data.get("source_id") is not None
            else (
                json_data.get("sourceId")
                if json_data.get("sourceId") is not None
                else (
                    json_data.get("source_agent")
                    if json_data.get("source_agent") is not None
                    else (json_data.get("source") if json_data.get("source") is not None else "")
                )
            )
        )
        # Dart line 24:
        target_id = str(
            json_data.get("target_id")
            if json_data.get("target_id") is not None
            else (
                json_data.get("targetId")
                if json_data.get("targetId") is not None
                else (
                    json_data.get("target_agent")
                    if json_data.get("target_agent") is not None
                    else (json_data.get("target") if json_data.get("target") is not None else "")
                )
            )
        )
        # Dart line 25:
        label = str(
            json_data.get("label")
            if json_data.get("label") is not None
            else (
                json_data.get("message_type")
                if json_data.get("message_type") is not None
                else (json_data.get("preview") if json_data.get("preview") is not None else "")
            )
        )
        # Dart line 26 (REMEDIATED IN ITERATION 2):
        # isPulsing: json['is_pulsing'] == true || json['isPulsing'] == true
        is_pulsing = (json_data.get("is_pulsing") is True) or (json_data.get("isPulsing") is True)

        # Dart line 27:
        pulse_color = str(
            json_data.get("pulse_color")
            if json_data.get("pulse_color") is not None
            else (
                json_data.get("pulseColor")
                if json_data.get("pulseColor") is not None
                else "#06B6D4"
            )
        )

        # Dart line 28:
        raw_latency = json_data.get("latency_ms") if json_data.get("latency_ms") is not None else json_data.get("latencyMs")
        if isinstance(raw_latency, (int, float)):
            latency_ms = int(raw_latency)
        else:
            latency_ms = 0

        return cls(
            source_id=source_id,
            target_id=target_id,
            label=label,
            is_pulsing=is_pulsing,
            pulse_color=pulse_color,
            latency_ms=latency_ms,
        )

    def to_json(self) -> Dict[str, Any]:
        # Dart lines 32-44:
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

    @property
    def key(self) -> str:
        return f"{self.source_id}->{self.target_id}"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DartGraphEdgeModel):
            return False
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.is_pulsing == other.is_pulsing
        )

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.is_pulsing))


class DartTaskProgressModel:
    """Exact behavioral replica of Alpha/apk/lib/models/task_progress.dart."""
    def __init__(
        self,
        task_id: str,
        task_name: str,
        progress_percent: int,
        current_step: str,
        assigned_agent: str,
        status: str = "running",
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.progress_percent = progress_percent
        self.current_step = current_step
        self.assigned_agent = assigned_agent
        self.status = status

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "DartTaskProgressModel":
        raw_id = str(json_data.get("task_id") or json_data.get("taskId") or "")
        raw_name = str(json_data.get("task_name") or json_data.get("taskName") or "")
        raw_pct = json_data.get("progress_percent") if json_data.get("progress_percent") is not None else json_data.get("progressPercent")
        if isinstance(raw_pct, (int, float)):
            pct = int(raw_pct)
        else:
            pct = 0
        raw_step = str(json_data.get("current_step") or json_data.get("currentStep") or "")
        raw_agent = str(json_data.get("assigned_agent") or json_data.get("assignedAgent") or "")
        raw_status = str(json_data.get("status") or "running")
        return cls(
            task_id=raw_id,
            task_name=raw_name,
            progress_percent=pct,
            current_step=raw_step,
            assigned_agent=raw_agent,
            status=raw_status,
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "taskId": self.task_id,
            "task_name": self.task_name,
            "taskName": self.task_name,
            "progress_percent": self.progress_percent,
            "progressPercent": self.progress_percent,
            "current_step": self.current_step,
            "currentStep": self.current_step,
            "assigned_agent": self.assigned_agent,
            "assignedAgent": self.assigned_agent,
            "status": self.status,
        }

    def format_progress_bar(self) -> str:
        # Dart lines 48-53 (REMEDIATED IN ITERATION 2):
        # final int clamped = progressPercent.clamp(0, 100);
        # final int filled = (clamped / 10).round().clamp(0, 10);
        # final int empty = (10 - filled).clamp(0, 10);
        # return '[${'█' * filled}${'░' * empty}] $clamped%';
        clamped = max(0, min(100, self.progress_percent))
        val = clamped / 10.0
        # Emulate Dart's (double).round(): standard arithmetic rounding (.5 -> up)
        rounded = int(math.floor(val + 0.5))
        filled = max(0, min(10, rounded))
        empty = max(0, min(10, 10 - filled))
        bar = ("█" * filled) + ("░" * empty)
        return f"[{bar}] {clamped}%"

    @property
    def progress_fraction(self) -> float:
        return max(0.0, min(1.0, self.progress_percent / 100.0))

    @property
    def is_done(self) -> bool:
        return self.status in ("done", "completed") or self.progress_percent >= 100

    @property
    def is_running(self) -> bool:
        return self.status == "running"


# ==============================================================================
# Challenge 1: GraphEdge 100+ Randomized Round-Trip Stress Test
# ==============================================================================

def test_graph_edge_randomized_roundtrip_fidelity_stress():
    """Adversarially generate 100+ randomized GraphEdge instances with varied properties.

    Verify 100% round-trip fidelity through toJson() -> fromJson().
    Specifically verify that non-pulsing edges NEVER mutate into pulsing edges.
    """
    rng = random.Random(42)  # Deterministic seed for reproducible stress-testing

    sample_colors = [
        "#06B6D4", "#3B82F6", "#10B981", "#EF4444", "#F59E0B", "#8B5CF6",
        "#EC4899", "#14B8A6", "#6366F1", "#000000", "#FFFFFF", "#ABCDEF"
    ]

    sample_agents = [
        "CEO", "CTO", "CMO", "CPO", "CDO", "CFO", "COO", "CHRO", "CIO",
        "CSO", "CLO", "CAO-Claude", "CAO-ChatGPT", "Founder", "External-User"
    ]

    generated_edges: List[DartGraphEdgeModel] = []

    # Generate 50 non-pulsing edges
    for i in range(50):
        s = rng.choice(sample_agents)
        t = rng.choice(sample_agents)
        while t == s:
            t = rng.choice(sample_agents)
        color = rng.choice(sample_colors)
        lat = rng.randint(0, 500)
        lbl = f"Route {i}: {s} -> {t}"
        edge = DartGraphEdgeModel(
            source_id=f"node_{s.lower()}",
            target_id=f"node_{t.lower()}",
            label=lbl,
            is_pulsing=False,
            pulse_color=color,
            latency_ms=lat,
        )
        generated_edges.append(edge)

    # Generate 50 pulsing edges
    for i in range(50):
        s = rng.choice(sample_agents)
        t = rng.choice(sample_agents)
        while t == s:
            t = rng.choice(sample_agents)
        color = rng.choice(sample_colors)
        lat = rng.randint(0, 500)
        lbl = f"Pulsing Stream {i}: {s} -> {t}"
        edge = DartGraphEdgeModel(
            source_id=f"node_{s.lower()}",
            target_id=f"node_{t.lower()}",
            label=lbl,
            is_pulsing=True,
            pulse_color=color,
            latency_ms=lat,
        )
        generated_edges.append(edge)

    # Add 20 edge-case boundary edges
    edge_cases = [
        # Empty fields
        DartGraphEdgeModel(source_id="", target_id="", label="", is_pulsing=False, pulse_color="", latency_ms=0),
        DartGraphEdgeModel(source_id="", target_id="", label="", is_pulsing=True, pulse_color="", latency_ms=0),
        # Default color
        DartGraphEdgeModel(source_id="a", target_id="b", is_pulsing=False, pulse_color="#06B6D4"),
        DartGraphEdgeModel(source_id="a", target_id="b", is_pulsing=True, pulse_color="#06B6D4"),
        # Extreme latency
        DartGraphEdgeModel(source_id="x", target_id="y", is_pulsing=False, pulse_color="#3B82F6", latency_ms=999999),
        DartGraphEdgeModel(source_id="x", target_id="y", is_pulsing=True, pulse_color="#3B82F6", latency_ms=999999),
        # Negative latency (boundary check)
        DartGraphEdgeModel(source_id="x", target_id="y", is_pulsing=False, pulse_color="#3B82F6", latency_ms=-10),
        # Unicode labels
        DartGraphEdgeModel(source_id="alpha", target_id="beta", label="🚀 Data Stream → CAO", is_pulsing=False, pulse_color="#10B981"),
        DartGraphEdgeModel(source_id="alpha", target_id="beta", label="🔥 High Priority Alert", is_pulsing=True, pulse_color="#EF4444"),
    ]
    generated_edges.extend(edge_cases)

    assert len(generated_edges) >= 100, f"Expected at least 100 edges, got {len(generated_edges)}"

    # Round-trip stress testing
    mutation_failures = []
    fidelity_failures = []

    for idx, original in enumerate(generated_edges):
        json_payload = original.to_json()
        reconstituted = DartGraphEdgeModel.from_json(json_payload)

        # 1. Non-pulsing edges must NEVER mutate to pulsing
        if not original.is_pulsing and reconstituted.is_pulsing:
            mutation_failures.append((idx, original, reconstituted, json_payload))

        # 2. Pulsing edges must remain pulsing
        if original.is_pulsing and not reconstituted.is_pulsing:
            mutation_failures.append((idx, original, reconstituted, json_payload))

        # 3. Complete field-by-field fidelity
        if reconstituted.source_id != original.source_id:
            fidelity_failures.append((idx, "source_id", original.source_id, reconstituted.source_id))
        if reconstituted.target_id != original.target_id:
            fidelity_failures.append((idx, "target_id", original.target_id, reconstituted.target_id))
        if reconstituted.label != original.label:
            fidelity_failures.append((idx, "label", original.label, reconstituted.label))
        if reconstituted.pulse_color != original.pulse_color:
            fidelity_failures.append((idx, "pulse_color", original.pulse_color, reconstituted.pulse_color))
        if reconstituted.latency_ms != original.latency_ms:
            fidelity_failures.append((idx, "latency_ms", original.latency_ms, reconstituted.latency_ms))
        if reconstituted.key != original.key:
            fidelity_failures.append((idx, "key", original.key, reconstituted.key))

    assert len(mutation_failures) == 0, f"MUTATION BUG DETECTED: {len(mutation_failures)} edges mutated! {mutation_failures[:3]}"
    assert len(fidelity_failures) == 0, f"FIDELITY FAILURES: {len(fidelity_failures)} mismatches! {fidelity_failures[:3]}"


def test_graph_edge_adversarial_json_deserialization_payloads():
    """Adversarial stress-testing of from_json with malformed, type-mismatched, and partial payloads."""
    # 1. Payload with explicit is_pulsing: false and non-null pulse_color
    e1 = DartGraphEdgeModel.from_json({
        "source_id": "ceo",
        "target_id": "cto",
        "is_pulsing": False,
        "pulse_color": "#06B6D4",
    })
    assert e1.is_pulsing is False, "Non-pulsing edge mutated to true with pulse_color!"

    # 2. Payload with only camelCase isPulsing: false and non-null pulseColor
    e2 = DartGraphEdgeModel.from_json({
        "sourceId": "ceo",
        "targetId": "cto",
        "isPulsing": False,
        "pulseColor": "#3B82F6",
    })
    assert e2.is_pulsing is False

    # 3. Payload with string boolean 'false' -> must NOT evaluate to true (truth equality)
    e3 = DartGraphEdgeModel.from_json({
        "source_id": "ceo",
        "target_id": "cto",
        "is_pulsing": "false",
        "pulse_color": "#06B6D4",
    })
    assert e3.is_pulsing is False

    # 4. Payload with integer 1 / 0
    e4 = DartGraphEdgeModel.from_json({"is_pulsing": 0})
    assert e4.is_pulsing is False
    e5 = DartGraphEdgeModel.from_json({"is_pulsing": 1})
    assert e5.is_pulsing is False  # In Dart, 1 == true is false

    # 5. Missing all pulsing keys -> defaults to False
    e6 = DartGraphEdgeModel.from_json({
        "source_id": "ceo",
        "target_id": "cto",
        "pulse_color": "#06B6D4",
    })
    assert e6.is_pulsing is False

    # 6. Fallback aliases for source and target
    e7 = DartGraphEdgeModel.from_json({"source_agent": "COO", "target_agent": "CFO"})
    assert e7.source_id == "COO"
    assert e7.target_id == "CFO"
    assert e7.key == "COO->CFO"

    e8 = DartGraphEdgeModel.from_json({"source": "CSO", "target": "CLO", "preview": "Legal check"})
    assert e8.source_id == "CSO"
    assert e8.target_id == "CLO"
    assert e8.label == "Legal check"


# ==============================================================================
# Challenge 2: TaskProgress formatProgressBar() Clamping Stress Test
# ==============================================================================

def test_task_progress_boundary_clamping_exact_values():
    """Verify exact return strings for -50, 0, 10, 50, 80, 100, 150."""
    cases = [
        (-50, "[░░░░░░░░░░] 0%"),
        (0, "[░░░░░░░░░░] 0%"),
        (10, "[█░░░░░░░░░] 10%"),
        (50, "[█████░░░░░] 50%"),
        (80, "[████████░░] 80%"),
        (100, "[██████████] 100%"),
        (150, "[██████████] 100%"),
    ]

    for input_pct, expected_bar in cases:
        task = DartTaskProgressModel(
            task_id="t_test",
            task_name="Test Task",
            progress_percent=input_pct,
            current_step="Testing",
            assigned_agent="CEO",
        )
        actual_bar = task.format_progress_bar()
        assert actual_bar == expected_bar, (
            f"Clamping failure for progressPercent={input_pct}: "
            f"expected '{expected_bar}', got '{actual_bar}'"
        )


def test_task_progress_extreme_bounds_and_no_out_of_bounds_text():
    """Verify extreme underflows and overflows never emit out-of-bounds percentages."""
    extreme_inputs = [
        -1, -2, -10, -50, -100, -999, -1000, -999999, -2147483648,
        101, 105, 110, 150, 200, 500, 1000, 999999, 2147483647
    ]

    # Strict regex: must start with [, exactly 10 block/shade characters, ], space, clamped 0..100, %
    bar_regex = re.compile(r"^\[([█░]{10})\] (100|[1-9]?[0-9])%$")

    for val in extreme_inputs:
        task = DartTaskProgressModel(
            task_id="t_extreme",
            task_name="Extreme Task",
            progress_percent=val,
            current_step="Testing",
            assigned_agent="CEO",
        )
        output = task.format_progress_bar()

        # 1. Matches strict format
        match = bar_regex.match(output)
        assert match is not None, f"Output '{output}' does not conform to regex for input {val}"

        glyphs = match.group(1)
        clamped_text = match.group(2)

        # 2. Check inner glyph count is always 10
        assert len(glyphs) == 10

        # 3. Check underflow behavior
        if val <= 0:
            assert glyphs == "░" * 10, f"Expected 10 empty glyphs for {val}, got {glyphs}"
            assert clamped_text == "0", f"Expected '0' display for {val}, got {clamped_text}"
            assert task.progress_fraction == 0.0

        # 4. Check overflow behavior
        if val >= 100:
            assert glyphs == "█" * 10, f"Expected 10 filled glyphs for {val}, got {glyphs}"
            assert clamped_text == "100", f"Expected '100' display for {val}, got {clamped_text}"
            assert task.progress_fraction == 1.0

        # 5. CRITICAL: Out-of-bounds text check
        assert f"{val}%" not in output or (0 <= val <= 100), (
            f"CRITICAL DEFECT: Unclamped raw value {val}% leaked into output: '{output}'"
        )


def test_task_progress_exhaustive_integer_sweep_neg200_to_300():
    """Exhaustively sweep 501 consecutive integers from -200 to +300."""
    bar_regex = re.compile(r"^\[([█░]{10})\] (\d+)%$")

    for pct in range(-200, 301):
        task = DartTaskProgressModel(
            task_id=f"t_{pct}",
            task_name="Sweep Task",
            progress_percent=pct,
            current_step="Sweep",
            assigned_agent="COO",
        )
        bar = task.format_progress_bar()
        match = bar_regex.match(bar)
        assert match is not None, f"Regex failure for {pct}: '{bar}'"

        glyphs, display_num_str = match.groups()
        display_num = int(display_num_str)

        # Display number must be strictly bounded in [0, 100]
        assert 0 <= display_num <= 100, f"Display number {display_num} out of bounds for input {pct}"

        # Glyphs filled count must match (display_num / 10).round()
        filled_count = glyphs.count("█")
        empty_count = glyphs.count("░")
        assert filled_count + empty_count == 10
        expected_filled = max(0, min(10, int(math.floor((display_num / 10.0) + 0.5))))
        assert filled_count == expected_filled, f"Glyph mismatch for {pct}: filled={filled_count}, expected={expected_filled}"


# ==============================================================================
# Challenge 3: Dart Source Code Invariant Verification via Lexer/Parser
# ==============================================================================

def test_source_code_ast_delimiters_across_all_23_dart_files():
    """Empirically audit lexer-based delimiter balance across all Dart files in apk/."""
    files = sorted(glob.glob(os.path.join(APK_DIR, "**", "*.dart"), recursive=True))
    assert len(files) >= 23, f"Expected at least 23 Dart files in apk/, found {len(files)}"

    pairs = {')': '(', '}': '{', ']': '['}

    for filepath in files:
        rel = os.path.relpath(filepath, APK_DIR)
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        stack = []
        i = 0
        n = len(code)
        in_line_comment = False
        in_block_comment = False
        in_single_str = False
        in_double_str = False
        in_triple_single = False
        in_triple_double = False
        line, col = 1, 1
        err = None

        while i < n:
            c = code[i]
            if c == '\n':
                line += 1
                col = 0
                if in_line_comment:
                    in_line_comment = False
            col += 1

            if not (in_single_str or in_double_str or in_triple_single or in_triple_double):
                if not (in_line_comment or in_block_comment):
                    if code[i:i + 2] == '//':
                        in_line_comment = True
                        i += 2
                        continue
                    elif code[i:i + 2] == '/*':
                        in_block_comment = True
                        i += 2
                        continue
                elif in_block_comment:
                    if code[i:i + 2] == '*/':
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                elif in_line_comment:
                    i += 1
                    continue

            if not (in_line_comment or in_block_comment):
                if code[i:i + 3] == "'''":
                    in_triple_single = not in_triple_single
                    i += 3
                    continue
                elif code[i:i + 3] == '"""':
                    in_triple_double = not in_triple_double
                    i += 3
                    continue
                elif c == "'" and not in_triple_single and not in_double_str and not in_triple_double:
                    if i > 0 and code[i - 1] == '\\' and (i < 2 or code[i - 2] != '\\'):
                        pass
                    else:
                        in_single_str = not in_single_str
                    i += 1
                    continue
                elif c == '"' and not in_triple_double and not in_single_str and not in_triple_single:
                    if i > 0 and code[i - 1] == '\\' and (i < 2 or code[i - 2] != '\\'):
                        pass
                    else:
                        in_double_str = not in_double_str
                    i += 1
                    continue

            if not (in_line_comment or in_block_comment or in_single_str or in_double_str or in_triple_single or in_triple_double):
                if c in '({[':
                    stack.append((c, line, col))
                elif c in ')}]':
                    assert stack, f"Delimiter error in {rel}: extra closing '{c}' at {line}:{col}"
                    top, t_line, t_col = stack.pop()
                    assert pairs[c] == top, (
                        f"Delimiter mismatch in {rel}: '{top}' (line {t_line}:{t_col}) "
                        f"closed with '{c}' at {line}:{col}"
                    )
            i += 1

        assert not stack, f"Delimiter error in {rel}: unclosed '{stack[-1][0]}' from {stack[-1][1]}:{stack[-1][2]}"


def test_source_code_tokens_in_graph_edge_and_task_progress():
    """Verify exact token sequences in graph_edge.dart and task_progress.dart on disk."""
    edge_file = os.path.join(APK_DIR, "lib", "models", "graph_edge.dart")
    with open(edge_file, "r", encoding="utf-8") as f:
        edge_src = f.read()

    # The buggy check '(json['pulse_color'] != null)' must NOT exist
    assert "pulse_color != null" not in edge_src, "CRITICAL DEFECT: pulse_color != null still found in graph_edge.dart!"
    assert "pulseColor != null" not in edge_src

    # Must contain boolean check
    assert "is_pulsing'] == true || json['isPulsing'] == true" in edge_src or \
           "is_pulsing'] == true ||" in edge_src, "Boolean check missing in graph_edge.dart!"

    task_file = os.path.join(APK_DIR, "lib", "models", "task_progress.dart")
    with open(task_file, "r", encoding="utf-8") as f:
        task_src = f.read()

    # Must contain clamping in formatProgressBar()
    assert "final int clamped = progressPercent.clamp(0, 100);" in task_src
    assert "$clamped%" in task_src


def test_anti_cheat_absence_of_mockups_and_presence_of_authentic_imports():
    """Verify test suites do not contain dummy mockup widgets or test evasion tricks."""
    widget_test_path = os.path.join(APK_DIR, "test", "widget", "canvas_and_progress_test.dart")
    with open(widget_test_path, "r", encoding="utf-8") as f:
        widget_test_src = f.read()

    forbidden_classes = [
        "class ProgressBarCardWidget",
        "class AgentCardWidget",
        "class MockArchifyCanvasWidget",
        "class Dummy",
        "class Fake",
    ]
    for forbidden in forbidden_classes:
        assert forbidden not in widget_test_src, f"ANTI-CHEAT VIOLATION: '{forbidden}' found in widget test!"

    # Authentic production imports must be present
    assert "package:alpha_mobile/main.dart" in widget_test_src
    assert "package:alpha_mobile/theme/alpha_theme.dart" in widget_test_src
    assert "package:alpha_mobile/theme/alpha_colors.dart" in widget_test_src

    # Unit test imports
    unit_test_path = os.path.join(APK_DIR, "test", "unit", "api_and_models_test.dart")
    with open(unit_test_path, "r", encoding="utf-8") as f:
        unit_test_src = f.read()

    assert "../../lib/models/models.dart" in unit_test_src
    assert "TaskProgress clamps out-of-bounds negative and excessive percentages" in unit_test_src
    assert "GraphEdge preserves isPulsing false across JSON round-trip serialization" in unit_test_src
    assert "GraphEdge preserves isPulsing true across JSON round-trip serialization" in unit_test_src
