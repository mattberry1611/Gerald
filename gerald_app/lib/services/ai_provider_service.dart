import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

enum AiProvider { claude, openai, gemini }

class AiProviderInfo {
  final AiProvider id;
  final String name;
  final String vendor;
  final String model;
  final bool requiresApiKey;
  final String status; // 'active' | 'planned'
  final String description;

  const AiProviderInfo({
    required this.id,
    required this.name,
    required this.vendor,
    required this.model,
    required this.requiresApiKey,
    required this.status,
    required this.description,
  });

  bool get isAvailable => status == 'active';
}

const List<AiProviderInfo> kAiProviders = [
  AiProviderInfo(
    id: AiProvider.claude,
    name: 'Claude Code',
    vendor: 'Anthropic',
    model: 'claude-sonnet-4-6',
    requiresApiKey: false,
    status: 'active',
    description: 'Autonomous code editing via Claude CLI',
  ),
  AiProviderInfo(
    id: AiProvider.openai,
    name: 'ChatGPT',
    vendor: 'OpenAI',
    model: 'gpt-4o',
    requiresApiKey: true,
    status: 'planned',
    description: 'API-based code assistance (planned V2.1)',
  ),
  AiProviderInfo(
    id: AiProvider.gemini,
    name: 'Gemini',
    vendor: 'Google',
    model: 'gemini-2.0-flash',
    requiresApiKey: true,
    status: 'planned',
    description: 'API-based code assistance (planned V2.1)',
  ),
];

class AiProviderService {
  static final AiProviderService instance = AiProviderService._();
  AiProviderService._();

  AiProvider _activeProvider = AiProvider.claude;
  final Map<AiProvider, String> _apiKeys = {};

  AiProvider get activeProvider => _activeProvider;

  AiProviderInfo get activeProviderInfo =>
      kAiProviders.firstWhere((p) => p.id == _activeProvider);

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _activeProvider = _parseProvider(prefs.getString('aiProvider') ?? 'claude');
    for (final p in kAiProviders) {
      final key = prefs.getString('apiKey_${_providerId(p.id)}');
      if (key != null && key.isNotEmpty) {
        _apiKeys[p.id] = key;
      }
    }
  }

  Future<void> setActiveProvider(AiProvider provider) async {
    _activeProvider = provider;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('aiProvider', _providerId(provider));
  }

  Future<void> setApiKey(AiProvider provider, String key) async {
    _apiKeys[provider] = key;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('apiKey_${_providerId(provider)}', key);
  }

  String? getApiKey(AiProvider provider) => _apiKeys[provider];

  Future<void> syncToBackend(String baseUrl) async {
    try {
      await http
          .post(
            Uri.parse('$baseUrl/set-provider'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'provider': _providerId(_activeProvider),
              'api_key': _apiKeys[_activeProvider] ?? '',
            }),
          )
          .timeout(const Duration(seconds: 10));
    } catch (_) {}
  }

  Future<String> fetchActiveProviderFromBackend(String baseUrl) async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/provider-status'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['active_provider'] as String? ?? 'claude';
      }
    } catch (_) {}
    return 'claude';
  }

  String _providerId(AiProvider p) {
    switch (p) {
      case AiProvider.claude:
        return 'claude';
      case AiProvider.openai:
        return 'openai';
      case AiProvider.gemini:
        return 'gemini';
    }
  }

  AiProvider _parseProvider(String s) {
    switch (s.toLowerCase()) {
      case 'openai':
        return AiProvider.openai;
      case 'gemini':
        return AiProvider.gemini;
      default:
        return AiProvider.claude;
    }
  }
}
