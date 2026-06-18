import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../theme.dart';
import '../widgets/push_to_talk_button.dart';
import '../widgets/message_bubble.dart';
import '../widgets/status_panel.dart';
import '../widgets/activity_log.dart';
import '../widgets/project_selector.dart';
import '../widgets/text_input_bar.dart';
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
      appBar: _buildAppBar(context),
      body: SafeArea(
        bottom: false, // We handle bottom padding manually
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

            const StatusPanel(),

            // Conversation area (fills remaining space)
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

            // Text input bar (optional)
            if (state.showTextInput) const TextInputBar(),

            // Bottom section — adapts to keyboard + screen size
            if (keyboardVisible)
              _CompactBar(state: state)
            else
              _BottomSection(
                state: state,
                bottomPad: bottomPad,
                screenH: screenH,
                showTextInput: state.showTextInput,
              ),
          ],
        ),
      ),
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context) {
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
            Column(
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
                Text(
                  'AI CODING SUPERVISOR',
                  style: TextStyle(
                    fontSize: 8.5,
                    letterSpacing: 2.5,
                    color: kAccentBlue.withOpacity(0.7),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
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

// ── Bottom section (adaptive) ─────────────────────────────────────────────────

class _BottomSection extends StatelessWidget {
  final AppState state;
  final double bottomPad;
  final double screenH;
  final bool showTextInput;

  const _BottomSection({
    required this.state,
    required this.bottomPad,
    required this.screenH,
    required this.showTextInput,
  });

  @override
  Widget build(BuildContext context) {
    // On small screens or when text input is open, omit activity log
    final isSmall = screenH < 620 || showTextInput;

    if (isSmall) {
      return _VoiceSection(state: state, bottomPad: bottomPad);
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const ActivityLog(),
        _VoiceSection(state: state, bottomPad: bottomPad),
      ],
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
            icon: state.showTextInput
                ? Icons.keyboard_hide_rounded
                : Icons.keyboard_alt_outlined,
            active: state.showTextInput,
            activeColor: kAccentBlue,
            tooltip: 'Text input',
            onPressed: state.toggleTextInput,
          ),
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

// ── Full voice section ────────────────────────────────────────────────────────

class _VoiceSection extends StatelessWidget {
  final AppState state;
  final double bottomPad;
  const _VoiceSection({required this.state, required this.bottomPad});

  @override
  Widget build(BuildContext context) {
    final screenH = MediaQuery.of(context).size.height;
    final isSmall = screenH < 620;
    final vPad = isSmall ? 10.0 : 14.0;
    final midGap = isSmall ? 10.0 : 16.0;

    return Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(top: BorderSide(color: kBorderColor)),
      ),
      padding: EdgeInsets.fromLTRB(16, vPad, 16, bottomPad + vPad),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Mode selector
          _ModeSelector(state: state, compact: isSmall),
          SizedBox(height: midGap),

          // Voice control
          const PushToTalkButton(),
          SizedBox(height: isSmall ? 10.0 : 14.0),

          // Utility row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _UtilityButton(
                icon: state.showTextInput
                    ? Icons.keyboard_hide_rounded
                    : Icons.keyboard_alt_outlined,
                active: state.showTextInput,
                activeColor: kAccentBlue,
                tooltip: 'Text input',
                onPressed: state.toggleTextInput,
              ),
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
                tooltip: 'Clear',
                onPressed: () => _confirmClear(context, state),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Mode selector ─────────────────────────────────────────────────────────────

class _ModeSelector extends StatelessWidget {
  final AppState state;
  final bool compact;
  const _ModeSelector({required this.state, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final convMode = state.conversationMode;
    final height = compact ? 36.0 : 42.0;

    return Container(
      height: height,
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(compact ? 9 : 12),
        border: Border.all(color: kBorderColor),
      ),
      child: Stack(
        children: [
          // Sliding indicator
          AnimatedAlign(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeInOut,
            alignment:
                convMode ? Alignment.centerRight : Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: 0.5,
              child: Container(
                margin: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  color: kAccentBlue.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(compact ? 6 : 9),
                  border: Border.all(
                    color: kAccentBlue.withOpacity(0.45),
                    width: 1,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: kAccentBlue.withOpacity(0.15),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
            ),
          ),
          // Labels
          Row(
            children: [
              Expanded(
                child: GestureDetector(
                  onTap: () => state.setConversationMode(false),
                  child: Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.touch_app_outlined,
                          size: 12,
                          color: !convMode ? kAccentBlue : kTextSecondary,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'MODE A',
                          style: TextStyle(
                            color: !convMode ? kAccentBlue : kTextSecondary,
                            fontSize: compact ? 9 : 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              Expanded(
                child: GestureDetector(
                  onTap: () => state.setConversationMode(true),
                  child: Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.record_voice_over_outlined,
                          size: 12,
                          color: convMode ? kAccentBlue : kTextSecondary,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'MODE B',
                          style: TextStyle(
                            color: convMode ? kAccentBlue : kTextSecondary,
                            fontSize: compact ? 9 : 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Utility button ────────────────────────────────────────────────────────────

class _UtilityButton extends StatelessWidget {
  final IconData icon;
  final bool active;
  final Color activeColor;
  final String tooltip;
  final VoidCallback onPressed;

  const _UtilityButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.active = false,
    this.activeColor = kAccentBlue,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onPressed,
        child: Container(
          width: 44,
          height: 44,
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
          child: Icon(
            icon,
            size: 22,
            color: active ? activeColor : kTextSecondary,
          ),
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
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: kAccentBlue.withOpacity(0.20),
                    blurRadius: 40,
                    spreadRadius: 10,
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(18),
                child: Image.asset('assets/gerald_logo.png', fit: BoxFit.cover),
              ),
            ),
            const SizedBox(height: 24),
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
              'Push-to-talk or use conversation mode',
              style: TextStyle(color: kTextSecondary, fontSize: 13),
            ),
            const SizedBox(height: 32),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _Hint(
                  icon: Icons.touch_app_outlined,
                  label: 'MODE A',
                  sub: 'Hold mic to speak',
                ),
                Container(
                  width: 1,
                  height: 32,
                  color: kBorderColor,
                  margin: const EdgeInsets.symmetric(horizontal: 20),
                ),
                _Hint(
                  icon: Icons.record_voice_over_outlined,
                  label: 'MODE B',
                  sub: 'Auto-listens',
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
            leading: const Icon(Icons.photo_library_outlined, color: kAccentBlue),
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
