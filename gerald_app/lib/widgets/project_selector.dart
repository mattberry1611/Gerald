import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../models/project_brain.dart';
import '../services/gerald_api.dart';
import '../theme.dart';

class ProjectSelector extends StatelessWidget {
  const ProjectSelector({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final hasProject = state.selectedProject != null;
    final hasBrain = state.hasBrain;

    return Tooltip(
      message: hasProject
          ? 'Project: ${state.selectedProject}'
          : 'Select a project',
      child: GestureDetector(
        onTap: () => _showPicker(context, state),
        child: Container(
          constraints: const BoxConstraints(maxWidth: 130),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: kSurfaceColor,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: hasProject
                  ? kAccentBlue.withOpacity(0.25)
                  : kBorderColor,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Icon(
                    Icons.folder_outlined,
                    size: 12,
                    color: hasProject
                        ? kAccentBlue.withOpacity(0.85)
                        : kTextSecondary,
                  ),
                  if (hasProject && hasBrain)
                    Positioned(
                      top: -2,
                      right: -2,
                      child: Container(
                        width: 5,
                        height: 5,
                        decoration: const BoxDecoration(
                          color: kAccentGreen,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(width: 5),
              Flexible(
                child: Text(
                  state.selectedProject ?? 'Project',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w500,
                    color: hasProject
                        ? kAccentBlue.withOpacity(0.85)
                        : kTextSecondary,
                    letterSpacing: 0.2,
                  ),
                ),
              ),
              const SizedBox(width: 2),
              Icon(
                Icons.keyboard_arrow_down_rounded,
                size: 13,
                color: hasProject
                    ? kAccentBlue.withOpacity(0.7)
                    : kTextSecondary,
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showPicker(BuildContext context, AppState state) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => _PickerSheet(state: state),
    );
  }
}

// ── Project picker sheet ──────────────────────────────────────────────────────

class _PickerSheet extends StatelessWidget {
  final AppState state;
  const _PickerSheet({required this.state});

  @override
  Widget build(BuildContext context) {
    final projects = state.projectsFull.isNotEmpty
        ? state.projectsFull
        : [
            {'name': 'RentMe', 'description': ''},
            {'name': 'PlantBrain', 'description': ''},
            {'name': 'CommuteCoder', 'description': ''},
          ];

    return SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 12),
          Container(
            width: 36,
            height: 4,
            decoration: BoxDecoration(
              color: kBorderColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 14),

          // Header row with title + "+" button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'SELECT PROJECT',
                    style: TextStyle(
                      fontSize: 10,
                      letterSpacing: 2.5,
                      color: kTextSecondary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                GestureDetector(
                  onTap: () {
                    Navigator.pop(context);
                    _showCreateProject(context, state);
                  },
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: kAccentBlue.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(7),
                      border: Border.all(
                        color: kAccentBlue.withOpacity(0.3),
                      ),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.add_rounded, size: 13, color: kAccentBlue),
                        SizedBox(width: 4),
                        Text(
                          'NEW',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            color: kAccentBlue,
                            letterSpacing: 1,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 8),
          Container(height: 1, color: kBorderColor),

          // None option
          ListTile(
            leading: Icon(
              Icons.cancel_outlined,
              size: 18,
              color: kTextSecondary,
            ),
            title: const Text(
              'None',
              style: TextStyle(color: kTextSecondary, fontSize: 14),
            ),
            onTap: () {
              state.setProject(null);
              Navigator.pop(context);
            },
          ),

          // Project tiles
          ...projects.map((p) {
            final name = (p['name'] ?? '').toString();
            final description = (p['description'] ?? '').toString();
            final selected = state.selectedProject == name;

            return ListTile(
              leading: Icon(
                selected ? Icons.folder : Icons.folder_outlined,
                size: 18,
                color: selected ? kAccentBlue : kTextSecondary,
              ),
              title: Text(
                name,
                style: TextStyle(
                  color: selected ? kAccentBlue : kTextPrimary,
                  fontWeight:
                      selected ? FontWeight.w600 : FontWeight.normal,
                  fontSize: 14,
                ),
              ),
              subtitle: description.isNotEmpty
                  ? Text(
                      description,
                      style: const TextStyle(
                        fontSize: 11,
                        color: kTextSecondary,
                      ),
                    )
                  : null,
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Brain viewer button
                  GestureDetector(
                    onTap: () {
                      Navigator.pop(context);
                      _showBrain(context, state, name);
                    },
                    child: Container(
                      padding: const EdgeInsets.all(5),
                      child: Icon(
                        Icons.psychology_outlined,
                        size: 16,
                        color: selected ? kAccentGreen : kTextSecondary,
                      ),
                    ),
                  ),
                  if (selected)
                    const Icon(Icons.check_rounded,
                        color: kAccentBlue, size: 18),
                ],
              ),
              onTap: () {
                state.setProject(name);
                Navigator.pop(context);
              },
            );
          }),

          const SizedBox(height: 12),
        ],
      ),
    );
  }

  void _showCreateProject(BuildContext context, AppState state) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => _CreateProjectSheet(state: state),
    );
  }

  void _showBrain(BuildContext context, AppState state, String projectName) {
    if (state.selectedProject == projectName) {
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (_) => _BrainSheet(
          brain: state.projectBrain,
          projectName: projectName,
          onInitBrain: () => state.initProjectBrain(projectName),
        ),
      );
    } else {
      state._api_getProjectBrain(context, projectName);
    }
  }
}

// Expose api for brain lookup from non-selected project
extension _StateExt on AppState {
  void _api_getProjectBrain(BuildContext context, String projectName) {
    final api = GeraldApi(baseUrl);
    api.getProjectBrain(projectName).then((brain) {
      if (!context.mounted) return;
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (_) =>
            _BrainSheet(brain: brain, projectName: projectName),
      );
    }).catchError((_) {
      if (!context.mounted) return;
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (_) =>
            _BrainSheet(brain: null, projectName: projectName),
      );
    });
  }
}

// ── Brain viewer sheet ────────────────────────────────────────────────────────

// ── Create project sheet ──────────────────────────────────────────────────────

class _CreateProjectSheet extends StatefulWidget {
  final AppState state;
  const _CreateProjectSheet({required this.state});

  @override
  State<_CreateProjectSheet> createState() => _CreateProjectSheetState();
}

class _CreateProjectSheetState extends State<_CreateProjectSheet> {
  final _nameCtrl = TextEditingController();
  final _pathCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  bool _creating = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _pathCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Project name is required');
      return;
    }

    setState(() {
      _creating = true;
      _error = null;
    });

    try {
      final result = await widget.state.createProject(
        name: name,
        path: _pathCtrl.text.trim(),
        description: _descCtrl.text.trim(),
      );

      if (!mounted) return;

      if (result['ok'] == true) {
        widget.state.setProject(name);
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Project '$name' created")),
        );
      } else {
        setState(() {
          _error = result['error'] as String? ?? 'Creation failed';
          _creating = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Error: $e';
        _creating = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title bar
              Row(
                children: [
                  const Icon(Icons.create_new_folder_outlined,
                      color: kAccentBlue, size: 18),
                  const SizedBox(width: 8),
                  const Text(
                    'NEW PROJECT',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 2.5,
                      color: kTextPrimary,
                    ),
                  ),
                  const Spacer(),
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: const Icon(Icons.close_rounded,
                        size: 18, color: kTextSecondary),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Project Name *',
                  hintText: 'e.g. MyApp',
                  prefixIcon: Icon(Icons.folder_outlined,
                      size: 16, color: kTextSecondary),
                ),
                style: const TextStyle(fontSize: 14, color: kTextPrimary),
                textCapitalization: TextCapitalization.words,
                autofocus: true,
                onChanged: (_) {
                  // Auto-fill path when name changes
                  final name = _nameCtrl.text.trim();
                  if (name.isNotEmpty && _pathCtrl.text.isEmpty) {
                    _pathCtrl.text = 'C:\\$name';
                  }
                },
              ),

              const SizedBox(height: 12),

              TextField(
                controller: _pathCtrl,
                decoration: const InputDecoration(
                  labelText: 'Path (optional)',
                  hintText: r'C:\MyApp',
                  prefixIcon:
                      Icon(Icons.storage_outlined, size: 16, color: kTextSecondary),
                  helperText: 'Defaults to C:\\{Name}',
                ),
                style: const TextStyle(fontSize: 14, color: kTextPrimary),
                autocorrect: false,
              ),

              const SizedBox(height: 12),

              TextField(
                controller: _descCtrl,
                decoration: const InputDecoration(
                  labelText: 'Description (optional)',
                  hintText: 'What is this project?',
                  prefixIcon: Icon(Icons.notes_outlined,
                      size: 16, color: kTextSecondary),
                ),
                style: const TextStyle(fontSize: 14, color: kTextPrimary),
                maxLines: 2,
              ),

              if (_error != null) ...[
                const SizedBox(height: 10),
                Text(
                  _error!,
                  style: const TextStyle(
                    color: kStatusError,
                    fontSize: 12,
                  ),
                ),
              ],

              const SizedBox(height: 16),

              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _creating ? null : _submit,
                  icon: _creating
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.add_rounded, size: 16),
                  label: Text(_creating ? 'CREATING...' : 'CREATE PROJECT'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 13),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BrainSheet extends StatefulWidget {
  final ProjectBrain? brain;
  final String projectName;
  final Future<Map<String, dynamic>> Function()? onInitBrain;

  const _BrainSheet({
    required this.brain,
    required this.projectName,
    this.onInitBrain,
  });

  @override
  State<_BrainSheet> createState() => _BrainSheetState();
}

class _BrainSheetState extends State<_BrainSheet> {
  bool _initing = false;
  bool _initDone = false;

  Future<void> _handleInitBrain() async {
    if (widget.onInitBrain == null) return;
    setState(() => _initing = true);
    try {
      await widget.onInitBrain!();
      setState(() => _initDone = true);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _initing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final brain = widget.brain;
    final projectName = widget.projectName;

    return DraggableScrollableSheet(
      initialChildSize: 0.65,
      minChildSize: 0.35,
      maxChildSize: 0.92,
      expand: false,
      builder: (_, scrollCtrl) {
        return Container(
          decoration: const BoxDecoration(
            color: kSurface2,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 10),
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: kBorderColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 14),

              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    const Icon(Icons.psychology_outlined,
                        color: kAccentGreen, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            projectName.toUpperCase(),
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 2,
                              color: kAccentGreen,
                            ),
                          ),
                          const Text(
                            'PROJECT BRAIN',
                            style: TextStyle(
                              fontSize: 9,
                              letterSpacing: 2,
                              color: kTextSecondary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    GestureDetector(
                      onTap: () => Navigator.pop(context),
                      child: const Icon(Icons.close_rounded,
                          size: 18, color: kTextSecondary),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 10),
              Container(height: 1, color: kBorderColor),

              // Files chips
              if (brain != null && brain.files.isNotEmpty) ...[
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: brain.files
                        .map(
                          (f) => Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: kAccentGreen.withOpacity(0.08),
                              borderRadius: BorderRadius.circular(5),
                              border: Border.all(
                                  color: kAccentGreen.withOpacity(0.25)),
                            ),
                            child: Text(
                              f,
                              style: const TextStyle(
                                fontSize: 10,
                                color: kAccentGreen,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ),
                Container(height: 1, color: kBorderColor),
              ],

              // Content
              Expanded(
                child: brain == null
                    ? const Center(
                        child: Text(
                          'Brain not available',
                          style: TextStyle(color: kTextSecondary),
                        ),
                      )
                    : brain.hasBrain
                        ? SingleChildScrollView(
                            controller: scrollCtrl,
                            padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
                            child: Text(
                              brain.brain,
                              style: const TextStyle(
                                fontSize: 12.5,
                                color: kTextPrimary,
                                height: 1.55,
                                fontFamily: 'monospace',
                              ),
                            ),
                          )
                        : _NoBrainView(
                            projectName: projectName,
                            path: brain.path,
                            onInitBrain: widget.onInitBrain != null
                                ? _handleInitBrain
                                : null,
                            initing: _initing,
                            initDone: _initDone,
                          ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ── No-brain empty state with Init button ─────────────────────────────────────

class _NoBrainView extends StatelessWidget {
  final String projectName;
  final String path;
  final VoidCallback? onInitBrain;
  final bool initing;
  final bool initDone;

  const _NoBrainView({
    required this.projectName,
    required this.path,
    this.onInitBrain,
    this.initing = false,
    this.initDone = false,
  });

  @override
  Widget build(BuildContext context) {
    if (initDone) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle_outline_rounded,
                size: 40, color: kAccentGreen),
            SizedBox(height: 12),
            Text(
              'Brain files created',
              style: TextStyle(color: kAccentGreen, fontSize: 13),
            ),
            SizedBox(height: 4),
            Text(
              'Close and reopen to view',
              style: TextStyle(color: kTextMuted, fontSize: 11),
            ),
          ],
        ),
      );
    }

    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.psychology_alt_outlined,
              size: 40, color: kTextMuted),
          const SizedBox(height: 12),
          const Text(
            'No brain files found',
            style: TextStyle(color: kTextSecondary, fontSize: 13),
          ),
          const SizedBox(height: 4),
          Text(
            'Missing: project_brain.md, roadmap.md,\ncurrent_status.md, architecture.md\nat ${path.isNotEmpty ? path : 'C:\\$projectName'}',
            textAlign: TextAlign.center,
            style: const TextStyle(color: kTextMuted, fontSize: 11),
          ),
          if (onInitBrain != null) ...[
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: initing ? null : onInitBrain,
              icon: initing
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.auto_fix_high_rounded, size: 16),
              label: Text(initing ? 'INITIALISING...' : 'INIT BRAIN'),
              style: ElevatedButton.styleFrom(
                backgroundColor: kAccentBlue.withOpacity(0.2),
                side: BorderSide(color: kAccentBlue.withOpacity(0.5)),
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
