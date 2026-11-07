// Alpha Mobile — Project Data Model
// Conforms to PROJECT.md Feature 67 and FastAPI schemas.py (ProjectSummary / ProjectDetail)

class Project {
  final String id;
  final String title;
  final String description;
  final String status;
  final double progress;
  final String priority;
  final String? createdAt;
  final String leadAgent;
  final List<String> assignedAgents;
  final Map<String, dynamic>? deliverables;
  final String? auditStatus;

  Project({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    this.progress = 0.0,
    this.priority = 'medium',
    this.createdAt,
    this.leadAgent = 'CEO',
    this.assignedAgents = const [],
    this.deliverables,
    this.auditStatus,
  });

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: (json['project_id'] ?? json['id'] ?? '').toString(),
      title: (json['title'] ?? json['name'] ?? '').toString(),
      description: (json['description'] ?? json['user_goal'] ?? '').toString(),
      status: (json['status'] ?? 'planning').toString(),
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
      priority: (json['priority'] ?? 'medium').toString(),
      createdAt: json['created_at']?.toString(),
      leadAgent: (json['lead_agent'] ?? 'CEO').toString(),
      assignedAgents: (json['assigned_agents'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      deliverables: json['deliverables'] is Map<String, dynamic>
          ? json['deliverables'] as Map<String, dynamic>
          : null,
      auditStatus: json['audit_status']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'project_id': id,
        'id': id,
        'title': title,
        'description': description,
        'status': status,
        'progress': progress,
        'priority': priority,
        if (createdAt != null) 'created_at': createdAt,
        'lead_agent': leadAgent,
        'assigned_agents': assignedAgents,
        if (deliverables != null) 'deliverables': deliverables,
        if (auditStatus != null) 'audit_status': auditStatus,
      };

  Project copyWith({
    String? id,
    String? title,
    String? description,
    String? status,
    double? progress,
    String? priority,
    String? createdAt,
    String? leadAgent,
    List<String>? assignedAgents,
    Map<String, dynamic>? deliverables,
    String? auditStatus,
  }) {
    return Project(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      status: status ?? this.status,
      progress: progress ?? this.progress,
      priority: priority ?? this.priority,
      createdAt: createdAt ?? this.createdAt,
      leadAgent: leadAgent ?? this.leadAgent,
      assignedAgents: assignedAgents ?? this.assignedAgents,
      deliverables: deliverables ?? this.deliverables,
      auditStatus: auditStatus ?? this.auditStatus,
    );
  }

  bool get isCompleted =>
      status == 'completed' || status == 'done' || progress >= 1.0;
  bool get isActive => status == 'in_progress' || status == 'active';
  bool get isPlanning => status == 'planning';
  bool get isBlocked => status == 'blocked';
  bool get isAuditing => status == 'auditing' || status == 'review';
  int get progressPercent => (progress * 100).round().clamp(0, 100);

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Project &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          title == other.title &&
          status == other.status &&
          progress == other.progress;

  @override
  int get hashCode =>
      id.hashCode ^ title.hashCode ^ status.hashCode ^ progress.hashCode;

  @override
  String toString() =>
      'Project(id: $id, title: $title, status: $status, progress: $progress)';
}
