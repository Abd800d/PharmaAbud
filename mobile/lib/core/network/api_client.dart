/// REST API client (§36–§37). Versioned endpoints, auth header,
/// pagination-friendly JSON, typed errors — no raw stack traces surfaced.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../errors/failures.dart';

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl, String? token})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBase,
        _token = token;

  final http.Client _client;
  final String _baseUrl;
  String? _token;

  set token(String? value) => _token = value;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        if (_token != null && _token!.isNotEmpty) 'Authorization': 'Bearer $_token',
      };

  Future<Map<String, dynamic>> get(String path, {Map<String, String>? query}) =>
      _request('GET', path, query: query);

  Future<Map<String, dynamic>> post(String path, {Object? body}) =>
      _request('POST', path, body: body);

  Future<Map<String, dynamic>> patch(String path, {Object? body}) =>
      _request('PATCH', path, body: body);

  Future<Map<String, dynamic>> delete(String path) => _request('DELETE', path);

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
  }) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    try {
      final request = http.Request(method, uri);
      request.headers.addAll(_headers);
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _client.send(request).timeout(const Duration(seconds: 30));
      final response = await http.Response.fromStream(streamed);
      return _handle(response);
    } on SocketException {
      throw const NetworkFailure();
    } on TimeoutException {
      throw const NetworkFailure();
    }
  }

  Map<String, dynamic> _handle(http.Response response) {
    final Map<String, dynamic> data = response.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (response.statusCode >= 200 && response.statusCode < 300) return data;
    final error = data['error'] ?? data['detail'];
    final message = error is Map
        ? (error['message'] ?? 'Request failed')
        : (error?.toString() ?? 'Request failed');
    switch (response.statusCode) {
      case 401:
        throw UnauthorizedFailure(message);
      case 403:
        throw ForbiddenFailure(message);
      case 404:
        throw NotFoundFailure(message);
      case 422:
        throw ValidationFailure(message);
      case 429:
        throw const RateLimitFailure();
      default:
        throw ServerFailure(message);
    }
  }

  void dispose() => _client.close();
}
