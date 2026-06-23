import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import '../models/project_brain.dart';

class GeraldApi {
  final String baseUrl;

  GeraldApi(this.baseUrl);

  Future<Map<String, dynamic>> sendPrompt(String prompt,
      {String? project}) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'prompt': prompt, 'project': project}),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {'message': decoded.toString()};
    }
    throw Exception('Backend error: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> readResult({String? project}) async {
    final uri = (project != null && project.isNotEmpty)
        ? Uri.parse('$baseUrl/read?project=${Uri.encodeComponent(project)}')
        : Uri.parse('$baseUrl/read');
    final response = await http
        .get(uri)
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {'output': decoded.toString()};
    }
    throw Exception('Read error: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> getTaskTruth() async {
    final response = await http
        .get(Uri.parse('$baseUrl/task/truth'))
        .timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    return {};
  }

  Future<Map<String, dynamic>> getTaskResult({String? project}) async {
    final uri = (project != null && project.isNotEmpty)
        ? Uri.parse('$baseUrl/task/result?project=${Uri.encodeComponent(project)}')
        : Uri.parse('$baseUrl/task/result');
    final response = await http.get(uri).timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    return {};
  }

  Future<Map<String, dynamic>> getStatus() async {
    final response = await http
        .get(Uri.parse('$baseUrl/status'))
        .timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    return {'status': 'idle'};
  }

  Future<List<Map<String, dynamic>>> getProjectsFull() async {
    final response = await http
        .get(Uri.parse('$baseUrl/projects'))
        .timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data is List) {
        return data.whereType<Map<String, dynamic>>().toList();
      }
    }
    return [];
  }

  Future<List<String>> getProjects() async {
    final full = await getProjectsFull();
    return full
        .map((p) => (p['name'] ?? '').toString())
        .where((s) => s.isNotEmpty)
        .toList();
  }

  Future<void> approve() async {
    await http
        .post(
          Uri.parse('$baseUrl/send-to-claude-code'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'approved': true}),
        )
        .timeout(const Duration(seconds: 10));
  }

  Future<void> reject() async {
    await http
        .post(
          Uri.parse('$baseUrl/reject'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({}),
        )
        .timeout(const Duration(seconds: 10));
  }

  // ── Project Brain ───────────────────────────────────────────────────────────

  Future<ProjectBrain?> getProjectBrain(String projectName) async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/project-brain/$projectName'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is Map<String, dynamic>) {
          return ProjectBrain.fromJson(data);
        }
      }
    } catch (_) {}
    return null;
  }

  Future<Map<String, dynamic>> initProjectBrain(String projectName) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/init-brain/$projectName'),
          headers: {'Content-Type': 'application/json'},
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    throw Exception('Init brain failed: ${response.statusCode}');
  }

  // ── Automatic Project Creation ──────────────────────────────────────────────

  Future<Map<String, dynamic>> createProject({
    required String name,
    String path = '',
    String description = '',
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/create-project'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'name': name,
            'path': path,
            'description': description,
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    throw Exception('Create project error: ${response.statusCode}');
  }

  // ── Build Verification ──────────────────────────────────────────────────────

  Future<Map<String, dynamic>> triggerBuild({
    String flavor = 'debug',
    String project = 'CommuteCoder',
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/build-verify'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'flavor': flavor, 'project': project}),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Build trigger failed: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> getBuildStatus() async {
    final response = await http
        .get(Uri.parse('$baseUrl/build-status'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    return {'status': 'error', 'error_count': 0, 'is_running': false};
  }

  // ── Multi-AI Provider ───────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getProviderStatus() async {
    final response = await http
        .get(Uri.parse('$baseUrl/provider-status'))
        .timeout(const Duration(seconds: 8));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    return {'active_provider': 'claude', 'providers': []};
  }

  Future<Map<String, dynamic>> setProvider(
      String providerId, {
      String apiKey = '',
    }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/set-provider'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'provider': providerId, 'api_key': apiKey}),
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Set provider failed: ${response.statusCode}');
  }

  // ── Remote APK Delivery ─────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getApkStatus() async {
    final response = await http
        .get(Uri.parse('$baseUrl/apk-status'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    return {'available': false};
  }

  String getApkDownloadUrl() => '$baseUrl/apk-latest/download';

  // ── Image Upload ────────────────────────────────────────────────────────────

  /// Upload an image to /upload-image (dashboard-compatible endpoint).
  /// Returns {"ok": true, "url": "/dashboard/uploads/<file>", ...}
  Future<Map<String, dynamic>> uploadImage(
    Uint8List bytes,
    String mimeType,
  ) async {
    final parts = mimeType.split('/');
    final contentType = MediaType(
      parts.isNotEmpty ? parts[0] : 'image',
      parts.length > 1 ? parts[1] : 'jpeg',
    );
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/upload-image'),
    )..files.add(http.MultipartFile.fromBytes(
        'image',
        bytes,
        filename: 'upload.${parts.length > 1 ? parts[1] : "jpg"}',
        contentType: contentType,
      ));

    final streamed = await request.send().timeout(const Duration(seconds: 60));
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {'message': decoded.toString()};
    }
    throw Exception('Upload error: ${response.statusCode}');
  }

  // ── Vision ──────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> uploadVisionImage(
    Uint8List bytes,
    String mimeType, {
    String prompt = '',
  }) async {
    final parts = mimeType.split('/');
    final contentType = MediaType(
      parts.isNotEmpty ? parts[0] : 'image',
      parts.length > 1 ? parts[1] : 'jpeg',
    );
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/gerald-vision'),
    )
      ..files.add(http.MultipartFile.fromBytes(
        'image',
        bytes,
        filename: 'image.${parts.length > 1 ? parts[1] : "jpg"}',
        contentType: contentType,
      ))
      ..fields['prompt'] = prompt;

    final streamed = await request.send().timeout(const Duration(seconds: 60));
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {'message': decoded.toString()};
    }
    throw Exception('Vision error: ${response.statusCode}');
  }

  // ── Design Studio ────────────────────────────────────────────────────────────

  /// Returns the base URL to use for Design Studio endpoints (/design/*).
  /// Design Studio is proxied through the main bridge at the same host/port,
  /// so no port substitution is needed (avoids HTTP/HTTPS mismatch on port 8002).
  static String designStudioUrl(String baseUrl) => baseUrl;

  /// Generate 1–3 visual UI concept images for [description].
  /// Calls POST /design/generate on the Design Studio service (port 8002).
  Future<List<Map<String, dynamic>>> generateDesignConcepts(
    String description, {
    int count = 3,
  }) async {
    final dsUrl = designStudioUrl(baseUrl);
    final response = await http
        .post(
          Uri.parse('$dsUrl/design/generate'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'description': description, 'count': count}),
        )
        .timeout(const Duration(seconds: 120));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      final concepts = decoded['concepts'];
      if (concepts is List) {
        return concepts.whereType<Map<String, dynamic>>().toList();
      }
      return [];
    }
    throw Exception('Design generate error: ${response.statusCode}');
  }

  /// Iterate on a concept with refinement notes.
  /// Calls POST /design/iterate on the Design Studio service (port 8002).
  Future<List<Map<String, dynamic>>> iterateDesignConcept(
    String originalDescription,
    String iterationNotes, {
    int count = 1,
  }) async {
    final dsUrl = designStudioUrl(baseUrl);
    final response = await http
        .post(
          Uri.parse('$dsUrl/design/iterate'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'original_description': originalDescription,
            'iteration_notes': iterationNotes,
            'count': count,
          }),
        )
        .timeout(const Duration(seconds: 120));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      final concepts = decoded['concepts'];
      if (concepts is List) {
        return concepts.whereType<Map<String, dynamic>>().toList();
      }
      return [];
    }
    throw Exception('Design iterate error: ${response.statusCode}');
  }

  // ── Visual Copy Mode ─────────────────────────────────────────────────────────

  /// POST /compare-images — compare a target reference image against a current
  /// result screenshot. Returns {"ok": true, "comparison": {...}, ...}.
  Future<Map<String, dynamic>> compareImages(
    Uint8List targetBytes,
    String targetMime,
    Uint8List resultBytes,
    String resultMime,
  ) async {
    MediaType toMt(String mime) {
      final p = mime.split('/');
      return MediaType(p.isNotEmpty ? p[0] : 'image', p.length > 1 ? p[1] : 'jpeg');
    }

    String toExt(String mime) {
      final p = mime.split('/');
      return p.length > 1 ? p[1] : 'jpg';
    }

    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/compare-images'))
      ..files.add(http.MultipartFile.fromBytes(
        'target', targetBytes,
        filename: 'target.${toExt(targetMime)}',
        contentType: toMt(targetMime),
      ))
      ..files.add(http.MultipartFile.fromBytes(
        'result', resultBytes,
        filename: 'result.${toExt(resultMime)}',
        contentType: toMt(resultMime),
      ));

    final streamed = await request.send().timeout(const Duration(seconds: 120));
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {'message': decoded.toString()};
    }
    throw Exception('Compare error ${response.statusCode}');
  }
}
