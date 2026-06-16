import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../services/ai_provider_service.dart';
import '../services/build_verification_service.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _urlCtrl;
  final Map<AiProvider, TextEditingController> _apiKeyCtrl = {};

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController(text: context.read<AppState>().baseUrl);
    for (final p in kAiProviders) {
      if (p.requiresApiKey) {
        _apiKeyCtrl[p.id] = TextEditingController(
          text: AiProviderService.instance.getApiKey(p.id) ?? '',
        );
      }
    }
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    for (final c in _apiKeyCtrl.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      backgroundColor: kBgColor,
      appBar: AppBar(
        backgroundColor: kBgColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded,
              size: 18, color: kTextSecondary),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'SETTINGS',
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 3,
            color: kTextPrimary,
          ),
        ),
        centerTitle: true,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            height: 1,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.transparent,
                  kAccentBlue.withOpacity(0.35),
                  Colors.transparent,
                ],
              ),
            ),
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 4),

          // Backend
          _SectionHeader(title: 'Backend Connection'),
          _Card(
            child: Column(
              children: [
                TextField(
                  controller: _urlCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Gerald Backend URL',
                    hintText: 'http://192.168.1.x:8000',
                    prefixIcon: Icon(Icons.wifi_outlined,
                        size: 18, color: kTextSecondary),
                    helperText:
                        "Use your PC's LAN IP when connecting from phone",
                  ),
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  style: const TextStyle(fontSize: 14, color: kTextPrimary),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: () {
                      final url = _urlCtrl.text.trim();
                      if (url.isEmpty) return;
                      state.setBaseUrl(url);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Backend URL saved')),
                      );
                    },
                    icon: const Icon(Icons.sync_rounded, size: 16),
                    label: const Text('SAVE & RECONNECT'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 13),
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Voice
          _SectionHeader(title: 'Voice'),
          _Card(
            child: Column(
              children: [
                _PremiumSwitch(
                  icon: Icons.volume_up_outlined,
                  title: 'Speak Responses',
                  subtitle: 'Gerald reads replies aloud via TTS',
                  value: state.ttsEnabled,
                  onChanged: (v) => state.setTtsEnabled(v),
                ),
                Container(height: 1, color: kBorderColor),
                _PremiumSwitch(
                  icon: Icons.record_voice_over_outlined,
                  title: 'Conversation Mode',
                  subtitle: 'Auto-listen after each response (Mode B)',
                  value: state.conversationMode,
                  onChanged: (v) => state.setConversationMode(v),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Status
          _SectionHeader(title: 'Status'),
          _Card(
            child: Column(
              children: [
                _InfoRow(
                  label: 'Backend URL',
                  value: state.baseUrl,
                  icon: Icons.link_rounded,
                ),
                Container(height: 1, color: kBorderColor),
                _InfoRow(
                  label: 'Project',
                  value: state.selectedProject ?? 'None',
                  icon: Icons.folder_outlined,
                ),
                Container(height: 1, color: kBorderColor),
                _InfoRow(
                  label: 'Connection',
                  value: _connLabel(state.status),
                  valueColor: _connColor(state.status),
                  icon: Icons.circle,
                  iconColor: _connColor(state.status),
                ),
                Container(height: 1, color: kBorderColor),
                _InfoRow(
                  label: 'Messages',
                  value: '${state.messages.length}',
                  icon: Icons.chat_bubble_outline_rounded,
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // AI Provider
          _SectionHeader(title: 'AI Provider'),
          _Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ...kAiProviders.map((p) {
                  final isActive = state.aiProvider == p.id;
                  final isPlanned = p.status == 'planned';
                  return Column(
                    children: [
                      InkWell(
                        onTap: isPlanned
                            ? null
                            : () => state.setAiProvider(p.id),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 12),
                          child: Row(
                            children: [
                              Icon(
                                isActive
                                    ? Icons.radio_button_checked_rounded
                                    : Icons.radio_button_unchecked_rounded,
                                size: 18,
                                color: isActive
                                    ? kAccentBlue
                                    : isPlanned
                                        ? kTextMuted
                                        : kTextSecondary,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Text(
                                          p.name,
                                          style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w600,
                                            color: isPlanned
                                                ? kTextMuted
                                                : kTextPrimary,
                                          ),
                                        ),
                                        if (isPlanned) ...[
                                          const SizedBox(width: 6),
                                          Container(
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 5, vertical: 1),
                                            decoration: BoxDecoration(
                                              color: kAccentBlue.withOpacity(0.15),
                                              borderRadius:
                                                  BorderRadius.circular(4),
                                            ),
                                            child: const Text(
                                              'PLANNED',
                                              style: TextStyle(
                                                fontSize: 9,
                                                fontWeight: FontWeight.w700,
                                                color: kAccentBlue,
                                                letterSpacing: 1,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ],
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      '${p.vendor} · ${p.model}',
                                      style: const TextStyle(
                                        fontSize: 11.5,
                                        color: kTextSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              if (isActive)
                                const Icon(Icons.check_circle_rounded,
                                    size: 16, color: kAccentGreen),
                            ],
                          ),
                        ),
                      ),
                      if (p.requiresApiKey && _apiKeyCtrl.containsKey(p.id))
                        Padding(
                          padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
                          child: Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _apiKeyCtrl[p.id],
                                  decoration: InputDecoration(
                                    labelText: '${p.vendor} API Key',
                                    hintText: 'sk-...',
                                    prefixIcon: const Icon(Icons.vpn_key_outlined,
                                        size: 16, color: kTextSecondary),
                                  ),
                                  obscureText: true,
                                  style: const TextStyle(
                                      fontSize: 13, color: kTextPrimary),
                                ),
                              ),
                              const SizedBox(width: 8),
                              ElevatedButton(
                                onPressed: () {
                                  final key =
                                      _apiKeyCtrl[p.id]?.text.trim() ?? '';
                                  state.setProviderApiKey(p.id, key);
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                        content:
                                            Text('${p.vendor} key saved')),
                                  );
                                },
                                child: const Text('SAVE'),
                              ),
                            ],
                          ),
                        ),
                      if (p != kAiProviders.last)
                        Container(height: 1, color: kBorderColor),
                    ],
                  );
                }),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Build Verification
          _SectionHeader(title: 'Build Verification'),
          _Card(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 12),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Last Build: ${state.buildResult.statusLabel}',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: _buildColor(state.buildResult.status),
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              state.buildResult.status == BuildStatus.neverRun
                                  ? 'No build run yet'
                                  : '${state.buildResult.errorCount} errors · '
                                      '${state.buildResult.warningCount} warnings · '
                                      '${state.buildResult.durationS.toStringAsFixed(0)}s',
                              style: const TextStyle(
                                  fontSize: 11.5, color: kTextSecondary),
                            ),
                          ],
                        ),
                      ),
                      ElevatedButton.icon(
                        onPressed: state.buildTriggering
                            ? null
                            : () => state.triggerBuildVerification(),
                        icon: state.buildTriggering
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.build_rounded, size: 15),
                        label: Text(
                            state.buildTriggering ? 'BUILDING...' : 'BUILD'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 10),
                        ),
                      ),
                    ],
                  ),
                ),
                if (state.buildResult.errors.isNotEmpty) ...[
                  Container(height: 1, color: kBorderColor),
                  Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'ERRORS',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.5,
                            color: kStatusError,
                          ),
                        ),
                        const SizedBox(height: 6),
                        ...state.buildResult.errors.take(5).map(
                              (e) => Padding(
                                padding: const EdgeInsets.only(bottom: 4),
                                child: Text(
                                  e,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: kStatusError,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ),
                            ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Data
          _SectionHeader(title: 'Data'),
          _Card(
            child: ListTile(
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
              leading: const Icon(Icons.delete_outline_rounded,
                  color: kStatusError, size: 20),
              title: const Text(
                'Clear Conversation & Log',
                style: TextStyle(fontSize: 14),
              ),
              trailing: const Icon(Icons.chevron_right_rounded,
                  color: kTextSecondary, size: 18),
              onTap: () {
                state.clearMessages();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Cleared')),
                );
              },
            ),
          ),

          const SizedBox(height: 40),

          // Version footer
          Center(
            child: Column(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: kAccentBlue.withOpacity(0.2),
                        blurRadius: 12,
                      ),
                    ],
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.asset('assets/gerald_logo.png',
                        fit: BoxFit.cover),
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'GERALD  v1.4.0',
                  style: TextStyle(
                    color: kTextSecondary,
                    fontSize: 11,
                    letterSpacing: 2,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Flutter · Voice-driven AI Supervisor',
                  style: TextStyle(
                    color: kTextMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  String _connLabel(GeraldStatus s) => switch (s) {
        GeraldStatus.offline => 'Offline',
        GeraldStatus.error => 'Error',
        _ => 'Connected',
      };

  Color _connColor(GeraldStatus s) => switch (s) {
        GeraldStatus.offline => kStatusError,
        GeraldStatus.error => kStatusError,
        _ => kAccentGreen,
      };

  Color _buildColor(BuildStatus s) {
    switch (s) {
      case BuildStatus.success:
        return kAccentGreen;
      case BuildStatus.failed:
      case BuildStatus.timeout:
      case BuildStatus.error:
        return kStatusError;
      case BuildStatus.running:
        return kAccentBlue;
      default:
        return kTextSecondary;
    }
  }
}

// ── Shared Settings widgets ───────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          color: kAccentBlue,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 2.5,
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final Widget child;
  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kBorderColor),
      ),
      clipBehavior: Clip.hardEdge,
      child: child,
    );
  }
}

class _PremiumSwitch extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _PremiumSwitch({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Icon(icon, size: 18, color: value ? kAccentBlue : kTextSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: value ? kTextPrimary : kTextSecondary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 11.5,
                    color: kTextSecondary,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color? valueColor;
  final Color? iconColor;

  const _InfoRow({
    required this.label,
    required this.value,
    required this.icon,
    this.valueColor,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Icon(icon,
              size: 14,
              color: iconColor ?? kTextSecondary),
          const SizedBox(width: 10),
          Text(
            label,
            style: const TextStyle(
              color: kTextSecondary,
              fontSize: 13,
            ),
          ),
          const Spacer(),
          Flexible(
            child: Text(
              value,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.end,
              style: TextStyle(
                fontSize: 13,
                color: valueColor ?? kTextPrimary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
