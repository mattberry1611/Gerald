# CommuteCoder — Project Brain

## Overview
Voice-driven AI coding supervisor. Matt speaks tasks by voice during his commute; Gerald (the bridge) routes them to Claude Code; Claude plans and executes changes.

## Tech Stack
- **Backend:** Python 3.x, FastAPI, uvicorn
- **Bridge:** `gerald_bridge.py` — FastAPI server, project brain injection, isolation, build verify, multi-AI routing
- **Mobile app:** Flutter 3.x / Dart — `gerald_app/` (see `gerald_app/project_brain.md`)
- **AI:** Claude Code (`claude.cmd`) via PowerShell subprocess
- **Build tools:** flutter, gradle, Kotlin (Android)
- **Personality:** Senior development supervisor style (voice_mode_prompts.py)

## Architecture
- `gerald_bridge.py` — main HTTP server (port 8000). All logic here.
- `build_verifier.py` — runs `flutter build apk`, reports result
- `multi_ai_router.py` — routes to Claude / OpenAI / Gemini
- `claude_desktop_controller.py` — pyautogui terminal injection (legacy approval flow)
- `voice_mode_prompts.py` — personality rules for voice interaction
- `gerald_app/` — Flutter mobile app (see its own brain files)
- `cloud_migration/` — Docker/nginx migration plan
- `remote_build/` — APK build & deliver scripts

## Key Files
- `gerald_bridge.py` — CANONICAL entry point
- `gerald_projects.json` — dynamic project registry (auto-created)
- `gerald_status.json` — live status (idle/working/error)
- `gerald_outbox.json` — latest Claude result (mirrored per-project)
- `voice_mode_prompts.py` — personality configuration

## Key Decisions
- FastAPI + BackgroundTasks for async Claude execution
- Brain files injected into every Claude prompt (auto-created if missing)
- Per-project isolation: forbidden paths injected into prompt
- Project creation via voice command "create project X" routed at `/start`
- Senior supervisor personality: concise, actionable, 1-3 sentence defaults
