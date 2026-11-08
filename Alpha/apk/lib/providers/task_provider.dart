// Alpha Mobile — Task State Provider
// Manages granular task progress, ASCII bars, checklists, and execution logs

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/websocket_service.dart';

class TaskProvider extends ChangeNotifier {
  final AlphaWebSocketService? _wsService;
  StreamSubscription<WebSocketEnvelope>? _wsSubscription;

  final Map<String, TaskProgress> _tasks = {};
  final List<String> _executionLogs = [];
  String _statusFilter = 'all'; // 'all', 'running', 'auditing', 'blocked', 'done'
  String? _selectedTaskId;

  TaskProvider({AlphaWebSocketService? wsService}) : _wsService = wsService {
    if (_wsService != null) {
      _wsSubscription = _wsService?.onEnvelope.listen((env) {
        handleWebSocketEnvelope(env);
      });
    }
  }

  // Getters
  List<TaskProgress> get allTasks => List.unmodifiable(_tasks.values.toList());

  List<TaskProgress> get filteredTasks {
    if (_statusFilter == 'all') return List.unmodifiable(_tasks.values.toList());
    return List.unmodifiable(_tasks.values.where((t) {
      if (_statusFilter == 'running') return t.isRunning;
      if (_statusFilter == 'auditing') return t.isAuditing;
      if (_statusFilter == 'blocked') return t.isBlocked;
      if (_statusFilter == 'done') return t.isDone;
      return t.status == _statusFilter;
    }).toList());
  }

  List<TaskProgress> get runningTasks =>
      List.unmodifiable(_tasks.values.where((t) => t.isRunning).toList());
  List<TaskProgress> get auditingTasks =>
      List.unmodifiable(_tasks.values.where((t) => t.isAuditing).toList());
  List<TaskProgress> get blockedTasks =>
      List.unmodifiable(_tasks.values.where((t) => t.isBlocked).toList());
  List<TaskProgress> get doneTasks =>
      List.unmodifiable(_tasks.values.where((t) => t.isDone).toList());

  List<String> get executionLogs => List.unmodifiable(_executionLogs);
  TaskProgress? get selectedTask => _selectedTaskId != null ? _tasks[_selectedTaskId] : null;

  int get totalCount => _tasks.length;
  int get runningCount => runningTasks.length;
  int get blockedCount => blockedTasks.length;
  int get doneCount => doneTasks.length;

  double get overallProgress {
    if (_tasks.isEmpty) return 0.0;
    final total = _tasks.values.fold<int>(0, (sum, t) => sum + t.progressPercent);
    return (total / (_tasks.length * 100.0)).clamp(0.0, 1.0);
  }

  void setStatusFilter(String filter) {
    if (_statusFilter != filter) {
      _statusFilter = filter;
      notifyListeners();
    }
  }

  void selectTask(String? taskId) {
    _selectedTaskId = taskId;
    notifyListeners();
  }

  void addLog(String message) {
    final timestamp = DateTime.now().toIso8601String().substring(11, 19);
    _executionLogs.insert(0, '[$timestamp] $message');
    if (_executionLogs.length > 200) {
      _executionLogs.removeLast();
    }
    notifyListeners();
  }

  void updateTask(TaskProgress task) {
    _tasks[task.taskId] = task;
    addLog('[${task.assignedAgent}] ${task.taskName}: ${task.currentStep} (${task.progressPercent}%)');
    notifyListeners();
  }

  void clearSeedTasks() {
    bool removed = false;
    for (final id in ['task_001', 'task_002', 'task_003', 'task_004']) {
      if (_tasks.containsKey(id)) {
        _tasks.remove(id);
        removed = true;
      }
    }
    if (removed) {
      notifyListeners();
    }
  }

  /// Handles real-time 'task_progress_update' events
  void handleTaskProgressUpdate(Map<String, dynamic> data) {
    final task = TaskProgress.fromJson(data);
    if (!task.taskId.startsWith('task_00')) {
      clearSeedTasks();
    }
    _tasks[task.taskId] = task;
    addLog('[${task.assignedAgent}] ${task.taskName.isNotEmpty ? task.taskName : task.taskId}: ${task.currentStep} (${task.progressPercent}%)');
    notifyListeners();
  }

  void handleWebSocketEnvelope(WebSocketEnvelope envelope) {
    if (envelope.isTaskProgress) {
      handleTaskProgressUpdate(envelope.data);
    }
  }

  void clearTasks() {
    _tasks.clear();
    notifyListeners();
  }

  void clearLogs() {
    _executionLogs.clear();
    notifyListeners();
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}
