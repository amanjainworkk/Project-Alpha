// Project Alpha Mobile APK — REST API Client Architecture
// File Target: Alpha/apk/lib/services/api_client.dart
// Milestone 10: Features 67, 68

import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;
import 'package:http/http.dart' as http;

import '../models/models.dart';

// ============================================================================
// 1. Custom Exception Hierarchy for Robust Mobile Error Handling
// ============================================================================

abstract class AlphaException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic details;

  AlphaException(this.message, {this.statusCode, this.details});

  @override
  String toString() {
    if (statusCode != null) {
      return '$runtimeType (HTTP $statusCode): $message';
    }
    return '$runtimeType: $message';
  }
}

/// Generic API error for unclassified HTTP error responses (e.g. 400, 500).
class ApiException extends AlphaException {
  ApiException(super.message, {super.statusCode, super.details});
}

/// Authentication and authorization errors (HTTP 401 Unauthorized, 403 Forbidden).
class AuthException extends AlphaException {
  AuthException(super.message, {super.statusCode, super.details});
}

/// Request validation failure (HTTP 422 Unprocessable Entity) containing detailed field violations.
class ValidationException extends AlphaException {
  ValidationException(super.message, {super.statusCode, super.details});
}

/// Resource not found (HTTP 404 Not Found).
class NotFoundException extends AlphaException {
  NotFoundException(super.message, {super.statusCode, super.details});
}

/// Network level connectivity failure (connection refused, DNS failure, offline socket).
class NetworkException extends AlphaException {
  NetworkException(super.message, {super.details});
}

/// Request timed out before the server responded.
class RequestTimeoutException extends AlphaException {
  RequestTimeoutException(super.message, {super.details});
}

// ============================================================================
// 2. AlphaApiClient Implementation
// ============================================================================

class AlphaApiClient {
  /// Default base URL for Android Emulator connecting to desktop host.
  static const String defaultEmulatorBaseUrl = 'http://10.0.2.2:8765';

  /// Default base URL for desktop testing or direct loopback.
  static const String defaultLocalhostBaseUrl = 'http://127.0.0.1:8765';

  /// Default HTTP request timeout.
  static const Duration defaultTimeout = Duration(seconds: 10);

  /// Root URL of the Project Alpha FastAPI Desktop backend (e.g. "http://10.0.2.2:8765").
  final String baseUrl;

  /// Bearer token for authenticating against ALPHA_TOKEN protected routes.
  String? token;

  /// Underlying HTTP client instance, injectable for hermetic unit testing.
  final http.Client _client;

  /// Configurable request timeout.
  final Duration timeout;

  /// Internal flag tracking whether this instance created and owns the HTTP client.
  final bool _ownsClient;

  AlphaApiClient({
    String? baseUrl,
    this.token,
    http.Client? client,
    this.timeout = defaultTimeout,
  })  : baseUrl = _normalizeBaseUrl(baseUrl ?? defaultEmulatorBaseUrl),
        _client = client ?? http.Client(),
        _ownsClient = client == null;

  /// Factory constructor for local loopback execution (desktop or tests).
  factory AlphaApiClient.localhost({
    String? token,
    http.Client? client,
    Duration? timeout,
  }) {
    return AlphaApiClient(
      baseUrl: defaultLocalhostBaseUrl,
      token: token,
      client: client,
      timeout: timeout ?? defaultTimeout,
    );
  }

  /// Factory constructor for Android Emulator execution.
  factory AlphaApiClient.emulator({
    String? token,
    http.Client? client,
    Duration? timeout,
  }) {
    return AlphaApiClient(
      baseUrl: defaultEmulatorBaseUrl,
      token: token,
      client: client,
      timeout: timeout ?? defaultTimeout,
    );
  }

  /// Factory constructor for local Wi-Fi / LAN execution.
  factory AlphaApiClient.lan(
    String host, {
    int port = 8765,
    String? token,
    http.Client? client,
    Duration? timeout,
  }) {
    return AlphaApiClient(
      baseUrl: 'http://$host:$port',
      token: token,
      client: client,
      timeout: timeout ?? defaultTimeout,
    );
  }

  /// Strips any trailing slashes from the base URL.
  static String _normalizeBaseUrl(String url) {
    var trimmed = url.trim();
    while (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    return trimmed;
  }

  /// Build standard JSON request headers including Bearer token authorization.
  Map<String, String> _buildHeaders({Map<String, String>? extraHeaders}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (token != null && token!.trim().isNotEmpty) {
      headers['Authorization'] = 'Bearer ${token!.trim()}';
    }

    if (extraHeaders != null) {
      headers.addAll(extraHeaders);
    }
    return headers;
  }

  /// Helper to safely decode and parse JSON error response body.
  dynamic _parseErrorBody(http.Response response) {
    try {
      if (response.body.isNotEmpty) {
        return jsonDecode(response.body);
      }
    } catch (_) {
      // Body is plain text or HTML error page
    }
    return response.body;
  }

  /// Dispatch and evaluate HTTP response status code, throwing typed AlphaExceptions.
  dynamic _handleResponse(http.Response response) {
    final status = response.statusCode;

    // Successful status codes
    if (status >= 200 && status < 300) {
      if (response.body.isEmpty) {
        return <String, dynamic>{};
      }
      try {
        return jsonDecode(utf8.decode(response.bodyBytes));
      } catch (e) {
        throw ApiException(
          'Failed to decode JSON response: $e',
          statusCode: status,
          details: response.body,
        );
      }
    }

    // Process error payload
    final parsedBody = _parseErrorBody(response);
    String errorMessage = 'HTTP request failed with status $status';
    dynamic errorDetail;

    if (parsedBody is Map<String, dynamic>) {
      errorMessage = parsedBody['detail']?.toString() ??
          parsedBody['error']?.toString() ??
          parsedBody['message']?.toString() ??
          errorMessage;
      errorDetail = parsedBody['detail'] ?? parsedBody;
    } else if (parsedBody is String && parsedBody.isNotEmpty) {
      errorMessage = parsedBody;
    }

    switch (status) {
      case 401:
        throw AuthException(
          'Unauthorized: $errorMessage',
          statusCode: status,
          details: errorDetail,
        );
      case 403:
        throw AuthException(
          'Forbidden: $errorMessage',
          statusCode: status,
          details: errorDetail,
        );
      case 404:
        throw NotFoundException(
          'Not Found: $errorMessage',
          statusCode: status,
          details: errorDetail,
        );
      case 422:
        throw ValidationException(
          'Validation Error: $errorMessage',
          statusCode: status,
          details: errorDetail,
        );
      case 500:
      case 502:
      case 503:
      case 504:
        throw ApiException(
          'Server Error: $errorMessage',
          statusCode: status,
          details: errorDetail,
        );
      default:
        throw ApiException(
          errorMessage,
          statusCode: status,
          details: errorDetail,
        );
    }
  }

  /// Safe request execution wrapper wrapping timeouts and socket errors.
  Future<http.Response> _executeWithTimeout(
    Future<http.Response> Function() action, {
    String? requestDescription,
  }) async {
    try {
      return await action().timeout(timeout);
    } on TimeoutException catch (e) {
      throw RequestTimeoutException(
        'Request timed out after ${timeout.inSeconds} seconds${requestDescription != null ? " ($requestDescription)" : ""}',
        details: e,
      );
    } on SocketException catch (e) {
      throw NetworkException(
        'Network unreachable or connection refused: ${e.message}',
        details: e,
      );
    } on http.ClientException catch (e) {
      throw NetworkException(
        'HTTP client communication error: ${e.message}',
        details: e,
      );
    } catch (e) {
      if (e is AlphaException) rethrow;
      throw NetworkException('Unexpected network error: $e', details: e);
    }
  }

  // ==========================================================================
  // 3. API Endpoints Implementation
  // ==========================================================================

  /// Check system health probe (GET /health or /api/health).
  /// Returns `true` if backend responds 200 OK and status is healthy/degraded.
  /// Does not throw on network failure; safely returns `false`.
  Future<bool> checkHealth() async {
    final uri = Uri.parse('$baseUrl/health');
    try {
      final response = await _client.get(uri).timeout(timeout);
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          final s = decoded['status'];
          return s == 'healthy' || s == 'degraded';
        }
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Fetch list of project summaries (GET /api/projects).
  Future<List<Project>> getProjects({
    String? statusFilter,
    int limit = 50,
    bool includeArchived = false,
  }) async {
    final queryParams = <String, String>{
      'limit': limit.toString(),
      'include_archived': includeArchived.toString(),
    };
    if (statusFilter != null && statusFilter.isNotEmpty) {
      queryParams['status'] = statusFilter;
    }

    final uri = Uri.parse('$baseUrl/api/projects').replace(queryParameters: queryParams);
    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/projects',
    );

    final dynamic body = _handleResponse(response);
    if (body is List) {
      return body
          .whereType<Map<String, dynamic>>()
          .map((item) => Project.fromJson(item))
          .toList();
    }
    return <Project>[];
  }

  /// Retrieve full detailed project manifest, deliverables, and audit scorecard (GET /api/projects/{id}).
  Future<Map<String, dynamic>> getProject(String id) async {
    final cleanId = id.trim();
    if (cleanId.isEmpty) {
      throw ValidationException('Project ID cannot be empty');
    }

    final uri = Uri.parse('$baseUrl/api/projects/$cleanId');
    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/projects/$cleanId',
    );

    final dynamic body = _handleResponse(response);
    if (body is Map<String, dynamic>) {
      return body;
    }
    throw ApiException('Expected JSON object for project detail, got ${body.runtimeType}');
  }

  /// Fetch all 13 canonical C-Suite executive agent cards for the Boardroom screen (GET /api/agents).
  Future<List<Agent>> getAgents({bool activeOnly = false}) async {
    final uri = Uri.parse('$baseUrl/api/agents').replace(
      queryParameters: {'active_only': activeOnly.toString()},
    );

    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/agents',
    );

    final dynamic body = _handleResponse(response);
    if (body is List) {
      return body
          .whereType<Map<String, dynamic>>()
          .map((item) => Agent.fromJson(item))
          .toList();
    }
    return <Agent>[];
  }

  /// Retrieve comprehensive agent profile, skills, JD summary, and episodic memory counts (GET /api/agents/{id}).
  Future<Map<String, dynamic>> getAgent(String id) async {
    final cleanId = id.trim();
    if (cleanId.isEmpty) {
      throw ValidationException('Agent ID cannot be empty');
    }

    final uri = Uri.parse('$baseUrl/api/agents/$cleanId');
    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/agents/$cleanId',
    );

    final dynamic body = _handleResponse(response);
    if (body is Map<String, dynamic>) {
      return body;
    }
    throw ApiException('Expected JSON object for agent detail, got ${body.runtimeType}');
  }

  /// Submit a high-level goal directive for autonomous execution (POST /api/goals).
  Future<Map<String, dynamic>> submitGoal({
    required String title,
    required String description,
    int? complexity,
    String priority = 'medium',
  }) async {
    final cleanTitle = title.trim();
    if (cleanTitle.isEmpty) {
      throw ValidationException('Goal title cannot be empty');
    }

    final payload = <String, dynamic>{
      'title': cleanTitle,
      'description': description.trim(),
      'priority': priority,
    };
    if (complexity != null) {
      payload['complexity'] = complexity;
    }

    final uri = Uri.parse('$baseUrl/api/goals');
    final response = await _executeWithTimeout(
      () => _client.post(
        uri,
        headers: _buildHeaders(),
        body: jsonEncode(payload),
      ),
      requestDescription: 'POST /api/goals',
    );

    final dynamic body = _handleResponse(response);
    if (body is Map<String, dynamic>) {
      return body;
    }
    throw ApiException('Expected JSON object for goal submission response, got ${body.runtimeType}');
  }

  /// Query real-time execution status and deliverables for a goal project (GET /api/goals/{id}).
  Future<Map<String, dynamic>> getGoalStatus(String id) async {
    final cleanId = id.trim();
    if (cleanId.isEmpty) {
      throw ValidationException('Goal ID cannot be empty');
    }

    final uri = Uri.parse('$baseUrl/api/goals/$cleanId');
    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/goals/$cleanId',
    );

    final dynamic body = _handleResponse(response);
    if (body is Map<String, dynamic>) {
      return body;
    }
    throw ApiException('Expected JSON object for goal status, got ${body.runtimeType}');
  }

  /// Read structured JSON document from Alpha's Vault.
  /// Queries primary route `GET /api/vault/read?path=...` with automatic fallback to `GET /api/vault?path=...`.
  Future<Map<String, dynamic>> readVault(String path) async {
    final cleanPath = path.trim();
    if (cleanPath.isEmpty) {
      throw ValidationException('Vault path cannot be empty');
    }

    // Try primary FastAPI endpoint: /api/vault/read?path={path}
    final primaryUri = Uri.parse('$baseUrl/api/vault/read').replace(
      queryParameters: {'path': cleanPath},
    );

    try {
      final response = await _executeWithTimeout(
        () => _client.get(primaryUri, headers: _buildHeaders()),
        requestDescription: 'GET /api/vault/read?path=$cleanPath',
      );
      final dynamic body = _handleResponse(response);
      if (body is Map<String, dynamic>) {
        return body;
      }
      return <String, dynamic>{'data': body};
    } on NotFoundException {
      // Attempt fallback to /api/vault?path={path} in case of route alias
      final fallbackUri = Uri.parse('$baseUrl/api/vault').replace(
        queryParameters: {'path': cleanPath},
      );
      final response = await _executeWithTimeout(
        () => _client.get(fallbackUri, headers: _buildHeaders()),
        requestDescription: 'GET /api/vault?path=$cleanPath',
      );
      final dynamic body = _handleResponse(response);
      if (body is Map<String, dynamic>) {
        return body;
      }
      return <String, dynamic>{'data': body};
    }
  }

  /// Semantic vector search across Vault collections (GET /api/vault/search).
  Future<List<dynamic>> searchVault(
    String query, {
    int topK = 5,
    String? pathPrefix,
  }) async {
    final cleanQuery = query.trim();
    if (cleanQuery.isEmpty) {
      throw ValidationException('Search query cannot be empty');
    }

    final queryParams = <String, String>{
      'query': cleanQuery,
      'top_k': topK.toString(),
    };
    if (pathPrefix != null && pathPrefix.isNotEmpty) {
      queryParams['path_prefix'] = pathPrefix;
    }

    final uri = Uri.parse('$baseUrl/api/vault/search').replace(queryParameters: queryParams);
    final response = await _executeWithTimeout(
      () => _client.get(uri, headers: _buildHeaders()),
      requestDescription: 'GET /api/vault/search',
    );

    final dynamic body = _handleResponse(response);
    if (body is List) {
      return body;
    }
    return <dynamic>[];
  }

  /// Direct message instruction to an executive agent (POST /api/agents/{id}/message).
  Future<Map<String, dynamic>> messageAgent(String id, String message) async {
    final cleanId = id.trim();
    final cleanMsg = message.trim();
    if (cleanId.isEmpty) {
      throw ValidationException('Agent ID cannot be empty');
    }
    if (cleanMsg.isEmpty) {
      throw ValidationException('Message cannot be empty');
    }

    final uri = Uri.parse('$baseUrl/api/agents/$cleanId/message');
    final response = await _executeWithTimeout(
      () => _client.post(
        uri,
        headers: _buildHeaders(),
        body: jsonEncode({'message': cleanMsg}),
      ),
      requestDescription: 'POST /api/agents/$cleanId/message',
    );

    final dynamic body = _handleResponse(response);
    if (body is Map<String, dynamic>) {
      return body;
    }
    return <String, dynamic>{'response': body.toString()};
  }

  /// Clean up underlying client resources if created internally.
  void dispose() {
    if (_ownsClient) {
      _client.close();
    }
  }
}
