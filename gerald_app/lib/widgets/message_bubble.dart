import 'dart:io';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/app_state.dart';
import '../theme.dart';

class MessageBubble extends StatefulWidget {
  final Message message;
  const MessageBubble({super.key, required this.message});

  @override
  State<MessageBubble> createState() => _MessageBubbleState();
}

class _MessageBubbleState extends State<MessageBubble> {
  bool _showTs = false;
  bool _filesExpanded = false;

  @override
  Widget build(BuildContext context) {
    final isUser = widget.message.role == 'user';

    // Result card takes over the full bubble for terminal task states.
    if (!isUser && widget.message.resultCard != null) {
      return _buildResultCard(context, widget.message.resultCard!);
    }

    final align = isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;

    final hasImage = widget.message.imagePath != null;
    final showText = widget.message.content.isNotEmpty &&
        widget.message.content != '[Image]';

    return GestureDetector(
      onLongPress: () => setState(() => _showTs = !_showTs),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        child: Column(
          crossAxisAlignment: align,
          children: [
            // Sender label
            if (!isUser)
              Padding(
                padding: const EdgeInsets.only(left: 6, bottom: 4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(3),
                        boxShadow: [
                          BoxShadow(
                            color: kAccentBlue.withOpacity(0.3),
                            blurRadius: 6,
                          ),
                        ],
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: Image.asset(
                          'assets/gerald_logo.png',
                          fit: BoxFit.cover,
                        ),
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      'GERALD',
                      style: TextStyle(
                        color: kAccentBlue.withOpacity(0.85),
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ],
                ),
              ),

            // Bubble
            ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.82,
              ),
              child: Container(
                decoration: BoxDecoration(
                  color: isUser ? kUserBubble : kGeraldBubble,
                  borderRadius: isUser
                      ? const BorderRadius.only(
                          topLeft: Radius.circular(18),
                          topRight: Radius.circular(5),
                          bottomLeft: Radius.circular(18),
                          bottomRight: Radius.circular(18),
                        )
                      : const BorderRadius.only(
                          topLeft: Radius.circular(5),
                          topRight: Radius.circular(18),
                          bottomLeft: Radius.circular(18),
                          bottomRight: Radius.circular(18),
                        ),
                  border: Border.all(
                    color: isUser
                        ? kAccentBlue.withOpacity(0.2)
                        : kAccentGreen.withOpacity(0.12),
                    width: 1,
                  ),
                ),
                padding: EdgeInsets.symmetric(
                  horizontal: hasImage ? 6 : 14,
                  vertical: hasImage ? 6 : 11,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (hasImage) _buildImage(widget.message.imagePath!),
                    if (hasImage && showText) const SizedBox(height: 8),
                    if (showText || (!hasImage && !showText))
                      Padding(
                        padding: hasImage
                            ? const EdgeInsets.symmetric(horizontal: 8)
                            : EdgeInsets.zero,
                        child: _buildContent(widget.message.content),
                      ),
                  ],
                ),
              ),
            ),

            // Timestamp (on long press)
            if (_showTs)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  DateFormat('HH:mm:ss').format(widget.message.timestamp),
                  style: const TextStyle(
                    fontSize: 10,
                    color: kTextSecondary,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildImage(String imagePath) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Image.file(
        File(imagePath),
        fit: BoxFit.cover,
        width: double.infinity,
        errorBuilder: (_, __, ___) => Container(
          height: 80,
          decoration: BoxDecoration(
            color: kSurface2,
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Center(
            child: Icon(Icons.broken_image_outlined,
                color: kTextSecondary, size: 32),
          ),
        ),
      ),
    );
  }

  Widget _buildContent(String content) {
    final parts = content.split('```');
    if (parts.length < 3) {
      return SelectableText(
        content,
        style: const TextStyle(
          fontSize: 14.5,
          height: 1.5,
          color: kTextPrimary,
        ),
      );
    }

    final widgets = <Widget>[];
    for (int i = 0; i < parts.length; i++) {
      if (i.isEven) {
        if (parts[i].isNotEmpty) {
          widgets.add(SelectableText(
            parts[i],
            style: const TextStyle(
              fontSize: 14.5,
              height: 1.5,
              color: kTextPrimary,
            ),
          ));
        }
      } else {
        final raw = parts[i].replaceFirst(RegExp(r'^\w+\n'), '');
        widgets.add(
          Container(
            margin: const EdgeInsets.symmetric(vertical: 8),
            padding: const EdgeInsets.all(12),
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFF070710),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: kBorderColor),
            ),
            child: SelectableText(
              raw,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12.5,
                color: Color(0xFF7EC8C8),
                height: 1.5,
              ),
            ),
          ),
        );
      }
    }
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: widgets);
  }

  Widget _buildResultCard(BuildContext context, Map<String, dynamic> card) {
    final status = (card['status'] as String? ?? '').toLowerCase();
    final summary = card['summary'] as String? ?? '';
    final failureReason = card['failure_reason'] as String?;
    final nextAction = card['next_action'] as String?;
    final files = (card['files_changed'] as List?)?.cast<String>() ?? [];
    final apkBuilt = card['apk_built'] == true;
    final apkUrl = card['apk_download_url'] as String?;

    final Color headerColor;
    final IconData headerIcon;
    final String headerLabel;
    switch (status) {
      case 'completed':
        headerColor = const Color(0xFF22C55E);
        headerIcon = Icons.check_circle_outline;
        headerLabel = 'COMPLETED';
        break;
      case 'partial':
        headerColor = const Color(0xFFF59E0B);
        headerIcon = Icons.warning_amber_outlined;
        headerLabel = 'PARTIALLY COMPLETED';
        break;
      case 'contract_failed':
        headerColor = const Color(0xFFEF4444);
        headerIcon = Icons.cancel_outlined;
        headerLabel = 'CONTRACT FAILED';
        break;
      case 'failed':
        headerColor = const Color(0xFFEF4444);
        headerIcon = Icons.error_outline;
        headerLabel = 'FAILED';
        break;
      default:
        headerColor = kAccentBlue;
        headerIcon = Icons.info_outline;
        headerLabel = status.toUpperCase();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // GERALD label
          Padding(
            padding: const EdgeInsets.only(left: 6, bottom: 4),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(3),
                    boxShadow: [
                      BoxShadow(color: kAccentBlue.withOpacity(0.3), blurRadius: 6),
                    ],
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: Image.asset('assets/gerald_logo.png', fit: BoxFit.cover),
                  ),
                ),
                const SizedBox(width: 5),
                Text(
                  'GERALD',
                  style: TextStyle(
                    color: kAccentBlue.withOpacity(0.85),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.5,
                  ),
                ),
              ],
            ),
          ),

          // Card body
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFF0D1B2A),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: headerColor.withOpacity(0.35), width: 1.2),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status header bar
                Container(
                  decoration: BoxDecoration(
                    color: headerColor.withOpacity(0.12),
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(13)),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  child: Row(
                    children: [
                      Icon(headerIcon, color: headerColor, size: 18),
                      const SizedBox(width: 8),
                      Text(
                        headerLabel,
                        style: TextStyle(
                          color: headerColor,
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ],
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Summary
                      if (summary.isNotEmpty)
                        SelectableText(
                          summary,
                          style: const TextStyle(
                            fontSize: 14,
                            height: 1.45,
                            color: kTextPrimary,
                          ),
                        ),

                      // Failure reason
                      if (failureReason != null && failureReason.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: const Color(0xFF1A0A0A),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: const Color(0xFFEF4444).withOpacity(0.25),
                            ),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Icon(Icons.report_outlined,
                                  color: Color(0xFFEF4444), size: 14),
                              const SizedBox(width: 6),
                              Expanded(
                                child: SelectableText(
                                  failureReason,
                                  style: const TextStyle(
                                    fontSize: 12.5,
                                    color: Color(0xFFFFB3B3),
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],

                      // Files changed
                      if (files.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        GestureDetector(
                          onTap: () => setState(() => _filesExpanded = !_filesExpanded),
                          child: Row(
                            children: [
                              Icon(Icons.edit_document,
                                  size: 13, color: kAccentBlue.withOpacity(0.8)),
                              const SizedBox(width: 5),
                              Text(
                                '${files.length} file${files.length == 1 ? '' : 's'} changed',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: kAccentBlue.withOpacity(0.8),
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(width: 4),
                              Icon(
                                _filesExpanded
                                    ? Icons.keyboard_arrow_up
                                    : Icons.keyboard_arrow_down,
                                size: 14,
                                color: kTextSecondary,
                              ),
                            ],
                          ),
                        ),
                        if (_filesExpanded) ...[
                          const SizedBox(height: 6),
                          ...files.map((f) => Padding(
                                padding: const EdgeInsets.symmetric(vertical: 2),
                                child: Row(
                                  children: [
                                    const Icon(Icons.circle,
                                        size: 5, color: kTextSecondary),
                                    const SizedBox(width: 6),
                                    Expanded(
                                      child: Text(
                                        f,
                                        style: const TextStyle(
                                          fontFamily: 'monospace',
                                          fontSize: 11.5,
                                          color: kTextSecondary,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  ],
                                ),
                              )),
                        ],
                      ],

                      // APK row
                      if (apkBuilt) ...[
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: const Color(0xFF166534),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.android, size: 13, color: Color(0xFF86EFAC)),
                                  SizedBox(width: 4),
                                  Text(
                                    'APK BUILT',
                                    style: TextStyle(
                                      color: Color(0xFF86EFAC),
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.8,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (apkUrl != null) ...[
                              const SizedBox(width: 8),
                              GestureDetector(
                                onTap: () => launchUrl(Uri.parse(apkUrl)),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: kAccentBlue.withOpacity(0.15),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(
                                        color: kAccentBlue.withOpacity(0.4)),
                                  ),
                                  child: const Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.download,
                                          size: 13, color: kAccentBlue),
                                      SizedBox(width: 4),
                                      Text(
                                        'DOWNLOAD',
                                        style: TextStyle(
                                          color: kAccentBlue,
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                          letterSpacing: 0.8,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ],

                      // Next action
                      if (nextAction != null && nextAction.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0A1628),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: kBorderColor),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.arrow_forward,
                                  size: 13, color: kTextSecondary),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  nextAction,
                                  style: const TextStyle(
                                    fontSize: 12.5,
                                    color: kTextSecondary,
                                    fontStyle: FontStyle.italic,
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
              ],
            ),
          ),
        ],
      ),
    );
  }
}
