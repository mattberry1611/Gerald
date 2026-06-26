# Sprint 001 — Gerald OS Foundation

**Sprint start:** 2026-06-26
**Governing document:** `gerald_os.md`
**Engineering role:** Gerald Engineering Worker

---

## Sprint Goal

Create the core operating framework that every future Gerald feature will use.

This sprint establishes the foundation of Gerald OS: the architecture document, the deployment pipeline, and the evidence-based verification system. No future feature is built without these in place.

---

## Success Criteria

- Gerald OS document completed.
- Deployment Manager implemented.
- Task Completion Verifier implemented.
- Every future implementation follows Gerald OS.
- No feature bypasses verification.

---

## Tasks

### Task 1 — Gerald OS Document

**File:** `gerald_os.md`
**Status:** Completed

Defines the governing architecture: vision, core principles, component responsibilities, request flow, verification rules, deployment rules, roadmap, and non-negotiables. All future work references this document before implementation begins.

---

### Task 2 — Deployment Manager

**File:** `deployment_manager.py`
**Endpoint:** `POST /deploy/auto` (in `gerald_bridge.py`)
**Status:** Completed

Maps git-changed files to deployment actions and executes them:

- Root-level `*.py` changed → restart `gerald`
- `gerald_design_studio.py` changed → restart `gerald-design-studio`
- `gerald_app/lib/` or `pubspec.yaml` changed → `flutter build apk --debug`, copy to `apk_serve/gerald-latest.apk`
- `dashboard/` changed → mark dashboard changed, no build

Key functions: `get_git_changed_files()`, `plan_deployment_actions()`, `run_deployment_actions()`, `auto_deploy()`

Matt calls `POST /deploy/auto` after any Claude/Cursor session and gets back a structured JSON report of what was deployed.

---

### Task 3 — Task Completion Verifier

**File:** `task_completion_verifier.py`
**Status:** Completed

Evidence-based verification that requested work actually happened. Verification only — no restarts, no builds.

Functions:

- `verify_file_exists(path)` — confirms a file or directory exists at the given path
- `verify_symbols_exist(file_paths, symbols)` — confirms functions, classes, and endpoints are present in files
- `detect_deployment_required(changed_files)` — reports which deployment actions are needed without running them
- `verify_python_syntax(file_paths)` — runs `python3 -m py_compile` on each Python file and captures failures
- `build_verification_report(contract, changed_files)` — orchestrates all checks and returns the full structured report

Report shape:

```json
{
  "verified": true,
  "missing": [],
  "warnings": [],
  "deployment_required": {
    "restart_backend": false,
    "restart_design_studio": false,
    "build_apk": false,
    "dashboard_changed": false
  },
  "syntax": {},
  "confidence": 100
}
```

---

### Task 4 — Engineering Worker

**File:** TBD
**Status:** Pending

Formal worker module that accepts a task contract, delegates to the appropriate execution backend (Claude Code or Cursor), and returns structured output for the Verifier to evaluate. Implements the Engineering Worker role defined in `gerald_os.md` Section 3.

---

### Task 5 — Cursor Worker

**File:** TBD
**Status:** Pending

Worker implementation that routes implementation tasks into the Cursor IDE environment. Handles local file edits and refactors on the Gerald server or connected dev machine. Implements the Cursor Worker role defined in `gerald_os.md` Section 3.

---

### Task 6 — Server Worker

**File:** TBD
**Status:** Pending

Server-side worker capable of running autonomously without Matt's PC being online. Required for 24/7 task execution. Corresponds to Phase 6 of the `gerald_os.md` roadmap.

---

## Exit Criteria

Sprint 001 is complete only when:

- Gerald can verify work — `task_completion_verifier.py` exists, `build_verification_report()` returns structured evidence.
- Gerald can determine deployment actions — `deployment_manager.py` exists, `POST /deploy/auto` returns correct action plan and result.
- Gerald no longer requires Matt to remember deployment commands — all restart and build steps are triggered automatically from changed files.

---

## Lessons Learned

*(Leave blank — to be filled at sprint close.)*

---

## Sprint Review

*(Leave blank — to be filled at sprint close.)*
