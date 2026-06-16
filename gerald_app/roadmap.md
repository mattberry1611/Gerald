# Gerald App — Roadmap

## Completed

### V1.0 — Foundation
- [x] Flutter app scaffold (dark theme, brand palette)
- [x] Speech-to-text (speech_to_text package)
- [x] Backend API integration (gerald_bridge.py)
- [x] Push-to-talk button with glow animation
- [x] Message bubbles (user + Gerald)
- [x] Activity log
- [x] Settings screen

### V1.1 — Voice Modes
- [x] Mode A (Push-to-Talk)
- [x] Mode B (Conversation / auto-listen)
- [x] TTS (flutter_tts)
- [x] Speak Responses toggle
- [x] Stop Speaking button

### V1.2 — Premium UI
- [x] Branded app bar with Gerald logo
- [x] Segmented mode selector
- [x] Status panel with animated dot
- [x] Project selector (AppBar)
- [x] Image attach (camera + gallery)
- [x] Code block rendering in message bubbles

### V1.3 — Command Queue
- [x] Sequential task queue
- [x] Queue count display in StatusPanel
- [x] Queue survives rapid voice submissions

### V1.4 Phase 1 — Supervisor Upgrade
- [x] Fix all UI overflow issues (SafeArea, adaptive sizing)
- [x] Task progress bar (7 stages, elapsed timer, long-task warning >120s)
- [x] Conversation Orb (animated particle orb for Mode B)
- [x] TTS default ON
- [x] Adaptive UI for small screens (ActivityLog hides, button shrinks)

### V1.4 Phase 2 — Build & Provider
- [x] Autonomous Build Verification (build_verifier.py + /build-verify + /build-status + Settings UI)
- [x] Multi-AI Provider Framework (multi_ai_router.py + AiProviderService + Settings UI)
- [x] Cloud Migration Planning (cloud_migration/ — Dockerfile, docker-compose, nginx)
- [x] Remote APK Build Delivery Planning (remote_build/ — delivery_plan.md, build_and_deliver.py)

### V1.4 Phase 3A — Project Brain System ✅ CURRENT MILESTONE
- [x] Four brain files per project (project_brain.md, roadmap.md, current_status.md, architecture.md)
- [x] Brain files auto-injected into every Claude prompt
- [x] Brain stubs auto-created on first task if files are missing
- [x] GET /project-brain/{name} endpoint
- [x] POST /init-brain/{name} endpoint (manual init)
- [x] Flutter BrainSheet — in-app brain file viewer
- [x] Flutter ProjectBrainScreen — full-screen brain display
- [x] "Init Brain" button for projects with missing files
- [x] V1_4_PHASE_3A_COMPLETE.txt milestone marker

## Planned

### V1.4 Phase 3B — Automatic Project Creation
- [ ] POST /create-project endpoint (dir + brain stubs + registry entry)
- [ ] Flutter "Create Project" form in ProjectSelector sheet
- [ ] Voice command detection: "create project X" → auto-create
- [ ] Project persistence in gerald_projects.json

### V1.4 Phase 3C — Project Isolation
- [ ] Per-project outbox (gerald_outbox_{Name}.json)
- [ ] Isolation block in Claude prompt listing forbidden paths from other projects
- [ ] Per-project message isolation in Flutter (Map<String, List<Message>>)

### V1.5 — Cloud Ready
- [ ] Deploy gerald_bridge.py to Railway / Fly.io using cloud_migration/
- [ ] Bearer token authentication for all API endpoints
- [ ] FCM push notifications (task complete when app is backgrounded)
- [ ] Flutter ApkDeliveryService (poll /apk-status, OTA install notification)
- [ ] iOS support

### V1.6 — Build Automation
- [ ] Auto-trigger build verification after each approved edit
- [ ] Error auto-fix loop (retry Claude with error context)
- [ ] Build history / changelog view in app

### V2.0 — Full Autonomy
- [ ] Gerald plans AND executes without approval gate (optional mode)
- [ ] Test runner integration
- [ ] Git commit + PR creation via voice
- [ ] Slack / email notification on completion

### V2.1 — Multi-Model Integration
- [ ] Live OpenAI GPT-4o integration (stub → live)
- [ ] Live Google Gemini integration (stub → live)
- [ ] Per-provider cost estimate display
- [ ] Conversation history persistence
