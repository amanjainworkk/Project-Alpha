// Project Alpha Mobile APK — WebSocket Telemetry Service Architecture
// File Target: Alpha/apk/lib/services/websocket_service.dart
// Milestone 10: Features 67, 69

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

import '../models/models.dart';

// ============================================================================
// 1. Connection State Enumeration & Types
// ============================================================================

/// Connection states for the Alpha real-time telemetry pipeline.
enum WebSocketConnectionState {
  disconnected,
  connecting,
  connected,
  reconnecting,
}

/// Function signature for injectable WebSocketChannel instantiation (enables hermetic testing).
typedef WebSocketChannelFactory = WebSocketChannel Function(Uri uri);

// ============================================================================
// 2. AlphaWebSocketService Implementation
// ============================================================================

class AlphaWebSocketService {
  /// Default WebSocket endpoint path.
  static const String defaultPath = '/ws';

  /// Initial reconnect backoff delay in seconds (1s, 2s, 4s, 8s...).
  static const Duration defaultInitialRetryDelay = Duration(seconds: 1);

  /// Maximum reconnect backoff delay cap.
  static const Duration defaultMaxRetryDelay = Duration(seconds: 30);

  /// Desktop backend host and port (e.g. "10.0.2.2:8765" or "127.0.0.1:8765").
  final String host;

  /// Bearer token for query-based WebSocket handshake authentication.
  String? token;

  /// Injectable WebSocketChannel factory for mock channel injection during tests.
  final WebSocketChannelFactory _channelFactory;

  /// Initial retry delay before exponential backoff.
  final Duration initialRetryDelay;

  /// Maximum backoff cap for reconnect attempts.
  final Duration maxRetryDelay;

  // --------------------------------------------------------------------------
  // Internal State
  // --------------------------------------------------------------------------
  WebSocketChannel? _channel;
  StreamSubscription? _channelSubscription;
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;

  Duration _currentRetryDelay;
  bool _manuallyDisconnected = false;
  bool _isDisposed = false;
  WebSocketConnectionState _connectionState = WebSocketConnectionState.disconnected;

  /// Last recorded server heartbeat or pong timestamp.
  DateTime? _lastHeartbeat;

  /// Active project subscriptions to automatically re-subscribe upon reconnect.
  final Set<String> _subscribedProjects = <String>{};

  // --------------------------------------------------------------------------
  // Stream Controllers
  // --------------------------------------------------------------------------
  final StreamController<WebSocketEnvelope> _envelopeController =
      StreamController<WebSocketEnvelope>.broadcast();

  final StreamController<WebSocketConnectionState> _connectionStateController =
      StreamController<WebSocketConnectionState>.broadcast();

  AlphaWebSocketService({
    String? host,
    this.token,
    WebSocketChannelFactory? channelFactory,
    Duration? initialRetryDelay,
    Duration? maxRetryDelay,
  })  : host = _normalizeHost(host ?? '10.0.2.2:8765'),
        _channelFactory = channelFactory ?? ((uri) => WebSocketChannel.connect(uri)),
        initialRetryDelay = initialRetryDelay ?? defaultInitialRetryDelay,
        maxRetryDelay = maxRetryDelay ?? defaultMaxRetryDelay,
        _currentRetryDelay = initialRetryDelay ?? defaultInitialRetryDelay;

  /// Factory constructor configuring service from an existing REST API base URL.
  factory AlphaWebSocketService.fromBaseUrl(
    String baseUrl, {
    String? token,
    WebSocketChannelFactory? channelFactory,
  }) {
    final uri = Uri.parse(baseUrl);
    final hostStr = uri.hasPort ? '${uri.host}:${uri.port}' : uri.host;
    return AlphaWebSocketService(
      host: hostStr,
      token: token,
      channelFactory: channelFactory,
    );
  }

  /// Strips protocol schemes and trailing slashes to isolate host:port.
  static String _normalizeHost(String rawHost) {
    var clean = rawHost.trim();
    if (clean.startsWith('ws://') || clean.startsWith('http://')) {
      clean = clean.substring(clean.indexOf('://') + 3);
    } else if (clean.startsWith('wss://') || clean.startsWith('https://')) {
      clean = clean.substring(clean.indexOf('://') + 3);
    }
    while (clean.endsWith('/')) {
      clean = clean.substring(0, clean.length - 1);
    }
    return clean;
  }

  // ==========================================================================
  // 3. Public Getters & Observables
  // ==========================================================================

  /// Current connection state.
  WebSocketConnectionState get connectionState => _connectionState;

  /// Whether the WebSocket is actively connected.
  bool get isConnected => _connectionState == WebSocketConnectionState.connected;

  /// Last server timestamp or heartbeat received.
  DateTime? get lastHeartbeat => _lastHeartbeat;

  /// Observable stream of connection state changes.
  Stream<WebSocketConnectionState> get connectionStateStream =>
      _connectionStateController.stream;

  /// Broadcast stream of all incoming raw WebSocketEnvelope payloads.
  Stream<WebSocketEnvelope> get onEnvelope => _envelopeController.stream;

  // --------------------------------------------------------------------------
  // Typed Event Filtering Streams
  // --------------------------------------------------------------------------

  /// Typed stream of executive agent status changes (event: 'agent_status_change').
  Stream<Map<String, dynamic>> get onAgentActivity {
    return _envelopeController.stream
        .where((env) => env.event == 'agent_status_change')
        .map((env) => env.data);
  }

  /// Typed stream of granular task progress updates (event: 'task_progress_update').
  Stream<TaskProgress> get onTaskProgress {
    return _envelopeController.stream
        .where((env) => env.event == 'task_progress_update')
        .map((env) => TaskProgress.fromJson(env.data));
  }

  /// Typed stream of Archify+ animated canvas spline pulses (event: 'node_flow_pulse').
  Stream<Map<String, dynamic>> get onGraphUpdate {
    return _envelopeController.stream
        .where((env) => env.event == 'node_flow_pulse')
        .map((env) => env.data);
  }

  /// Typed stream of Dual CAO audit updates and Founder escalations (event: 'audit_status_update').
  Stream<Map<String, dynamic>> get onAuditEvent {
    return _envelopeController.stream
        .where((env) => env.event == 'audit_status_update')
        .map((env) => env.data);
  }

  /// Typed stream of project state changes and thread messages (events: 'project_state_change', 'thread_message').
  Stream<Map<String, dynamic>> get onThreadMessage {
    return _envelopeController.stream
        .where((env) => env.event == 'thread_message' || env.event == 'project_state_change')
        .map((env) => env.data);
  }

  /// Typed stream of system telemetry heartbeats and server metrics (event: 'telemetry_heartbeat').
  Stream<Map<String, dynamic>> get onSystemMetric {
    return _envelopeController.stream
        .where((env) => env.event == 'telemetry_heartbeat')
        .map((env) => env.data);
  }

  // ==========================================================================
  // 4. Connection Lifecycle & Reconnect Engine
  // ==========================================================================

  /// Compute the full WebSocket handshake URI including authentication token.
  Uri get uri {
    final queryParams = <String, String>{};
    if (token != null && token!.trim().isNotEmpty) {
      queryParams['token'] = token!.trim();
    }
    return Uri(
      scheme: 'ws',
      host: host.contains(':') ? host.split(':')[0] : host,
      port: host.contains(':') ? int.tryParse(host.split(':')[1]) : 8765,
      path: defaultPath,
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );
  }

  /// Connect to the Project Alpha WebSocket telemetry stream.
  Future<void> connect() async {
    if (_isDisposed) return;
    if (_connectionState == WebSocketConnectionState.connected ||
        _connectionState == WebSocketConnectionState.connecting) {
      return;
    }

    _manuallyDisconnected = false;
    _setConnectionState(WebSocketConnectionState.connecting);

    try {
      final wsUri = uri;
      _channel = _channelFactory(wsUri);

      _channelSubscription = _channel!.stream.listen(
        _handleIncomingMessage,
        onError: _handleSocketError,
        onDone: _handleSocketDone,
        cancelOnError: false,
      );

      // Connected successfully
      _setConnectionState(WebSocketConnectionState.connected);
      _currentRetryDelay = initialRetryDelay; // Reset backoff delay

      // Re-subscribe to any active project subscriptions
      _reapplySubscriptions();

      // Start client ping keepalive timer (every 30 seconds)
      _startHeartbeatTimer();
    } catch (e) {
      _handleSocketError(e);
    }
  }

  /// Process inbound text frame from desktop backend.
  void _handleIncomingMessage(dynamic rawData) {
    if (_isDisposed) return;

    try {
      final String text = rawData is String ? rawData : utf8.decode(rawData as List<int>);
      final dynamic decoded = jsonDecode(text);

      if (decoded is! Map<String, dynamic>) return;

      final envelope = WebSocketEnvelope.fromJson(decoded);

      // Process protocol messages internally
      if (envelope.event == 'pong' || envelope.event == 'telemetry_heartbeat') {
        _lastHeartbeat = DateTime.now();
      }

      // Dispatch to public envelope stream
      if (!_envelopeController.isClosed) {
        _envelopeController.add(envelope);
      }
    } catch (e) {
      // Ignore malformed text or partial chunks
    }
  }

  /// Handle socket-level connection errors.
  void _handleSocketError(dynamic error) {
    _cleanupChannel();
    _scheduleReconnect();
  }

  /// Handle server-initiated connection close.
  void _handleSocketDone() {
    _cleanupChannel();
    if (!_manuallyDisconnected && !_isDisposed) {
      _scheduleReconnect();
    } else {
      _setConnectionState(WebSocketConnectionState.disconnected);
    }
  }

  /// Schedule next reconnect attempt with exponential backoff.
  void _scheduleReconnect() {
    if (_manuallyDisconnected || _isDisposed) {
      _setConnectionState(WebSocketConnectionState.disconnected);
      return;
    }

    _setConnectionState(WebSocketConnectionState.reconnecting);

    _reconnectTimer?.cancel();
    final delay = _currentRetryDelay;

    // Double the backoff delay capped at maxRetryDelay
    final nextDelayMs = math.min(
      _currentRetryDelay.inMilliseconds * 2,
      maxRetryDelay.inMilliseconds,
    );
    _currentRetryDelay = Duration(milliseconds: nextDelayMs);

    _reconnectTimer = Timer(delay, () {
      if (!_manuallyDisconnected && !_isDisposed) {
        connect();
      }
    });
  }

  /// Helper to safely transition connection state and emit notifications.
  void _setConnectionState(WebSocketConnectionState newState) {
    if (_connectionState == newState) return;
    _connectionState = newState;
    if (!_connectionStateController.isClosed) {
      _connectionStateController.add(newState);
    }
  }

  /// Helper to teardown channel subscription and socket resources.
  void _cleanupChannel() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;

    try {
      _channelSubscription?.cancel();
    } catch (_) {}
    _channelSubscription = null;

    try {
      _channel?.sink.close(status.goingAway);
    } catch (_) {}
    _channel = null;
  }

  // ==========================================================================
  // 5. Client Outbound Directives
  // ==========================================================================

  /// Transmit an outbound JSON action to the backend ConnectionManager.
  void send(Map<String, dynamic> payload) {
    if (_channel != null && _connectionState == WebSocketConnectionState.connected) {
      try {
        _channel!.sink.add(jsonEncode(payload));
      } catch (e) {
        _handleSocketError(e);
      }
    }
  }

  /// Send ping keepalive request to verify network liveness.
  void sendPing() {
    send({
      'action': 'ping',
      'data': {'client_time': DateTime.now().toUtc().toIso8601String()},
    });
  }

  /// Subscribe to telemetry events filtered for a specific project ID.
  void subscribeProject(String projectId) {
    final cleanId = projectId.trim();
    if (cleanId.isEmpty) return;
    _subscribedProjects.add(cleanId);
    send({'action': 'subscribe', 'project_id': cleanId});
  }

  /// Unsubscribe from telemetry events for a specific project ID.
  void unsubscribeProject(String projectId) {
    final cleanId = projectId.trim();
    if (cleanId.isEmpty) return;
    _subscribedProjects.remove(cleanId);
    send({'action': 'unsubscribe', 'project_id': cleanId});
  }

  /// Re-issue active project subscriptions after a reconnection.
  void _reapplySubscriptions() {
    for (final pid in _subscribedProjects) {
      send({'action': 'subscribe', 'project_id': pid});
    }
  }

  /// Periodic ping keepalive runner.
  void _startHeartbeatTimer() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (isConnected) {
        sendPing();
      }
    });
  }

  // ==========================================================================
  // 6. Clean Disconnect & Disposal
  // ==========================================================================

  /// Explicitly disconnect from the WebSocket server without auto-reconnecting.
  void disconnect() {
    _manuallyDisconnected = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _cleanupChannel();
    _setConnectionState(WebSocketConnectionState.disconnected);
  }

  /// Permanently dispose all streams and timers.
  void dispose() {
    _isDisposed = true;
    disconnect();
    _envelopeController.close();
    _connectionStateController.close();
  }
}
