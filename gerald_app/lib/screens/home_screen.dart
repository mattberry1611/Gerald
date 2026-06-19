import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/app_state.dart';
import '../services/build_verification_service.dart';
import '../theme.dart';
import '../widgets/push_to_talk_button.dart';
import '../widgets/message_bubble.dart';
import '../widgets/status_panel.dart';
import '../widgets/activity_log.dart';
import '../widgets/project_selector.dart';
import 'settings_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final mediaQuery = MediaQuery.of(context);
    final keyboardVisible = mediaQuery.viewInsets.bottom > 0;
    final bottomPad = mediaQuery.padding.bottom;
    final screenH = mediaQuery.size.height;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: kBgColor,
      appBar: _buildAppBar(context, state),
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // Gradient separator
            Container(
              height: 1,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.transparent,
                    kAccentBlue.withOpacity(0.4),
                    Colors.transparent,
                  ],
                ),
              ),
            ),

            // Status panel — hidden when idle with no active task
            if (state.status != GeraldStatus.idle ||
                state.hasActiveTask ||
                state.isSpeaking)
              const StatusPanel(),

            // Conversation area
            Expanded(
              child: state.messages.isEmpty
                  ? const _EmptyState()
                  : ListView.builder(
                      reverse: true,
                      padding: const EdgeInsets.fromLTRB(0, 12, 0, 8),
                      itemCount: state.messages.length,
                      itemBuilder: (_, i) {
                        final msg =
                            state.messages[state.messages.length - 1 - i];
                        return MessageBubble(message: msg);
                      },
                    ),
            ),

            // Unified TYPE / SPEAK input section
            _InputSection(
              state: state,
              bottomPad: bottomPad,
              screenH: screenH,
              keyboardVisible: keyboardVisible,
            ),
          ],
        ),
      ),
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, AppState state) {
    final isIdle = state.status == GeraldStatus.idle && !state.isSpeaking;

    return AppBar(
      toolbarHeight: 62,
      titleSpacing: 0,
      title: Padding(
        padding: const EdgeInsets.only(left: 16),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Logo
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(9),
                boxShadow: [
                  BoxShadow(
                    color: kAccentBlue.withOpacity(0.35),
                    blurRadius: 14,
                    spreadRadius: 1,
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(9),
                child: Image.asset(
                  'assets/gerald_logo.png',
                  fit: BoxFit.cover,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'GERALD',
                    style: TextStyle(
                      fontWeight: FontWeight.w900,
                      letterSpacing: 5,
                      fontSize: 20,
                      color: kTextPrimary,
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'AI CODING SUPERVISOR',
                        style: TextStyle(
                          fontSize: 8.5,
                          letterSpacing: 2.5,
                          color: kAccentBlue.withOpacity(0.7),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      if (isIdle) ...[
                        const SizedBox(width: 7),
                        Container(
                          width: 5,
                          height: 5,
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            color: kStatusIdle,
                          ),
                        ),
                        const SizedBox(width: 3),
                        const Text(
                          'IDLE',
                          style: TextStyle(
                            fontSize: 7.5,
                            letterSpacing: 1.5,
                            color: kStatusIdle,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        const ProjectSelector(),
        const SizedBox(width: 2),
        IconButton(
          icon: const Icon(Icons.tune_rounded, size: 22),
          color: kTextSecondary,
          tooltip: 'Settings',
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const SettingsScreen()),
          ),
        ),
        const SizedBox(width: 4),
      ],
    );
  }
}

// ── Input section (unified TYPE / SPEAK) ──────────────────────────────────────

class _InputSection extends StatefulWidget {
  final AppState state;
  final double bottomPad;
  final double screenH;
  final bool keyboardVisible;

  const _InputSection({
    required this.state,
    required this.bottomPad,
    required this.screenH,
    required this.keyboardVisible,
  });

  @override
  State<_InputSection> createState() => _InputSectionState();
}

class _InputSectionState extends State<_InputSection> {
  bool _speakMode = false;
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    _focusNode.requestFocus();
    widget.state.sendPrompt(text);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final isSmall = widget.screenH < 620;
    final vPad = isSmall ? 8.0 : 10.0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (!isSmall) const ActivityLog(),
        Container(
          decoration: BoxDecoration(
            color: kSurfaceColor,
            border: Border(top: BorderSide(color: kBorderColor)),
          ),
          padding: EdgeInsets.fromLTRB(16, vPad, 16, widget.bottomPad + vPad),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // TYPE | SPEAK top-level toggle
              _buildInputToggle(isSmall),
              const SizedBox(height: 10),
              // Active input
              if (_speakMode)
                _buildSpeakContent(state, isSmall)
              else
                _buildTextField(state),
              SizedBox(height: isSmall ? 8.0 : 10.0),
              _UtilitySubRow(state: state),
              SizedBox(height: isSmall ? 2.0 : 4.0),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInputToggle(bool isSmall) {
    final height = isSmall ? 34.0 : 40.0;
    final fontSize = isSmall ? 9.0 : 10.0;

    return Container(
      height: height,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kBorderColor),
      ),
      child: Row(
        children: [
          _InputToggleSegment(
            label: 'TYPE',
            icon: Icons.keyboard_outlined,
            active: !_speakMode,
            fontSize: fontSize,
            onTap: () {
              setState(() => _speakMode = false);
              Future.microtask(() => _focusNode.requestFocus());
            },
          ),
          _InputToggleSegment(
            label: 'SPEAK',
            icon: Icons.mic_none_rounded,
            active: _speakMode,
            fontSize: fontSize,
            onTap: () => setState(() => _speakMode = true),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField(AppState state) {
    final loading = state.isLoading;

    return Container(
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kAccentBlue.withOpacity(0.65), width: 1.5),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              minLines: 1,
              maxLines: 4,
              style: const TextStyle(
                fontSize: 14,
                color: kTextPrimary,
                height: 1.4,
              ),
              decoration: InputDecoration(
                hintText: 'Type a message to Gerald…',
                hintStyle: TextStyle(color: Colors.white.withOpacity(0.38), fontSize: 14),
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                filled: false,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                isDense: true,
              ),
              onSubmitted: (_) => _send(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 0, 6, 6),
            child: Tooltip(
              message: 'Send message',
              child: GestureDetector(
                onTap: loading ? null : _send,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: loading ? kBorderColor : kAccentBlue,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    Icons.send_rounded,
                    size: 18,
                    color: loading ? kTextMuted : Colors.white,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSpeakContent(AppState state, bool isSmall) {
    final convMode = state.conversationMode;
    final microcopy = convMode
        ? 'Gerald listens automatically after each reply'
        : 'Hold the mic button, speak, then release to send';

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _ModeSelector(state: state, compact: isSmall),
        const SizedBox(height: 6),
        Text(
          microcopy,
          style: TextStyle(
            fontSize: 10,
            color: kTextSecondary.withOpacity(0.8),
            height: 1.3,
          ),
          textAlign: TextAlign.center,
        ),
        SizedBox(height: isSmall ? 8.0 : 12.0),
        const PushToTalkButton(),
        SizedBox(height: isSmall ? 6.0 : 8.0),
      ],
    );
  }
}

// ── Input toggle segment ──────────────────────────────────────────────────────

class _InputToggleSegment extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool active;
  final double fontSize;
  final VoidCallback onTap;

  const _InputToggleSegment({
    required this.label,
    required this.icon,
    required this.active,
    required this.fontSize,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            color: active ? kAccentBlue.withOpacity(0.18) : Colors.transparent,
            borderRadius: BorderRadius.circular(7),
            border: active
                ? Border.all(color: kAccentBlue.withOpacity(0.55))
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 11,
                color: active ? kAccentBlue : kTextSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  color: active ? kAccentBlue : kTextSecondary,
                  fontSize: fontSize,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Compact bar (keyboard visible) ────────────────────────────────────────────

class _CompactBar extends StatelessWidget {
  final AppState state;
  const _CompactBar({required this.state});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(top: BorderSide(color: kBorderColor)),
      ),
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _UtilityButton(
            icon: Icons.attach_file_rounded,
            tooltip: 'Attach image',
            onPressed: () => _pickImage(context, state),
          ),
          if (state.isSpeaking)
            _UtilityButton(
              icon: Icons.stop_circle_outlined,
              active: true,
              activeColor: kAccentPurple,
              tooltip: 'Stop speaking',
              onPressed: state.stopSpeaking,
            ),
          _UtilityButton(
            icon: Icons.delete_sweep_outlined,
            tooltip: 'Clear conversation',
            onPressed: () => _confirmClear(context, state),
          ),
        ],
      ),
    );
  }
}

// ── Mode selector (COMMAND / CONVERSE — shown only in SPEAK mode) ─────────────

class _ModeSelector extends StatelessWidget {
  final AppState state;
  final bool compact;
  const _ModeSelector({required this.state, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final convMode = state.conversationMode;
    final height = compact ? 34.0 : 40.0;
    final fontSize = compact ? 9.0 : 10.0;

    return Row(
      children: [
        Expanded(
          child: Container(
            height: height,
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              color: kSurface2,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: kBorderColor),
            ),
            child: Row(
              children: [
                // COMMAND segment
                Expanded(
                  child: Tooltip(
                    message: 'COMMAND — Hold mic, speak your instruction, release to send',
                    child: GestureDetector(
                      onTap: () => state.setConversationMode(false),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 160),
                        curve: Curves.easeInOut,
                        decoration: BoxDecoration(
                          color: !convMode
                              ? kAccentBlue.withOpacity(0.22)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(7),
                          border: !convMode
                              ? Border.all(color: kAccentBlue.withOpacity(0.65))
                              : null,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.touch_app_outlined,
                              size: 11,
                              color: !convMode ? kAccentBlue : kTextSecondary,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              'COMMAND',
                              style: TextStyle(
                                color: !convMode ? kAccentBlue : kTextSecondary,
                                fontSize: fontSize,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.0,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                // CONVERSE segment
                Expanded(
                  child: Tooltip(
                    message: 'CONVERSE — Gerald listens automatically after each reply',
                    child: GestureDetector(
                      onTap: () => state.setConversationMode(true),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 160),
                        curve: Curves.easeInOut,
                        decoration: BoxDecoration(
                          color: convMode
                              ? kAccentBlue.withOpacity(0.22)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(7),
                          border: convMode
                              ? Border.all(color: kAccentBlue.withOpacity(0.65))
                              : null,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.record_voice_over_outlined,
                              size: 11,
                              color: convMode ? kAccentBlue : kTextSecondary,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              'CONVERSE',
                              style: TextStyle(
                                color: convMode ? kAccentBlue : kTextSecondary,
                                fontSize: fontSize,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.0,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 6),
        Tooltip(
          message: 'About input modes',
          child: GestureDetector(
            onTap: () => _showModeInfo(context),
            child: Icon(
              Icons.info_outline_rounded,
              size: 18,
              color: kTextSecondary.withOpacity(0.5),
            ),
          ),
        ),
      ],
    );
  }

  static void _showModeInfo(BuildContext context) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: kBorderColor,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'VOICE MODES',
                style: TextStyle(
                  color: kTextSecondary,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2.5,
                ),
              ),
              const SizedBox(height: 16),
              const _ModeInfoRow(
                icon: Icons.touch_app_outlined,
                title: 'COMMAND',
                subtitle: 'One-shot voice commands',
                description:
                    'Hold the mic button, speak your command, then release. '
                    'Gerald processes it once. Best for specific, targeted requests.',
                color: kAccentBlue,
              ),
              const SizedBox(height: 16),
              const _ModeInfoRow(
                icon: Icons.record_voice_over_outlined,
                title: 'CONVERSE',
                subtitle: 'Continuous conversation',
                description:
                    'Gerald listens automatically after each response — '
                    'hands-free back-and-forth. Great for extended sessions.',
                color: kAccentGreen,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Mode info row (used in bottom sheet) ─────────────────────────────────────

class _ModeInfoRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final String description;
  final Color color;

  const _ModeInfoRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.description,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: color.withOpacity(0.12),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: kTextSecondary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: const TextStyle(
                  color: kTextSecondary,
                  fontSize: 12,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Utility sub-row: Attach | Clear | Build APK ───────────────────────────────

class _UtilitySubRow extends StatelessWidget {
  final AppState state;
  const _UtilitySubRow({required this.state});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceAround,
      children: [
        _UtilityButton(
          icon: Icons.attach_file_rounded,
          tooltip: 'Attach image',
          label: 'Attach',
          onPressed: () => _pickImage(context, state),
        ),
        _UtilityButton(
          icon: Icons.delete_sweep_outlined,
          tooltip: 'Clear conversation',
          label: 'Clear',
          onPressed: () => _confirmClear(context, state),
        ),
        const _ApkChip(),
      ],
    );
  }
}

// ── APK chip (inline, grayed when unavailable) ────────────────────────────────

class _ApkChip extends StatelessWidget {
  const _ApkChip();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final result = state.buildResult;
    final busy = state.buildTriggering || result.status == BuildStatus.running;
    final hasProject = state.selectedProject != null;

    final String label;
    final IconData icon;
    final Color color;
    final VoidCallback? onTap;

    if (!hasProject) {
      label = 'Build APK';
      icon = Icons.android_rounded;
      color = kTextMuted;
      onTap = () => ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Select a project first')),
          );
    } else if (busy) {
      label = 'Building…';
      icon = Icons.hourglass_top_rounded;
      color = kAccentBlue;
      onTap = null;
    } else if (result.status == BuildStatus.success) {
      label = 'Download APK';
      icon = Icons.check_circle_rounded;
      color = kAccentGreen;
      onTap = () => _onDownload(context, state);
    } else if (result.status == BuildStatus.failed ||
        result.status == BuildStatus.timeout) {
      label = 'Retry Build';
      icon = Icons.refresh_rounded;
      color = kStatusError;
      onTap = () => state.triggerBuildVerification();
    } else {
      label = 'Build APK';
      icon = Icons.android_rounded;
      color = kAccentBlue;
      onTap = () => state.triggerBuildVerification();
    }

    final tooltipMsg = !hasProject
        ? 'Select a project to enable build'
        : 'Build APK for ${state.selectedProject}';

    return Tooltip(
      message: tooltipMsg,
      child: GestureDetector(
        onTap: onTap,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (busy)
              SizedBox(
                width: 13,
                height: 13,
                child: CircularProgressIndicator(
                  strokeWidth: 1.8,
                  color: kAccentBlue,
                ),
              )
            else
              Icon(icon, size: 14, color: color),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _onDownload(BuildContext context, AppState state) async {
    final uri = Uri.parse('${state.baseUrl}/apk-latest/download');
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open browser — URL: $uri')),
        );
      }
    }
  }
}

// ── Utility button ────────────────────────────────────────────────────────────

class _UtilityButton extends StatelessWidget {
  final IconData icon;
  final bool active;
  final Color activeColor;
  final String tooltip;
  final VoidCallback onPressed;
  final String? label;

  const _UtilityButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.active = false,
    this.activeColor = kAccentBlue,
    this.label,
  });

  @override
  Widget build(BuildContext context) {
    final iconColor = active ? activeColor : kTextSecondary;
    final iconWidget = Icon(icon, size: 22, color: iconColor);

    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onPressed,
        child: Container(
          width: label == null ? 44 : null,
          height: label == null ? 44 : null,
          padding: label != null
              ? const EdgeInsets.symmetric(horizontal: 10, vertical: 6)
              : null,
          decoration: active
              ? BoxDecoration(
                  color: activeColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: activeColor.withOpacity(0.4),
                    width: 1,
                  ),
                )
              : null,
          child: label != null
              ? Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    iconWidget,
                    const SizedBox(height: 3),
                    Text(
                      label!,
                      style: TextStyle(
                        fontSize: 9,
                        color: iconColor,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ],
                )
              : iconWidget,
        ),
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Ready to assist',
              style: TextStyle(
                color: kTextPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.3,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Switch between typing and speaking with the toggle below',
              style: TextStyle(color: kTextSecondary, fontSize: 13),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _Hint(
                  icon: Icons.touch_app_outlined,
                  label: 'COMMAND',
                  sub: 'Hold mic to send',
                ),
                Container(
                  width: 1,
                  height: 32,
                  color: kBorderColor,
                  margin: const EdgeInsets.symmetric(horizontal: 20),
                ),
                _Hint(
                  icon: Icons.record_voice_over_outlined,
                  label: 'CONVERSE',
                  sub: 'Auto-listen mode',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Hint extends StatelessWidget {
  final IconData icon;
  final String label;
  final String sub;
  const _Hint({required this.icon, required this.label, required this.sub});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 20, color: kAccentBlue.withOpacity(0.6)),
        const SizedBox(height: 6),
        Text(
          label,
          style: const TextStyle(
            color: kTextSecondary,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 2),
        Text(sub, style: TextStyle(color: kTextMuted, fontSize: 11)),
      ],
    );
  }
}

// ── Shared helpers ────────────────────────────────────────────────────────────

Future<void> _pickImage(BuildContext context, AppState state) async {
  final source = await showModalBottomSheet<ImageSource>(
    context: context,
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 8),
          Container(
            width: 36,
            height: 4,
            decoration: BoxDecoration(
              color: kBorderColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'ATTACH IMAGE',
            style: TextStyle(
              fontSize: 10,
              letterSpacing: 2.5,
              color: kTextSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          ListTile(
            leading: const Icon(Icons.camera_alt_outlined, color: kAccentBlue),
            title: const Text('Camera'),
            onTap: () => Navigator.pop(ctx, ImageSource.camera),
          ),
          ListTile(
            leading:
                const Icon(Icons.photo_library_outlined, color: kAccentBlue),
            title: const Text('Gallery'),
            onTap: () => Navigator.pop(ctx, ImageSource.gallery),
          ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );

  if (source == null || !context.mounted) return;

  try {
    final file = await ImagePicker()
        .pickImage(source: source, imageQuality: 85, maxWidth: 1280);
    if (file == null || !context.mounted) return;
    final bytes = await file.readAsBytes();
    final mimeType = file.mimeType ?? 'image/jpeg';
    await state.addImageMessage(file.path, bytes, mimeType);
  } catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Image error: $e')),
      );
    }
  }
}

void _confirmClear(BuildContext context, AppState state) {
  showDialog(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Clear conversation?'),
      content: const Text(
        'This removes all messages and the activity log.',
        style: TextStyle(color: kTextSecondary),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () {
            state.clearMessages();
            Navigator.pop(ctx);
          },
          child: const Text('Clear', style: TextStyle(color: kStatusError)),
        ),
      ],
    ),
  );
}
