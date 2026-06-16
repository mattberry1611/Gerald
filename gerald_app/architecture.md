# Gerald App — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Gerald App (Flutter / Android)              │
│                                                                  │
│  ┌──────────┐    ┌────────────────────┐    ┌──────────────────┐ │
│  │  Voice   │    │     AppState       │    │   UI Widgets     │ │
│  │  Input   │───▶│  (ChangeNotifier)  │───▶│  HomeScreen      │ │
│  │  STT     │    │                    │    │  StatusPanel     │ │
│  └──────────┘    │  TaskStage enum    │    │  ConversationOrb │ │
│                  │  taskProgress      │    │  PushToTalkBtn   │ │
│  ┌──────────┐    │  _commandQueue     │    │  ActivityLog     │ │
│  │   TTS    │◀───│  projectMessages   │    │  MessageBubble   │ │
│  │ Service  │    │  buildState        │    └──────────────────┘ │
│  └──────────┘    │  aiProvider        │                          │
│                  └────────┬───────────┘                          │
│                           │                                      │
│                  ┌────────▼───────────┐                          │
│                  │    GeraldApi       │                          │
│                  │  (HTTP, LAN:8000)  │                          │
│                  └────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │  LAN HTTP  port 8000
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  gerald_bridge.py  (FastAPI)                     │
│                                                                  │
│  POST /start          Queue prompt → build_prompt() → claude     │
│  GET  /status         idle / planning / executing / awaiting     │
│  GET  /read           Return last result JSON                    │
│  GET  /projects       List gerald_projects.json                  │
│  POST /send-to-...    Approve: pyautogui → Claude Code terminal  │
│  POST /reject         Cancel pending task                        │
│  GET  /project-brain  Read brain files for project               │
│  POST /init-brain     Create stub brain files                    │
│  POST /build-verify   Run build_verifier.py                      │
│  GET  /build-status   Return last build result                   │
│  GET  /provider-status  Active AI provider                       │
│  POST /set-provider   Switch AI provider                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
               ┌──────────┴──────────┐
               │                     │
               ▼                     ▼
        Claude Code (CLI)      build_verifier.py
        claude.cmd -p          flutter build apk
        in project CWD
```

## State Machine (AppState)

```
GeraldStatus (from backend /status):
  offline ──▶ idle ──▶ planning ──▶ executing ──▶ idle
                  ╰──▶ awaiting ──▶ executing ──▶ idle
                  ╰──▶ error

TaskStage (Flutter progress tracking — inferred from status):
  none ──▶ queued ──▶ sending ──▶ accepted ──▶ working ──▶ reviewing ──▶ finalising ──▶ complete ──▶ none
                                                          ╰──▶ error ──▶ none (after 5s auto-clear)
```

## Data Flow — Sending a Prompt

```
1. User speaks (STT) or types
2. AppState.sendPrompt(prompt)
   ├─ If busy or queue not empty: enqueue → stage = queued
   └─ If free: _executePrompt(prompt)
       ├─ stage = sending, startElapsedTimer()
       ├─ POST /start → stage = accepted
       └─ _poll() every 3s:
           planning/executing → stage = working
           awaiting           → stage = reviewing
           idle               → _readResult()
3. _readResult()
   ├─ GET /read → stage = finalising
   ├─ Add message bubble
   ├─ TTS speak result (if enabled)
   └─ stage = complete → none after brief display
4. _processNextInQueue() if items waiting
```

## Data Flow — Brain Injection (Phase 3A)

```
1. Flutter POST /start {prompt, project}
2. gerald_bridge resolves project path from gerald_projects.json
3. read_brain_files(project_path) → reads all four .md files
   └─ If any missing: create_brain_files(project_path) → write stubs
4. build_prompt(task, brain_context) → assembles full Claude prompt:
   ┌──────────────────────────────────────────┐
   │ [BRAIN CONTEXT]                          │
   │ project_brain.md content                 │
   │ architecture.md content                  │
   │ current_status.md content                │
   │ roadmap.md content                       │
   │                                          │
   │ [TASK]                                   │
   │ <user prompt>                            │
   │                                          │
   │ [INSTRUCTIONS]                           │
   │ Plan only. Do not edit without approval. │
   └──────────────────────────────────────────┘
5. claude.cmd -p <full_prompt> run in project CWD
6. Result → gerald_outbox.json → Flutter reads via GET /read
```

## Widget Tree

```
GeraldApp
└── ChangeNotifierProvider<AppState>
    └── MaterialApp (dark theme)
        └── SplashScreen (1.5s branded)
            └── HomeScreen
                ├── AppBar
                │   ├── Gerald logo
                │   ├── ProjectSelector (tap → ProjectSelectorSheet)
                │   │   └── BrainSheet (tap brain icon → BrainViewer)
                │   └── Settings icon
                ├── StatusPanel
                │   ├── Status dot (color-coded by GeraldStatus)
                │   ├── 7-stage progress bar (TaskStage)
                │   └── Elapsed timer / long-task warning
                ├── Expanded ListView (conversation)
                │   └── MessageBubble* (user or Gerald)
                ├── [TextInputBar] (keyboard input, optional)
                └── keyboard? CompactBar : BottomSection
                    ├── [ActivityLog] (hidden on small screens or keyboard open)
                    └── VoiceSection
                        ├── ModeSelector (A / B segmented)
                        ├── PushToTalkButton
                        │   ├── Mode A: GlowCircle mic button
                        │   └── Mode B: ConversationOrb (particles + rings)
                        └── UtilityRow (text / image / stop / clear)
```

## Key Design Decisions

1. **Provider over Bloc/Riverpod** — App is small; Provider is readable without boilerplate.
2. **Polling (3s) over WebSocket** — Backend is HTTP-only; polling is reliable on LAN.
3. **TTS default ON** — Matt commutes hands-free; audio response is primary UX.
4. **Stage-based progress** — Backend doesn't stream; stages inferred from status transitions + isLoading.
5. **Adaptive layout** — Mode A shrinks button to 84px on screens <620px height. ActivityLog hidden when keyboard open or screen is small.
6. **Particle orb via CustomPainter** — No third-party animation library; pure Flutter gives full control over premium visual.
7. **Brain injected at PROMPT level** — Works with `--dangerously-skip-permissions`; no Claude system-level config needed.
8. **Approval gate** — pyautogui desktop injection is the bottleneck; deliberate to keep Matt in control.

## Key Files

| File | Role |
|------|------|
| `lib/main.dart` | Entry point; Provider setup |
| `lib/theme.dart` | Brand colors + text styles |
| `lib/providers/app_state.dart` | All state, queuing, polling, brain API calls |
| `lib/screens/home_screen.dart` | Main adaptive UI |
| `lib/services/gerald_api.dart` | All HTTP calls including brain endpoints |
| `lib/services/tts_service.dart` | flutter_tts wrapper |
| `lib/services/ai_provider_service.dart` | Provider enum + SharedPreferences |
| `lib/widgets/conversation_orb.dart` | CustomPainter particle orb |
| `lib/widgets/status_panel.dart` | Progress bar + elapsed timer |
