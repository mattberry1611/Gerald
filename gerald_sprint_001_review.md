# Sprint 001 Review — Gerald OS Foundation

**Sprint:** 001
**Status:** Complete
**Closed:** 2026-06-26
**Governing document:** `gerald_os.md`

---

## Objectives Completed

All three exit criteria from `gerald_sprint_001.md` were met:

| Exit Criterion | Result |
|---|---|
| Gerald can verify work | ✓ `task_completion_verifier.py` exists; `build_verification_report()` returns structured evidence with confidence score |
| Gerald can determine deployment actions | ✓ `deployment_manager.py` exists; `POST /deploy/auto` returns HTTP 200 with valid JSON |
| Gerald no longer requires Matt to remember deployment commands | ✓ Restarts, APK builds, and serve steps all triggered automatically from changed files |

---

## Components Created

All components were verified to compile clean (`PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile`) and pass functional tests.

### Documentation

| File | Purpose |
|---|---|
| `gerald_os.md` | Governing architecture document — vision, component roles, request flow, verification rules, deployment rules, roadmap, non-negotiables |
| `gerald_company.md` | Permanent organisational structure — CEO, CTO, CPO, Design Director, Engineering / Verification / Deployment / Memory departments |
| `gerald_sprint_001.md` | Sprint plan, task list, and exit criteria |

### Code Modules

| File | Role | Key Functions |
|---|---|---|
| `deployment_manager.py` | Deployment Department | `get_git_changed_files()`, `plan_deployment_actions()`, `run_deployment_actions()`, `auto_deploy()` |
| `task_completion_verifier.py` | Verification Department | `verify_file_exists()`, `verify_symbols_exist()`, `detect_deployment_required()`, `verify_python_syntax()`, `build_verification_report()`, `verify_worker_result()` |
| `engineering_manager.py` | Engineering Department — Planning | `select_worker()`, `estimate_complexity()`, `produce_engineering_plan()` |
| `engineering_worker.py` | Engineering Department — Execution | `select_execution_adapter()`, `build_execution_prompt()`, `execute_engineering_plan()` |
| `gerald_orchestrator.py` | Gerald OS Pipeline | `run_planning_stage()`, `run_execution_stage()`, `run_verification_stage()`, `run_deployment_stage()`, `run_pipeline()`, `OrchestratorDeps` |

### Endpoint Added

| Endpoint | File | Status |
|---|---|---|
| `POST /deploy/auto` | `gerald_bridge.py` | Live — HTTP 200 confirmed |

---

## Lessons Learned

### 1. `__pycache__` permission conflicts block compile checks in the sandbox

Running `python3 -m py_compile` in the `/opt/Gerald` directory fails with a permission error when the sandbox cannot write `.pyc` files to `__pycache__`. Fix: always use `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile` in this environment.

### 2. Self-restart via `systemctl restart gerald` kills the response mid-flight

`POST /deploy/auto` restarts the `gerald` service as part of its action set. If the restart fires synchronously, the response never arrives. Fix implemented: `gerald` restart is always the last action, run as a background `Popen` with `start_new_session=True` so the endpoint can return before the service stops.

### 3. Module docstrings must explicitly state Gerald OS role

Early iterations of modules had minimal docstrings. When a module's responsibility boundary is ambiguous, it becomes unclear whether to add logic there or in a neighbouring module. Fix: every module now opens with its Gerald OS role reference, constraint statement, and explicit "does NOT" list.

### 4. The `verify_worker_result()` integration point was missing from the initial verifier spec

The first pass of `task_completion_verifier.py` only accepted a generic `contract` dict. The Engineering Worker returns a different shape. Without a bridge function, callers would have had to reshape data manually each time. Fix: `verify_worker_result(plan, worker_result)` was added — it accepts exactly what `engineering_worker.execute_engineering_plan()` returns and builds the contract internally.

### 5. Dependency injection must be established from day one

The `gerald_orchestrator.py` uses an `OrchestratorDeps` dataclass to inject all four department callables. This was decided at design time rather than retrofitted. It allowed every stage to be tested with stubs in the same session it was written, with zero mocking frameworks required.

### 6. Document-first engineering produces fewer ambiguous handoffs

Modules written before `gerald_os.md` existed (prior to this sprint) had overlapping responsibilities. Every module written during Sprint 001 had a reference document to check against before the first line of code. The result: zero cases of a module accidentally doing another module's job.

---

## Architectural Decisions Made

### Decision 1: Dependency injection over direct imports in the orchestrator

**Choice:** `OrchestratorDeps` dataclass with injectable callables rather than hard module imports in `run_pipeline()`.

**Reason:** Any department (Engineering Manager, Verifier, Deployment Manager) can be swapped for a stub, a future replacement, or a test double without modifying orchestrator logic. This enforces the Gerald OS single-responsibility principle at the architecture level.

**Consequence:** Every stage is independently testable. The orchestrator has no hard coupling to any specific department implementation.

---

### Decision 2: Verifier always ignores worker self-reported status

**Choice:** `verify_worker_result()` accepts `worker_result["status"]` as metadata only and stores it in the report as `worker_status`, but sets `trust_override: "verified_by_evidence"` unconditionally.

**Reason:** Directly implements `gerald_os.md` Section 2: "No worker is trusted because it says done." A worker returning `"success"` is not evidence.

**Consequence:** The verification pipeline cannot be short-circuited by a worker claiming success. Evidence from the filesystem is the only path to `verified: true`.

---

### Decision 3: Deployment runs only after verified=true

**Choice:** `run_pipeline()` exits with `status: "retry_required"` and skips the deployment stage entirely if `verification_report["verified"]` is false.

**Reason:** Deploying unverified work is a non-negotiable violation per `gerald_os.md` Section 10.

**Consequence:** A failed verification is a hard stop. Matt receives a `retry_required` result with the exact `missing` list from the verifier rather than a partial deployment.

---

### Decision 4: `gerald` service restart is backgrounded

**Choice:** When `deployment_manager.py` restarts the `gerald` service, it uses `subprocess.Popen(..., start_new_session=True)` and returns immediately rather than waiting.

**Reason:** `gerald_bridge.py` is hosted inside the `gerald` service. A synchronous restart kills the process that is trying to return the HTTP response.

**Consequence:** The `POST /deploy/auto` endpoint always returns a result. The `gerald` restart fires in the background a few hundred milliseconds later. This is a known and accepted trade-off.

---

## Risks Discovered

### Risk 1: Dirty git working tree inflates deployment scope

**Observed:** `POST /deploy/auto` reads `git status --short` to decide what to deploy. The current working tree has 50+ uncommitted files — including unrelated JSON state files, logs, and generated artefacts. Every call to `/deploy/auto` currently treats all of these as changed and triggers all deployment actions.

**Severity:** Medium. The APK build is time-consuming (~10 minutes). Running it on every call when only a Python file changed is wasteful.

**Recommended mitigation (Sprint 002):** Scope deployment detection to files changed since a specific commit or since the last deployment run, not the full dirty working tree. Alternatively, add a `changed_files` parameter to `POST /deploy/auto` so callers can pass an explicit file list.

---

### Risk 2: Engineering Worker execution is not yet wired

**Observed:** `engineering_worker.execute_engineering_plan(plan, dry_run=False)` returns `status: "not_implemented"`. No real code execution happens through the Gerald OS pipeline yet.

**Severity:** Low for Sprint 001 (the pipeline structure was the goal), High for Sprint 002 (the next sprint must wire real execution).

**Recommended mitigation:** Implement the Cursor Worker adapter in Sprint 002, starting with `dry_run=False` execution for backend Python tasks via Claude Code.

---

### Risk 3: No persistent pipeline state between requests

**Observed:** Each call to `run_pipeline()` is stateless. If the service restarts between the planning stage and the deployment stage, all intermediate results are lost. There is no durable record of a pipeline run.

**Severity:** Low today (all stages run in one request). Will become Medium when long-running tasks span multiple sessions.

**Recommended mitigation (Sprint 003+):** Add a pipeline run ID and persist stage results to a JSON file in `/opt/Gerald/pipeline_runs/`. The Memory Department owns this.

---

### Risk 4: `task_completion_verifier` cannot verify Flutter output

**Observed:** The verifier checks Python syntax via `py_compile` and file/symbol existence. It has no equivalent for Dart/Flutter — it cannot confirm `flutter analyze` passes or that a widget class exists in Dart source.

**Severity:** Low today (Python is the primary target). Medium when Flutter tasks are verified through the pipeline.

**Recommended mitigation:** Future UI Verifier (listed in `gerald_company.md`) should include a `verify_flutter_syntax(file_paths)` function that wraps `flutter analyze`.

---

## Recommendations for Sprint 002

### Priority 1 — Wire real execution into Engineering Worker

The entire Gerald OS pipeline exists but executes no real code. Sprint 002 must connect at least one real adapter — Claude Code — to `execute_engineering_plan(plan, dry_run=False)`. Without this, Gerald OS is architecture without effect.

**Suggested task:** Implement `claude_code_worker.py` with a function `run_task(prompt: str) -> dict` that invokes Claude Code and returns changed files and output. Wire it into `engineering_worker` when `adapter == "claude_code"`.

### Priority 2 — Scope `/deploy/auto` to a specific file list

The current behaviour deploys based on the full dirty git working tree. This causes unnecessary APK builds and service restarts. Sprint 002 should add an optional `changed_files` body parameter to `POST /deploy/auto` so the caller (or the orchestrator) can scope deployment to only the files the current task touched.

### Priority 3 — Add `POST /orchestrate` to `gerald_bridge.py`

`gerald_orchestrator.run_pipeline()` exists but is not reachable over HTTP. Sprint 002 should add a `POST /orchestrate` endpoint that accepts a request dict, runs the full pipeline, and returns the result. This makes the entire Gerald OS pipeline callable from the Flutter app, dashboard, or Cursor.

### Priority 4 — Implement `verify_worker_result()` with real changed_files

Currently `verify_worker_result()` falls back to `plan.get("likely_files")` because the V1 worker does not return real changed files. Once the Claude Code Worker is wired in Sprint 002, it should return the actual files it modified, and the verifier should use those rather than the plan's estimate.

### Priority 5 — Create `gerald_sprint_002.md` before starting work

Sprint 001 demonstrated that document-first engineering reduces ambiguity. Sprint 002 must open with a sprint plan before any code is written.

---

## Sprint Exit Confirmation

| Exit Criterion | Evidence |
|---|---|
| `task_completion_verifier.py` exists | `ls -la` confirmed, 16,989 bytes |
| `build_verification_report()` works | Unit tests passed, confidence=100 on clean files |
| `deployment_manager.py` exists | `ls -la` confirmed, 8,575 bytes |
| `POST /deploy/auto` live | HTTP 200 confirmed, `success: true`, `apk_url: /apk-latest/download` |
| All modules compile clean | `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile` exit 0 on all five modules |
| Matt does not need deployment commands | `POST /deploy/auto` handles restarts, APK builds, and reporting automatically |

**Sprint 001 is closed.**

---

*Gerald Sprint 001 Review — closed 2026-06-26.*
