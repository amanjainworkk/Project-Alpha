// Alpha Mobile — GraphNode Data Model
// Conforms to PROJECT.md Feature 67, 70 (Archify+ Interactive Living Canvas)

class GraphNode {
  final String id;
  final String label;
  final String type; // 'service', 'agent', 'store', 'gateway', 'external'
  final String status; // 'active', 'healthy', 'degraded', 'blocked', 'idle'
  final double dx;
  final double dy;
  final Map<String, dynamic>? metadata;

  GraphNode({
    required this.id,
    required this.label,
    required this.type,
    required this.status,
    this.dx = 0.0,
    this.dy = 0.0,
    this.metadata,
  });

  factory GraphNode.fromJson(Map<String, dynamic> json) {
    return GraphNode(
      id: (json['id'] ?? '').toString(),
      label: (json['label'] ?? json['name'] ?? '').toString(),
      type: (json['type'] ?? 'service').toString(),
      status: (json['status'] ?? 'active').toString(),
      dx: (json['dx'] ?? json['x'] as num?)?.toDouble() ?? 0.0,
      dy: (json['dy'] ?? json['y'] as num?)?.toDouble() ?? 0.0,
      metadata: json['metadata'] is Map<String, dynamic>
          ? json['metadata'] as Map<String, dynamic>
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'label': label,
        'type': type,
        'status': status,
        'dx': dx,
        'dy': dy,
        if (metadata != null) 'metadata': metadata,
      };

  GraphNode copyWith({
    String? id,
    String? label,
    String? type,
    String? status,
    double? dx,
    double? dy,
    Map<String, dynamic>? metadata,
  }) {
    return GraphNode(
      id: id ?? this.id,
      label: label ?? this.label,
      type: type ?? this.type,
      status: status ?? this.status,
      dx: dx ?? this.dx,
      dy: dy ?? this.dy,
      metadata: metadata ?? this.metadata,
    );
  }

  bool get isHealthy => status == 'healthy' || status == 'active';
  bool get isAgent => type == 'agent';
  bool get isStore => type == 'store' || type == 'storage';
  bool get isService => type == 'service';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GraphNode &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          type == other.type &&
          status == other.status;

  @override
  int get hashCode => id.hashCode ^ type.hashCode ^ status.hashCode;

  @override
  String toString() =>
      'GraphNode(id: $id, label: $label, type: $type, status: $status, pos: ($dx, $dy))';
}
