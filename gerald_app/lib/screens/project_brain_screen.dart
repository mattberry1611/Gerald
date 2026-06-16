import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/project_brain.dart';
import '../providers/app_state.dart';
import '../theme.dart';

const _kBrainFiles = [
  'project_brain.md',
  'roadmap.md',
  'current_status.md',
  'architecture.md',
];

class ProjectBrainScreen extends StatefulWidget {
  const ProjectBrainScreen({super.key});

  @override
  State<ProjectBrainScreen> createState() => _ProjectBrainScreenState();
}

class _ProjectBrainScreenState extends State<ProjectBrainScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<AppState>().refreshProjectBrain();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final brain = state.projectBrain;
    final loading = state.brainLoading;
    final project = state.selectedProject ?? 'Project';

    return Scaffold(
      backgroundColor: kBgColor,
      appBar: AppBar(
        backgroundColor: kBgColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded,
              size: 18, color: kTextSecondary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              project.toUpperCase(),
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w800,
                letterSpacing: 3,
                color: kTextPrimary,
              ),
            ),
            const Text(
              'PROJECT BRAIN',
              style: TextStyle(
                fontSize: 8.5,
                letterSpacing: 2.5,
                color: kAccentBlue,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: kTextSecondary),
                  )
                : const Icon(Icons.refresh_rounded,
                    size: 20, color: kTextSecondary),
            onPressed: loading ? null : () => state.refreshProjectBrain(),
            tooltip: 'Refresh brain',
          ),
          const SizedBox(width: 6),
        ],
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
      body: loading && brain == null
          ? const Center(child: CircularProgressIndicator(color: kAccentBlue))
          : brain == null
              ? _EmptyBrain(project: project)
              : _BrainBody(brain: brain),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyBrain extends StatelessWidget {
  final String project;
  const _EmptyBrain({required this.project});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.psychology_outlined,
              size: 52, color: kTextSecondary.withOpacity(0.3)),
          const SizedBox(height: 16),
          const Text(
            'No brain data',
            style: TextStyle(color: kTextSecondary, fontSize: 15),
          ),
          const SizedBox(height: 8),
          Text(
            'Send a task to $project to initialise',
            style: const TextStyle(color: kTextMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

// ── Main body ─────────────────────────────────────────────────────────────────

class _BrainBody extends StatelessWidget {
  final ProjectBrain brain;
  const _BrainBody({required this.brain});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        // Brain file checklist
        _SectionCard(
          title: 'BRAIN FILES',
          child: Column(
            children: _kBrainFiles.map((f) {
              final exists = brain.files.contains(f);
              return Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                child: Row(
                  children: [
                    Icon(
                      exists
                          ? Icons.check_circle_rounded
                          : Icons.radio_button_unchecked_rounded,
                      size: 14,
                      color: exists ? kAccentGreen : kTextMuted,
                    ),
                    const SizedBox(width: 10),
                    Text(
                      f,
                      style: TextStyle(
                        fontSize: 13,
                        fontFamily: 'monospace',
                        color: exists ? kTextPrimary : kTextMuted,
                      ),
                    ),
                    if (!exists) ...[
                      const Spacer(),
                      Text(
                        'missing',
                        style: TextStyle(
                          fontSize: 10,
                          color: kStatusError.withOpacity(0.7),
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ],
                ),
              );
            }).toList(),
          ),
        ),

        const SizedBox(height: 12),

        // Project path
        if (brain.path.isNotEmpty)
          _SectionCard(
            title: 'PROJECT PATH',
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
              child: SelectableText(
                brain.path,
                style: const TextStyle(
                  fontSize: 12,
                  color: kTextSecondary,
                  fontFamily: 'monospace',
                  height: 1.4,
                ),
              ),
            ),
          ),

        const SizedBox(height: 12),

        // Brain content
        _SectionCard(
          title: 'BRAIN CONTENT',
          child: brain.brain.isNotEmpty
              ? Padding(
                  padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
                  child: SelectableText(
                    brain.brain,
                    style: const TextStyle(
                      fontSize: 12,
                      color: kTextSecondary,
                      height: 1.6,
                    ),
                  ),
                )
              : Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
                  child: Row(
                    children: [
                      Icon(Icons.info_outline_rounded,
                          size: 14, color: kTextMuted),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'Brain files found but empty. Send tasks to this '
                          'project and Gerald will populate them.',
                          style: TextStyle(
                              fontSize: 12, color: kTextMuted, height: 1.5),
                        ),
                      ),
                    ],
                  ),
                ),
        ),

        const SizedBox(height: 24),
      ],
    );
  }
}

// ── Section card ──────────────────────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget child;
  const _SectionCard({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kBorderColor),
      ),
      clipBehavior: Clip.hardEdge,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(14, 9, 14, 8),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: kBorderColor)),
            ),
            child: Text(
              title,
              style: const TextStyle(
                color: kAccentBlue,
                fontSize: 9.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 2.5,
              ),
            ),
          ),
          child,
        ],
      ),
    );
  }
}
