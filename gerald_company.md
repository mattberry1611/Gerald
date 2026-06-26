# Gerald Company

**Governing architecture:** `gerald_os.md`
**Last updated:** 2026-06-26

---

## Gerald Company Vision

Gerald is an AI software company in a box. Matt asks for outcomes; Gerald organises the company to deliver them.

Gerald is not a chatbot. Gerald is not a code runner. Gerald is a structured organisation of specialised roles that together plan, build, verify, deploy, and report software work — so Matt never has to manage the pipeline manually.

Every role has a single responsibility. No role does the job of another. The result is a company that is traceable, improvable, and honest about what it has and has not done.

---

## CEO

**Responsibility:** Final authority. Release gate. Keeper of principles.

- Own all final decisions about what ships to Matt.
- Approve releases only after verification passes — never on the worker's word alone.
- Balance speed vs quality — neither is infinitely sacrificed for the other.
- Protect Gerald OS principles when other pressures push against them.
- Decide when work is genuinely ready for Matt, based on evidence, not optimism.

**Constraint:** Does not write code. Does not run deployments. Governs outcomes.

---

## CTO

**Responsibility:** Engineering architecture and technical direction.

- Own the engineering architecture of Gerald end-to-end.
- Guide the Engineering Manager on technical approach and trade-offs.
- Review significant technical decisions before they become permanent.
- Prevent random feature sprawl — every addition must fit the architecture.
- Ensure the layer boundaries in Gerald OS (plan → execute → verify → deploy) are respected.

**Constraint:** Does not implement features directly. Delegates execution to Engineering.

---

## CPO

**Responsibility:** Product vision, roadmap, and requirements.

- Define what Gerald should become — not just what it is today.
- Own the sprint roadmap and decide what gets built next.
- Write requirements clearly enough that Engineering can produce an unambiguous Engineering Plan.
- Decide which projects Gerald supports (CommuteCoder, RentMe, PlantBrain, and future products).
- Sprint planning — break the roadmap into deliverable chunks with clear exit criteria.

**Constraint:** Does not approve technical architecture. Does not direct engineering workers. Shapes the what, not the how.

---

## Design Director

**Responsibility:** Visual quality and design language.

- Set and protect UI and UX quality standards across all Gerald-built products.
- Define Gerald's visual design language so products feel consistent and considered.
- Commission work from Design Studio and review the output before it goes to Engineering.
- Compare the final delivered result against the original visual intent.
- Reject implementations that diverge from the approved design without a documented reason.

**Constraint:** Does not write frontend code. Does not bypass Engineering to push visual changes. Approves design; delegates implementation.

---

## Engineering Department

**Purpose:** Plan, assign, and execute software work.

No engineering worker self-certifies completion. All results pass to Verification before anything is deployed or reported to Matt.

### Engineering Manager

**File:** `engineering_manager.py`

- Receives a task and produces a structured Engineering Plan.
- Selects the right worker based on task signals (Flutter → Cursor, Python backend → Claude Code).
- Estimates complexity: trivial / small / medium / large.
- Defines verification requirements and deployment expectations in the plan.
- Never executes work itself.

### Engineering Worker

**File:** `engineering_worker.py`

- Receives an Engineering Plan from the Engineering Manager.
- Selects the execution adapter (Cursor or Claude Code).
- Builds the execution prompt with strict boundary instructions: do not verify, do not deploy, do not expand scope.
- Returns raw execution result to Verification.
- V1: `dry_run=True` returns what would run without executing; `dry_run=False` not yet wired.

### Cursor Worker

**File:** `cursor_worker.py` *(pending)*

- Executes tasks inside the Cursor IDE on Matt's PC.
- Required for Flutter/Dart UI work and tasks needing full IDE project context.
- Requires Matt's PC to be online with Cursor open.

### Claude Code Worker

**File:** `claude_code_worker.py` *(pending)*

- Executes tasks autonomously on the server via Claude Code CLI.
- Required for backend Python, scripting, refactors, and server-side changes.
- Does not require Matt's PC.

### Server Worker

**File:** TBD *(pending)*

- Executes tasks 24/7 on the server without Matt's PC.
- Enables Gerald to work overnight, between sessions, or in CI/CD pipelines.
- Phase 6 of the `gerald_os.md` roadmap.

---

## Verification Department

**Purpose:** Prove work is actually complete before Gerald claims success.

No result from Engineering is deployed or reported to Matt until Verification passes. Verification is always independent — it never trusts a worker's self-reported status.

### Task Completion Verifier

**File:** `task_completion_verifier.py`

- `verify_file_exists(path)` — confirms required files are on disk.
- `verify_symbols_exist(file_paths, symbols)` — confirms functions, classes, and endpoints exist via AST and regex.
- `detect_deployment_required(changed_files)` — reports what deployment actions are needed, without running them.
- `verify_python_syntax(file_paths)` — runs `python3 -m py_compile` and captures failures.
- `build_verification_report(contract, changed_files)` — full structured report with confidence score (0–100).
- `verify_worker_result(plan, worker_result)` — bridges Engineering Worker output to verification; ignores worker's status claim entirely.

### Future: UI Verifier

*(Not yet built)*

Screenshot or DOM-based confirmation that UI changes are visible and match the approved design. Will integrate with the Vision Worker and Design Director review process.

### Future: API Verifier

*(Not yet built)*

Live HTTP endpoint tests confirming required routes respond correctly with expected structure and status codes.

---

## Deployment Department

**Purpose:** Restart services, build APKs, serve artefacts, and confirm deployment health.

Deployment only runs after Verification passes. Unverified work is never deployed.

### Deployment Manager

**File:** `deployment_manager.py`
**Endpoint:** `POST /deploy/auto`

| Changed files | Action |
|---|---|
| Root-level `*.py` (e.g. `gerald_bridge.py`) | `systemctl restart gerald` |
| `gerald_design_studio.py` | `systemctl restart gerald-design-studio` |
| `gerald_app/lib/` or `pubspec.yaml` | `flutter build apk --debug` → copy to `apk_serve/gerald-latest.apk` |
| `dashboard/` | Mark dashboard changed — no APK build |

Matt never needs to remember deployment commands. `POST /deploy/auto` handles the full sequence and returns a structured JSON result.

---

## Memory Department

**Purpose:** Make Gerald improve over time and avoid repeating mistakes.

Memory is what separates a company from a stateless tool. Every task outcome is stored. Every lesson is accessible to future planning. Architecture decisions persist across sessions.

### Project Brain

**Files:** `project_brains/`, `gerald_brain.py`, `*_product_brain.json`

Structured context for every project Gerald works on. Injected into task planning so the Engineering Manager understands the project before assigning work.

### Lessons

**Files:** `project_memories/*_lessons.md`

Per-project record of what went wrong and what worked. Injected into contracts so workers do not repeat documented failures.

### Roadmap

**Files:** `gerald_sprint_*.md`, `gerald_os.md` Section 8

Structured sprint plans and phase roadmaps. Defines what has been built, what is next, and what is deferred.

### Architecture

**Files:** `gerald_os.md`, `gerald_company.md`

Permanent governing documents. Not session state — long-lived organisational memory that defines how Gerald operates at all times.

### History

**Files:** `gerald_task_history_*.json`, session logs

Durable record of every completed task: what was requested, what was built, what Verification found, what was deployed, and what the final confidence score was.

---

## How Gerald Company Maps to Gerald OS

`gerald_os.md` defines the technical flow. `gerald_company.md` defines who owns each layer.

```
Matt
  │  (states an outcome)
  ▼
CEO / CPO
  │  (approve, prioritise, plan sprint)
  ▼
─── Planning Layer ──────────────────────────────────────────
  Engineering Manager   →  produce_engineering_plan()
  Memory Department     →  context, lessons, project brain
─── Execution Layer ─────────────────────────────────────────
  Engineering Worker    →  execute_engineering_plan()
  Cursor Worker         →  IDE execution (PC required)
  Claude Code Worker    →  server execution (autonomous)
─── Verification Layer ──────────────────────────────────────
  Task Completion Verifier  →  verify_worker_result()
  Future: UI Verifier
  Future: API Verifier
─── Deployment Layer ────────────────────────────────────────
  Deployment Manager    →  auto_deploy() / POST /deploy/auto
─── Memory Layer ────────────────────────────────────────────
  Project Brain + Lessons + History + Architecture
  │
  ▼
Result to Matt
  (summary, evidence, APK URL or endpoint, next action)
```

### Layer ownership

| Layer | Gerald OS component | Gerald Company owner |
|---|---|---|
| Planning | Engineering Manager | CTO → Engineering Manager |
| Execution | Engineering Worker, Cursor Worker, Claude Code Worker | Engineering Department |
| Verification | Task Completion Verifier, UI Verifier, API Verifier | Verification Department |
| Deployment | Deployment Manager | Deployment Department |
| Memory | Project Brain, Lessons, History, Architecture | Memory Department |
| Product decisions | Supervisor intake | CEO + CPO |
| Design quality | Design Studio | Design Director |

---

## Non-Negotiables

These apply to every department, every role, every sprint. They do not change when a sprint is pressured or when a task is running late.

- **No worker self-certifies completion.** Verification is always independent. A worker returning `"success"` is not evidence.
- **Matt should never need to remember build or restart commands.** Gerald handles `systemctl`, `flutter build`, APK serving, and health checks automatically.
- **Every task ends with evidence.** Files, syntax checks, endpoint tests, build output — not assertions. Not summaries. Evidence.
- **Gerald protects project isolation.** CommuteCoder, RentMe, PlantBrain, and other projects do not bleed into each other. Context, files, and history are scoped per project.
- **Gerald asks for outcomes, not instructions.** Matt says what he wants. Gerald plans, assigns, verifies, deploys, and reports. Matt does not manage the pipeline.
- **Gerald must become more reliable after every failure.** Each failure is captured in Lessons. Each repeated failure is a process failure, not just a technical one.

---

*Gerald Company v1 — permanent organisational reference.*
