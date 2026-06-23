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

  @override
  void initState() {
    super.initState();

    _rotCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    )..repeat();

    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3600),
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
      OrbState.speaking  => const Duration(seconds: 3),
      OrbState.listening => const Duration(seconds: 5),
      OrbState.thinking  => const Duration(seconds: 6),
      OrbState.idle      => const Duration(seconds: 18),
    };

    _pulseCtrl.duration = switch (s) {
      OrbState.speaking  => const Duration(milliseconds: 650),
      OrbState.listening => const Duration(milliseconds: 1100),
      OrbState.thinking  => const Duration(milliseconds: 2000),
      OrbState.idle      => const Duration(milliseconds: 3600),
    };
  }

  Color get _accentColor => switch (widget.state) {
        OrbState.speaking  => kAccentPurple,
        OrbState.listening => kAccentGreen,
        OrbState.thinking  => kAccentBlue,
        OrbState.idle      => kAccentBlue,
      };

  bool get _isActive => widget.state != OrbState.idle;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_rotCtrl, _pulseCtrl, _waveCtrl, _burstCtrl]),
      builder: (_, __) => CustomPaint(
        painter: _OrbPainter(
          accentColor: _accentColor,
          rotation: _rotCtrl.value * 2 * pi,
          pulse: _pulseCtrl.value,
          wave: _waveCtrl.value,
          burst: _burstCtrl.value,
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
}

// ── Ring definitions ──────────────────────────────────────────────────────────

class _Ring {
  final double majorFactor;
  final double minorFactor;
  final double baseTilt;
  final double speedFactor;
  final double opacity;

  const _Ring({
    required this.majorFactor,
    required this.minorFactor,
    required this.baseTilt,
    required this.speedFactor,
    required this.opacity,
  });
}

const List<_Ring> _kRings = [
  _Ring(majorFactor: 1.72, minorFactor: 0.30, baseTilt: -0.38, speedFactor: 1.00, opacity: 0.85),
  _Ring(majorFactor: 1.58, minorFactor: 0.20, baseTilt:  0.55, speedFactor: 0.75, opacity: 0.70),
  _Ring(majorFactor: 1.44, minorFactor: 0.13, baseTilt:  1.20, speedFactor: 0.55, opacity: 0.55),
];

// ── Orb painter ───────────────────────────────────────────────────────────────

class _OrbPainter extends CustomPainter {
  final Color accentColor;
  final double rotation;
  final double pulse;
  final double wave;
  final double burst;
  final bool isSpeaking;
  final bool isActive;

  const _OrbPainter({
    required this.accentColor,
    required this.rotation,
    required this.pulse,
    required this.wave,
    required this.burst,
    required this.isSpeaking,
    required this.isActive,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseR  = size.width * 0.30;
    final pulseScale = 1.0 + pulse * (isActive ? 0.13 : 0.07);
    final coreR  = baseR * pulseScale;
    final glowBoost = isActive ? 2.8 : 1.8;

    // ── Bloom glow (wide → tight, dramatically stronger) ──────────────────
    _drawGlow(canvas, center, baseR * 7.0,
        accentColor.withOpacity((0.08 + pulse * 0.06) * glowBoost));
    _drawGlow(canvas, center, baseR * 5.0,
        accentColor.withOpacity((0.18 + pulse * 0.10) * glowBoost));
    _drawGlow(canvas, center, baseR * 3.0,
        accentColor.withOpacity((0.35 + pulse * 0.18) * glowBoost));
    _drawGlow(canvas, center, baseR * 1.85,
        accentColor.withOpacity((0.55 + pulse * 0.20) * glowBoost));
    _drawGlow(canvas, center, baseR * 1.30,
        accentColor.withOpacity((0.45 + pulse * 0.15) * glowBoost));

    // ── Back-half orbital rings (behind sphere) ────────────────────────────
    canvas.save();
    canvas.clipRect(Rect.fromLTRB(0, center.dy, size.width, size.height));
    _drawAllRings(canvas, center, baseR);
    canvas.restore();

    // ── Core sphere ────────────────────────────────────────────────────────
    _drawCore(canvas, center, coreR);
    _drawHighlight(canvas, center, coreR);
    _drawG(canvas, center, coreR);

    // ── Front-half orbital rings (in front of sphere) ──────────────────────
    canvas.save();
    canvas.clipRect(Rect.fromLTRB(0, 0, size.width, center.dy));
    _drawAllRings(canvas, center, baseR);
    canvas.restore();

    // ── Speaking wave rings ────────────────────────────────────────────────
    if (isSpeaking) {
      for (int i = 0; i < 5; i++) {
        final phase = (wave + i * 0.20) % 1.0;
        final waveR = coreR + phase * baseR * 2.2;
        canvas.drawCircle(
          center,
          waveR,
          Paint()
            ..color = accentColor.withOpacity((1.0 - phase) * 0.42)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5,
        );
      }
    }

    // ── Burst ring (state-transition effect) ───────────────────────────────
    if (burst > 0) {
      canvas.drawCircle(
        center,
        baseR + burst * baseR * 1.6,
        Paint()
          ..color = accentColor.withOpacity((1.0 - burst) * 0.55)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.0,
      );
    }
  }

  void _drawAllRings(Canvas canvas, Offset center, double baseR) {
    for (final ring in _kRings) {
      final tilt = ring.baseTilt + rotation * ring.speedFactor * 0.08;
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(tilt);

      final rect = Rect.fromCenter(
        center: Offset.zero,
        width:  ring.majorFactor * baseR * 2,
        height: ring.minorFactor * baseR * 2,
      );

      // Outer glow halo — wide, blurred
      canvas.drawOval(
        rect,
        Paint()
          ..color = accentColor.withOpacity(ring.opacity * 0.28)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 10.0
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5.0),
      );

      // Mid glow layer
      canvas.drawOval(
        rect,
        Paint()
          ..color = accentColor.withOpacity(ring.opacity * 0.55)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 4.0
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2.0),
      );

      // Bright core trail — white-blue tinted
      canvas.drawOval(
        rect,
        Paint()
          ..color = Color.lerp(accentColor, Colors.white, 0.60)!
              .withOpacity(ring.opacity * 0.80)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4,
      );

      canvas.restore();
    }
  }

  void _drawGlow(Canvas canvas, Offset center, double radius, Color c) {
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..shader = RadialGradient(
          colors: [c, c.withOpacity(0.0)],
        ).createShader(Rect.fromCircle(center: center, radius: radius)),
    );
  }

  void _drawCore(Canvas canvas, Offset center, double r) {
    canvas.drawCircle(
      center,
      r,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.38, -0.45),
          radius: 0.90,
          colors: const [
            Color(0xFFFFFFFF),  // pure white top-left
            Color(0xFFB0D8FF),  // bright blue-white
            Color(0xFF2979FF),  // electric blue mid
            Color(0xFF1050B0),  // deep blue
            Color(0xFF030C1E),  // near-black navy edge
          ],
          stops: const [0.0, 0.18, 0.45, 0.72, 1.0],
        ).createShader(Rect.fromCircle(center: center, radius: r)),
    );
  }

  void _drawHighlight(Canvas canvas, Offset center, double coreR) {
    // Primary highlight — large, vivid white-blue spot
    final hlCenter = center + Offset(-coreR * 0.30, -coreR * 0.32);
    final hlR = coreR * 0.38;
    canvas.drawCircle(
      hlCenter,
      hlR,
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withOpacity(0.92),
            Colors.white.withOpacity(0.0),
          ],
        ).createShader(Rect.fromCircle(center: hlCenter, radius: hlR)),
    );

    // Specular micro-point — tiny pure-white hotspot
    final spCenter = center + Offset(-coreR * 0.36, -coreR * 0.38);
    final spR = coreR * 0.10;
    canvas.drawCircle(
      spCenter,
      spR,
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withOpacity(1.0),
            Colors.white.withOpacity(0.0),
          ],
        ).createShader(Rect.fromCircle(center: spCenter, radius: spR)),
    );
  }

  void _drawG(Canvas canvas, Offset center, double coreR) {
    final tp = TextPainter(
      text: TextSpan(
        text: 'G',
        style: TextStyle(
          color: Colors.white,
          fontSize: coreR * 1.02,
          fontWeight: FontWeight.w700,
          height: 1.0,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(
      canvas,
      center + Offset(-tp.width * 0.50, -tp.height * 0.50),
    );
  }

  @override
  bool shouldRepaint(_OrbPainter old) =>
      old.rotation    != rotation    ||
      old.pulse       != pulse       ||
      old.wave        != wave        ||
      old.burst       != burst       ||
      old.accentColor != accentColor ||
      old.isActive    != isActive;
}
