import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/app_state.dart';
import '../services/build_verification_service.dart';
import '../services/gerald_api.dart';
import '../theme.dart';
import '../widgets/conversation_orb.dart';
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
                        'YOUR AI COMMAND BRAIN',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 8.5,
                          letterSpacing: 2.0,
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
          icon: Icons.compare_outlined,
          tooltip: 'Visual Copy Mode — compare two images',
          label: 'Compare',
          onPressed: () => _showVisualCopySheet(context, state),
        ),
        _UtilityButton(
          icon: Icons.auto_awesome_rounded,
          tooltip: 'Design Studio — generate visual UI concepts',
          label: 'Design',
          onPressed: () => _showDesignStudioSheet(context, state),
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final orbSize = (constraints.maxWidth * 0.48).clamp(120.0, 180.0);
        return Center(
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ConversationOrb(state: OrbState.idle, size: orbSize),
                const SizedBox(height: 20),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 24),
                  child: Text(
                    'YOUR AI COMMAND BRAIN',
                    style: TextStyle(
                      color: kAccentBlue,
                      fontSize: 11,
                      letterSpacing: 4.0,
                      fontWeight: FontWeight.w500,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Text(
                    'Speak or type to begin',
                    style: TextStyle(color: kTextSecondary, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          ),
        );
      },
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

// ── Design Studio ─────────────────────────────────────────────────────────────

void _showDesignStudioSheet(BuildContext context, AppState state) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _DesignStudioSheet(state: state),
  );
}

class _DesignStudioSheet extends StatefulWidget {
  final AppState state;
  const _DesignStudioSheet({required this.state});

  @override
  State<_DesignStudioSheet> createState() => _DesignStudioSheetState();
}

class _DesignStudioSheetState extends State<_DesignStudioSheet> {
  final _descController = TextEditingController();
  int _conceptCount = 3;
  bool _loading = false;
  String? _error;
  List<Map<String, dynamic>> _concepts = [];
  final Map<int, TextEditingController> _iterControllers = {};
  final Map<int, bool> _iterLoading = {};

  @override
  void dispose() {
    _descController.dispose();
    for (final c in _iterControllers.values) c.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final desc = _descController.text.trim();
    if (desc.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _concepts = [];
    });
    try {
      final api = GeraldApi(widget.state.baseUrl);
      final concepts =
          await api.generateDesignConcepts(desc, count: _conceptCount);
      if (!mounted) return;
      setState(() {
        _loading = false;
        _concepts = concepts;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Generation failed: $e';
      });
    }
  }

  Future<void> _iterate(int index) async {
    final ctrl = _iterControllers[index];
    if (ctrl == null) return;
    final notes = ctrl.text.trim();
    if (notes.isEmpty) return;
    final originalDesc =
        _concepts[index]['description'] as String? ?? _descController.text;

    setState(() => _iterLoading[index] = true);
    try {
      final api = GeraldApi(widget.state.baseUrl);
      final concepts =
          await api.iterateDesignConcept(originalDesc, notes, count: 1);
      if (!mounted) return;
      if (concepts.isNotEmpty) {
        setState(() {
          _concepts[index] = concepts.first;
          _iterLoading[index] = false;
          ctrl.clear();
        });
      } else {
        setState(() => _iterLoading[index] = false);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _iterLoading[index] = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Iteration failed: $e')));
    }
  }

  void _approve(int index) {
    final concept = _concepts[index];
    final b64 = concept['image_b64'] as String? ?? '';
    if (b64.isEmpty) return;
    try {
      final bytes = base64Decode(b64);
      final desc =
          concept['description'] as String? ?? 'Design concept';
      widget.state.addImageMessage(
        'design_concept_${concept['id']}.png',
        bytes,
        'image/png',
        caption: 'Approved design concept: $desc',
      );
      if (context.mounted) Navigator.pop(context);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Approve failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.9,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (_, ctrl) => Container(
        decoration: BoxDecoration(
          color: kSurfaceColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          border: Border.all(color: kBorderColor),
        ),
        child: Column(
          children: [
            // Drag handle
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 4),
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                    color: kBorderColor,
                    borderRadius: BorderRadius.circular(2)),
              ),
            ),
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
              child: Row(children: [
                const Icon(Icons.auto_awesome_rounded,
                    color: kAccentBlue, size: 18),
                const SizedBox(width: 10),
                const Text('DESIGN STUDIO',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.5,
                      color: kTextPrimary,
                    )),
              ]),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Describe a screen — Gerald generates visual UI concepts',
                  style: TextStyle(fontSize: 11, color: kTextSecondary),
                ),
              ),
            ),
            // Description input
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                decoration: BoxDecoration(
                  color: kSurface2,
                  borderRadius: BorderRadius.circular(12),
                  border:
                      Border.all(color: kAccentBlue.withOpacity(0.5), width: 1.5),
                ),
                child: TextField(
                  controller: _descController,
                  maxLines: 3,
                  style:
                      const TextStyle(fontSize: 13, color: kTextPrimary, height: 1.4),
                  decoration: InputDecoration(
                    hintText:
                        'e.g. A dark home dashboard with project cards, animated orb, and task input at the bottom',
                    hintStyle: TextStyle(
                        color: kTextSecondary.withOpacity(0.6), fontSize: 12),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.all(12),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            // Concept count selector
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Text('Concepts:',
                      style: TextStyle(
                          fontSize: 11,
                          color: kTextSecondary,
                          letterSpacing: 0.5)),
                  const SizedBox(width: 10),
                  for (final n in [1, 2, 3])
                    GestureDetector(
                      onTap: () => setState(() => _conceptCount = n),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 36,
                        height: 28,
                        margin: const EdgeInsets.only(right: 6),
                        decoration: BoxDecoration(
                          color: _conceptCount == n
                              ? kAccentBlue.withOpacity(0.2)
                              : kSurface2,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _conceptCount == n
                                ? kAccentBlue
                                : kBorderColor,
                            width: _conceptCount == n ? 1.5 : 1,
                          ),
                        ),
                        child: Center(
                          child: Text('$n',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: _conceptCount == n
                                    ? kAccentBlue
                                    : kTextSecondary,
                              )),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            // Generate button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _loading ? null : _generate,
                  icon: _loading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.auto_awesome_rounded, size: 18),
                  label: Text(
                      _loading ? 'Generating concepts...' : 'GENERATE CONCEPTS'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: kAccentBlue,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: kBorderColor,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    textStyle: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.2),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                child: Text(_error!,
                    style: const TextStyle(
                        color: kStatusError, fontSize: 12)),
              ),
            // Concept cards
            if (_concepts.isNotEmpty)
              Expanded(
                child: ListView.builder(
                  controller: ctrl,
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  itemCount: _concepts.length,
                  itemBuilder: (_, i) => _ConceptCard(
                    key: ValueKey(_concepts[i]['id']),
                    concept: _concepts[i],
                    index: i,
                    iterController: _iterControllers.putIfAbsent(
                        i, () => TextEditingController()),
                    isIterLoading: _iterLoading[i] ?? false,
                    onIterate: () => _iterate(i),
                    onApprove: () => _approve(i),
                  ),
                ),
              )
            else
              const Expanded(child: SizedBox()),
          ],
        ),
      ),
    );
  }
}

class _ConceptCard extends StatefulWidget {
  final Map<String, dynamic> concept;
  final int index;
  final TextEditingController iterController;
  final bool isIterLoading;
  final VoidCallback onIterate;
  final VoidCallback onApprove;

  const _ConceptCard({
    super.key,
    required this.concept,
    required this.index,
    required this.iterController,
    required this.isIterLoading,
    required this.onIterate,
    required this.onApprove,
  });

  @override
  State<_ConceptCard> createState() => _ConceptCardState();
}

class _ConceptCardState extends State<_ConceptCard> {
  bool _showIter = false;

  Uint8List? get _imageBytes {
    final b64 = widget.concept['image_b64'] as String? ?? '';
    if (b64.isEmpty) return null;
    try {
      return base64Decode(b64);
    } catch (_) {
      return null;
    }
  }

  void _viewFullImage(BuildContext context, Uint8List bytes) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: kBgColor,
        insetPadding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
              child: Row(children: [
                Text(
                  'CONCEPT ${widget.index + 1}',
                  style: const TextStyle(
                      color: kAccentBlue,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.5),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close_rounded,
                      color: kTextSecondary, size: 20),
                  onPressed: () => Navigator.pop(ctx),
                ),
              ]),
            ),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(bytes, fit: BoxFit.contain),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bytes = _imageBytes;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kAccentBlue.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Card header
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
            child: Text(
              'CONCEPT ${widget.index + 1}',
              style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.5,
                color: kAccentBlue,
              ),
            ),
          ),
          // Concept image
          GestureDetector(
            onTap: bytes != null ? () => _viewFullImage(context, bytes) : null,
            child: bytes != null
                ? Image.memory(
                    bytes,
                    width: double.infinity,
                    height: 240,
                    fit: BoxFit.cover,
                  )
                : Container(
                    height: 240,
                    color: kBorderColor,
                    child: const Center(
                      child: Icon(Icons.broken_image_outlined,
                          color: kTextSecondary, size: 36),
                    ),
                  ),
          ),
          // Action row
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => setState(() => _showIter = !_showIter),
                    icon: const Icon(Icons.refresh_rounded, size: 15),
                    label: const Text('ITERATE'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: kTextSecondary,
                      side: const BorderSide(color: kBorderColor),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      textStyle: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.0),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(9)),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: widget.onApprove,
                    icon: const Icon(Icons.check_rounded, size: 15),
                    label: const Text('APPROVE'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: kAccentGreen,
                      side: BorderSide(color: kAccentGreen.withOpacity(0.6)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      textStyle: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.0),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(9)),
                    ),
                  ),
                ),
              ],
            ),
          ),
          // Iteration panel
          if (_showIter)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Column(
                children: [
                  Container(
                    decoration: BoxDecoration(
                      color: kSurfaceColor,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: kBorderColor),
                    ),
                    child: TextField(
                      controller: widget.iterController,
                      maxLines: 2,
                      style: const TextStyle(
                          fontSize: 12, color: kTextPrimary, height: 1.4),
                      decoration: InputDecoration(
                        hintText:
                            'Describe changes: e.g. make it lighter, add a sidebar…',
                        hintStyle: TextStyle(
                            color: kTextSecondary.withOpacity(0.6),
                            fontSize: 11),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.all(10),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed:
                          widget.isIterLoading ? null : widget.onIterate,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: kAccentBlue,
                        side: const BorderSide(color: kAccentBlue),
                        disabledForegroundColor:
                            kTextMuted,
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        textStyle: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.0),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(9)),
                      ),
                      child: widget.isIterLoading
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: kAccentBlue),
                            )
                          : const Text('REGENERATE WITH CHANGES'),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── Visual Copy Mode ──────────────────────────────────────────────────────────

void _showVisualCopySheet(BuildContext context, AppState state) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _VisualCopySheet(state: state),
  );
}

class _VisualCopySheet extends StatefulWidget {
  final AppState state;
  const _VisualCopySheet({required this.state});

  @override
  State<_VisualCopySheet> createState() => _VisualCopySheetState();
}

class _VisualCopySheetState extends State<_VisualCopySheet> {
  Uint8List? _targetBytes;
  String _targetMime = 'image/jpeg';
  Uint8List? _resultBytes;
  String _resultMime = 'image/jpeg';
  bool _loading = false;
  Map<String, dynamic>? _comparison;
  String? _error;

  Future<void> _pickSlot({required bool isTarget}) async {
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
              decoration: BoxDecoration(color: kBorderColor, borderRadius: BorderRadius.circular(2)),
            ),
            const SizedBox(height: 16),
            Text(
              isTarget ? 'TARGET IMAGE' : 'CURRENT RESULT',
              style: const TextStyle(fontSize: 10, letterSpacing: 2.5, color: kTextSecondary, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined, color: kAccentBlue),
              title: const Text('Camera'),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined, color: kAccentBlue),
              title: const Text('Gallery'),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;
    try {
      final file = await ImagePicker().pickImage(source: source, imageQuality: 85, maxWidth: 1280);
      if (file == null || !mounted) return;
      final bytes = await file.readAsBytes();
      final mime = file.mimeType ?? 'image/jpeg';
      setState(() {
        if (isTarget) {
          _targetBytes = bytes;
          _targetMime = mime;
        } else {
          _resultBytes = bytes;
          _resultMime = mime;
        }
        _comparison = null;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = 'Image error: $e');
    }
  }

  Future<void> _compare() async {
    setState(() { _loading = true; _error = null; _comparison = null; });
    try {
      final api = GeraldApi(widget.state.baseUrl);
      final result = await api.compareImages(_targetBytes!, _targetMime, _resultBytes!, _resultMime);
      final comp = result['comparison'];
      setState(() {
        _loading = false;
        if (comp is Map<String, dynamic>) {
          _comparison = comp;
        } else {
          _error = 'Invalid response from server';
        }
      });
    } catch (e) {
      setState(() { _loading = false; _error = 'Compare failed: $e'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (_, ctrl) => Container(
        decoration: BoxDecoration(
          color: kSurfaceColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          border: Border.all(color: kBorderColor),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 4),
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(color: kBorderColor, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
              child: Row(
                children: [
                  const Icon(Icons.compare_outlined, color: kAccentBlue, size: 18),
                  const SizedBox(width: 10),
                  const Text(
                    'VISUAL COPY MODE',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, letterSpacing: 1.5, color: kTextPrimary),
                  ),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Upload a target design and your current result to get visual fix recommendations',
                  style: TextStyle(fontSize: 11, color: kTextSecondary),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Expanded(child: _ImageSlot(
                    label: 'TARGET',
                    sublabel: 'Reference design',
                    bytes: _targetBytes,
                    onTap: () => _pickSlot(isTarget: true),
                  )),
                  const SizedBox(width: 10),
                  Expanded(child: _ImageSlot(
                    label: 'CURRENT RESULT',
                    sublabel: 'Your screenshot',
                    bytes: _resultBytes,
                    onTap: () => _pickSlot(isTarget: false),
                  )),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: (_targetBytes != null && _resultBytes != null && !_loading) ? _compare : null,
                  icon: _loading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.compare_arrows_rounded, size: 18),
                  label: Text(_loading ? 'Comparing…' : 'COMPARE IMAGES'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: kAccentBlue,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: kBorderColor,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 1.2),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                child: Text(_error!, style: const TextStyle(color: kStatusError, fontSize: 12)),
              ),
            if (_comparison != null)
              Expanded(
                child: SingleChildScrollView(
                  controller: ctrl,
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  child: _ComparisonResults(comparison: _comparison!),
                ),
              )
            else
              const Expanded(child: SizedBox()),
          ],
        ),
      ),
    );
  }
}

class _ImageSlot extends StatelessWidget {
  final String label;
  final String sublabel;
  final Uint8List? bytes;
  final VoidCallback onTap;

  const _ImageSlot({
    required this.label,
    required this.sublabel,
    required this.bytes,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final hasImage = bytes != null;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 140,
        decoration: BoxDecoration(
          color: kSurface2,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: hasImage ? kAccentBlue.withOpacity(0.7) : kBorderColor,
            width: hasImage ? 1.5 : 1,
          ),
        ),
        child: hasImage
            ? ClipRRect(
                borderRadius: BorderRadius.circular(11),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.memory(bytes!, fit: BoxFit.cover),
                    Positioned(
                      bottom: 0, left: 0, right: 0,
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 5),
                        color: Colors.black54,
                        child: Text(
                          label,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1.5, color: Colors.white),
                        ),
                      ),
                    ),
                  ],
                ),
              )
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.add_photo_alternate_outlined, size: 28, color: kAccentBlue.withOpacity(0.6)),
                  const SizedBox(height: 8),
                  Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: kTextPrimary)),
                  const SizedBox(height: 4),
                  Text(sublabel, style: const TextStyle(fontSize: 9, color: kTextSecondary), textAlign: TextAlign.center),
                ],
              ),
      ),
    );
  }
}

class _ComparisonResults extends StatelessWidget {
  final Map<String, dynamic> comparison;
  const _ComparisonResults({required this.comparison});

  @override
  Widget build(BuildContext context) {
    final score = (comparison['similarity_score'] as num?)?.toInt() ?? 0;
    final summary = comparison['summary'] as String? ?? '';
    final fixes = (comparison['top_5_fixes'] as List?)?.cast<String>() ?? [];

    final diffs = <({String label, String value})>[];
    void addDiff(String label, String key) {
      final v = comparison[key] as String? ?? '';
      if (v.isNotEmpty && v.toLowerCase() != 'none' && v.toLowerCase() != 'n/a') {
        diffs.add((label: label, value: v));
      }
    }
    addDiff('Layout', 'layout_differences');
    addDiff('Size & Proportion', 'size_proportion_differences');
    addDiff('Colours', 'colour_differences');
    addDiff('Typography', 'typography_differences');
    addDiff('Missing / Extra', 'missing_extra_elements');

    final scoreColor = score >= 75 ? kAccentGreen : score >= 50 ? kAccentBlue : kStatusError;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: kSurface2,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: scoreColor.withOpacity(0.4)),
          ),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: scoreColor.withOpacity(0.12),
                  border: Border.all(color: scoreColor, width: 2),
                ),
                child: Center(
                  child: Text(
                    '$score',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: scoreColor),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'SIMILARITY: $score / 100',
                      style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 1.2, color: scoreColor),
                    ),
                    if (summary.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(summary, style: const TextStyle(fontSize: 12, color: kTextSecondary, height: 1.4)),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
        if (diffs.isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text('DIFFERENCES', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 1.5, color: kTextSecondary)),
          const SizedBox(height: 8),
          for (final d in diffs)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: kSurface2,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: kBorderColor),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(d.label, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: kAccentBlue)),
                    const SizedBox(height: 4),
                    Text(d.value, style: const TextStyle(fontSize: 12, color: kTextPrimary, height: 1.4)),
                  ],
                ),
              ),
            ),
        ],
        if (fixes.isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text('TOP 5 FIXES', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 1.5, color: kTextSecondary)),
          const SizedBox(height: 8),
          for (final entry in fixes.asMap().entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 22,
                    height: 22,
                    margin: const EdgeInsets.only(top: 1, right: 10),
                    decoration: BoxDecoration(
                      color: kAccentBlue.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: kAccentBlue.withOpacity(0.4)),
                    ),
                    child: Center(
                      child: Text(
                        '${entry.key + 1}',
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: kAccentBlue),
                      ),
                    ),
                  ),
                  Expanded(
                    child: Text(entry.value, style: const TextStyle(fontSize: 13, color: kTextPrimary, height: 1.4)),
                  ),
                ],
              ),
            ),
        ],
      ],
    );
  }
}
