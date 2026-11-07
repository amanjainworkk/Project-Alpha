// Alpha Mobile — TaskProgress Data Model
// Conforms to PROJECT.md Feature 67, Task 10, and unit test ASCII progress bar rendering

class TaskProgress {
  final String taskId;
  final String taskName;
  final int progressPercent;
  final String currentStep;
  final String assignedAgent;
  final String status; // 'running', 'auditing', 'blocked', 'done', 'failed'

  TaskProgress({
    required this.taskId,
    required this.taskName,
    required this.progressPercent,
    required this.currentStep,
    required this.assignedAgent,
    required this.status,
  });

  factory TaskProgress.fromJson(Map<String, dynamic> json) {
    return TaskProgress(
      taskId: (json['task_id'] ?? json['taskId'] ?? '').toString(),
      taskName: (json['task_name'] ?? json['taskName'] ?? '').toString(),
      progressPercent: (json['progress_percent'] ?? json['progressPercent'] as num?)?.toInt() ?? 0,
      currentStep: (json['current_step'] ?? json['currentStep'] ?? '').toString(),
      assignedAgent: (json['assigned_agent'] ?? json['assignedAgent'] ?? '').toString(),
      status: (json['status'] ?? 'running').toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'task_id': taskId,
        'taskId': taskId,
        'task_name': taskName,
        'taskName': taskName,
        'progress_percent': progressPercent,
        'progressPercent': progressPercent,
        'current_step': currentStep,
        'currentStep': currentStep,
        'assigned_agent': assignedAgent,
        'assignedAgent': assignedAgent,
        'status': status,
      };

  /// Renders ASCII progress bar conforming to [api_and_models_test.dart]
  /// Example: [████████░░] 80%
  String formatProgressBar() {
    final int clamped = progressPercent.clamp(0, 100);
    final int filled = (clamped / 10).round().clamp(0, 10);
    final int empty = (10 - filled).clamp(0, 10);
    return '[${'█' * filled}${'░' * empty}] $clamped%';
  }

  double get progressFraction => (progressPercent / 100.0).clamp(0.0, 1.0);
  bool get isDone => status == 'done' || status == 'completed' || progressPercent >= 100;
  bool get isRunning => status == 'running';
  bool get isAuditing => status == 'auditing';
  bool get isBlocked => status == 'blocked';
  bool get isFailed => status == 'failed';

  TaskProgress copyWith({
    String? taskId,
    String? taskName,
    int? progressPercent,
    String? currentStep,
    String? assignedAgent,
    String? status,
  }) {
    return TaskProgress(
      taskId: taskId ?? this.taskId,
      taskName: taskName ?? this.taskName,
      progressPercent: progressPercent ?? this.progressPercent,
      currentStep: currentStep ?? this.currentStep,
      assignedAgent: assignedAgent ?? this.assignedAgent,
      status: status ?? this.status,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TaskProgress &&
          runtimeType == other.runtimeType &&
          taskId == other.taskId &&
          progressPercent == other.progressPercent &&
          status == other.status;

  @override
  int get hashCode => taskId.hashCode ^ progressPercent.hashCode ^ status.hashCode;

  @override
  String toString() =>
      'TaskProgress(id: $taskId, name: $taskName, progress: $progressPercent%, status: $status)';
}
