import 'dart:math';
import 'package:flutter/material.dart';
import '../theme.dart';
import 'home_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late final AnimationController _fadeCtrl;
  late final AnimationController _burstCtrl;
  late final AnimationController _orbitCtrl;
  late final Animation<double> _fade;
  late final Animation<double> _burstScale;
  late final Animation<double> _burstOpacity;

  @override
  void initState() {
    super.initState();

    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _burstCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    );
    _orbitCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();

    _fade = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _burstScale = Tween(begin: 0.5, end: 1.8).animate(
      CurvedAnimation(parent: _burstCtrl, curve: Curves.easeOut),
    );
    _burstOpacity = Tween(begin: 0.7, end: 0.0).animate(
      CurvedAnimation(parent: _burstCtrl, curve: Curves.easeOut),
    );

    _fadeCtrl.forward();
    _burstCtrl.forward();

    Future.delayed(const Duration(milliseconds: 2400), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const HomeScreen(),
            transitionsBuilder: (_, anim, __, child) =>
                FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 500),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _burstCtrl.dispose();
    _orbitCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBgColor,
      body: FadeTransition(
        opacity: _fade,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Hero: globe with orbital rings
              AnimatedBuilder(
                animation: Listenable.merge([_burstCtrl, _orbitCtrl]),
                builder: (_, child) => CustomPaint(
                  painter: _SplashRingsPainter(
                    orbitAngle: _orbitCtrl.value * 2 * pi,
                    burstScale: _burstScale.value,
                    burstOpacity: _burstOpacity.value,
                  ),
                  child: child,
                ),
                child: SizedBox(
                  width: 300,
                  height: 300,
                  child: Center(
                    child: Container(
                      width: 160,
                      height: 160,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: kAccentBlue.withOpacity(0.45),
                            blurRadius: 60,
                            spreadRadius: 20,
                          ),
                          BoxShadow(
                            color: kAccentBlue.withOpacity(0.18),
                            blurRadius: 110,
                            spreadRadius: 45,
                          ),
                        ],
                      ),
                      child: ClipOval(
                        child: Image.asset(
                          'assets/gerald_logo.png',
                          fit: BoxFit.cover,
                        ),
                      ),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 24),

              const Text(
                'GERALD',
                style: TextStyle(
                  fontWeight: FontWeight.w900,
                  letterSpacing: 14,
                  fontSize: 36,
                  color: kTextPrimary,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'YOUR AI COMMAND BRAIN',
                style: TextStyle(
                  color: kAccentBlue.withOpacity(0.75),
                  fontSize: 11,
                  letterSpacing: 4.0,
                  fontWeight: FontWeight.w500,
                ),
              ),

              const SizedBox(height: 56),

              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 1.5,
                  color: kAccentBlue.withOpacity(0.5),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SplashRingsPainter extends CustomPainter {
  final double orbitAngle;
  final double burstScale;
  final double burstOpacity;

  const _SplashRingsPainter({
    required this.orbitAngle,
    required this.burstScale,
    required this.burstOpacity,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final sphereR = size.width * 0.267; // ~80px on 300-wide canvas

    // Ambient background glow behind the globe
    canvas.drawCircle(
      center,
      size.width * 0.48,
      Paint()
        ..shader = RadialGradient(
          colors: [
            kAccentBlue.withOpacity(0.10),
            kAccentBlue.withOpacity(0.0),
          ],
        ).createShader(
            Rect.fromCircle(center: center, radius: size.width * 0.48)),
    );

    // Burst ring (entry animation only)
    if (burstOpacity > 0.01) {
      canvas.drawCircle(
        center,
        sphereR * burstScale,
        Paint()
          ..color = kAccentBlue.withOpacity(burstOpacity * 0.55)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5,
      );
    }

    // Orbital ring 1: primary wide tilted ellipse
    _drawRing(
      canvas,
      center,
      majorR: sphereR * 1.75,
      minorR: sphereR * 0.28,
      tilt: -0.38 + orbitAngle * 0.015,
      opacity: 0.55,
    );

    // Orbital ring 2: secondary ring at a different angle
    _drawRing(
      canvas,
      center,
      majorR: sphereR * 1.60,
      minorR: sphereR * 0.18,
      tilt: 0.52 + orbitAngle * 0.010,
      opacity: 0.35,
    );
  }

  void _drawRing(
    Canvas canvas,
    Offset center, {
    required double majorR,
    required double minorR,
    required double tilt,
    required double opacity,
  }) {
    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(tilt);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset.zero,
        width: majorR * 2,
        height: minorR * 2,
      ),
      Paint()
        ..color = kAccentBlue.withOpacity(opacity)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(_SplashRingsPainter old) =>
      old.orbitAngle != orbitAngle ||
      old.burstScale != burstScale ||
      old.burstOpacity != burstOpacity;
}
