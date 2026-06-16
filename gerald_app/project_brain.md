# Gerald App — Project Brain

**Last updated:** 2026-06-16 (V1.4 Phase 3A)

## Identity

Gerald is a voice-driven AI coding supervisor built for commuters. Matt speaks
requests by voice; Gerald routes them to Claude Code; Claude plans and executes
changes with an approval gate before any file is touched.

## Current Version

**V1.4 Phase 3A** — Flutter Android app (`C:\CommuteCoder\gerald_app\`)

## Core App Features

| Feature | Details |
|---------|---------|
| Mode A (Push-to-Talk) | Hold mic circle → speak → release → sends prompt |
| Mode B (Conversation) | Auto-listens; auto-resumes after Gerald finishes speaking |
| TTS | flutter_tts reads responses aloud (default ON) |
| Task Progress | 7-stage bar: Queued → Sending → Accepted → Working → Reviewing → Finalising → Complete |
| Elapsed Timer | Live duration counter; warns if task exceeds 120s |
| Command Queue | Multiple tasks queued; processed one at a time sequentially |
| Image Attach | Camera or gallery photo → sent alongside voice prompt |
| Conversation Orb | Mode B: animated particle orb with 3D-projected rings (CustomPainter) |
| Project Selector | Switch active project from AppBar; shows project description |
| Brain Viewer | In-app sheet displaying all four brain files for selected project |
| Init Brain | One-tap button creates stub brain files for projects missing them |
| Settings | Backend URL · TTS toggle · AI provider · Build verification |
| Adaptive Layout | SafeArea + responsive sizing; ActivityLog hidden on small screens |

## Backend Bridge (gerald_bridge.py)

Gerald app connects to `gerald_bridge.py` (FastAPI, port 8000) over LAN HTTP.

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/start` | Submit a prompt; background task queued |
| GET | `/status` | Poll: idle / planning / executing / awaiting / error |
| GET | `/read` | Fetch result after status returns idle |
| GET | `/projects` | List all registered projects |
| POST | `/send-to-claude-code` | Approve pending plan → triggers execution |
| POST | `/reject` | Reject pending task without executing |
| GET | `/project-brain/{name}` | Read all brain files for a named project |
| POST | `/init-brain/{name}` | Create stub brain files for a project |
| POST | `/build-verify` | Trigger `flutter build apk` |
| GET | `/build-status` | Poll last build result |
| GET | `/provider-status` | Active AI provider |
| POST | `/set-provider` | Switch provider (claude / openai / gemini) |

## Claude Integration

- Backend runs `claude.cmd -p <prompt>` as a PowerShell subprocess
- Prompt = brain context + task request + project isolation block (forbidden paths)
- Claude returns a PLAN; it does not edit files until approved
- Approval path: Flutter "Approve" button → `POST /send-to-claude-code` → pyautogui
  injects approved task into the Claude Code terminal window on the host machine
- Brain files are auto-read before every prompt; stubs auto-created if absent

## Phone App Status

- **Platform:** Android (Flutter 3.x / Dart)
- **iOS:** Not implemented — deferred to V1.5+
- **Build:** `flutter build apk --debug` → ✅ clean (0 errors, 0 warnings)
- **Analysis:** `flutter analyze` → 0 errors, ~101 info-level hints (pre-existing style hints)
- **Setup:** `flutter pub get` → set LAN IP in Settings → `flutter run`

## Project Brain System (Phase 3A — Complete)

Each registered project carries four brain files in its root directory:

| File | Purpose |
|------|---------|
| `project_brain.md` | Identity, features, decisions, known limitations |
| `roadmap.md` | Version history + planned milestones |
| `current_status.md` | Live working state + active issues |
| `architecture.md` | Structure, data flow, design decisions |

Behaviour:
- Auto-injected into every Claude prompt so Claude always has project context
- Auto-created as stub files on first task submission if missing
- Viewable in-app via BrainSheet (tap project name in selector)
- Manually initializable via "Init Brain" button or `POST /init-brain/{name}`

## Key Design Decisions

- **Approval gate:** Claude produces a plan; Matt must approve before any edits happen
- **3-second polling:** `/status` polled on a timer instead of WebSocket — simpler over LAN
- **TTS default ON:** Matt drives during commute; audio feedback required
- **Particle orb via CustomPainter:** No animation library; pure Flutter gives full control
- **Provider over Bloc/Riverpod:** App is small enough; Provider keeps state readable
- **Stage-based progress:** Backend has no streaming; stages inferred from status transitions

## Known Limitations

- Android only — no iOS support yet
- Requires LAN connectivity; no cloud backend deployment yet
- Approval injection uses pyautogui desktop automation — fragile if window loses focus
- OpenAI and Gemini providers exist in the backend framework but are not live
- No FCM push notifications — app must be open to receive task completion
- No persistent conversation history across app restarts
- Build verification only supports Flutter APK builds (not Python / Node projects)
- No automatic project creation from within the app yet (Phase 3B)
