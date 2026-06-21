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

### V1.5 — Web Command Centre
- [x] Browser-based Gerald Command Centre dashboard (dashboard/)
- [x] Dark mode, Gerald branding, animated orb (idle/thinking/success/error)
- [x] Project selector, task input, live status polling
- [x] Gerald response viewer, review/verification status panel
- [x] Build APK + download APK buttons
- [x] Project Brain viewer with tab navigation
- [x] Activity log panel
- [x] No build step — pure React via importmap/CDN ESM
- [x] Project Context Manager: explicit project selection enforced, task guard, inline create form, Gerald branding isolation

### V1.6 — Dashboard Premium UI
- [x] Project-first landing with large cards (CommuteCoder, MultiMe, RentMe, PlantBrain, Create New)
- [x] Enlarged animated Gerald orb on landing (200px; idle pulse+rotate, thinking spin+glow)
- [x] Active project bar at top of workspace with project name + description
- [x] Larger task input (68px min-height) with premium spacing
- [x] Gerald-only branding enforced; project name in header subtitle only
- [x] Image attachment upload: paperclip button, thumbnail preview, POST /upload-image, stored in dashboard/uploads/

### V1.7 — Dashboard Premium UI Rebuild
- [x] Sidebar navigation: Projects, Build & Deploy, Brain, Logs, Settings, System Health
- [x] gerald_logo.png orb — real logo image replaces SVG, glow animations: breathe (idle), spin (thinking), pulse (success), shake (error)
- [x] Conversation panel: response + task input combined in single glass card, centered in main area
- [x] Voice mic button: Web Speech API mic in task input row
- [x] App shell layout: sidebar (220px) + main area with scrollable content
- [x] Activity log always anchored at bottom of content scroll
- [x] No robot imagery; no SVG orb drawing; all imagery from gerald_logo.png

### V1.9 — Planner + Task Contract + Auditor
- [x] Planner: create_task_contract() generates JSON contract before every Claude Code run
- [x] Contract fields: user_intent, scope, non_negotiables, requirements_checklist, likely_files, forbidden_files, definition_of_done, verification_checklist, recommended_execution_steps, is_large_task, phases
- [x] Large-task phase splitting: is_large_task → Phase 1 executed first, phases listed in contract
- [x] Contract saved to active_task.json and preserved across all write_task_state() calls
- [x] Auditor: audit_task_contract() checks Claude's output against requirements after review passes
- [x] Auditor verdicts: COMPLETE / PARTIAL / FAILED; PARTIAL/FAILED block COMPLETE status
- [x] Dashboard TaskContractPanel: shows intent, requirements checklist with live met/missing/pending icons, audit verdict
- [x] /task/contract GET endpoint
- [x] CSS: review-verdict--partial, stage-pill--partial, stage-pill--contract_failed, contract-checklist styles
- [x] Planner: robust extraction — full prompt (no truncation), max_tokens=4096, _parse_contract_json helper, retry on parse failure, loud RuntimeError on double failure (no silent "Complete the requested task" fallback)
- [x] /planner/preview POST endpoint for Planner testing without task execution

### V2.0 — Gerald Brain V3 Persistent Session State
- [x] Per-project session log (conversations/{project}_session_log.json) — 100-event rolling window
- [x] Log every: user request, Gerald response, task contract, Claude result, audit result, Matt correction, outcome, lesson
- [x] Matt failure feedback detection (is_failure_feedback) — logs matt_correction + task_reopened events
- [x] Session context injected into Planner prompt, Auditor prompt, Claude worker prompt, Decision Agent (OpenAI) prompt
- [x] Per-project lessons memory (project_memories/{project}_lessons.md) — auto-appended on FAILED audits
- [x] GET /session/summary — read-only session summary for dashboard
- [x] GET /session/lessons — read-only lessons memory for dashboard

### V2.1 — Brain V3 Token Optimisation
- [x] Relevance-pruned memory window: last 5 turns, recent corrections, keyword-filtered lessons, compact task contract/audit, 2-line project summary
- [x] Hard token cap: ~2000 tokens per Brain V3 memory block (enforced in _build_brain_v3_memory_block)
- [x] Token count logged before every OpenAI call (ask_gerald + decide_supervisor_action)
- [x] Compact current_task/pending/last_outbox in decide_supervisor_action (no more 3000-char JSON blobs)
- [x] Full brain files no longer injected into OpenAI prompts (replaced by 2-line compact summary)

### V2.7 — User Reality Override
- [x] user_reality_override.py: USER_REALITY_PHRASES, is_user_reality_conflict(), get_matched_phrases(), flag_active_task_as_suspect(), handle_user_reality_override()
- [x] Detects 5 phrases: "still broken", "not what I asked for", "can't see it", "where is it", "looks the same"
- [x] Flags active task stage to "suspect" in active_task.json when URO phrase detected and task is non-idle
- [x] Emits user_reality_conflict event with structured evidence (phrase detection, task reopening, status dispute)
- [x] Hooked into log_event() in gerald_session_state.py — fires on matt_correction; no gerald_bridge.py changes required
- [x] New phrases added to FAILURE_PHRASES — is_failure_feedback() now catches all 5 URO phrases

### V3.0 — Mobile App V3 Phase 2
- [x] Conversation screen is the default experience (GeraldOrb as visual anchor)
- [x] Large GeraldOrb at top of Conversation screen (130px idle, 80px with messages, animated)
- [x] Orb reflects live Gerald state: idle / listening / thinking / speaking / error
- [x] Voice interaction primary — SPEAK mode defaults to on
- [x] Simplified empty state — orb is the centerpiece
- [x] Projects and Brain screens unchanged

## Planned

### V2.8 — UI Component Verifier
- [x] ui_component_verifier.py: verify_ui_components() — detects duplicate TaskInput, zero TaskInput, missing composer wrapper
- [x] VerificationLayer gains "ui_components" check type
- [x] gerald_session_state.py hook on outcome/completed: runs UI check for UI tasks, overrides COMPLETE to contract_failed when issues found
- [x] Emits ui_component_conflict event with issues + evidence

### V1.8 — Cloud Ready
- [ ] Deploy gerald_bridge.py to Railway/Fly.io
- [ ] Bearer token auth on all endpoints
- [ ] FCM push notifications

### V2.0 — Full Autonomy
- [ ] Gerald plans AND executes without approval gate
- [ ] Test runner integration
- [ ] Git commit + PR creation
