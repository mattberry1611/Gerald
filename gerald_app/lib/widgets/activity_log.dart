import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../theme.dart';

class ActivityLog extends StatelessWidget {
  const ActivityLog({super.key});

  @override
  Widget build(BuildContext context) {
    final log = context.watch<AppState>().activityLog;

    return Container(
      height: 90,
      margin: const EdgeInsets.fromLTRB(12, 6, 12, 6),
      decoration: BoxDecoration(
        color: const Color(0xFF07070F),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kBorderColor),
        // Subtle left accent bar
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Row(
          children: [
            // Left accent bar
            Container(
              width: 2,
              color: kAccentBlue.withOpacity(0.35),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(10, 7, 10, 7),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.terminal_rounded,
                          size: 9,
                          color: kTextSecondary.withOpacity(0.7),
                        ),
                        const SizedBox(width: 5),
                        Text(
                          'ACTIVITY LOG',
                          style: TextStyle(
                            fontSize: 8.5,
                            letterSpacing: 2.5,
                            color: kTextSecondary.withOpacity(0.7),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 5),
                    Expanded(
                      child: log.isEmpty
                          ? Text(
                              'Waiting for activity...',
                              style: TextStyle(
                                fontSize: 11,
                                color: kTextMuted,
                                fontFamily: 'monospace',
                              ),
                            )
                          : ListView.builder(
                              itemCount: log.length,
                              itemBuilder: (_, i) {
                                final entry = log[i];
                                // Split [HH:MM:SS] from the rest
                                final tsMatch =
                                    RegExp(r'^\[(\d{2}:\d{2}:\d{2})\] (.*)$')
                                        .firstMatch(entry);
                                if (tsMatch == null) {
                                  return Text(
                                    entry,
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontFamily: 'monospace',
                                      color: kTextSecondary,
                                      height: 1.4,
                                    ),
                                  );
                                }
                                return RichText(
                                  text: TextSpan(
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontFamily: 'monospace',
                                      height: 1.45,
                                    ),
                                    children: [
                                      TextSpan(
                                        text: '[${tsMatch.group(1)}] ',
                                        style: TextStyle(
                                          color: kAccentBlue.withOpacity(0.5),
                                        ),
                                      ),
                                      TextSpan(
                                        text: tsMatch.group(2),
                                        style: const TextStyle(
                                          color: kTextSecondary,
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
