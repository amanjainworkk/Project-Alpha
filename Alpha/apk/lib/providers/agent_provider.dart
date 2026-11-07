// Alpha Mobile — Agent State Provider
// Manages 13 executive C-suite agent states, costs, models, and real-time boardroom telemetry

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../services/websocket_service.dart';

abstract class IAgentApiClient {
  Future<List<Agent>> getAgents();
  Future<Map<String, dynamic>> getAgent(String id);
}

class AgentProvider extends ChangeNotifier {
  final AlphaApiClient? _apiClient;
  final IAgentApiClient? _customClient;
  final AlphaWebSocketService? _wsService;
  StreamSubscription<WebSocketEnvelope>? _wsSubscription;

  final Map<String, Agent> _agents = {};

  bool _isLoading = false;
  String? _errorMessage;
  Agent? _selectedAgent;

  AgentProvider({
    AlphaApiClient? apiClient,
    AlphaWebSocketService? wsService,
    IAgentApiClient? customClient,
  })  : _apiClient = apiClient,
        _wsService = wsService,
        _customClient = customClient {
    _initDefaultRoster();
    if (_wsService != null) {
      _wsSubscription = _wsService?.onEnvelope.listen((env) {
        handleWebSocketEnvelope(env);
      });
    }
  }

  /// Pre-populates the 13 C-Suite Executive Roster per PROJECT.md
  void _initDefaultRoster() {
    final roster = [
      Agent(agentId: 'CEO', role: 'Chief Executive Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Executive Officer'),
      Agent(agentId: 'CTO', role: 'Chief Technology Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Technology Officer'),
      Agent(agentId: 'CMO', role: 'Chief Marketing Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Marketing Officer'),
      Agent(agentId: 'CPO', role: 'Chief Product Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Product Officer'),
      Agent(agentId: 'CDO', role: 'Chief Design Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Design Officer'),
      Agent(agentId: 'CFO', role: 'Chief Financial Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Financial Officer'),
      Agent(agentId: 'COO', role: 'Chief Operations Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Operations Officer'),
      Agent(agentId: 'CHRO', role: 'Chief Human Resources Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Human Resources Officer'),
      Agent(agentId: 'CIO', role: 'Chief Information Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Information Officer'),
      Agent(agentId: 'CSO', role: 'Chief Strategy Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Strategy Officer'),
      Agent(agentId: 'CLO', role: 'Chief Legal Officer', status: 'active', model: 'ollama/llama3.2', fullTitle: 'Chief Legal Officer'),
      Agent(agentId: 'CAO-Claude', role: 'Chief Audit Officer (Claude)', status: 'active', model: 'claude-3-5-sonnet', fullTitle: 'Chief Audit Officer (Claude)'),
      Agent(agentId: 'CAO-ChatGPT', role: 'Chief Audit Officer (ChatGPT)', status: 'active', model: 'gpt-4o', fullTitle: 'Chief Audit Officer (ChatGPT)'),
    ];

    for (final a in roster) {
      _agents[a.agentId] = a;
    }
  }

  // Getters
  List<Agent> get allAgents => List.unmodifiable(_agents.values.toList());
  List<Agent> get activeAgents =>
      List.unmodifiable(_agents.values.where((a) => a.isActive).toList());
  List<Agent> get idleAgents =>
      List.unmodifiable(_agents.values.where((a) => a.isIdle).toList());
  Agent? get selectedAgent => _selectedAgent;
  int get totalCount => _agents.length;
  int get activeCount => activeAgents.length;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  double get totalCostToday =>
      _agents.values.fold(0.0, (sum, a) => sum + a.costToday);

  int get totalTokensToday =>
      _agents.values.fold(0, (sum, a) => sum + a.tokensUsed);

  String get formattedTotalCost => '\$${totalCostToday.toStringAsFixed(4)}';

  Agent? getAgent(String agentId) {
    if (_agents.containsKey(agentId)) return _agents[agentId];
    for (final entry in _agents.entries) {
      if (entry.key.toLowerCase() == agentId.toLowerCase()) return entry.value;
    }
    return null;
  }

  void selectAgent(String agentId) {
    _selectedAgent = getAgent(agentId);
    notifyListeners();
  }

  /// Alias for fetchAgents to support standard UI lifecycle hooks
  Future<void> loadAgents() => fetchAgents();

  Future<void> fetchAgents([dynamic client]) async {
    final activeClient = client ?? _customClient ?? _apiClient;
    if (activeClient == null) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final List<Agent> fetchedList = await activeClient.getAgents();
      for (final agent in fetchedList) {
        _agents[agent.agentId] = agent;
      }
      if (_selectedAgent != null) {
        _selectedAgent = _agents[_selectedAgent!.agentId];
      }
    } catch (e) {
      _errorMessage = 'Failed to fetch agents: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Handles real-time 'agent_status_change' events
  void handleAgentStatusChange(Map<String, dynamic> data) {
    final agentId = (data['agent_id'] ?? data['agentId'] ?? '').toString();
    if (agentId.isEmpty) return;

    final existing = getAgent(agentId);
    final newStatus = (data['new_status'] ?? data['status'] ?? 'active').toString();
    final currentTask = data['current_task']?.toString();
    final modelUsed = data['model_used']?.toString();
    final tokensUsed = (data['tokens_used'] as num?)?.toInt();

    if (existing != null) {
      _agents[existing.agentId] = existing.copyWith(
        status: newStatus,
        currentTask: currentTask ?? existing.currentTask,
        model: modelUsed ?? existing.model,
        tokensUsed: tokensUsed != null
            ? existing.tokensUsed + tokensUsed
            : existing.tokensUsed,
      );
      if (_selectedAgent?.agentId == existing.agentId) {
        _selectedAgent = _agents[existing.agentId];
      }
    } else {
      _agents[agentId] = Agent.fromJson(data);
    }
    notifyListeners();
  }

  void handleWebSocketEnvelope(WebSocketEnvelope envelope) {
    if (envelope.isAgentStatus) {
      handleAgentStatusChange(envelope.data);
    }
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}
