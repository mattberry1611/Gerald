# Gerald App — Flutter V1.1

Gerald is a dark-themed Android app that lets Matt talk to his AI coding supervisor while driving.

---

## Quick start

### Prerequisites

| Tool | Version |
|------|---------|
| Flutter SDK | 3.16+ |
| Android SDK | API 21+ |
| Physical Android phone (API 21+) | Required for mic + speech |

### 1. Install dependencies

```bash
cd C:\CommuteCoder\gerald_app
flutter pub get
```

### 2. Start the Gerald backend (on PC)

```bash
cd C:\CommuteCoder
uvicorn gerald_bridge:app --host 0.0.0.0 --port 8000
```

### 3. Connect phone

- Enable Developer Options + USB Debugging on your phone
- Plug in via USB
- Run `flutter devices` to confirm it appears

### 4. Run the app

```bash
flutter run
```

Or build a release APK for sideloading:

```bash
flutter build apk --release
# APK at: build/app/outputs/flutter-apk/app-release.apk
```

---

## First-time setup on phone

1. Open Gerald
2. Tap **Settings** (gear icon, top right)
3. Change the backend URL to your PC's LAN IP:
   ```
   http://192.168.1.XXX:8000
   ```
   (Find your PC's IP with `ipconfig` on Windows — look for the Wi-Fi adapter)
4. Tap **Save & Reconnect**
5. Status dot should turn from red (offline) to grey (idle)

---

## Voice Modes (V1.1)

Gerald supports two voice modes selectable from the bottom of the main screen.

### Mode A — Push-to-Talk (default)
- Tap the **A  PUSH-TO-TALK** chip (or it is active by default).
- Tap the green mic circle to start recording, tap again to send.
- Gerald processes the command and replies in the message feed.
- Best for discrete, one-shot commands.

### Mode B — Conversation Mode
- Tap the **B  CONVERSATION** chip to activate.
- Gerald **auto-listens** immediately. When you pause speaking, the command is sent automatically.
- After Gerald responds, listening resumes automatically — no tapping required.
- Tap **END** (the red button) or the **A  PUSH-TO-TALK** chip to exit.
- Best for back-and-forth dialogue while commuting.

### Text-to-Speech
- Go to **Settings → Voice → Speak Gerald responses** to enable.
- When enabled, all Gerald replies are spoken aloud using the on-device TTS engine.
- No internet required — uses Android's built-in TextToSpeech API.

---

## V2 Roadmap: Locked-Screen / Background Continuous Listening

True background or locked-screen continuous listening is **not implemented in V1**.  
In V1, Mode B requires the app to remain in the foreground.

Achieving locked-screen continuous conversation on Android requires:

- **Android Foreground Service** with a persistent notification to keep the process alive.  
- **FOREGROUND_SERVICE_MICROPHONE** permission (Android 14+).  
- Binding to `SpeechRecognizer` directly in Kotlin native code (not via the Flutter plugin) so the mic stays active across screen locks.  
- **WAKE_LOCK** to prevent CPU sleep.  
- Optional **wake-word detection** (e.g. Vosk offline model) so the mic is only fully active when triggered, avoiding constant recording.  
- Native `RecognitionListener` callbacks piped back to Flutter via a `MethodChannel`.

These are planned for **Gerald V2**.

---

## Using Gerald while driving

1. Select a project using the **folder chip** in the header
2. Choose **Mode A** (tap mic) or **Mode B** (auto-listen)
3. Speak your request — Gerald sends it to the backend
4. Wait for the status panel to show the result
5. If the status shows **AWAITING APPROVAL**, tap **APPROVE** or **REJECT**
6. Tap the **keyboard icon** to type instead of speaking
7. Tap the **paperclip icon** to attach a photo (camera or gallery)
8. If Gerald is busy, new commands are automatically **queued** — the status panel shows how many tasks are waiting

---

## App structure

```
lib/
├── main.dart                    — entry point, initialises notifications + TTS
├── theme.dart                   — dark colour palette + MaterialApp theme
├── providers/
│   └── app_state.dart           — ChangeNotifier: messages, status, polling, voice modes, TTS
├── services/
│   ├── gerald_api.dart          — HTTP client (POST /start, GET /read, etc.)
│   ├── notification_service.dart — local notifications + FCM placeholder
│   └── tts_service.dart         — flutter_tts singleton, speaks Gerald responses
├── screens/
│   ├── home_screen.dart         — Mode A/B selector, voice section, keyboard-safe layout
│   └── settings_screen.dart     — backend URL, TTS toggle, voice mode toggle, clear data
└── widgets/
    ├── push_to_talk_button.dart  — Mode A PTT + Mode B auto-listen indicator
    ├── message_bubble.dart       — chat bubbles (user/gerald), code blocks, image preview
    ├── status_panel.dart         — status dot, task label, approve/reject, queue count
    ├── activity_log.dart         — timestamped mini-log panel
    ├── project_selector.dart     — bottom-sheet project picker
    └── text_input_bar.dart       — text fallback input
```

---

## Backend API used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/start` | Send voice/text prompt |
| GET | `/read` | Poll for completed result |
| GET | `/status` | 3-second polling for status |
| GET | `/projects` | Populate project selector |
| POST | `/send-to-claude-code` | Approve a planned task |
| POST | `/reject` | Reject a planned task |

---

## Push notifications

V1 uses `flutter_local_notifications` for on-device notifications when a task completes (fires from the polling loop when status transitions from `executing` → `idle`).

Production FCM is stubbed in `notification_service.dart::registerForPushNotifications()`. To wire it up:
1. Add `firebase_messaging` to `pubspec.yaml`
2. Create Firebase project → download `google-services.json` → place in `android/app/`
3. Add `classpath 'com.google.gms:google-services:4.x'` to `android/build.gradle`
4. Replace the stub in `notification_service.dart` with `FirebaseMessaging.instance.getToken()`
5. POST the token to `/register-device` on the backend
6. Add `firebase-admin` to `gerald_bridge.py` and call `messaging.send()` on task completion

---

## Command queue

If a task is already in progress when you send a new command (by voice or text), the new command is automatically added to a queue. The status panel shows a yellow "N tasks queued" label. Tasks process in order once the current task completes or is rejected.

The queue is cleared when you use the **Clear conversation** button.

---

## Image attachment

Tap the **paperclip** icon (bottom bar) to attach a photo. Choose **Camera** or **Gallery**. The image appears in the conversation thread immediately. In V1, images are stored locally on the device and displayed as a preview — backend upload is not yet implemented.

**Required permissions (Android):** Camera, Read Media Images (API 33+) / Read External Storage (API ≤ 32). The app requests these at runtime when you first use the image picker.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Status stuck "OFFLINE" | Check backend URL in Settings; ensure `gerald_bridge.py` is running |
| Mic button does nothing | Grant microphone permission in Android app settings |
| HTTP cleartext error | `usesCleartextTraffic=true` is already set in AndroidManifest.xml |
| Speech not recognised | `speech_to_text` requires a native build — use `flutter run`, not Expo Go |
| "flutter.sdk not found" | Run `flutter pub get` first to generate `android/local.properties` |
| Image picker crashes | Grant Camera / Photos permission in Android app settings |
