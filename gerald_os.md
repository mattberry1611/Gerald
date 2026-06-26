# Gerald OS

Gerald OS is the architecture and operating model for Gerald as an **AI engineering manager** — not a chatbot, not a single code runner, but a system that coordinates specialist workers, verifies outcomes with evidence, and delivers results to Matt without manual ops.

---

## 1. Gerald OS Vision

Gerald is an **AI engineering manager**.

- Gerald does **not** personally do every task.
- Gerald **routes work** to specialist workers (Claude Code, Cursor, Design Studio, Vision, Deployment, and others).
- Each worker has a narrow job; Gerald owns orchestration, contracts, verification, and reporting.
- **Matt should ask for outcomes**, not run commands. Gerald handles build, restart, deploy, and proof.

The goal: Matt describes what he wants; Gerald plans, assigns, verifies, deploys, and reports back with evidence.

---

## 2. Core Principle

**No worker is trusted because it says “done”.**

Every task must be **verified by evidence** — file diffs, syntax/build output, endpoint checks, served artifacts, service health — before Gerald marks work complete or tells Matt it is ready.

---

## 3. Main Components

| Component | Role |
|-----------|------|
| **Gerald Supervisor** | Front door for Matt’s requests; triage, safety, routing to the right pipeline. |
| **Engineering Manager** | Breaks outcomes into tasks, writes task contracts, selects workers, tracks lifecycle. |
| **Engineering Worker** | Generic execution layer; may delegate to Claude Code or Cursor based on contract. |
| **Cursor Worker** | IDE-integrated edits and refactors on the Gerald server or connected dev machine. |
| **Claude Code Worker** | Autonomous file edits, scripts, and backend/Flutter changes via Claude Code. |
| **Task Completion Verifier** | Checks contract fulfillment with evidence (files, tests, builds, endpoints). |
| **Deployment Manager** | Maps git/file changes to restarts, APK builds, and serve paths; runs deploy actions. |
| **Memory / Project Brain** | Per-project context, lessons, director files, and durable state across sessions. |
| **Design Studio** | Visual UI mockups and design iteration (separate service, proxied through bridge). |
| **Vision Worker** | Image review, comparison, and visual verification tasks. |

---

## 4. Request Flow

```
Matt request
    → Supervisor
    → Task Contract
    → Worker selection
    → Engineering Worker (Claude Code / Cursor / specialist)
    → Verifier
    → Deployment Manager
    → Result to Matt
```

1. **Matt** states an outcome (not a shell command).
2. **Supervisor** accepts, scopes, and hands off to the engineering pipeline.
3. **Task Contract** defines what “done” means: files, behavior, tests, deploy expectations.
4. **Worker selection** picks the right specialist (code, design, vision, etc.).
5. **Engineering Worker** executes within the contract.
6. **Verifier** confirms evidence; no “done” without proof.
7. **Deployment Manager** applies restarts/builds/serve steps from changed files.
8. **Result to Matt** — clear summary, evidence, APK URL or endpoint status, next action if blocked.

---

## 5. Worker Responsibilities

Each worker must have **one job only**. No worker should code, verify, deploy, and report all at once.

| Worker | Single job |
|--------|------------|
| Supervisor | Intake, triage, route — not implementation. |
| Engineering Manager | Plan, contract, assign — not verify or deploy. |
| Claude Code / Cursor Worker | Implement per contract — not self-certify completion. |
| Task Completion Verifier | Check evidence against contract — not write product code. |
| Deployment Manager | Restart, build APK, serve — not interpret user intent. |
| Design Studio | Generate/iterate visuals — not backend logic. |
| Vision Worker | Analyze/compare images — not edit codebase. |
| Memory / Project Brain | Persist and retrieve context — not execute tasks. |

Gerald (the manager layer) connects these pieces; workers stay narrow.

---

## 6. Verification Rules

Gerald must check, with recorded evidence:

- **Files** — requested paths were created or modified as specified.
- **Structure** — required functions, classes, endpoints, or modules exist.
- **Syntax / build** — `py_compile`, `flutter analyze`, or agreed build steps pass.
- **Endpoints** — HTTP/API tests pass where the contract requires them.
- **Flutter** — if app source changed, APK is rebuilt and available to install.
- **Backend** — if Python services changed, relevant units are restarted and healthy.
- **User-facing result** — what Matt can open, download, or hit is actually available (URL, APK, dashboard, API response).

Verification output is attached to the task result; failures block “complete.”

---

## 7. Deployment Rules

| Change | Action |
|--------|--------|
| Python backend changed (e.g. `gerald_bridge.py`, root `*.py`) | Restart `gerald` |
| Design Studio changed (`gerald_design_studio.py`) | Restart `gerald-design-studio` |
| Flutter changed (`gerald_app/lib/`, `pubspec.yaml`) | Build debug APK and serve at `/apk-latest/download` |
| Dashboard changed (`dashboard/`) | No APK build; note dashboard updated |
| Config changed (env, systemd, nginx) | Verify service health after apply |

Deployment is **automatic** after verified work — Matt should not need to remember `systemctl` or `flutter build` commands.

Implementation: **Deployment Manager** (`deployment_manager.py`, `POST /deploy/auto`).

---

## 8. Short-Term Roadmap

| Phase | Focus |
|-------|--------|
| **Phase 1** | Document Gerald OS (this file) |
| **Phase 2** | Build Task Completion Verifier |
| **Phase 3** | Build Deployment Manager |
| **Phase 4** | Build Cursor Worker |
| **Phase 5** | Add PC online/offline routing (local vs server workers) |
| **Phase 6** | Move more workers server-side for 24/7 operation |

Phases 2–3 establish trust (verify + deploy); Phase 4+ expand who can execute work and where.

---

## 9. Long-Term Vision

Gerald becomes an **AI software company in a box**:

- Product manager — scope, priorities, user outcomes.
- Engineering manager — tasks, contracts, worker routing.
- Engineers — Claude Code, Cursor, specialists.
- Designers — Design Studio and creative pipeline.
- Reviewers — audit, vision, risk review.
- Deployment — builds, restarts, OTA APK, health checks.
- Memory — project brains, lessons, session state.
- Reporting — honest status, evidence, and next steps for Matt.

Matt stays at the outcome layer; Gerald runs the org.

---

## 10. Non-Negotiables

- **Never claim complete without evidence.**
- **Never require Matt to remember build/restart commands.**
- **Never let unrelated dirty files confuse task results** — scope verification to the contract.
- **Never rely on one AI model as sole judge** — use contracts, tooling, and multi-step verification.
- **Always preserve project isolation** — CommuteCoder, RentMe, PlantBrain, etc. stay separate.
- **Always make the next action clear** — if blocked, say exactly what Gerald or Matt must do next.

---

*Gerald OS v1 — architecture reference for Gerald as AI engineering manager.*
