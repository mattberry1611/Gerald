import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart';
import '../providers/app_state.dart';
import '../theme.dart';
import 'conversation_orb.dart';

class PushToTalkButton extends StatefulWidget {
  const PushToTalkButton({super.key});

  @override
  State<PushToTalkButton> createState() => _PushToTalkButtonState();
}

class _PushToTalkButtonState extends State<PushToTalkButton>
    with TickerProviderStateMixin {
  final _speech = SpeechToText();
  bool _speechAvailable = false;
  String _recognized = '';

  bool _buttonHeld = false;

  bool _wasConversationMode = false;
  int _lastResumeTick = -1;
  bool _resumeScheduled = false;

  // Pulsing scale animation for PTT mode
  late AnimationController _pulse;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();

    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
    _pulseAnim = Tween(begin: 1.0, end: 1.15).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );

    _initSpeech();
  }

  Future<void> _initSpeech() async {
    _speechAvailable = await _speech.initialize(
      onStatus: (s) {
        // In PTT mode, ignore status-driven finalize while the button is held —
        // the recognizer fires 'notListening' mid-sentence during normal cycles.
        if ((s == 'done' || s == 'notListening') && !_buttonHeld) _finalize();
      },
      onError: (_) {
        if (mounted) context.read<AppState>().setListening(false);
      },
    );
    if (mounted) {
      setState(() {});
      if (_speechAvailable && context.read<AppState>().conversationMode) {
        _start();
      }
    }
  }

  void _finalize() {
    if (!mounted) return;
    final state = context.read<AppState>();
    state.setListening(false);
    if (_recognized.trim().isNotEmpty) {
      state.sendPrompt(_recognized.trim());
      _recognized = '';
    } else if (state.conversationMode) {
      _scheduleStart();
    }
  }

  Future<void> _start() async {
    if (!_speechAvailable || !mounted) return;
    if (_speech.isListening) return;
    HapticFeedback.mediumImpact();
    final state = context.read<AppState>();
    state.setListening(true);
    _recognized = '';
    // PTT mode: use a long pauseFor so natural mid-sentence pauses don't
    // finalize the recording while the button is still held down.
    final pauseFor = state.conversationMode
        ? const Duration(seconds: 3)
        : const Duration(seconds: 10);
    await _speech.listen(
      onResult: (r) => _recognized = r.recognizedWords,
      listenOptions: SpeechListenOptions(
        listenFor: const Duration(seconds: 60),
        pauseFor: pauseFor,
      ),
    );
  }

  Future<void> _stop() async {
    await _speech.stop();
    _finalize();
  }

  void _scheduleStart() {
    if (_resumeScheduled) return;
    _resumeScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _resumeScheduled = false;
      if (mounted) {
        final s = context.read<AppState>();
        if (s.conversationMode && !s.isLoading) {
          _start();
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final listening = state.isListening;
    final loading = state.isLoading;
    final speaking = state.isSpeaking;
    final convMode = state.conversationMode;
    final tick = state.resumeListenTick;

    if (_lastResumeTick == -1) {
      _lastResumeTick = tick;
    }

    if (convMode && !_wasConversationMode) {
      _wasConversationMode = true;
      _scheduleStart();
    } else if (!convMode && _wasConversationMode) {
      _wasConversationMode = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _speech.isListening) {
          _speech.cancel();
          context.read<AppState>().setListening(false);
        }
      });
    }

    if (convMode && tick > _lastResumeTick) {
      _lastResumeTick = tick;
      _scheduleStart();
    }

    if (convMode) {
      return _buildOrbView(listening, loading, speaking);
    } else {
      return _buildPttButton(listening, loading, speaking, context);
    }
  }

  // ── Mode A: Push-to-Talk ──────────────────────────────────────────────────

  Widget _buildPttButton(
      bool listening, bool loading, bool speaking, BuildContext ctx) {
    final screenH = MediaQuery.of(ctx).size.height;
    final isSmall = screenH < 620;

    final btnSize = isSmall ? 84.0 : 106.0;
    final glowSize = isSmall ? 106.0 : 130.0;
    final iconSize = isSmall ? 36.0 : 46.0;

    final Color color;
    final IconData icon;
    String label;

    if (speaking) {
      color = kAccentPurple;
      icon = Icons.volume_up_rounded;
      label = 'GERALD SPEAKING';
    } else if (loading) {
      color = kStatusPlanning;
      icon = Icons.hourglass_empty_rounded;
      label = 'PROCESSING...';
    } else if (listening) {
      color = kStatusError;
      icon = Icons.mic;
      label = 'LISTENING';
    } else {
      color = kAccentBlue;
      icon = Icons.mic_none_rounded;
      label = 'HOLD TO SPEAK';
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Listener(
          onPointerDown: (_) {
            if (loading || listening || speaking) return;
            _buttonHeld = true;
            _start();
          },
          onPointerUp: (_) {
            _buttonHeld = false;
            if (listening) _stop();
          },
          onPointerCancel: (_) {
            _buttonHeld = false;
            if (listening) _stop();
          },
          child: AnimatedBuilder(
            animation: _pulseAnim,
            builder: (_, __) => Transform.scale(
              scale: listening ? _pulseAnim.value : 1.0,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Outer glow
                  Container(
                    width: glowSize,
                    height: glowSize,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: color.withOpacity(listening ? 0.20 : 0.10),
                          blurRadius: 40,
                          spreadRadius: 10,
                        ),
                      ],
                    ),
                  ),
                  // Button circle
                  Container(
                    width: btnSize,
                    height: btnSize,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: color.withOpacity(0.12),
                      border: Border.all(
                        color: color.withOpacity(listening ? 0.9 : 0.6),
                        width: 2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: color.withOpacity(listening ? 0.55 : 0.30),
                          blurRadius: listening ? 28 : 18,
                          spreadRadius: listening ? 4 : 2,
                        ),
                      ],
                    ),
                    child: Icon(icon, color: color, size: iconSize),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        AnimatedDefaultTextStyle(
          duration: const Duration(milliseconds: 200),
          style: TextStyle(
            color: color.withOpacity(0.85),
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 2,
          ),
          child: Text(label),
        ),
      ],
    );
  }

  // ── Mode B: Conversation (Orb) ────────────────────────────────────────────

  Widget _buildOrbView(bool listening, bool loading, bool speaking) {
    final OrbState orbState;
    final String label;

    if (speaking) {
      orbState = OrbState.speaking;
      label = 'SPEAKING...';
    } else if (loading) {
      orbState = OrbState.thinking;
      label = 'PROCESSING...';
    } else if (listening) {
      orbState = OrbState.listening;
      label = 'LISTENING...';
    } else {
      orbState = OrbState.idle;
      label = 'READY';
    }

    final color = switch (orbState) {
      OrbState.speaking => kAccentPurple,
      OrbState.listening => kAccentGreen,
      OrbState.thinking => kAccentBlue,
      OrbState.idle => kStatusIdle,
    };

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ConversationOrb(state: orbState),
        const SizedBox(height: 8),
        AnimatedDefaultTextStyle(
          duration: const Duration(milliseconds: 250),
          style: TextStyle(
            color: color.withOpacity(0.85),
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 2,
          ),
          child: Text(label),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    _speech.cancel();
    super.dispose();
  }
}
