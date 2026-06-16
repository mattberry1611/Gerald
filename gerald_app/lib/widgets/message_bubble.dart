import 'dart:io';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
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

  @override
  Widget build(BuildContext context) {
    final isUser = widget.message.role == 'user';
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
}
