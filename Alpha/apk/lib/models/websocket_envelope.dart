// Alpha Mobile — WebSocketEnvelope Data Model
// Conforms to PROJECT.md Feature 69 and backend websocket.py universal envelopes

import 'agent.dart';
import 'graph_edge.dart';
import 'task_progress.dart';

class WebSocketEnvelope {
  final String event;
  final Map<String, dynamic> data;
  final String timestamp;

  WebSocketEnvelope({
    required this.event,
    required this.data,
    required this.timestamp,
  });

  factory WebSocketEnvelope.fromJson(Map<String, dynamic> json) {
    return WebSocketEnvelope(
      event: (json['event'] ?? '').toString(),
      data: (json['data'] as Map<String, dynamic>?) ?? {},
      timestamp: json['timestamp']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'event': event,
        'data': data,
        'timestamp': timestamp,
      };

  // Typed event classification getters
  bool get isTaskProgress => event == 'task_progress_update';
  bool get isAgentStatus => event == 'agent_status_change';
  bool get isNodeFlowPulse => event == 'node_flow_pulse';
  bool get isAuditStatus => event == 'audit_status_update';
  bool get isProjectState => event == 'project_state_change';
  bool get isHeartbeat => event == 'telemetry_heartbeat';
  bool get isConnected => event == 'connected';
  bool get isPong => event == 'pong';

  // Strongly-typed payload converters
  TaskProgress? asTaskProgress() =>
      isTaskProgress ? TaskProgress.fromJson(data) : null;

  Agent? asAgent() => isAgentStatus ? Agent.fromJson(data) : null;

  GraphEdge? asGraphEdgePulse() =>
      isNodeFlowPulse ? GraphEdge.fromJson(data) : null;

  @override
  String toString() =>
      'WebSocketEnvelope(event: $event, time: $timestamp, dataKeys: ${data.keys.toList()})';
}
