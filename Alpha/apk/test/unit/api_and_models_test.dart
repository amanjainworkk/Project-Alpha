// Project Alpha Mobile APK — Unit Test Suite
// Verifies genuine Dart Data Models imported from lib/models/models.dart,
// JSON round-trip serialization, ASCII progress bar formatting, and WebSocket envelopes.

import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';

// Genuine Dart domain models conforming to PROJECT.md Features 67-69
import '../../lib/models/models.dart';

void main() {
  group('Dart Data Models Serialization & Deserialization', () {
    test('Project model deserializes correctly from backend JSON', () {
      final jsonMap = {
        'project_id': 'proj_001',
        'title': 'AI Invoice SaaS',
        'description': 'Automated line item extractor',
        'status': 'in_progress',
        'progress': 0.75,
      };

      final project = Project.fromJson(jsonMap);
      expect(project.id, equals('proj_001'));
      expect(project.title, equals('AI Invoice SaaS'));
      expect(project.description, equals('Automated line item extractor'));
      expect(project.status, equals('in_progress'));
      expect(project.progress, equals(0.75));

      final backToJson = project.toJson();
      expect(backToJson['project_id'], equals('proj_001'));
      expect(backToJson['id'], equals('proj_001'));
    });

    test('Project model supports alias fallback for id and name', () {
      final aliasJson = {
        'id': 'proj_alt_02',
        'name': 'Alternative Title',
        'user_goal': 'Goal description',
      };
      final project = Project.fromJson(aliasJson);
      expect(project.id, equals('proj_alt_02'));
      expect(project.title, equals('Alternative Title'));
      expect(project.description, equals('Goal description'));
      expect(project.status, equals('planning'));
      expect(project.progress, equals(0.0));
    });

    test('Agent model deserializes with default values', () {
      final jsonMap = {
        'agent_id': 'CTO',
        'role': 'Chief Technology Officer',
        'status': 'active',
      };

      final agent = Agent.fromJson(jsonMap);
      expect(agent.agentId, equals('CTO'));
      expect(agent.role, equals('Chief Technology Officer'));
      expect(agent.model, equals('ollama/llama3.2'));
      expect(agent.costToday, equals(0.0));
      expect(agent.isActive, isTrue);

      final backJson = agent.toJson();
      expect(backJson['agent_id'], equals('CTO'));
      expect(backJson['agentId'], equals('CTO'));
      expect(backJson['model'], equals('ollama/llama3.2'));
    });

    test('TaskProgress model renders ASCII progress bar accurately', () {
      final task = TaskProgress(
        taskId: 'task_001',
        taskName: 'Generate Tech Spec',
        progressPercent: 80,
        currentStep: 'Resolving CAO audit flags',
        assignedAgent: 'CTO',
        status: 'auditing',
      );

      expect(task.formatProgressBar(), equals('[████████░░] 80%'));
      expect(task.isAuditing, isTrue);
      expect(task.progressFraction, equals(0.8));
    });

    test('TaskProgress clamps 0% and 100% boundary bars', () {
      final taskZero = TaskProgress(
        taskId: 't0',
        taskName: 'Init',
        progressPercent: 0,
        currentStep: 'Starting',
        assignedAgent: 'CEO',
        status: 'running',
      );
      expect(taskZero.formatProgressBar(), equals('[░░░░░░░░░░] 0%'));
      expect(taskZero.isRunning, isTrue);

      final taskHundred = TaskProgress(
        taskId: 't100',
        taskName: 'Finalize',
        progressPercent: 100,
        currentStep: 'Done',
        assignedAgent: 'CEO',
        status: 'done',
      );
      expect(taskHundred.formatProgressBar(), equals('[██████████] 100%'));
      expect(taskHundred.isDone, isTrue);

      final taskFifty = TaskProgress(
        taskId: 't50',
        taskName: 'Midpoint',
        progressPercent: 50,
        currentStep: 'Processing',
        assignedAgent: 'CFO',
        status: 'running',
      );
      expect(taskFifty.formatProgressBar(), equals('[█████░░░░░] 50%'));
    });

    test('TaskProgress clamps out-of-bounds negative and excessive percentages in progress bar', () {
      final taskNegative = TaskProgress(
        taskId: 't_neg',
        taskName: 'Negative Value Test',
        progressPercent: -50,
        currentStep: 'Underflow test',
        assignedAgent: 'CEO',
        status: 'running',
      );
      expect(taskNegative.formatProgressBar(), equals('[░░░░░░░░░░] 0%'));
      expect(taskNegative.progressFraction, equals(0.0));

      final taskExcess = TaskProgress(
        taskId: 't_excess',
        taskName: 'Excessive Value Test',
        progressPercent: 150,
        currentStep: 'Overflow test',
        assignedAgent: 'CEO',
        status: 'done',
      );
      expect(taskExcess.formatProgressBar(), equals('[██████████] 100%'));
      expect(taskExcess.progressFraction, equals(1.0));
    });

    test('GraphNode parses interactive node properties', () {
      final jsonMap = {
        'id': 'node_vault',
        'label': 'Alpha Vault SQLite',
        'type': 'storage',
        'status': 'healthy',
        'dx': 120.0,
        'dy': 350.5,
      };
      final node = GraphNode.fromJson(jsonMap);
      expect(node.id, equals('node_vault'));
      expect(node.label, equals('Alpha Vault SQLite'));
      expect(node.type, equals('storage'));
      expect(node.status, equals('healthy'));
      expect(node.dx, equals(120.0));
      expect(node.dy, equals(350.5));
      expect(node.isHealthy, isTrue);
      expect(node.isStore, isTrue);
    });

    test('GraphEdge deserializes spline connection properties', () {
      final edgeJson = {
        'source_id': 'node_ceo',
        'target_id': 'node_cto',
        'label': 'Architecture Delegation',
        'is_pulsing': true,
        'pulse_color': '#06B6D4',
        'latency_ms': 45,
      };
      final edge = GraphEdge.fromJson(edgeJson);
      expect(edge.sourceId, equals('node_ceo'));
      expect(edge.targetId, equals('node_cto'));
      expect(edge.label, equals('Architecture Delegation'));
      expect(edge.isPulsing, isTrue);
      expect(edge.pulseColor, equals('#06B6D4'));
      expect(edge.latencyMs, equals(45));
      expect(edge.key, equals('node_ceo->node_cto'));
    });

    test('GraphEdge preserves isPulsing false across JSON round-trip serialization', () {
      final edge = GraphEdge(
        sourceId: 'node_ceo',
        targetId: 'node_cto',
        isPulsing: false,
        pulseColor: '#06B6D4',
        latencyMs: 30,
      );
      expect(edge.isPulsing, isFalse);

      final jsonMap = edge.toJson();
      expect(jsonMap['is_pulsing'], isFalse);
      expect(jsonMap['isPulsing'], isFalse);

      final reconstituted = GraphEdge.fromJson(jsonMap);
      expect(reconstituted.isPulsing, isFalse);
      expect(reconstituted.sourceId, equals('node_ceo'));
      expect(reconstituted.targetId, equals('node_cto'));
    });

    test('GraphEdge preserves isPulsing true across JSON round-trip serialization', () {
      final activeEdge = GraphEdge(
        sourceId: 'node_cto',
        targetId: 'node_cdo',
        label: 'Design System Delivery',
        isPulsing: true,
        pulseColor: '#3B82F6',
        latencyMs: 30,
      );

      final jsonMap = activeEdge.toJson();
      expect(jsonMap['is_pulsing'], isTrue);
      expect(jsonMap['isPulsing'], isTrue);

      final reconstituted = GraphEdge.fromJson(jsonMap);
      expect(reconstituted.isPulsing, isTrue);
      expect(reconstituted.sourceId, equals('node_cto'));
      expect(reconstituted.targetId, equals('node_cdo'));
      expect(reconstituted.pulseColor, equals('#3B82F6'));
    });

    test('ThreadMessage parses deliberation communications', () {
      final msgJson = {
        'message_id': 'msg_01',
        'sender': 'CTO',
        'content': 'Architecture plan drafted and submitted to CAO-Claude',
        'timestamp': '2026-11-07T12:00:00Z',
        'message_type': 'DELIBERATION',
        'to_agents': ['CEO', 'CAO-Claude'],
      };
      final msg = ThreadMessage.fromJson(msgJson);
      expect(msg.messageId, equals('msg_01'));
      expect(msg.sender, equals('CTO'));
      expect(msg.content, contains('Architecture plan'));
      expect(msg.messageType, equals('DELIBERATION'));
      expect(msg.isDeliberation, isTrue);
      expect(msg.toAgents, contains('CEO'));
      expect(msg.toAgents, contains('CAO-Claude'));
    });
  });

  group('WebSocket Envelope Parsing', () {
    test('WebSocketEnvelope parses typed telemetry payloads', () {
      final rawWsJson = jsonEncode({
        'event': 'task_progress_update',
        'data': {
          'task_id': 'task_001',
          'progress_percent': 85,
          'status': 'running',
        },
        'timestamp': '1730912400',
      });

      final decoded = jsonDecode(rawWsJson) as Map<String, dynamic>;
      final envelope = WebSocketEnvelope.fromJson(decoded);

      expect(envelope.event, equals('task_progress_update'));
      expect(envelope.isTaskProgress, isTrue);
      expect(envelope.data['task_id'], equals('task_001'));
      expect(envelope.data['progress_percent'], equals(85));
      expect(envelope.timestamp, equals('1730912400'));

      final task = envelope.asTaskProgress();
      expect(task, isNotNull);
      expect(task!.taskId, equals('task_001'));
      expect(task.progressPercent, equals(85));
    });

    test('WebSocketEnvelope handles empty or malformed data gracefully', () {
      final envelope = WebSocketEnvelope.fromJson({});
      expect(envelope.event, equals(''));
      expect(envelope.data, isEmpty);
      expect(envelope.timestamp, equals(''));
      expect(envelope.asTaskProgress(), isNull);
      expect(envelope.asAgent(), isNull);
    });
  });
}
