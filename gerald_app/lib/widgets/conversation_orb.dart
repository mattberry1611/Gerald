import 'dart:math';
import 'package:flutter/material.dart';
import '../theme.dart';

enum OrbState { idle, listening, thinking, speaking }

class ConversationOrb extends StatefulWidget {
  final OrbState state;
  final double size;

  const ConversationOrb({
    super.key,
    required this.state,
    this.size = 110,
  });

  @override
  State<ConversationOrb> createState() => _ConversationOrbState();
}

class _ConversationOrbState extends State<ConversationOrb>
    with TickerProviderStateMixin {
  late AnimationController _rotCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _waveCtrl;
  late AnimationController _burstCtrl;

  late final List<_Particle> _particles;

  @override
  void initState() {
    super.initState();

    // Build particles once with fixed seed for determinism
    _particles = _buildParticles(seed: 73);

    _rotCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..repeat();

    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat(reverse: true);

    _waveCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();

    _burstCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );

    _applyState(widget.state);
  }

  @override
  void didUpdateWidget(ConversationOrb old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state) {
      if (old.state == OrbState.idle && widget.state != OrbState.idle) {
        _burstCtrl.forward(from: 0);
      }
      _applyState(widget.state);
    }
  }

  void _applyState(OrbState s) {
    _rotCtrl.duration = switch (s) {
      OrbState.speaking => const Duration(seconds: 3),
      OrbState.listening => const Duration(seconds: 5),
      OrbState.thinking => const Duration(seconds: 6),
      OrbState.idle => const Duration(seconds: 12),
    };

    _pulseCtrl.duration = switch (s) {
      OrbState.speaking => const Duration(milliseconds: 700),
      OrbState.listening => const Duration(milliseconds: 1100),
      OrbState.thinking => const Duration(milliseconds: 1600),
      OrbState.idle => const Duration(milliseconds: 2800),
    };
  }

  Color get _color => switch (widget.state) {
        OrbState.speaking => kAccentPurple,
        OrbState.listening => kAccentGreen,
        OrbState.thinking => kAccentBlue,
        OrbState.idle => const Color(0xFF3E4060),
      };

  bool get _isActive => widget.state != OrbState.idle;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_rotCtrl, _pulseCtrl, _waveCtrl, _burstCtrl]),
      builder: (_, __) => CustomPaint(
        painter: _OrbPainter(
          color: _color,
          rotation: _rotCtrl.value * 2 * pi,
          pulse: _pulseCtrl.value,
          wave: _waveCtrl.value,
          burst: _burstCtrl.value,
          particles: _particles,
          isSpeaking: widget.state == OrbState.speaking,
          isActive: _isActive,
        ),
        size: Size(widget.size, widget.size),
      ),
    );
  }

  @override
  void dispose() {
    _rotCtrl.dispose();
    _pulseCtrl.dispose();
    _waveCtrl.dispose();
    _burstCtrl.dispose();
    super.dispose();
  }

  static List<_Particle> _buildParticles({required int seed}) {
    final rng = Random(seed);
    final list = <_Particle>[];

    // Three orbital rings
    const ringTilts = [0.25, 1.05, 1.85];
    const ringSpeeds = [1.0, 0.7, 1.3];
    const ringCounts = [6, 5, 4];

    for (int r = 0; r < ringTilts.length; r++) {
      for (int i = 0; i < ringCounts[r]; i++) {
        final baseAngle = (i / ringCounts[r]) * 2 * pi + rng.nextDouble() * 0.4;
        list.add(_Particle(
          orbitTilt: ringTilts[r],
          orbitRadius: 0.68 + rng.nextDouble() * 0.10,
          startAngle: baseAngle,
          speedFactor: ringSpeeds[r] * (0.85 + rng.nextDouble() * 0.3),
          size: 2.2 + rng.nextDouble() * 2.8,
        ));
      }
    }

    // Scattered micro-particles
    for (int i = 0; i < 5; i++) {
      list.add(_Particle(
        orbitTilt: rng.nextDouble() * pi,
        orbitRadius: 0.50 + rng.nextDouble() * 0.20,
        startAngle: rng.nextDouble() * 2 * pi,
        speedFactor: 0.4 + rng.nextDouble() * 0.5,
        size: 1.2 + rng.nextDouble() * 1.6,
      ));
    }

    return list;
  }
}

// ── Particle ──────────────────────────────────────────────────────────────────

class _Particle {
  final double orbitTilt;
  final double orbitRadius;
  final double startAngle;
  final double speedFactor;
  final double size;

  const _Particle({
    required this.orbitTilt,
    required this.orbitRadius,
    required this.startAngle,
    required this.speedFactor,
    required this.size,
  });
}

// ── Projected particle ────────────────────────────────────────────────────────

class _PData {
  final Offset pos;
  final double z;
  final double r;
  final double opacity;
  const _PData({
    required this.pos,
    required this.z,
    required this.r,
    required this.opacity,
  });
}

// ── Orb painter ───────────────────────────────────────────────────────────────

class _OrbPainter extends CustomPainter {
  final Color color;
  final double rotation;
  final double pulse;
  final double wave;
  final double burst;
  final List<_Particle> particles;
  final bool isSpeaking;
  final bool isActive;

  const _OrbPainter({
    required this.color,
    required this.rotation,
    required this.pulse,
    required this.wave,
    required this.burst,
    required this.particles,
    required this.isSpeaking,
    required this.isActive,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseR = size.width * 0.26;
    final pulseScale = 1.0 + pulse * (isActive ? 0.10 : 0.04) + burst * 0.18;
    final coreR = baseR * pulseScale;

    // Wide ambient glow
    _drawGlow(canvas, center, baseR * 4.0,
        color.withOpacity(0.07 + pulse * 0.05));

    // Tight mid glow
    _drawGlow(canvas, center, baseR * 2.2,
        color.withOpacity(0.15 + pulse * 0.10));

    // Speaking wave rings
    if (isSpeaking) {
      for (int i = 0; i < 4; i++) {
        final phase = (wave + i * 0.25) % 1.0;
        final waveR = coreR + phase * baseR * 2.0;
        final wavePaint = Paint()
          ..color = color.withOpacity((1.0 - phase) * 0.32)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5;
        canvas.drawCircle(center, waveR, wavePaint);
      }
    }

    // Compute + sort particles
    final pData = _projectParticles(center, baseR);

    // Back layer particles
    for (final pd in pData) {
      if (pd.z < 0) _drawParticle(canvas, pd);
    }

    // Core sphere
    _drawCore(canvas, center, coreR);

    // Specular highlight
    _drawHighlight(canvas, center, coreR);

    // Front layer particles
    for (final pd in pData) {
      if (pd.z >= 0) _drawParticle(canvas, pd);
    }

    // Burst ring
    if (burst > 0) {
      final burstR = baseR + burst * baseR * 1.6;
      final burstPaint = Paint()
        ..color = color.withOpacity((1.0 - burst) * 0.55)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;
      canvas.drawCircle(center, burstR, burstPaint);
    }
  }

  void _drawGlow(Canvas canvas, Offset center, double radius, Color c) {
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [c, c.withOpacity(0.0)],
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawCircle(center, radius, paint);
  }

  void _drawCore(Canvas canvas, Offset center, double r) {
    final highlight = Color.lerp(Colors.white, color, 0.22)!;
    final shadow = Color.lerp(color, Colors.black, 0.40)!;
    final paint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.35, -0.45),
        radius: 0.88,
        colors: [highlight, color, shadow],
        stops: const [0.0, 0.52, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, paint);
  }

  void _drawHighlight(Canvas canvas, Offset center, double coreR) {
    final hlCenter = center + Offset(-coreR * 0.28, -coreR * 0.30);
    final hlR = coreR * 0.30;
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.white.withOpacity(0.42),
          Colors.white.withOpacity(0.0),
        ],
      ).createShader(Rect.fromCircle(center: hlCenter, radius: hlR));
    canvas.drawCircle(hlCenter, hlR, paint);
  }

  List<_PData> _projectParticles(Offset center, double baseR) {
    final list = <_PData>[];
    for (final p in particles) {
      final angle = p.startAngle + rotation * p.speedFactor;
      final cosT = cos(p.orbitTilt);
      final sinT = sin(p.orbitTilt);
      final ox = cos(angle) * p.orbitRadius;
      final oy = sin(angle) * p.orbitRadius;
      final projX = ox;
      final projY = oy * cosT;
      final projZ = oy * sinT;

      final depth = (projZ + 1) / 2;
      list.add(_PData(
        pos: center + Offset(projX, projY) * baseR,
        z: projZ,
        r: p.size * (0.5 + 0.5 * depth),
        opacity: 0.25 + 0.75 * depth,
      ));
    }
    list.sort((a, b) => a.z.compareTo(b.z));
    return list;
  }

  void _drawParticle(Canvas canvas, _PData pd) {
    final paint = Paint()
      ..color = color.withOpacity(pd.opacity * (0.6 + pulse * 0.4));
    canvas.drawCircle(pd.pos, pd.r, paint);
  }

  @override
  bool shouldRepaint(_OrbPainter old) =>
      old.rotation != rotation ||
      old.pulse != pulse ||
      old.wave != wave ||
      old.burst != burst ||
      old.color != color;
}
