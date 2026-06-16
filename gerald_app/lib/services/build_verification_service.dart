import 'dart:convert';
import 'package:http/http.dart' as http;

enum BuildStatus { neverRun, running, success, failed, timeout, error }

class BuildResult {
  final BuildStatus status;
  final int errorCount;
  final int warningCount;
  final double durationS;
  final String output;
  final List<String> errors;
  final List<String> warnings;
  final String timestamp;
  final String flavor;

  const BuildResult({
    required this.status,
    required this.errorCount,
    required this.warningCount,
    required this.durationS,
    required this.output,
    required this.errors,
    required this.warnings,
    required this.timestamp,
    required this.flavor,
  });

  factory BuildResult.fromJson(Map<String, dynamic> json) {
    final statusStr = json['status'] as String? ?? 'never_run';
    BuildStatus status;
    switch (statusStr) {
      case 'success':
        status = BuildStatus.success;
        break;
      case 'failed':
        status = BuildStatus.failed;
        break;
      case 'running':
        status = BuildStatus.running;
        break;
      case 'timeout':
        status = BuildStatus.timeout;
        break;
      case 'never_run':
        status = BuildStatus.neverRun;
        break;
      default:
        status = BuildStatus.error;
    }
    return BuildResult(
      status: status,
      errorCount: (json['error_count'] as int?) ?? 0,
      warningCount: (json['warning_count'] as int?) ?? 0,
      durationS: ((json['duration_s'] as num?) ?? 0).toDouble(),
      output: (json['output'] as String?) ?? '',
      errors: List<String>.from(json['errors'] as List? ?? []),
      warnings: List<String>.from(json['warnings'] as List? ?? []),
      timestamp: (json['timestamp'] as String?) ?? '',
      flavor: (json['flavor'] as String?) ?? 'debug',
    );
  }

  static BuildResult neverRan() => const BuildResult(
        status: BuildStatus.neverRun,
        errorCount: 0,
        warningCount: 0,
        durationS: 0,
        output: '',
        errors: [],
        warnings: [],
        timestamp: '',
        flavor: 'debug',
      );

  String get statusLabel {
    switch (status) {
      case BuildStatus.neverRun:
        return 'Not Run';
      case BuildStatus.running:
        return 'Building...';
      case BuildStatus.success:
        return 'Build OK';
      case BuildStatus.failed:
        return 'Build Failed';
      case BuildStatus.timeout:
        return 'Timeout';
      case BuildStatus.error:
        return 'Error';
    }
  }
}

class BuildVerificationService {
  static final BuildVerificationService instance = BuildVerificationService._();
  BuildVerificationService._();

  Future<Map<String, dynamic>> triggerBuild(
      String baseUrl, {
      String flavor = 'debug',
    }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/build-verify'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'flavor': flavor}),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Build trigger failed: ${response.statusCode}');
  }

  Future<BuildResult> getBuildStatus(String baseUrl) async {
    final response = await http
        .get(Uri.parse('$baseUrl/build-status'))
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return BuildResult.fromJson(data);
    }
    throw Exception('Build status error: ${response.statusCode}');
  }
}
