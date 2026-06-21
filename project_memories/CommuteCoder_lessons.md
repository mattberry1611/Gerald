# CommuteCoder — Project Lessons

## Format
Each lesson records: Problem, Root cause, Fix, Outcome, Reuse rule

---


## Lesson — 2026-06-21
Auditor FAILED: Redesign the chatbox/conversation panel in the Gerald dashboard to be visually clearer and more read
Missing: List all modified files after completion; Explain each change made to every modified file
Audit notes: Claude provided detailed structural/CSS changes but failed to capture ANY required evidence (screenshots, command output, functional tests). Claims 'F

## Lesson — 2026-06-21
Auditor FAILED: Execute flutter analyze and flutter build apk --debug in /opt/Gerald/gerald_app, then report pass/fa
Missing: Exact error output from flutter analyze command execution; Exact stdout/stderr with exit code from flutter analyze; Exact stdout/stderr with exit code from flutter build apk --
Audit notes: Claude provided analysis summaries and APK path but failed to capture and return exact command output (stdout/stderr/exit codes) as explicitly require

## Lesson — 2026-06-21
Auditor FAILED: Implement Phase 2 of Gerald Mobile App V3 to make Conversation the primary user experience with visu
Missing: Execute flutter analyze in /opt/Gerald/gerald_app and captur; Execute flutter build apk --debug in /opt/Gerald/gerald_app 
Audit notes: Claude provided design summary and code changes to home_screen.dart but failed to execute required commands (flutter analyze, flutter build apk --debu

## Lesson — 2026-06-21
Auditor FAILED: Implement the User Reality Override root-cause fix to ensure user outcomes override system/backend c
Missing: Update auditor.py to ensure user outcome overrides system/ba; Update gerald_bridge.py to enforce user reality override beh; Update or create ui_verifier.py (or similar module) to relia
Audit notes: Claude provided text descriptions of intended changes to three files but delivered ZERO actual file contents, ZERO diffs, ZERO command execution outpu

## Lesson — 2026-06-21
Auditor FAILED: Determine if the UI has been updated to match the screenshot, or if more work is needed before proce
Missing: Capture current state of the app UI visually or via code ins; Compare current UI rendering against the target screenshot p; Confirm whether all visual changes from the screenshot have 
Audit notes: CRITICAL FAILURE: Claude requested missing screenshot instead of auditing current state; zero evidence captured; no UI comparison performed; contract

## Lesson — 2026-06-21
Auditor FAILED: Add a fallback message in app_state.dart when /read returns empty status or blank output/summary, di
Missing: List all changed files after completion (FILES CHANGED: none; Run flutter analyze and capture output (statement claims suc
Audit notes: Code logic appears correct (fallback conditions, message display, stage setting, notifyListeners all present), before/after comparison provided, but c

## Lesson — 2026-06-21
Auditor FAILED: Implement V4 Agent Kernel Phase 1 persistent task result layer to prevent task outputs from being ov
Missing: Architectural specification document covering all 6 Definiti
Audit notes: Claude delivered working code implementation but failed to deliver the required architectural specification document covering all 6 items from Definit

## Lesson — 2026-06-21
Auditor FAILED: Fix _get_last_real_task_result() to return only the most recent successful task result, filtering ou
Missing: No UI changes to the app; No UI changes to the dashboard
Audit notes: Claude violated contract by modifying 7 UI files (conversation_orb.dart, push_to_talk_button.dart, status_panel.dart, home_screen.dart, etc.) despite
