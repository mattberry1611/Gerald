import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/project_brain.dart';
import '../services/gerald_api.dart';
import '../services/notification_service.dart';
import '../services/tts_service.dart';
import '../services/ai_provider_service.dart';
import '../services/build_verification_service.dart';

enum GeraldStatus { idle, planning, awaiting, executing, error, offline }

enum TaskStage { none, queued, sending, accepted, working, reviewing, finalising, complete, error }

const _kGlobal = '__global__';

class Message {
  final String id;
  final String role; // 'user' or 'gerald'
  final String content;
  final DateTime timestamp;
  final String? imagePath;

  Message({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.imagePath,
  });
}

class AppState extends ChangeNotifier {
  String _baseUrl = 'https://geraldai.com.au';
  String? _selectedProject;
  GeraldStatus _status = GeraldStatus.offline;
  bool _backendReachable = false;
  bool _isListening = false;
  bool _isLoading = false;
  bool _isSpeaking = false;
  bool _showTextInput = false;
  bool _conversationMode = false;
  bool _ttsEnabled = true;
  int _resumeListenTick = 0;

  // Task progress
  TaskStage _taskStage = TaskStage.none;
  DateTime? _taskStartTime;
  Timer? _completeTimer;
  Timer? _elapsedTimer;

  // ── Per-project message isolation ──────────────────────────────────────────
  // Keys: project name or _kGlobal when no project selected
  final Map<String, List<Message>> _projectMessages = {};

  final List<String> _activityLog = [];
  List<Map<String, dynamic>> _projectsFull = [];
  String _currentTask = '';
  Timer? _pollTimer;

  final List<String> _commandQueue = [];

  // ── Project Brain ──────────────────────────────────────────────────────────
  ProjectBrain? _projectBrain;
  bool _brainLoading = false;

  // ── Build Verification ─────────────────────────────────────────────────────
  BuildResult _buildResult = BuildResult.neverRan();
  bool _buildTriggering = false;

  // ── AI Provider ────────────────────────────────────────────────────────────
  AiProvider _aiProvider = AiProvider.claude;

  // ── Getters ────────────────────────────────────────────────────────────────

  String get baseUrl => _baseUrl;
  String? get selectedProject => _selectedProject;
  GeraldStatus get status => _status;
  bool get backendReachable => _backendReachable;
  bool get isListening => _isListening;
  bool get isLoading => _isLoading;
  bool get isSpeaking => _isSpeaking;
  bool get showTextInput => _showTextInput;
  bool get conversationMode => _conversationMode;
  bool get ttsEnabled => _ttsEnabled;
  int get resumeListenTick => _resumeListenTick;
  String get currentTask => _currentTask;
  int get queueCount => _commandQueue.length;

  /// Messages scoped to the currently selected project (or global bucket).
  List<Message> get messages {
    final key = _selectedProject ?? _kGlobal;
    return List.unmodifiable(_projectMessages[key] ?? []);
  }

  List<String> get activityLog => List.unmodifiable(_activityLog);

  /// Project names for the selector.
  List<String> get projects =>
      _projectsFull.map((p) => (p['name'] ?? '').toString()).where((s) => s.isNotEmpty).toList();

  /// Full project metadata (name, path, description).
  List<Map<String, dynamic>> get projectsFull => List.unmodifiable(_projectsFull);

  // Project Brain
  ProjectBrain? get projectBrain => _projectBrain;
  bool get brainLoading => _brainLoading;
  bool get hasBrain => _projectBrain?.hasBrain ?? false;

  // Build Verification
  BuildResult get buildResult => _buildResult;
  bool get buildTriggering => _buildTriggering;

  // AI Provider
  AiProvider get aiProvider => _aiProvider;
  AiProviderInfo get aiProviderInfo => AiProviderService.instance.activeProviderInfo;

  // Progress getters
  TaskStage get taskStage => _taskStage;
  int get taskProgress => _stagePercent(_taskStage);
  String get taskStageName => _stageName(_taskStage);
  Duration get taskElapsed =>
      _taskStartTime != null ? DateTime.now().difference(_taskStartTime!) : Duration.zero;
  bool get hasActiveTask => _taskStage != TaskStage.none;
  bool get isLongTask =>
      _taskStartTime != null &&
      DateTime.now().difference(_taskStartTime!).inSeconds > 120;

  GeraldApi get _api => GeraldApi(_baseUrl);

  bool get _isBusy =>
      _isLoading ||
      (_status != GeraldStatus.idle &&
          _status != GeraldStatus.offline &&
          _status != GeraldStatus.error);

  // ── Init ───────────────────────────────────────────────────────────────────

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString('baseUrl') ?? 'https://geraldai.com.au';
    _selectedProject = prefs.getString('selectedProject');
    _conversationMode = prefs.getBool('conversationMode') ?? false;
    _ttsEnabled = prefs.getBool('ttsEnabled') ?? true;

    TtsService.instance.onSpeakingChanged = _onSpeakingChanged;

    await AiProviderService.instance.init();
    _aiProvider = AiProviderService.instance.activeProvider;

    notifyListeners();
    _startPolling();
    _fetchProjects();

    // Load brain for the persisted project if any
    if (_selectedProject != null) {
      _loadProjectBrain(_selectedProject!);
    }
  }

  void _onSpeakingChanged(bool speaking) {
    _isSpeaking = speaking;
    notifyListeners();
  }

  Future<void> stopSpeaking() async {
    await TtsService.instance.stop();
  }

  // ── Polling ────────────────────────────────────────────────────────────────

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _poll());
  }

  Future<void> _poll() async {
    try {
      final data = await _api.getStatus();
      final rawStatus = data['status'] as String? ?? 'idle';
      final next = _parseStatus(rawStatus);

      if (next != _status) {
        final prev = _status;
        _status = next;
        _log('Status → ${_statusLabel(_status)}');

        if (next == GeraldStatus.planning || next == GeraldStatus.executing) {
          if (_taskStage == TaskStage.sending ||
              _taskStage == TaskStage.accepted ||
              _taskStage == TaskStage.queued) {
            _taskStage = TaskStage.working;
          }
        } else if (next == GeraldStatus.awaiting) {
          _taskStage = TaskStage.reviewing;
        }

        if ((prev == GeraldStatus.executing || prev == GeraldStatus.planning) &&
            (next == GeraldStatus.idle || next == GeraldStatus.error)) {
          await _readResult();
          await _processNextInQueue();
        }
        notifyListeners();
      }
    } catch (_) {
      _backendReachable = false;
      if (_status != GeraldStatus.offline) {
        _status = GeraldStatus.offline;
        notifyListeners();
      }
    }
  }

  // ── Result reading ─────────────────────────────────────────────────────────

  Future<void> _readResult() async {
    try {
      _taskStage = TaskStage.finalising;
      notifyListeners();

      final result = await _api.readResult();

      if (result['status'] == 'empty') {
        _clearTaskProgress();
        return;
      }

      final output = result['output'] as String? ?? '';
      final summary = result['summary'] as String? ?? '';
      final error = result['error'] as String? ?? '';
      final isError = result['status'] == 'error';

      final mainText = summary.isNotEmpty ? summary : output;

      if (mainText.isNotEmpty) {
        _addMessage('gerald', mainText);
        _log('Response received');
        final preview =
            mainText.length > 80 ? '${mainText.substring(0, 80)}...' : mainText;
        await NotificationService.instance.showTaskComplete(preview);

        _taskStage = TaskStage.complete;
        notifyListeners();

        // Refresh project brain to surface any updates Claude made during the task
        if (_selectedProject != null) {
          _loadProjectBrain(_selectedProject!);
        }

        if (_ttsEnabled) {
          try {
            await TtsService.instance.speak(mainText);
          } catch (_) {}
        }
      } else if (isError && error.isNotEmpty) {
        _addMessage('gerald', 'Error:\n$error');
        _log('Error received: ${_shortLabel(error)}');
        _taskStage = TaskStage.error;
        notifyListeners();
      } else if (isError) {
        _addMessage('gerald', 'Gerald encountered an error. Check backend logs.');
        _log('Error received (no detail)');
        _taskStage = TaskStage.error;
        notifyListeners();
      }

      _scheduleProgressReset(_taskStage == TaskStage.error ? 5 : 3);

      if (_conversationMode) {
        _resumeListenTick++;
        notifyListeners();
      }
    } catch (e) {
      _log('Read error: $e');
      _taskStage = TaskStage.error;
      _scheduleProgressReset(5);
      notifyListeners();
    }
  }

  void _scheduleProgressReset(int delaySec) {
    _completeTimer?.cancel();
    _completeTimer = Timer(Duration(seconds: delaySec), () {
      _taskStage = TaskStage.none;
      _taskStartTime = null;
      _elapsedTimer?.cancel();
      _elapsedTimer = null;
      notifyListeners();
    });
  }

  void _clearTaskProgress() {
    _taskStage = TaskStage.none;
    _taskStartTime = null;
    _elapsedTimer?.cancel();
    _elapsedTimer = null;
  }

  // ── Projects ───────────────────────────────────────────────────────────────

  Future<void> _fetchProjects() async {
    try {
      final list = await _api.getProjectsFull();
      if (list.isNotEmpty) {
        _projectsFull = list;
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> refreshProjects() async => _fetchProjects();

  // ── Project Brain ──────────────────────────────────────────────────────────

  Future<void> _loadProjectBrain(String projectName) async {
    _brainLoading = true;
    notifyListeners();
    try {
      final brain = await _api.getProjectBrain(projectName);
      _projectBrain = brain;
    } catch (_) {
      _projectBrain = ProjectBrain.empty(projectName);
    } finally {
      _brainLoading = false;
      notifyListeners();
    }
  }

  Future<void> refreshProjectBrain() async {
    if (_selectedProject != null) {
      await _loadProjectBrain(_selectedProject!);
    }
  }

  Future<Map<String, dynamic>> initProjectBrain(String projectName) async {
    try {
      final result = await _api.initProjectBrain(projectName);
      _log('Brain initialised: $projectName');
      if (_selectedProject == projectName) {
        await _loadProjectBrain(projectName);
      }
      return result;
    } catch (e) {
      _log('Brain init error: $e');
      return {'ok': false, 'error': e.toString()};
    }
  }

  // ── Automatic Project Creation ─────────────────────────────────────────────

  Future<Map<String, dynamic>> createProject({
    required String name,
    String path = '',
    String description = '',
  }) async {
    final result = await _api.createProject(
      name: name,
      path: path,
      description: description,
    );
    if (result['ok'] == true) {
      await _fetchProjects();
      _log('Project created: $name');
    }
    return result;
  }

  // ── Send prompt ────────────────────────────────────────────────────────────

  static String? _detectCreateProjectName(String text) {
    final lower = text.trim().toLowerCase();
    const prefixes = [
      'create new project ',
      'create project ',
      'new project ',
      'make new project ',
      'make project ',
      'start project ',
      'start new project ',
      'create new app ',
      'create app ',
      'new app ',
    ];
    for (final prefix in prefixes) {
      if (lower.startsWith(prefix)) {
        final remainder = text.substring(prefix.length).trim();
        final first = remainder.split(RegExp(r'[\s,\.!?]')).first.trim();
        if (first.length >= 2 && first.length <= 40) return first;
      }
    }
    return null;
  }

  Future<void> sendPrompt(String prompt) async {
    if (prompt.trim().isEmpty) return;
    final trimmed = prompt.trim();

    // Voice command: "create project X" → auto-create without sending to Claude
    final createName = _detectCreateProjectName(trimmed);
    if (createName != null) {
      _addMessage('user', trimmed);
      _log('Create project detected: $createName');
      final result = await createProject(name: createName, description: '');
      final ok = result['ok'] as bool? ?? false;
      if (ok) {
        final msg =
            "Project '$createName' created. Select it from the project picker to get started.";
        _addMessage('gerald', msg);
        _log('Project created: $createName');
        if (_ttsEnabled) TtsService.instance.speak(msg).ignore();
        await setProject(createName);
      } else {
        final err = result['error'] as String? ?? 'Unknown error';
        _addMessage('gerald', "Couldn't create project '$createName': $err");
        _log('Project create failed: $err');
      }
      return;
    }

    if (_isBusy) {
      _commandQueue.add(trimmed);
      if (_taskStage == TaskStage.none) _taskStage = TaskStage.queued;
      _log('Queued [${_commandQueue.length}]: ${_shortLabel(trimmed)}');
      notifyListeners();
      return;
    }

    await _executePrompt(trimmed);
  }

  /// Scans recent messages for a vision image + Gerald reply exchange and, if
  /// found, prepends that analysis as context so the backend knows what was
  /// in the image even though it never received the raw bytes.
  String _buildContextualPrompt(String prompt) {
    final msgs = messages; // already includes the just-added user message
    if (msgs.length < 3) return prompt; // need at least: image, gerald, new user

    // Exclude the message we just added (last entry) and look at what's before
    final history = msgs.sublist(0, msgs.length - 1);
    final recent = history.length > 6 ? history.sublist(history.length - 6) : history;

    for (int i = recent.length - 1; i >= 0; i--) {
      final msg = recent[i];
      if (msg.role == 'user' && msg.imagePath != null) {
        // Found a recent image message — grab the Gerald response that followed it
        if (i + 1 < recent.length && recent[i + 1].role == 'gerald') {
          final visionContext = recent[i + 1].content;
          return 'Context from my previous image analysis:\n$visionContext\n\n$prompt';
        }
      }
    }
    return prompt;
  }

  Future<void> _executePrompt(String prompt) async {
    _addMessage('user', prompt);
    _isLoading = true;
    _currentTask = prompt;
    _taskStage = TaskStage.sending;
    _taskStartTime = DateTime.now();
    _completeTimer?.cancel();

    _elapsedTimer?.cancel();
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_taskStage != TaskStage.none) notifyListeners();
    });

    _log('Sent: ${_shortLabel(prompt)}');
    notifyListeners();

    final enrichedPrompt = _buildContextualPrompt(prompt);

    try {
      final result = await _api.sendPrompt(enrichedPrompt, project: _selectedProject);
      final ok = result['ok'] as bool? ?? true;
      if (!ok) {
        final errMsg = result['error'] as String? ?? 'Gerald rejected the request';
        _addMessage('gerald', 'Error: $errMsg');
        _log('Request rejected: ${_shortLabel(errMsg)}');
        _status = GeraldStatus.error;
        _taskStage = TaskStage.error;
        _scheduleProgressReset(5);
        return;
      }
      _taskStage = TaskStage.accepted;
      _status = GeraldStatus.executing;
      _log('Waiting for Gerald...');
    } catch (e) {
      _log('Error: $e');
      _addMessage('gerald',
          'Connection error: $e\n\nIs gerald_bridge.py running?');
      _status = GeraldStatus.error;
      _taskStage = TaskStage.error;
      _scheduleProgressReset(5);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _processNextInQueue() async {
    if (_commandQueue.isEmpty) return;
    final next = _commandQueue.removeAt(0);
    final remaining = _commandQueue.length;
    if (remaining > 0) {
      _log('Processing queued task ($remaining still waiting)');
    } else {
      _log('Processing last queued task');
    }
    notifyListeners();
    await _executePrompt(next);
  }

  // ── Image ──────────────────────────────────────────────────────────────────

  Future<void> addImageMessage(
    String imagePath,
    Uint8List bytes,
    String mimeType, {
    String caption = '',
  }) async {
    _addMessage(
      'user',
      caption.isNotEmpty ? caption : '[Image]',
      imagePath: imagePath,
    );
    _log('Image attached: ${imagePath.split(RegExp(r'[/\\]')).last}');

    try {
      final result = await _api.uploadVisionImage(bytes, mimeType, prompt: caption);
      final reply = (result['message'] ?? result['reply'] ?? result['output'] ?? '').toString().trim();
      if (reply.isNotEmpty) {
        _addMessage('gerald', reply);
        if (_ttsEnabled) TtsService.instance.speak(reply).ignore();
      }
    } catch (e) {
      _addMessage('gerald', 'Vision error: $e');
      _log('Vision error: $e');
    }
  }

  // ── Approval ───────────────────────────────────────────────────────────────

  Future<void> approve() async {
    try {
      await _api.approve();
      _log('Approved — executing');
      _status = GeraldStatus.executing;
      _taskStage = TaskStage.working;
      notifyListeners();
    } catch (e) {
      _log('Approve error: $e');
    }
  }

  Future<void> reject() async {
    try {
      await _api.reject();
      _log('Rejected');
      _status = GeraldStatus.idle;
      _addMessage('gerald', 'Task rejected.');
      _clearTaskProgress();
      notifyListeners();
      await _processNextInQueue();
    } catch (e) {
      _log('Reject error: $e');
    }
  }

  // ── UI state ───────────────────────────────────────────────────────────────

  void setListening(bool value) {
    _isListening = value;
    notifyListeners();
  }

  void toggleTextInput() {
    _showTextInput = !_showTextInput;
    notifyListeners();
  }

  Future<void> setConversationMode(bool value) async {
    if (_conversationMode == value) return;
    _conversationMode = value;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('conversationMode', value);
    if (!value) {
      await TtsService.instance.stop();
    }
    _log('Conversation mode: ${value ? "ON" : "OFF"}');
    notifyListeners();
  }

  Future<void> setTtsEnabled(bool value) async {
    _ttsEnabled = value;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('ttsEnabled', value);
    if (!value) await TtsService.instance.stop();
    _log('Speak responses: ${value ? "ON" : "OFF"}');
    notifyListeners();
  }

  Future<void> setProject(String? project) async {
    _selectedProject = project;
    _projectBrain = null;

    final prefs = await SharedPreferences.getInstance();
    if (project != null) {
      await prefs.setString('selectedProject', project);
      _loadProjectBrain(project);
    } else {
      await prefs.remove('selectedProject');
    }

    _log('Project: ${project ?? "none"}');
    notifyListeners();
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('baseUrl', url);
    _log('Backend URL: $url');
    _fetchProjects();
    _startPolling();
    notifyListeners();
  }

  void clearMessages() {
    final key = _selectedProject ?? _kGlobal;
    _projectMessages.remove(key);
    _activityLog.clear();
    _commandQueue.clear();
    _clearTaskProgress();
    notifyListeners();
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  void _addMessage(String role, String content, {String? imagePath}) {
    final key = _selectedProject ?? _kGlobal;
    _projectMessages.putIfAbsent(key, () => []).add(Message(
          id: '${DateTime.now().millisecondsSinceEpoch}_$role',
          role: role,
          content: content,
          timestamp: DateTime.now(),
          imagePath: imagePath,
        ));
    notifyListeners();
  }

  void _log(String entry) {
    final t = DateTime.now();
    final ts =
        '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}:${t.second.toString().padLeft(2, '0')}';
    _activityLog.insert(0, '[$ts] $entry');
    if (_activityLog.length > 50) _activityLog.removeLast();
  }

  String _shortLabel(String s) =>
      s.length > 40 ? '${s.substring(0, 40)}...' : s;

  GeraldStatus _parseStatus(String s) {
    switch (s.toLowerCase()) {
      case 'planning':
        return GeraldStatus.planning;
      case 'awaiting_approval':
      case 'awaiting':
        return GeraldStatus.awaiting;
      case 'working':
      case 'executing':
        return GeraldStatus.executing;
      case 'error':
        return GeraldStatus.error;
      case 'offline':
        return GeraldStatus.offline;
      case 'done':
      default:
        return GeraldStatus.idle;
    }
  }

  String _statusLabel(GeraldStatus s) {
    switch (s) {
      case GeraldStatus.idle:
        return 'idle';
      case GeraldStatus.planning:
        return 'planning';
      case GeraldStatus.awaiting:
        return 'awaiting approval';
      case GeraldStatus.executing:
        return 'executing';
      case GeraldStatus.error:
        return 'error';
      case GeraldStatus.offline:
        return 'offline';
    }
  }

  int _stagePercent(TaskStage s) {
    switch (s) {
      case TaskStage.none:
        return 0;
      case TaskStage.queued:
        return 5;
      case TaskStage.sending:
        return 15;
      case TaskStage.accepted:
        return 25;
      case TaskStage.working:
        return 45;
      case TaskStage.reviewing:
        return 75;
      case TaskStage.finalising:
        return 90;
      case TaskStage.complete:
        return 100;
      case TaskStage.error:
        return 0;
    }
  }

  String _stageName(TaskStage s) {
    switch (s) {
      case TaskStage.none:
        return '';
      case TaskStage.queued:
        return 'Queued';
      case TaskStage.sending:
        return 'Sending';
      case TaskStage.accepted:
        return 'Accepted';
      case TaskStage.working:
        return 'Claude Working';
      case TaskStage.reviewing:
        return 'Reviewing';
      case TaskStage.finalising:
        return 'Finalising';
      case TaskStage.complete:
        return 'Complete';
      case TaskStage.error:
        return 'Error';
    }
  }

  // ── Build Verification ─────────────────────────────────────────────────────

  Future<void> triggerBuildVerification({String flavor = 'debug'}) async {
    if (_buildTriggering) return;
    _buildTriggering = true;
    _log('Build verification started (flutter build apk --$flavor)');
    notifyListeners();

    try {
      final result = await _api.triggerBuild(
        flavor: flavor,
        project: _selectedProject ?? 'CommuteCoder',
      );
      final ok = result['ok'] as bool? ?? true;
      if (ok) {
        _log('Build triggered — polling for result...');
        await _pollBuildResult();
      } else {
        _log('Build trigger failed: ${result['error'] ?? 'unknown'}');
      }
    } catch (e) {
      _log('Build trigger error: $e');
    } finally {
      _buildTriggering = false;
      notifyListeners();
    }
  }

  Future<void> _pollBuildResult() async {
    for (int i = 0; i < 120; i++) {
      await Future<void>.delayed(const Duration(seconds: 5));
      try {
        final data = await _api.getBuildStatus();
        final isRunning = data['is_running'] as bool? ?? false;
        _buildResult = BuildResult.fromJson(data);
        notifyListeners();
        if (!isRunning) {
          final label = _buildResult.statusLabel;
          _log('Build result: $label (${_buildResult.errorCount} errors, ${_buildResult.warningCount} warnings)');
          if (_ttsEnabled) {
            TtsService.instance
                .speak('Build $label. ${_buildResult.errorCount} errors.')
                .ignore();
          }
          return;
        }
      } catch (_) {}
    }
    _log('Build verification polling timed out');
  }

  Future<void> refreshBuildStatus() async {
    try {
      final data = await _api.getBuildStatus();
      _buildResult = BuildResult.fromJson(data);
      notifyListeners();
    } catch (_) {}
  }

  // ── AI Provider ────────────────────────────────────────────────────────────

  Future<void> setAiProvider(AiProvider provider) async {
    await AiProviderService.instance.setActiveProvider(provider);
    _aiProvider = provider;
    _log('AI provider → ${AiProviderService.instance.activeProviderInfo.name}');
    notifyListeners();
    try {
      await AiProviderService.instance.syncToBackend(_baseUrl);
    } catch (_) {}
  }

  Future<void> setProviderApiKey(AiProvider provider, String key) async {
    await AiProviderService.instance.setApiKey(provider, key);
    _log('API key saved for ${provider.name}');
    try {
      if (provider == _aiProvider) {
        await AiProviderService.instance.syncToBackend(_baseUrl);
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _completeTimer?.cancel();
    _elapsedTimer?.cancel();
    super.dispose();
  }
}
