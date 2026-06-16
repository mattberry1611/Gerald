import 'dart:async';
import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  static final TtsService instance = TtsService._();
  TtsService._();

  final FlutterTts _tts = FlutterTts();
  bool _initialized = false;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;

  bool get isSpeaking => _isSpeaking;

  /// Fired on the main isolate whenever speaking state toggles.
  void Function(bool speaking)? onSpeakingChanged;

  Future<void> init() async {
    if (_initialized) return;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.50);
    await _tts.setVolume(1.0);
    await _tts.setPitch(0.95);

    _tts.setStartHandler(() => _setActive(true));
    _tts.setCompletionHandler(_handleDone);
    _tts.setCancelHandler(_handleDone);
    _tts.setErrorHandler((_) => _handleDone());

    _initialized = true;
  }

  void _setActive(bool value) {
    if (_isSpeaking == value) return;
    _isSpeaking = value;
    onSpeakingChanged?.call(value);
  }

  void _handleDone() {
    _setActive(false);
    final c = _speakCompleter;
    _speakCompleter = null;
    if (c != null && !c.isCompleted) c.complete();
  }

  Future<void> speak(String text) async {
    if (!_initialized) await init();
    await _tts.stop();
    _speakCompleter = Completer<void>();
    await _tts.speak(text);
    await _speakCompleter!.future.timeout(
      const Duration(seconds: 120),
      onTimeout: _handleDone,
    );
  }

  Future<void> stop() async {
    await _tts.stop();
    _handleDone();
  }
}
