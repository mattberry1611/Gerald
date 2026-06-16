# CommuteCoder — Architecture

## Structure

```
C:\CommuteCoder\
├── gerald_bridge.py          # FastAPI server — main entry point
├── build_verifier.py         # Flutter build runner + result parser
├── multi_ai_router.py        # AI provider abstraction
├── claude_desktop_controller.py  # pyautogui terminal injection (legacy)
├── project_brain.md          # This project's brain
├── roadmap.md                # This project's roadmap
├── current_status.md         # This project's status
├── architecture.md           # This file
├── gerald_projects.json      # Dynamic project registry (auto-created)
├── gerald_status.json        # Live status (working/idle/error)
├── gerald_outbox.json        # Latest Claude result (global mirror)
├── gerald_outbox_{Name}.json # Per-project result files
├── cloud_migration/          # Docker + nginx migration plan
├── remote_build/             # APK build & delivery scripts
└── gerald_app/               # Flutter mobile app (its own brain files)
```

## Data Flow

### Normal Task
1. Flutter app → POST /start {prompt, project}
2. gerald_bridge detects project → resolves path
3. Brain files read from project dir → injected into prompt
4. Claude Code runs in project CWD (PowerShell subprocess)
5. Result written to gerald_outbox_{project}.json + global outbox
6. Flutter polls GET /status → GET /read → displays response

### Voice "Create Project X"
1. Flutter detects "create project X" in sendPrompt()
2. Calls AppState.createProject() → POST /create-project
3. Backend creates dir + brain stubs + registers in gerald_projects.json
4. Flutter refreshes project list + switches to new project

### Alternatively via Voice to Backend
1. Flutter sends "create project X" to POST /start
2. gerald_bridge detects pattern via detect_create_project_name()
3. Creates project + brain files + registers
4. Writes success message to outbox
5. Flutter reads result via GET /read

### Brain Auto-Init
- On any /start call: if project has 0 brain files → create_brain_files() called
- Manual: POST /init-brain/{name} → creates stubs for existing project

## Key Decisions
- Brain injected at PROMPT level, not at Claude system level (works with --dangerously-skip-permissions)
- Per-project outbox mirrors to global outbox so /read always works
- Voice command detection at BOTH Flutter (client) and backend (server) for reliability
- Brain stubs are minimal placeholders; Claude fills them in over time
