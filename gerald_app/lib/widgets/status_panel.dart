import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../theme.dart';

class StatusPanel extends StatelessWidget {
  const StatusPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final color = _statusColor(state.status, state.isSpeaking);
    final label = _statusLabel(state.status, state.isSpeaking);

    return Container(
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.25)),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.06),
            blurRadius: 16,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ── Status row ──────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
            child: Row(
              children: [
                _StatusDot(color: color),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: TextStyle(
                          color: color,
                          fontWeight: FontWeight.w700,
                          fontSize: 10,
                          letterSpacing: 1.8,
                        ),
                      ),
                      if (state.currentTask.isNotEmpty &&
                          state.status != GeraldStatus.idle)
                        Padding(
                          padding: const EdgeInsets.only(top: 3),
                          child: Text(
                            state.currentTask,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 11.5,
                              color: kTextSecondary,
                              height: 1.4,
                            ),
                          ),
                        ),
                      if (state.queueCount > 0)
                        Padding(
                          padding: const EdgeInsets.only(top: 3),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.queue_rounded,
                                size: 10,
                                color: kStatusAwaiting,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                '${state.queueCount} task${state.queueCount == 1 ? "" : "s"} queued',
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: kStatusAwaiting,
                                  letterSpacing: 0.3,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                if (state.status == GeraldStatus.awaiting) ...[
                  const SizedBox(width: 8),
                  _ActionButton(
                    label: 'APPROVE',
                    color: kAccentGreen,
                    onPressed: state.approve,
                  ),
                  const SizedBox(width: 6),
                  _ActionButton(
                    label: 'REJECT',
                    color: kStatusError,
                    onPressed: state.reject,
                  ),
                ],
                if (state.isSpeaking) ...[
                  const SizedBox(width: 8),
                  _ActionButton(
                    label: 'STOP',
                    color: kAccentPurple,
                    onPressed: state.stopSpeaking,
                  ),
                ],
              ],
            ),
          ),

          // ── Task progress section ────────────────────────────────────────────
          if (state.hasActiveTask)
            _TaskProgressSection(state: state),
        ],
      ),
    );
  }

  Color _statusColor(GeraldStatus s, bool speaking) {
    if (speaking) return kStatusSpeaking;
    return switch (s) {
      GeraldStatus.idle => kStatusIdle,
      GeraldStatus.planning => kStatusPlanning,
      GeraldStatus.awaiting => kStatusAwaiting,
      GeraldStatus.executing => kStatusExecuting,
      GeraldStatus.error => kStatusError,
      GeraldStatus.offline => kStatusError,
    };
  }

  String _statusLabel(GeraldStatus s, bool speaking) {
    if (speaking) return 'SPEAKING';
    return switch (s) {
      GeraldStatus.idle => 'IDLE',
      GeraldStatus.planning => 'PLANNING',
      GeraldStatus.awaiting => 'AWAITING APPROVAL',
      GeraldStatus.executing => 'EXECUTING',
      GeraldStatus.error => 'ERROR',
      GeraldStatus.offline => 'OFFLINE',
    };
  }
}

// ── Task progress bar ─────────────────────────────────────────────────────────

class _TaskProgressSection extends StatelessWidget {
  final AppState state;
  const _TaskProgressSection({required this.state});

  @override
  Widget build(BuildContext context) {
    final isError = state.taskStage == TaskStage.error;
    final isComplete = state.taskStage == TaskStage.complete;
    final progress = state.taskProgress / 100.0;
    final elapsed = state.taskElapsed;
    final elapsedStr = _formatElapsed(elapsed);

    final barColor = isError
        ? kStatusError
        : isComplete
            ? kAccentGreen
            : kAccentBlue;

    return Container(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: kBorderColor)),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(14)),
      ),
      padding: const EdgeInsets.fromLTRB(14, 8, 14, 10),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: isError ? null : progress, // null = indeterminate on error? No, show 0
              minHeight: 3,
              backgroundColor: kBorderColor,
              valueColor: AlwaysStoppedAnimation<Color>(barColor),
            ),
          ),

          const SizedBox(height: 6),

          // Stage label + elapsed
          Row(
            children: [
              // Stage indicator dot
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: barColor,
                ),
              ),
              const SizedBox(width: 6),
              // Stage name
              Expanded(
                child: Text(
                  state.taskStageName,
                  style: TextStyle(
                    color: barColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
              ),
              // Percent
              if (!isError)
                Text(
                  '${state.taskProgress}%',
                  style: TextStyle(
                    color: barColor.withOpacity(0.7),
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    fontFamily: 'monospace',
                  ),
                ),
              const SizedBox(width: 8),
              // Elapsed time
              Text(
                elapsedStr,
                style: const TextStyle(
                  color: kTextSecondary,
                  fontSize: 10,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),

          // Long task warning
          if (state.isLongTask && !isComplete && !isError)
            Padding(
              padding: const EdgeInsets.only(top: 5),
              child: Row(
                children: [
                  Icon(
                    Icons.access_time_rounded,
                    size: 10,
                    color: kStatusAwaiting,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Long task — Claude is still working',
                    style: const TextStyle(
                      color: kStatusAwaiting,
                      fontSize: 10,
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  String _formatElapsed(Duration d) {
    final m = d.inMinutes;
    final s = d.inSeconds % 60;
    if (m > 0) return '${m}m ${s.toString().padLeft(2, '0')}s';
    return '${s}s';
  }
}

// ── Status dot (animated) ─────────────────────────────────────────────────────

class _StatusDot extends StatefulWidget {
  final Color color;
  const _StatusDot({required this.color});

  @override
  State<_StatusDot> createState() => _StatusDotState();
}

class _StatusDotState extends State<_StatusDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _anim = Tween(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: widget.color,
          boxShadow: [
            BoxShadow(
              color: widget.color.withOpacity(_anim.value * 0.8),
              blurRadius: 8,
              spreadRadius: 2,
            ),
          ],
        ),
      ),
    );
  }
}

// ── Action button ─────────────────────────────────────────────────────────────

class _ActionButton extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onPressed;

  const _ActionButton({
    required this.label,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onPressed,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: color.withOpacity(0.14),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withOpacity(0.5)),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
            ),
          ),
        ),
      );
}
