
# CommuteCoder — Current Status

**Last Updated:** 2026-06-21
**Version:** V3.4.2 — Successful-only filter for /task/last-result

## What's Working

| Component | Status |
|-----------|--------|
| gerald_bridge.py FastAPI server | ✅ Running (port 8000) |
| Project Brain: read before task | ✅ Injected into every Claude prompt |
| Project Brain: auto-create if missing | ✅ On /start if no brain files found |
| Project Brain: update instructions | ✅ Appended to every Claude prompt |
| /init-brain/{name} endpoint | ✅ Implemented |
| /create-project endpoint | ✅ Implemented |
| Voice command "create project X" | ✅ Detected in /start, auto-creates |
| Flutter Create Project UI | ✅ NewProject sheet in ProjectSelector |
| Flutter Init Brain button | ✅ In BrainSheet for missing files |
| Flutter voice command detection | ✅ In AppState.sendPrompt() |
| Per-project outbox isolation | ✅ gerald_outbox_{name}.json |
| Prompt isolation block | ✅ Forbidden paths injected |
| Build Verification | ✅ build_verifier.py + /build-verify |
| Multi-AI Provider | ✅ multi_ai_router.py + /set-provider |
| Flutter app build | ✅ flutter build apk --debug clean |
| Web Command Centre dashboard | ✅ dashboard/ (React, served at /dashboard) |
| Dashboard Project Context Manager | ✅ Explicit project selection enforced in dashboard |
| Dashboard ＋ New Project | ✅ Inline create form in project selector |
| Dashboard task guard | ✅ Task input blocked until project is selected |
| Dashboard response isolation | ✅ Response panel clears on project switch; loads project-specific last output |
| /read?project= endpoint | ✅ Returns project-specific outbox; falls back to global |
| Dashboard API origin | ✅ Hardcoded to http://170.64.177.149:8000 (changed from localhost for remote browser access) |
| Dashboard Gerald favicon | ✅ SVG favicon added (orange orb with G, matches GeraldOrb component) |
| Dashboard project-first landing | ✅ Large cards for CommuteCoder/MultiMe/RentMe/PlantBrain + Create New |
| Dashboard enlarged animated orb | ✅ 200px orb on landing; idle=pulse+rotate, thinking=spin+glow, success/error glow |
| Dashboard active project bar | ✅ Prominent project name + description bar at top of workspace |
| Dashboard larger task input | ✅ Enlarged textarea (68px min) with premium spacing when project active |
| Dashboard Gerald-only branding | ✅ Header always shows "Gerald Command Centre"; project shown in subtitle |
| Dashboard Build APK button | ✅ Prominent orange button; /build-apk now async (BackgroundTasks); progress via /build-status |
| Dashboard Build APK placement | ✅ BuildPanel moved above panels-grid for immediate visibility in workspace |
| Dashboard image attachment | ✅ Paperclip button + thumbnail preview; POST /upload-image stores to dashboard/uploads/ |
| Dashboard premium UI rebuild | ✅ Sidebar nav, logo orb, conversation panel, glass theme |
| Dashboard sidebar navigation | ✅ Projects/Build/Brain/Logs/Settings/Health nav items |
| Dashboard gerald_logo.png orb | ✅ Real logo image with breathe/spin/pulse/shake/listen/speak CSS animations |
| Dashboard voice mic button | ✅ Web Speech API mic button — layout [Attach][Mic][text][Send] |
| Dashboard task input always visible | ✅ Permanently below conversation panel, all 4 controls in single row |
| Dashboard voice mode panel | ✅ Large orb (160px) + voice state label (Ready/Listening…/Thinking…/Error) |
| Dashboard listening orb state | ✅ Triggers when mic is active; lifted to App level via onListeningChange |
| Dashboard speaking orb state | ✅ CSS animation ready; wired when TTS is implemented |
| Planner: Task Contract generation | ✅ create_task_contract() — full prompt (no truncation), max_tokens=4096, _parse_contract_json helper |
| Planner: retry on parse failure | ✅ Conservative second attempt on JSON parse error; RuntimeError on double failure (no silent fallback) |
| Planner: /planner/preview endpoint | ✅ POST endpoint to test contract extraction without starting Claude Code (active after next restart) |
| Auditor: contract compliance check | ✅ audit_task_contract() runs after EVERY Claude Code task (review verdict no longer blocks) |
| Auditor: sole source of truth | ✅ Auditor verdict (COMPLETE/PARTIAL/FAILED) is now the ONLY terminal status decider |
| Task Contract in active_task.json | ✅ contract + audit fields preserved mid-task; audit cleared when new contract is written (no stale audit carry-over) |
| Dashboard TaskContractPanel | ✅ Auditor verdict shown in card header; Auditor note shown prominently |
| Dashboard StatusPanel | ✅ Auditor verdict + note shown above Detail field |
| /task/contract endpoint | ✅ Returns contract + audit + audit_verdict (top-level) + stage from active_task.json |
| Partial/contract_failed stages | ✅ Auditor can set PARTIAL or FAILED if requirements unmet |
| review_failed stage eliminated | ✅ Review FAIL no longer a terminal outcome; Auditor verdict overrides |
| Dashboard TEST AUDITOR button | ✅ Small green button in main conversation area (dashboard/app.js) |
| Planner: evidence_required in Task Contract | ✅ Planner enumerates verification steps that require real command/file/endpoint evidence |
| Auditor: missing evidence causes FAILED | ✅ Simulated/hypothetical/example outputs rejected; missing_evidence field listed in audit |
| Session state: per-project event log | ✅ gerald_session_state.py — logs user requests, Gerald responses, contracts, Claude results, audits, corrections, outcomes |
| Session state: Matt correction detection | ✅ is_failure_feedback() detects "still broken" + URO phrases; logs matt_correction + task_reopened events |
| User Reality Override | ✅ user_reality_override.py — detects 5 URO phrases, flags active task as suspect, emits user_reality_conflict event with verification evidence |
| Session state: context injection | ✅ load_session_context() injected into Planner prompt, Auditor prompt, Claude worker prompt, Decision Agent prompt |
| Session state: lessons memory | ✅ Per-project lessons file in project_memories/{project}_lessons.md; auto-appended on FAILED audits |
| /session/summary endpoint | ✅ GET /session/summary?project=X — read-only session summary for dashboard |
| /session/lessons endpoint | ✅ GET /session/lessons?project=X — read-only lessons memory for dashboard |
| UI Component Verifier | ✅ ui_component_verifier.py — detects duplicate TaskInput, zero TaskInput, missing composer wrapper; blocks COMPLETE verdict for UI tasks |
| Auditor Integrity V2: parse failure guard | ✅ auditor_integrity.handle_audit_unknown_verdict() — UNKNOWN verdict → FAILED on every outcome event |
| Auditor Integrity V2: review FAIL guard | ✅ auditor_integrity.handle_review_fail_enforcement() — review FAIL + COMPLETE audit → PARTIAL on completed outcomes |
| Auditor Integrity V2: scope check guard | ✅ auditor_integrity.handle_scope_check() — forbidden files changed → PARTIAL (some allowed) or FAILED (all forbidden) |
| V4 Phase 1: unique task_id per request | ✅ UUID generated at start of every real worker; stored in active_task.json + outbox data |
| V4 Phase 1: durable task history | ✅ gerald_task_history_{project}.json — appended on every terminal state (complete/partial/failed/timeout); max 200 records |
| V4 Phase 1: status checks isolated | ✅ truthful_status_response() writes to gerald_last_status_check.json — never overwrites real task outbox |
| V4 Phase 1: GET /task/last-result | ✅ Returns last successful real task result; skips status checks, error/contract_failed status, non-zero returncode, empty output+summary |
| Supervisor: message classification | ✅ classify_message_intent() — 5 classes injected into every ask_gerald + decide_supervisor_action call |
| Supervisor: Repetition Breaker | ✅ _is_frustration_turn() + skip-repeat flag (2-turn window) — prevents repeated answers, explains misclassification |
| Supervisor: visual evidence routing | ✅ visual_outcome_question routes to evidence comparison, not task status; missing evidence triggers verification request |
| Supervisor: foundational lesson | ✅ "Task complete does not mean user outcome matches design." auto-stored in project lessons once |

Remote phone-to-cloud file edits are now proven.

## Active Issues
- None known

## Recent Changes
- **V3.4.2**: Successful-only filter for `/task/last-result` — `gerald_bridge.py`: `_get_last_real_task_result()` now applies four additional skip conditions on top of the existing status-check filter: skips records with `status="error"`, skips `status="contract_failed"`, skips `returncode != 0`, skips records where both `output` and `summary` are empty. Only the first record passing all five checks is returned. No app/dashboard UI changes. Server restart required to activate.
- **V3.4.1**: Status phrase filter for `/task/last-result` — `gerald_bridge.py`: added `_STATUS_CHECK_PHRASES` list (7 phrases: "is the last task complete", "is it complete", "status check", "what is the status", "is claude still running", "are you done", "did it finish") and `_is_status_check_task()` helper; `_get_last_real_task_result()` now iterates history in reverse and skips any record where the `task` field contains a phrase (case-insensitive, inclusive substring match), returning the first non-matching entry. Verified by simulation: after appending "Say the word kernel-test only." followed by "is the last task complete?", the function correctly returns the kernel-test result. No app/dashboard UI changes. Server restart required to activate.
- **V3.3.0**: Auditor Integrity V2 — new `auditor_integrity.py` module with three post-outcome enforcement guards wired into `gerald_session_state.log_event()`: (1) `handle_audit_unknown_verdict()` fires on every outcome event — upgrades `audit.verdict=UNKNOWN` (from JSON parse failures) to `FAILED` in active_task.json and outbox; (2) `handle_review_fail_enforcement()` fires on completed outcomes — if `review_verdict=FAIL` AND `audit.verdict=COMPLETE`, downgrades to PARTIAL (review concern preserved; audit partial credit granted); (3) `handle_scope_check()` fires on completed outcomes — checks `files_changed` against `contract.forbidden_files`; PARTIAL if some allowed files changed, FAILED if all changed files were forbidden; all three patch active_task.json + outbox + gerald_status.json. Root cause of previous regression: server was running pre-V2.5 code (old exception handler returned `verdict=COMPLETE` on JSON parse error); V2.5/V2.6 fixes were in source but server not restarted. All 6 simulation tests pass. `gerald_bridge.py` unchanged. No app/dashboard UI changes.
- **V3.2.0**: Supervisor reasoning upgrade — `gerald_openai_brain.py`: (1) `classify_message_intent()` classifies every user message as `task_status_question`, `visual_outcome_question`, `user_feedback_or_disagreement`, `investigation_request`, or `new_task_request`; injected into every `ask_gerald` + `decide_supervisor_action` call. (2) `_is_frustration_turn()` + `_update_skip_repeat_flag()` + `is_skip_repeat_active()` + `_load_convo_state()` — two-turn skip-repeat window persisted to disk. (3) `_get_visual_evidence_summary()` reads `active_task.json` + outbox to surface evidence for visual questions. (4) `_build_response_strategy()` returns targeted guidance: Repetition Breaker (no repeat, explain misclassification), Visual Evidence (compare or request), Status, Investigation, or New Task. (5) `_ensure_foundational_lesson()` writes "Task complete does not mean user outcome matches design." once. (6) `GERALD_SYSTEM_PROMPT` + `decide_supervisor_action()` rules updated with classification + Repetition Breaker + Visual Outcome sections. `supervisor_brain.md`: Message Intent Classification + Repetition Breaker added. No app/dashboard/bridge changes. All 20 test_skip_repeat tests pass.
- **V3.1.0**: Orb as focal point — `gerald_app/lib/widgets/conversation_orb.dart`: (1) Idle now breathes visibly: rotation slowed to 18s, pulse cycle 3600ms, `pulseAmplitude=0.13`, `glowMultiplier=2.2` (glow expands/contracts with breathing). (2) Thinking now rotates prominently: rotation 3s (fast), pulse slow 2000ms, `pulseAmplitude=0.05` (rotation dominates, pulse is subtle). (3) Speaking now pulses strongly: rotation 5s (moderate), pulse 650ms (fast), `pulseAmplitude=0.18`, `glowMultiplier=1.6`, 5 wave rings with 0.42 opacity (was 4 rings at 0.32). (4) `_OrbPainter` gains `pulseAmplitude` + `glowMultiplier` params (passed per-state from `build()`). `gerald_app/lib/screens/home_screen.dart`: `_OrbHeader` hero orb size raised from 130→160px when no messages; state label added below orb when no messages ("Ready to assist" / "Thinking..." / "Speaking..." / "Listening..." / "Something went wrong") with per-state color. No backend changes.
- **V3.0.0-Phase2**: Mobile App V3 Phase 2 — `gerald_app/lib/screens/home_screen.dart`: (1) Added `_OrbHeader` widget — `ConversationOrb` always visible at top of conversation screen, 130px when no messages, 80px when messages present, animated size transition; orb state driven by `isListening`/`isSpeaking`/`GeraldStatus` (planning/awaiting/executing→thinking, error→error, else→idle). (2) `_speakMode` defaults to `true` — voice is now primary on launch. (3) Auto-focus keyboard guard: only requests focus when in TYPE mode. (4) `_EmptyState` simplified to "Speak or type to begin" — orb is the visual centerpiece. Added `conversation_orb.dart` import. No backend changes. Projects and Brain screens unchanged.
- **V2.9.1**: Command Evidence Capture — new `command_evidence_capture.py` (`run_with_evidence()`, `read_evidence()`, `_make_excerpt()`); `verification_layer.py` gains `FLUTTER_ANALYZE_LOG/EXIT` + `FLUTTER_BUILD_LOG/EXIT` constants, `flutter_analyze` check type in `run_verification_suite()`, and `_verify_flutter_analyze()` method. No UI changes.
- **V2.9**: Mobile App V3 Phase 1 — `gerald_app/lib/theme.dart`: V3 neon-cyan palette (`kAccentBlue` → `#00CFFF`, deeper navy backgrounds, neon-tinted borders, dark-on-cyan button text for contrast, `cardTheme` glass panel hints). `gerald_app/lib/widgets/conversation_orb.dart`: added `error` to `OrbState` enum (fast pulse 450ms, fast rotation 2s, red color); added `GeraldOrb`/`GeraldOrbState` typedefs as V3 public API. `gerald_app/lib/widgets/push_to_talk_button.dart`: added `OrbState.error` case to exhaustive color switch.
- **V2.8**: UI Component Verifier — new `ui_component_verifier.py` module; `verification_layer.py` gains `"ui_components"` check type; `gerald_session_state.py` hook on `log_event("outcome", status="completed")` runs `handle_ui_component_verification()` for UI-related tasks: detects duplicate `<${TaskInput}` renders, zero renders, or missing input wrapper (conversation-input-area/composer-bar); if issues found, overrides active_task.json to `contract_failed` and gerald_status.json to `error`, emits `ui_component_conflict` event. `gerald_bridge.py` unchanged.
- **V2.7**: User Reality Override — new `user_reality_override.py` module; 5 URO phrases added to `FAILURE_PHRASES` in `gerald_session_state.py`; `log_event()` hook triggers on `matt_correction`: detects URO phrases, flags active_task.json stage to "suspect", emits `user_reality_conflict` event with structured evidence covering phrase detection, task reopening, and status dispute. `gerald_bridge.py` unchanged.
- **V2.6**: Auditor Parse Failure Fix in `gerald_bridge.py` — two targeted changes: (1) `audit_task_contract()`: after `json.loads(raw)`, added post-parse integrity block that forces `verdict = "FAILED"` if `missing_evidence` is non-empty OR if `verdict` is not one of `COMPLETE/PARTIAL/FAILED`; COMPLETE is only kept when verdict is explicitly that value AND `missing_evidence` is empty. (2) `run_claude_code_worker()`: no-contract/review-PASS fallback changed from `verdict: "COMPLETE"` to `verdict: "UNKNOWN"`, which routes to `contract_failed` via the existing `else:` branch.
- **V2.5**: Auditor Integrity Rule enforced in `gerald_bridge.py` — four failure paths that previously returned COMPLETE now return UNKNOWN or FAILED: (1) `audit_task_contract()` exception handler changed COMPLETE→UNKNOWN; (2) no-requirements early return changed COMPLETE→UNKNOWN; (3) `_audit.get("verdict", "COMPLETE")` default changed to UNKNOWN; (4) `else:` catch-all in worker branching split into explicit `elif _av == "COMPLETE":` + new `else:` that routes any unexpected/UNKNOWN verdict to `contract_failed` status. Verified by forced parse failure test: verdict=UNKNOWN, Is COMPLETE=False.
- **V2.4**: Landing hero redesign — `dashboard/app.js`: replaced `.orb-section` title block with `.landing-hero` containing: 120px `GeraldOrb` (gerald_logo.png), large "GERALD" `h1` brand title, "The Command Center for Your Digital Life" tagline, prominent "Get Started" CTA button (scrolls to project cards), "Create your first AI command in seconds." microcopy, small ⓘ info button (absolute top-right, HTML title tooltip). `dashboard/style.css`: new `.landing-hero`, `.landing-brand-title` (2.4rem), `.landing-tagline`, `.landing-cta`, `.landing-microcopy`, `.landing-info-btn` styles; landing-scoped orb glow reduction (`.landing-hero .logo-orb-glow` override + `landingOrbBreath`/`landingGlowBreath` keyframes — halved outer glow vs default).
- **V2.3**: Dashboard accessibility & visual simplification — `dashboard/app.js`: sidebar now collapsible (60px icon-only mode with toggle button); large GeraldOrb removed from home panel and landing pages — logo appears only once in sidebar (32px); voice status chips renamed to plain English ("Voice Input", "AI Status", "Response Output") with HTML title tooltips; chat timestamps moved outside bubble to sit below avatar (closer to sender name). `dashboard/style.css`: excessive text-shadow/glow removed from static elements; sub-0.7rem font sizes raised; activity log entries larger (0.8rem, more padding); system health card softened; composer bar glow reduced; sidebar collapse CSS; chat-sender layout; workspace-orb-area--compact. `dashboard/components/LogsPanel.js`: quick filter chips (All / Build / System / Errors / Upload); badge tooltips explain each colour; Export button renamed to "Export".
- **V2.2**: Dashboard V3 design reference migration — `dashboard/app.js` restructured with: HOME nav item added first in sidebar, sidebar row-layout brand (orb + GERALD / COMMAND CENTRE), QUICK ACTIONS section label, Matt user footer; home panel shows 160px Gerald orb + "GERALD / YOUR AI COMMAND BRAIN" with system health card on right; conversation panel shows chat bubbles (You / Gerald); voice status bar (VOICE MODE, ORB STATUS, SPEAKING OUTPUT chips); TaskInput embedded in conversation panel; non-home panels retain composer bar; CLEAR CHAT button added. `dashboard/style.css` — new V3 CSS appended: `.sidebar-brand` row override, `.sidebar-brand-text/sub`, `.sidebar-section-label`, `.sidebar-user`, `.workspace-top/.workspace-orb-area/.workspace-right`, `.system-health-card` + status/active-project sub-elements, `.conversation-header/.conv-title`, `.chat-messages/.chat-msg/.chat-avatar/.chat-bubble/.chat-text/.chat-time`, `.conversation-input-area`, `.voice-status-bar/.voice-chip`, `.log-filter-chip`, `.log-badge`. `dashboard/components/LogsPanel.js` — added "All Activities ▾" filter chip, "EXPORT LOGS" button (downloads .log file), per-entry colored badge (INFO/ERROR/WARN/SUCCESS). All gerald_logo.png imagery preserved; no robot/SVG orb used anywhere.
- **V2.1**: Brain V3 relevance-pruned memory window — `gerald_openai_brain.py` rebuilt with `_build_brain_v3_memory_block()`: injects only last 5 turns, recent Matt corrections, keyword-relevant lessons, compact task contract/audit, and a 2-line project summary; hard cap ~2000 tokens per OpenAI call; estimated token count logged before every OpenAI call; `ask_gerald` now ~1450 tokens total, `decide_supervisor_action` ~870 tokens (down from 5000+ with full brain files).
- **V2.0**: Gerald Brain V3 persistent session state — new `gerald_session_state.py` module; logs all events (user_request, gerald_response, task_contract, claude_result, audit_result, matt_correction, task_reopened, outcome, lesson_learned); session context injected into Planner, Auditor, Decision Agent, and Claude worker prompts; failure feedback detection surfaces last task context on "still broken" etc.; per-project lessons auto-appended on FAILED audits; two new read-only endpoints: `/session/summary` and `/session/lessons`.
- **V1.9.4**: Robust Planner extraction — `create_task_contract()` no longer truncates input (`task_text[:2000]` removed); `max_tokens` raised from 1024 to 4096 (eliminates unterminated JSON); "keep 3-6 items" limit removed; new `_parse_contract_json()` helper strips markdown and finds outermost `{}`; automatic retry with conservative prompt on parse failure; `RuntimeError` raised (not silent fallback) on double failure; caller in `run_claude_code_worker` catches `RuntimeError` and writes error state; `/planner/preview` POST endpoint added for Planner testing without task execution. Verified: V2 dashboard 12-req prompt now produces 14-item requirements_checklist (all extracted individually).
- **V1.9.3**: Evidence-based verification enforcement — Planner now adds `evidence_required` array to every Task Contract (one entry per verification step that needs command output, file contents, or endpoint response). Auditor reads this list, rejects simulated/hypothetical evidence, populates `missing_evidence` in audit result, and returns FAILED if any required evidence is absent.
- **V1.9.2**: Audit reset on new task — `write_task_state` no longer carries over the previous task's `audit` when a new `contract` is being written; guarantees Task Contract and audit always belong to the same task.
- **V1.9.1**: Auditor as source of truth — Auditor now runs regardless of review verdict (previously only on review PASS); review_failed is no longer a terminal status; Auditor verdict (COMPLETE/PARTIAL/FAILED) is the sole final status decider; `started` field now preserved across all write_task_state() calls; /task/contract returns `audit_verdict` at top level; StatusPanel shows Auditor verdict above detail; TaskContractPanel moves verdict badge to header.
- **V1.9**: Planner + Task Contract + Auditor — create_task_contract() generates structured JSON contract (intent, scope, requirements, forbidden files, definition of done, verification checklist, phases) before every Claude Code task; audit_task_contract() checks deliverables after Claude finishes; contract/audit persisted in active_task.json; dashboard TaskContractPanel shows live contract state; PARTIAL/contract_failed stages introduced.
- **V1.8**: Dashboard voice mode panel — task input row reordered to [Attach][Mic][text][Send]; large 160px Gerald orb (centered, non-compact) in active workspace; voice state label below orb (Ready/Listening…/Thinking…/Error); listening/speaking CSS animations added to GeraldOrb; listening state lifted to App level via onListeningChange callback; effectiveOrbState derived from orbState + listening.
- **V1.7**: Dashboard premium UI rebuild — sidebar navigation (Projects, Build & Deploy, Brain, Logs, Settings, System Health), gerald_logo.png orb replacing SVG with breathe/spin/pulse/shake animations, conversation panel (response + input in glass card), activity log always at bottom, voice mic button (Web Speech API) in task input.
- **V1.6.3**: Image attachment upload — paperclip button in chat input, thumbnail preview, POST /upload-image endpoint stores files in dashboard/uploads/, URL appended to task text on send.
- **V1.6.2**: `dashboard/style.css` fully restyled — dark navy/black backgrounds, electric blue accents, glassmorphism panels/cards, glowing buttons, subtle CSS grid background. No layout or functionality changes.

## File Locations

| File | Purpose |
|------|---------|
| `gerald_bridge.py` | Main bridge — all endpoints |
| `build_verifier.py` | flutter build apk runner |
| `multi_ai_router.py` | AI provider router |
| `gerald_projects.json` | Dynamic project registry |
| `gerald_status.json` | Live status file |
| `gerald_outbox.json` | Latest Claude result |
| `gerald_app/` | Flutter mobile app |
| `dashboard/` | Browser-based Command Centre (React, no build step) |
