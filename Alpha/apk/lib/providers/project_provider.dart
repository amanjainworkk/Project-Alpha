// Alpha Mobile — Project State Provider
// Manages project list, selection, goal submissions, and real-time state sync

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../services/websocket_service.dart';

abstract class IProjectApiClient {
  Future<List<Project>> getProjects();
  Future<Map<String, dynamic>> getProject(String id);
  Future<Map<String, dynamic>> submitGoal({
    required String title,
    required String description,
    int? complexity,
    String priority,
  });
}

class ProjectProvider extends ChangeNotifier {
  final AlphaApiClient? _apiClient;
  final IProjectApiClient? _customClient;
  final AlphaWebSocketService? _wsService;
  StreamSubscription<WebSocketEnvelope>? _wsSubscription;

  List<Project> _projects = [];
  Project? _selectedProject;
  bool _isLoading = false;
  String? _errorMessage;
  String _filter = 'all'; // 'all', 'in_progress', 'completed', 'planning', 'blocked'

  ProjectProvider({
    AlphaApiClient? apiClient,
    AlphaWebSocketService? wsService,
    IProjectApiClient? customClient,
  })  : _apiClient = apiClient,
        _wsService = wsService,
        _customClient = customClient {
    if (_wsService != null) {
      _wsSubscription = _wsService?.onEnvelope.listen((env) {
        handleWebSocketEnvelope(env);
      });
    }
  }

  // Getters
  List<Project> get projects => List.unmodifiable(_projects);
  Project? get selectedProject => _selectedProject;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get hasError => _errorMessage != null;
  String get filter => _filter;

  List<Project> get filteredProjects {
    if (_filter == 'all') return List.unmodifiable(_projects);
    return List.unmodifiable(
      _projects.where((p) {
        if (_filter == 'completed') return p.isCompleted;
        if (_filter == 'in_progress') return p.isActive;
        if (_filter == 'planning') return p.isPlanning;
        if (_filter == 'blocked') return p.isBlocked;
        return p.status == _filter;
      }),
    );
  }

  int get totalCount => _projects.length;
  int get activeCount => _projects.where((p) => p.isActive).length;
  int get completedCount => _projects.where((p) => p.isCompleted).length;

  // Methods
  void setFilter(String filter) {
    if (_filter != filter) {
      _filter = filter;
      notifyListeners();
    }
  }

  void clearError() {
    if (_errorMessage != null) {
      _errorMessage = null;
      notifyListeners();
    }
  }

  /// Alias for fetchProjects to support standard UI lifecycle hooks
  Future<void> loadProjects() => fetchProjects();

  Future<void> fetchProjects([dynamic client]) async {
    final activeClient = client ?? _customClient ?? _apiClient;
    if (activeClient == null) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final List<Project> fetched = await activeClient.getProjects();
      _projects = fetched;
      if (_selectedProject != null) {
        final match = _projects.where((p) => p.id == _selectedProject!.id);
        if (match.isNotEmpty) {
          _selectedProject = match.first;
        }
      }
    } catch (e) {
      _errorMessage = 'Failed to fetch projects: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> selectProject(String projectId, [dynamic client]) async {
    final match = _projects.where((p) => p.id == projectId);
    if (match.isNotEmpty) {
      _selectedProject = match.first;
      notifyListeners();
    }

    final activeClient = client ?? _customClient ?? _apiClient;
    if (activeClient != null) {
      try {
        final Map<String, dynamic> detailMap = await activeClient.getProject(projectId);
        _selectedProject = Project.fromJson(detailMap);
        notifyListeners();
      } catch (e) {
        debugPrint('ProjectProvider: Detail fetch warning: $e');
      }
    }
  }

  Future<Project?> submitGoal({
    required String title,
    required String description,
    int? complexity,
    String priority = 'medium',
    dynamic client,
  }) async {
    final activeClient = client ?? _customClient ?? _apiClient;
    if (activeClient == null) {
      _errorMessage = 'API client unavailable for goal submission.';
      notifyListeners();
      return null;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final Map<String, dynamic> res = await activeClient.submitGoal(
        title: title,
        description: description,
        complexity: complexity,
        priority: priority,
      );

      final newProj = Project(
        id: (res['project_id'] ?? res['id'] ?? 'proj_${DateTime.now().millisecondsSinceEpoch}').toString(),
        title: title,
        description: description,
        status: (res['status'] ?? 'planning').toString(),
        progress: 0.0,
        priority: priority,
      );

      _projects.insert(0, newProj);
      _selectedProject = newProj;
      return newProj;
    } catch (e) {
      _errorMessage = 'Failed to submit goal: $e';
      return null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Handles real-time 'project_state_change' events
  void handleProjectStateChange(Map<String, dynamic> data) {
    final pid = (data['project_id'] ?? data['id'] ?? '').toString();
    if (pid.isEmpty) return;

    final index = _projects.indexWhere((p) => p.id == pid);
    final newStatus = (data['status'] ?? data['new_state'] ?? 'active').toString();
    final newProgress = (data['progress'] as num?)?.toDouble();
    final title = data['title']?.toString();

    if (index != -1) {
      final existing = _projects[index];
      _projects[index] = existing.copyWith(
        status: newStatus,
        progress: newProgress ?? existing.progress,
        title: title ?? existing.title,
      );
      if (_selectedProject?.id == pid) {
        _selectedProject = _projects[index];
      }
    } else if (title != null && title.isNotEmpty) {
      final created = Project(
        id: pid,
        title: title,
        description: '',
        status: newStatus,
        progress: newProgress ?? 0.0,
      );
      _projects.insert(0, created);
    }
    notifyListeners();
  }

  void handleWebSocketEnvelope(WebSocketEnvelope envelope) {
    if (envelope.isProjectState) {
      handleProjectStateChange(envelope.data);
    }
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}
