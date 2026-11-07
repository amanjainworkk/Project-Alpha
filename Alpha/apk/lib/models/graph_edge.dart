// Alpha Mobile — GraphEdge Data Model
// Conforms to PROJECT.md Feature 67, 71 (Live Pulsing Data Flows)

class GraphEdge {
  final String sourceId;
  final String targetId;
  final String label;
  final bool isPulsing;
  final String pulseColor; // Default neon cyan '#06B6D4'
  final int latencyMs;

  GraphEdge({
    required this.sourceId,
    required this.targetId,
    this.label = '',
    this.isPulsing = false,
    this.pulseColor = '#06B6D4',
    this.latencyMs = 0,
  });

  factory GraphEdge.fromJson(Map<String, dynamic> json) {
    return GraphEdge(
      sourceId: (json['source_id'] ?? json['sourceId'] ?? json['source_agent'] ?? json['source'] ?? '').toString(),
      targetId: (json['target_id'] ?? json['targetId'] ?? json['target_agent'] ?? json['target'] ?? '').toString(),
      label: (json['label'] ?? json['message_type'] ?? json['preview'] ?? '').toString(),
      isPulsing: json['is_pulsing'] == true || json['isPulsing'] == true,
      pulseColor: (json['pulse_color'] ?? json['pulseColor'] ?? '#06B6D4').toString(),
      latencyMs: (json['latency_ms'] ?? json['latencyMs'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'source_id': sourceId,
        'sourceId': sourceId,
        'target_id': targetId,
        'targetId': targetId,
        'label': label,
        'is_pulsing': isPulsing,
        'isPulsing': isPulsing,
        'pulse_color': pulseColor,
        'pulseColor': pulseColor,
        'latency_ms': latencyMs,
        'latencyMs': latencyMs,
      };

  String get key => '$sourceId->$targetId';

  GraphEdge copyWith({
    String? sourceId,
    String? targetId,
    String? label,
    bool? isPulsing,
    String? pulseColor,
    int? latencyMs,
  }) {
    return GraphEdge(
      sourceId: sourceId ?? this.sourceId,
      targetId: targetId ?? this.targetId,
      label: label ?? this.label,
      isPulsing: isPulsing ?? this.isPulsing,
      pulseColor: pulseColor ?? this.pulseColor,
      latencyMs: latencyMs ?? this.latencyMs,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GraphEdge &&
          runtimeType == other.runtimeType &&
          sourceId == other.sourceId &&
          targetId == other.targetId &&
          isPulsing == other.isPulsing;

  @override
  int get hashCode => sourceId.hashCode ^ targetId.hashCode ^ isPulsing.hashCode;

  @override
  String toString() =>
      'GraphEdge($sourceId -> $targetId, pulsing: $isPulsing, color: $pulseColor)';
}
