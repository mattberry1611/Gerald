import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../theme.dart';

class TextInputBar extends StatefulWidget {
  const TextInputBar({super.key});

  @override
  State<TextInputBar> createState() => _TextInputBarState();
}

class _TextInputBarState extends State<TextInputBar> {
  final _controller = TextEditingController();
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance
        .addPostFrameCallback((_) => _focus.requestFocus());
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _send(AppState state) {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    _focus.unfocus();
    state.sendPrompt(text);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(
          top: BorderSide(color: kBorderColor),
          bottom: BorderSide(color: kBorderColor),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              focusNode: _focus,
              minLines: 1,
              maxLines: 5,
              style: const TextStyle(
                fontSize: 14,
                color: kTextPrimary,
                height: 1.4,
              ),
              decoration: const InputDecoration(
                hintText: 'Type a command...',
                hintStyle: TextStyle(color: kTextSecondary),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                isDense: true,
              ),
              onSubmitted: (_) => _send(state),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: state.isLoading ? null : () => _send(state),
            child: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: state.isLoading
                    ? kBorderColor
                    : kAccentBlue.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: state.isLoading
                      ? kBorderColor
                      : kAccentBlue.withOpacity(0.5),
                ),
              ),
              child: Icon(
                Icons.send_rounded,
                size: 20,
                color: state.isLoading ? kTextSecondary : kAccentBlue,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
