# CommuteCoder — Roadmap

## Completed

### V1.0 — Foundation
- [x] FastAPI bridge (gerald_bridge.py)
- [x] Claude Code subprocess integration
- [x] Project detection and routing
- [x] Voice UI (Web Speech API)

### V1.1 — Mobile Bridge
- [x] Flutter app (gerald_app/) with push-to-talk
- [x] REST API integration (/start, /read, /status, /projects)
- [x] Project selector with description

### V1.2 — Project Brain System
- [x] Brain files: project_brain.md, roadmap.md, current_status.md, architecture.md
- [x] Auto-inject brain context into every Claude prompt
- [x] Auto-create brain stubs for new projects
- [x] Auto-init brain if missing when task runs on existing project
- [x] /project-brain/{name} endpoint
- [x] /init-brain/{name} endpoint (manual initialization)
- [x] Flutter brain viewer (BrainSheet + ProjectBrainScreen)
- [x] "Init Brain" button for projects with missing files

### V1.3 — Automatic Project Creation
- [x] /create-project endpoint (creates dir + brain files + registers)
- [x] Flutter Create Project form (NewProject sheet in ProjectSelector)
- [x] Voice command detection: "create project X" → auto-create at /start
- [x] Project persistence in gerald_projects.json

### V1.4 — Project Isolation
- [x] Per-project outbox files (gerald_outbox_{name}.json)
- [x] Isolation block injected into every Claude prompt
- [x] Forbidden paths listed from all other registered projects
- [x] Per-project message isolation in Flutter app (projectMessages map)

### V1.4 — Supervisor Upgrade (gerald_app)
- [x] Build verification (build_verifier.py + /build-verify)
- [x] Multi-AI provider framework (multi_ai_router.py)
- [x] Cloud migration planning (cloud_migration/)
- [x] Remote APK delivery (remote_build/)
- [x] Conversation orb, TTS, task progress, command queue

## Planned

### V1.5 — Cloud Ready
- [ ] Deploy gerald_bridge.py to Railway/Fly.io
- [ ] Bearer token auth on all endpoints
- [ ] FCM push notifications

### V2.0 — Full Autonomy
- [ ] Gerald plans AND executes without approval gate
- [ ] Test runner integration
- [ ] Git commit + PR creation
