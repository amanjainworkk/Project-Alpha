// Alpha Mobile — Connection State Provider
// Tracks desktop backend health, connection state, latency, and system heartbeats

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_client.dart';
import '../services/websocket_service.dart';

enum ConnectionStatus {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

abstract class IHealthApiClient {
  Future<bool> checkHealth();
}

class ConnectionProvider extends ChangeNotifier {
  final AlphaApiClient? _apiClient;
  final IHealthApiClient? _healthClient;
  final AlphaWebSocketService? _wsService;
  StreamSubscription<WebSocketConnectionState>? _wsStateSubscription;
  StreamSubscription<WebSocketEnvelope>? _wsEnvelopeSubscription;

  ConnectionStatus _status = ConnectionStatus.disconnected;
  String _backendBaseUrl = 'http://10.0.2.2:8765';
  String _websocketUrl = 'ws://10.0.2.2:8765/ws';
  int _latencyMs = 0;
  DateTime? _lastHeartbeatTime;
  double _serverUptimeSeconds = 0.0;
  int _serverActiveAgents = 13;
  int _serverActiveTasks = 0;
  double _serverMemoryMb = 0.0;
  double _serverCpuPercent = 0.0;
  String? _lastError;
  bool _isBackendReachable = false;

  ConnectionProvider({
    AlphaApiClient? apiClient,
    AlphaWebSocketService? wsService,
    IHealthApiClient? healthClient,
  })  : _apiClient = apiClient,
        _wsService = wsService,
        _healthClient = healthClient;

  // Getters
  ConnectionStatus get status => _status;
  bool get isConnected => _status == ConnectionStatus.connected;
  bool get isConnecting =>
      _status == ConnectionStatus.connecting || _status == ConnectionStatus.reconnecting;
  bool get isDisconnected => _status == ConnectionStatus.disconnected;
  bool get hasError => _status == ConnectionStatus.error || _lastError != null;

  int get latencyMs => _latencyMs;
  DateTime? get lastHeartbeatTime => _lastHeartbeatTime;
  double get serverUptimeSeconds => _serverUptimeSeconds;
  int get serverActiveAgents => _serverActiveAgents;
  int get serverActiveTasks => _serverActiveTasks;
  double get serverMemoryMb => _serverMemoryMb;
  double get serverCpuPercent => _serverCpuPercent;
  String? get lastError => _lastError;
  bool get isBackendReachable => _isBackendReachable;
  String get backendBaseUrl => _backendBaseUrl;
  String get websocketUrl => _websocketUrl;
  String get latencyDisplay => '${_latencyMs}ms';

  // State mutations
  void setStatus(ConnectionStatus newStatus) {
    if (_status != newStatus) {
      _status = newStatus;
      notifyListeners();
    }
  }

  void updateEndpoints({required String baseUrl, required String wsUrl}) {
    _backendBaseUrl = baseUrl;
    _websocketUrl = wsUrl;
    _apiClient?.updateBaseUrl(baseUrl);
    _wsService?.updateHost(wsUrl);
    notifyListeners();
  }

  void updateLatency(int ms) {
    _latencyMs = ms;
    notifyListeners();
  }

  void recordError(String error) {
    _lastError = error;
    _status = ConnectionStatus.error;
    notifyListeners();
  }

  void clearError() {
    _lastError = null;
    notifyListeners();
  }

  Future<void> initialize() async {
    if (_wsService != null) {
      _wsStateSubscription = _wsService?.connectionStateStream.listen((state) {
        switch (state) {
          case WebSocketConnectionState.connected:
            setStatus(ConnectionStatus.connected);
            break;
          case WebSocketConnectionState.connecting:
            setStatus(ConnectionStatus.connecting);
            break;
          case WebSocketConnectionState.reconnecting:
            setStatus(ConnectionStatus.reconnecting);
            break;
          case WebSocketConnectionState.disconnected:
            setStatus(ConnectionStatus.disconnected);
            break;
        }
      });

      _wsEnvelopeSubscription = _wsService?.onEnvelope.listen((envelope) {
        handleWebSocketEnvelope(envelope);
      });
    }
    await checkHealth();
  }

  /// Handles real-time 'telemetry_heartbeat' events
  void handleHeartbeat(Map<String, dynamic> data) {
    _lastHeartbeatTime = DateTime.now();
    _serverUptimeSeconds = (data['uptime_seconds'] as num?)?.toDouble() ?? 0.0;
    _serverActiveAgents = (data['active_agents'] as num?)?.toInt() ?? 13;
    _serverActiveTasks = (data['active_tasks'] as num?)?.toInt() ?? 0;
    _serverMemoryMb = (data['memory_mb'] as num?)?.toDouble() ?? 0.0;
    _serverCpuPercent = (data['cpu_percent'] as num?)?.toDouble() ?? 0.0;
    _isBackendReachable = true;

    if (_status != ConnectionStatus.connected) {
      _status = ConnectionStatus.connected;
    }
    notifyListeners();
  }

  void handleWebSocketEnvelope(WebSocketEnvelope envelope) {
    if (envelope.isHeartbeat) {
      handleHeartbeat(envelope.data);
    } else if (envelope.isConnected) {
      setStatus(ConnectionStatus.connected);
    }
  }

  Future<bool> checkHealth([dynamic client]) async {
    final activeClient = client ?? _healthClient ?? _apiClient;
    if (activeClient == null) return false;

    final stopwatch = Stopwatch()..start();
    try {
      final healthy = await activeClient.checkHealth();
      stopwatch.stop();
      _latencyMs = stopwatch.elapsedMilliseconds;
      _isBackendReachable = healthy;
      if (healthy && _status != ConnectionStatus.connected) {
        _status = ConnectionStatus.connected;
      }
      clearError();
      notifyListeners();
      return healthy;
    } catch (e) {
      stopwatch.stop();
      _isBackendReachable = false;
      recordError('Health check failure: $e');
      return false;
    }
  }

  @override
  void dispose() {
    _wsStateSubscription?.cancel();
    _wsEnvelopeSubscription?.cancel();
    super.dispose();
  }
}
