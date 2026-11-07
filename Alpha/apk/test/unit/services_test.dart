// Project Alpha Mobile APK — Services Master Unit Test Suite
// File Target: Alpha/apk/test/unit/services_test.dart
// Milestone 10: Features 68, 69

import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

// Import genuine services and models
import '../../lib/services/services.dart';
import '../../lib/models/models.dart';

// ============================================================================
// Hermetic Test Doubles (FakeHttpClient and FakeWebSocketChannel)
// ============================================================================

/// In-memory fake HTTP client allowing deterministic request matching and response synthesis.
class FakeHttpClient extends http.BaseClient {
  Future<http.Response> Function(http.BaseRequest request) handler;
  final List<http.BaseRequest> interceptedRequests = [];

  FakeHttpClient(this.handler);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    interceptedRequests.add(request);
    final response = await handler(request);
    return http.StreamedResponse(
      Stream.value(response.bodyBytes),
      response.statusCode,
      headers: response.headers,
      request: request,
    );
  }
}

/// Fake WebSocket sink capturing outbound client messages.
class FakeWebSocketSink implements WebSocketSink {
  final List<String> sentMessages = [];
  bool isClosed = false;
  int? closeCode;
  String? closeReason;

  @override
  void add(dynamic data) {
    if (isClosed) throw StateError('Cannot add to closed sink');
    sentMessages.add(data.toString());
  }

  @override
  void addError(Object error, [StackTrace? stackTrace]) {}

  @override
  Future addStream(Stream<dynamic> stream) async {
    await for (final data in stream) {
      add(data);
    }
  }

  @override
  Future close([int? closeCode, String? closeReason]) async {
    isClosed = true;
    this.closeCode = closeCode;
    this.closeReason = closeReason;
  }

  @override
  Future get done => Future.value();
}

/// Fake WebSocket channel providing controllable incoming stream and message inspection.
class FakeWebSocketChannel implements WebSocketChannel {
  final StreamController<dynamic> incomingController = StreamController<dynamic>.broadcast();
  final FakeWebSocketSink fakeSink = FakeWebSocketSink();

  @override
  Stream get stream => incomingController.stream;

  @override
  WebSocketSink get sink => fakeSink;

  @override
  String? get protocol => 'alpha-telemetry';

  @override
  int? get closeCode => fakeSink.closeCode;

  @override
  String? get closeReason => fakeSink.closeReason;

  void emitText(String text) {
    incomingController.add(text);
  }

  void emitEnvelope(String event, Map<String, dynamic> data) {
    emitText(jsonEncode({
      'event': event,
      'data': data,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    }));
  }

  void emitError(Object error) {
    incomingController.addError(error);
  }

  void emitDone() {
    incomingController.close();
  }
}

// ============================================================================
// Main Test Runner
// ============================================================================

void main() {
  group('AlphaApiClient — REST Communication & Error Resilience', () {
    test('Constructor normalizes trailing slashes and sets default host', () {
      final client = AlphaApiClient(baseUrl: 'http://10.0.2.2:8765///');
      expect(client.baseUrl, equals('http://10.0.2.2:8765'));

      final localhostClient = AlphaApiClient.localhost();
      expect(localhostClient.baseUrl, equals('http://127.0.0.1:8765'));

      final lanClient = AlphaApiClient.lan('192.168.1.100', port: 8765);
      expect(lanClient.baseUrl, equals('http://192.168.1.100:8765'));
    });

    test('checkHealth returns true on 200 OK healthy probe', () async {
      final fakeClient = FakeHttpClient((request) async {
        expect(request.url.path, equals('/health'));
        return http.Response(jsonEncode({'status': 'healthy', 'version': '1.0.0'}), 200);
      });

      final apiClient = AlphaApiClient(
        baseUrl: 'http://10.0.2.2:8765',
        client: fakeClient,
      );

      final healthy = await apiClient.checkHealth();
      expect(healthy, isTrue);
      expect(fakeClient.interceptedRequests.length, equals(1));
    });

    test('checkHealth returns false on 503 backend error without throwing', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(jsonEncode({'error': 'Vault unavailable'}), 503);
      });

      final apiClient = AlphaApiClient(
        baseUrl: 'http://10.0.2.2:8765',
        client: fakeClient,
      );

      final healthy = await apiClient.checkHealth();
      expect(healthy, isFalse);
    });

    test('getProjects serializes Authorization header and parses Project list', () async {
      final fakeClient = FakeHttpClient((request) async {
        expect(request.headers['authorization'], equals('Bearer test_token_xyz'));
        expect(request.headers['content-type'], contains('application/json'));

        final sampleProjects = [
          {
            'project_id': 'proj_alpha_01',
            'title': 'AI Voice Agent',
            'description': 'Real-time duplex voice conversational bot',
            'status': 'in_progress',
            'progress': 0.65,
          },
          {
            'project_id': 'proj_alpha_02',
            'title': 'Vault Indexer',
            'description': 'Vector embedding pipeline',
            'status': 'planning',
            'progress': 0.10,
          }
        ];
        return http.Response(jsonEncode(sampleProjects), 200);
      });

      final apiClient = AlphaApiClient(
        baseUrl: 'http://10.0.2.2:8765',
        token: 'test_token_xyz',
        client: fakeClient,
      );

      final projects = await apiClient.getProjects();
      expect(projects.length, equals(2));
      expect(projects[0].id, equals('proj_alpha_01'));
      expect(projects[0].title, equals('AI Voice Agent'));
      expect(projects[0].progress, equals(0.65));
      expect(projects[1].id, equals('proj_alpha_02'));
    });

    test('submitGoal posts directive and receives project_id and status', () async {
      final fakeClient = FakeHttpClient((request) async {
        expect(request.method, equals('POST'));
        expect(request.url.path, equals('/api/goals'));

        final bodyText = (request as http.Request).body;
        final decodedBody = jsonDecode(bodyText) as Map<String, dynamic>;
        expect(decodedBody['title'], equals('Build Mobile App'));
        expect(decodedBody['priority'], equals('high'));

        return http.Response(
          jsonEncode({
            'project_id': 'proj_goal_999',
            'status': 'planning',
            'title': 'Build Mobile App',
            'executive_summary': 'Autonomous execution pipeline scheduled.',
          }),
          200,
        );
      });

      final apiClient = AlphaApiClient(
        baseUrl: 'http://10.0.2.2:8765',
        token: 'auth_token',
        client: fakeClient,
      );

      final res = await apiClient.submitGoal(
        title: 'Build Mobile App',
        description: 'Design and launch Flutter client',
        priority: 'high',
        complexity: 3,
      );

      expect(res['project_id'], equals('proj_goal_999'));
      expect(res['status'], equals('planning'));
    });

    test('getAgents fetches and deserializes executive agent list', () async {
      final fakeClient = FakeHttpClient((request) async {
        expect(request.url.path, equals('/api/agents'));

        final sampleAgents = [
          {
            'agent_id': 'CEO',
            'role': 'Chief Executive Officer',
            'status': 'active',
            'model': 'ollama/llama3.2',
            'cost_today': 0.045,
          },
          {
            'agent_id': 'CTO',
            'role': 'Chief Technology Officer',
            'status': 'active',
            'model': 'ollama/llama3.2',
            'cost_today': 0.082,
          }
        ];
        return http.Response(jsonEncode(sampleAgents), 200);
      });

      final apiClient = AlphaApiClient(client: fakeClient);
      final agents = await apiClient.getAgents();

      expect(agents.length, equals(2));
      expect(agents[0].agentId, equals('CEO'));
      expect(agents[0].costToday, equals(0.045));
      expect(agents[1].agentId, equals('CTO'));
    });

    test('readVault queries primary path and returns document map', () async {
      final fakeClient = FakeHttpClient((request) async {
        expect(request.url.path, equals('/api/vault/read'));
        expect(request.url.queryParameters['path'], equals('company/identity.json'));

        return http.Response(
          jsonEncode({
            'company_name': 'Project Alpha Inc',
            'mission': 'Master AI systems',
          }),
          200,
        );
      });

      final apiClient = AlphaApiClient(client: fakeClient);
      final doc = await apiClient.readVault('company/identity.json');
      expect(doc['company_name'], equals('Project Alpha Inc'));
    });

    test('HTTP 401 Unauthorized triggers AuthException', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({'error': 'Unauthorized', 'detail': 'Invalid or expired token'}),
          401,
        );
      });

      final apiClient = AlphaApiClient(client: fakeClient);

      expect(
        () => apiClient.getProjects(),
        throwsA(isA<AuthException>().having((e) => e.statusCode, 'statusCode', 401)),
      );
    });

    test('HTTP 404 Not Found triggers NotFoundException', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({'error': 'Not Found', 'detail': 'Project not found'}),
          404,
        );
      });

      final apiClient = AlphaApiClient(client: fakeClient);

      expect(
        () => apiClient.getProject('nonexistent_id'),
        throwsA(isA<NotFoundException>().having((e) => e.statusCode, 'statusCode', 404)),
      );
    });

    test('HTTP 422 Unprocessable Entity triggers ValidationException', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({
            'error': 'Validation Error',
            'code': 422,
            'detail': 'Invalid priority value'
          }),
          422,
        );
      });

      final apiClient = AlphaApiClient(client: fakeClient);

      expect(
        () => apiClient.submitGoal(title: 'Valid Title', description: 'Desc'),
        throwsA(isA<ValidationException>().having((e) => e.statusCode, 'statusCode', 422)),
      );
    });

    test('HTTP 500 Server Error triggers ApiException', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({'error': 'Internal Server Error', 'detail': 'Database failure'}),
          500,
        );
      });

      final apiClient = AlphaApiClient(client: fakeClient);

      expect(
        () => apiClient.getAgents(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 500)),
      );
    });
  });

  group('AlphaWebSocketService — Real-Time Telemetry Pipeline', () {
    late FakeWebSocketChannel fakeChannel;

    setUp(() {
      fakeChannel = FakeWebSocketChannel();
    });

    tearDown(() {
      fakeChannel.emitDone();
    });

    test('Handshake URI builds with ws scheme, host, port 8765, and token param', () {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        token: 'ws_secret_token_123',
        channelFactory: (uri) => fakeChannel,
      );

      final uri = wsService.uri;
      expect(uri.scheme, equals('ws'));
      expect(uri.host, equals('10.0.2.2'));
      expect(uri.port, equals(8765));
      expect(uri.path, equals('/ws'));
      expect(uri.queryParameters['token'], equals('ws_secret_token_123'));
    });

    test('connect establishes active connection state', () async {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        channelFactory: (uri) => fakeChannel,
      );

      expect(wsService.isConnected, isFalse);
      await wsService.connect();
      expect(wsService.isConnected, isTrue);
      expect(wsService.connectionState, equals(WebSocketConnectionState.connected));

      wsService.dispose();
    });

    test('Incoming task_progress_update routes to onTaskProgress stream', () async {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        channelFactory: (uri) => fakeChannel,
      );

      await wsService.connect();

      final completer = Completer<TaskProgress>();
      final sub = wsService.onTaskProgress.listen((task) {
        completer.complete(task);
      });

      fakeChannel.emitEnvelope('task_progress_update', {
        'task_id': 'task_777',
        'task_name': 'Compile Android APK',
        'progress_percent': 90,
        'current_step': 'Optimizing Proguard R8 bytecode',
        'assigned_agent': 'CTO',
        'status': 'running',
      });

      final receivedTask = await completer.future.timeout(const Duration(seconds: 2));
      expect(receivedTask.taskId, equals('task_777'));
      expect(receivedTask.progressPercent, equals(90));
      expect(receivedTask.assignedAgent, equals('CTO'));
      expect(receivedTask.status, equals('running'));

      await sub.cancel();
      wsService.dispose();
    });

    test('Incoming agent_status_change routes to onAgentActivity stream', () async {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        channelFactory: (uri) => fakeChannel,
      );

      await wsService.connect();

      final completer = Completer<Map<String, dynamic>>();
      final sub = wsService.onAgentActivity.listen((data) {
        completer.complete(data);
      });

      fakeChannel.emitEnvelope('agent_status_change', {
        'agent_id': 'CTO',
        'new_status': 'active',
        'current_task': 'Reviewing PR #42',
      });

      final receivedData = await completer.future.timeout(const Duration(seconds: 2));
      expect(receivedData['agent_id'], equals('CTO'));
      expect(receivedData['new_status'], equals('active'));

      await sub.cancel();
      wsService.dispose();
    });

    test('Outbound directives serialize valid JSON actions to sink', () async {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        channelFactory: (uri) => fakeChannel,
      );

      await wsService.connect();

      // 1. Ping
      wsService.sendPing();
      expect(fakeChannel.fakeSink.sentMessages.length, equals(1));
      final pingAction = jsonDecode(fakeChannel.fakeSink.sentMessages.last);
      expect(pingAction['action'], equals('ping'));

      // 2. Subscribe
      wsService.subscribeProject('proj_alpha_99');
      final subAction = jsonDecode(fakeChannel.fakeSink.sentMessages.last);
      expect(subAction['action'], equals('subscribe'));
      expect(subAction['project_id'], equals('proj_alpha_99'));

      // 3. Unsubscribe
      wsService.unsubscribeProject('proj_alpha_99');
      final unsubAction = jsonDecode(fakeChannel.fakeSink.sentMessages.last);
      expect(unsubAction['action'], equals('unsubscribe'));
      expect(unsubAction['project_id'], equals('proj_alpha_99'));

      wsService.dispose();
    });

    test('Manual disconnect transitions state to disconnected without reconnecting', () async {
      final wsService = AlphaWebSocketService(
        host: '10.0.2.2:8765',
        channelFactory: (uri) => fakeChannel,
      );

      await wsService.connect();
      expect(wsService.isConnected, isTrue);

      wsService.disconnect();
      expect(wsService.isConnected, isFalse);
      expect(wsService.connectionState, equals(WebSocketConnectionState.disconnected));

      wsService.dispose();
    });
  });
}
