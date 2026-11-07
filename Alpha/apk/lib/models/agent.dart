// Alpha Mobile — Agent Data Model
// Conforms to PROJECT.md Feature 67 and FastAPI schemas.py (AgentCard / AgentDetail)

class Agent {
  final String agentId;
  final String role;
  final String status;
  final String model;
  final double costToday;
  final String fullTitle;
  final String currentTask;
  final int tokensUsed;
  final List<String> skills;
  final String communicationStyle;

  Agent({
    required this.agentId,
    required this.role,
    required this.status,
    this.model = 'ollama/llama3.2',
    this.costToday = 0.0,
    this.fullTitle = '',
    this.currentTask = 'Idle or awaiting delegation',
    this.tokensUsed = 0,
    this.skills = const [],
    this.communicationStyle = 'executive',
  });

  factory Agent.fromJson(Map<String, dynamic> json) {
    final rawId = (json['agent_id'] ?? json['agentId'] ?? json['id'] ?? '').toString();
    final rawRole = (json['role'] ?? rawId).toString();
    final rawTitle = (json['full_title'] ?? json['fullTitle'] ?? rawRole).toString();

    return Agent(
      agentId: rawId,
      role: rawRole,
      status: (json['status'] ?? 'active').toString(),
      model: (json['model'] ?? json['loaded_model'] ?? json['assigned_model'] ?? 'ollama/llama3.2').toString(),
      costToday: (json['cost_today'] ?? json['costToday'] as num?)?.toDouble() ?? 0.0,
      fullTitle: rawTitle,
      currentTask: (json['current_task'] ?? json['currentTask'] ?? 'Idle or awaiting delegation').toString(),
      tokensUsed: (json['tokens_used'] ?? json['tokensUsed'] as num?)?.toInt() ?? 0,
      skills: (json['skills'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      communicationStyle: (json['communication_style'] ?? 'executive').toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'agent_id': agentId,
        'agentId': agentId,
        'role': role,
        'status': status,
        'model': model,
        'cost_today': costToday,
        'costToday': costToday,
        'full_title': fullTitle,
        'current_task': currentTask,
        'tokens_used': tokensUsed,
        'skills': skills,
        'communication_style': communicationStyle,
      };

  Agent copyWith({
    String? agentId,
    String? role,
    String? status,
    String? model,
    double? costToday,
    String? fullTitle,
    String? currentTask,
    int? tokensUsed,
    List<String>? skills,
    String? communicationStyle,
  }) {
    return Agent(
      agentId: agentId ?? this.agentId,
      role: role ?? this.role,
      status: status ?? this.status,
      model: model ?? this.model,
      costToday: costToday ?? this.costToday,
      fullTitle: fullTitle ?? this.fullTitle,
      currentTask: currentTask ?? this.currentTask,
      tokensUsed: tokensUsed ?? this.tokensUsed,
      skills: skills ?? this.skills,
      communicationStyle: communicationStyle ?? this.communicationStyle,
    );
  }

  bool get isActive => status == 'active';
  bool get isIdle => status == 'idle' || currentTask.toLowerCase().contains('idle');
  bool get isAuditing => status == 'auditing';
  bool get isBlocked => status == 'blocked';
  String get formattedCost => '\$${costToday.toStringAsFixed(4)}';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Agent &&
          runtimeType == other.runtimeType &&
          agentId == other.agentId &&
          status == other.status &&
          costToday == other.costToday;

  @override
  int get hashCode => agentId.hashCode ^ status.hashCode ^ costToday.hashCode;

  @override
  String toString() =>
      'Agent(id: $agentId, role: $role, status: $status, model: $model, cost: $formattedCost)';
}
