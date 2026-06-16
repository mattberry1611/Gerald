# Gerald App — Current Status

**Date:** 2026-06-16
**Version:** V1.4 Phase 3A
**Build target:** Android (debug APK)
**Flutter SDK:** 3.x
**Milestone:** ✅ V1.4 Phase 3A complete — Project Brain System in place

## What's Working

| Feature | Status |
|---------|--------|
| Mode A Push-to-Talk | ✅ Working |
| Mode B Conversation | ✅ Working |
| TTS (default ON) | ✅ Working |
| Task progress bar (7 stages) | ✅ Working |
| Elapsed timer | ✅ Working |
| Long-task warning (>120s) | ✅ Working |
| Command queue | ✅ Working |
| Image attach (camera / gallery) | ✅ Working |
| Conversation Orb (Mode B) | ✅ Working |
| Adaptive layout / overflow fixes | ✅ Working |
| Small screen support | ✅ Working |
| Project Selector | ✅ Working |
| Brain Viewer (in-app sheet) | ✅ Working |
| Init Brain button | ✅ Working |
| Brain auto-inject into Claude prompt | ✅ Working (backend) |
| Brain auto-create stubs on first task | ✅ Working (backend) |
| /project-brain/{name} endpoint | ✅ Working |
| /init-brain/{name} endpoint | ✅ Working |
| Build Verification | ✅ Working (build_verifier.py + /build-verify) |
| Multi-AI Provider framework | ✅ Stubbed (claude active; openai/gemini not live) |
| flutter build apk --debug | ✅ Clean (0 errors) |
| flutter analyze | ✅ 0 errors (101 pre-existing info hints) |

## Not Yet Implemented

| Feature | Planned |
|---------|---------|
| Automatic project creation from app | Phase 3B |
| Project isolation (per-project outbox) | Phase 3C |
| Cloud backend deployment | V1.5 |
| FCM push notifications | V1.5 |
| iOS support | V1.5 |
| Live OpenAI / Gemini integration | V2.1 |
| Full autonomy (no approval gate) | V2.0 |

## Active Issues

- None currently known

## File Locations

| File | Purpose |
|------|---------|
| `lib/main.dart` | App entry point, Provider setup |
| `lib/theme.dart` | Colors (kAccentBlue, kAccentGreen, kBgColor) and text styles |
| `lib/providers/app_state.dart` | All app state: TaskStage, queue, messages, build/provider state |
| `lib/screens/home_screen.dart` | Main UI (adaptive, overflow-safe) |
| `lib/screens/splash_screen.dart` | 1.5s branded splash |
| `lib/screens/settings_screen.dart` | Settings: URL, TTS, provider, build |
| `lib/widgets/status_panel.dart` | Status dot + 7-stage progress bar |
| `lib/widgets/conversation_orb.dart` | Particle orb (Mode B) |
| `lib/widgets/push_to_talk_button.dart` | Mic circle (Mode A) or orb wrapper (Mode B) |
| `lib/widgets/message_bubble.dart` | User and Gerald chat bubbles |
| `lib/widgets/activity_log.dart` | Recent event log |
| `lib/widgets/text_input_bar.dart` | Keyboard text input |
| `lib/services/tts_service.dart` | flutter_tts wrapper |
| `lib/services/gerald_api.dart` | HTTP calls to gerald_bridge.py |
| `lib/services/ai_provider_service.dart` | Provider enum + API key storage |
| `lib/services/notification_service.dart` | flutter_local_notifications wrapper |

## Setup Instructions

1. Run `python gerald_bridge.py` on the host machine (port 8000)
2. Set the backend LAN IP in Gerald app Settings → Backend URL
3. Select a project from the project selector in the AppBar
4. Hold mic (Mode A) or switch to Mode B and speak
5. Gerald returns Claude's plan; tap Approve to execute or Reject to cancel
