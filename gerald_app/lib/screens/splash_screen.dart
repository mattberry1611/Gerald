import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/conversation_orb.dart';
import 'home_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fadeCtrl;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();

    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _fade = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _fadeCtrl.forward();

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
              const ConversationOrb(state: OrbState.idle, size: 200),
              const SizedBox(height: 32),
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
