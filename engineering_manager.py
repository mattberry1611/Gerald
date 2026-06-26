"""
engineering_manager.py — Gerald OS Engineering Manager

Part of Gerald OS (see gerald_os.md).

Responsibility: Plan and assign work. Never execute it.

The Engineering Manager sits between the Supervisor and the workers.
It receives a structured task, decides which worker is best suited,
estimates complexity, and produces an Engineering Plan that tells the
Engineering Worker exactly what to do and what counts as done.

Gerald OS role reference (gerald_os.md, Section 3):
  "Engineering Manager — Breaks outcomes into tasks, writes task contracts,
   selects workers, tracks lifecycle."

Gerald OS constraint (gerald_os.md, Section 5):
  "Engineering Manager: Plan, contract, assign — not verify or deploy."

This module has zero side-effects. It reads nothing from disk and calls
no external services. All public functions are pure: same input → same output.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ── Constants ─────────────────────────────────────────────────────────────────

WORKER_CURSOR = "cursor"
WORKER_CLAUDE_CODE = "claude_code"

COMPLEXITY_TRIVIAL = "trivial"
COMPLEXITY_SMALL = "small"
COMPLEXITY_MEDIUM = "medium"
COMPLEXITY_LARGE = "large"

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_WORKERS = {WORKER_CURSOR, WORKER_CLAUDE_CODE}

# Keywords that suggest the task involves Flutter / Dart / UI work
_FLUTTER_SIGNALS = frozenset([
    "flutter", "dart", "widget", "screen", "ui", "layout", "design",
    "apk", "mobile", "app", "pubspec", "gerald_app", "build apk",
])

# Keywords that suggest the task involves Python backend work
_BACKEND_SIGNALS = frozenset([
    "python", "backend", "fastapi", "endpoint", "api", "service", "module",
    "gerald_bridge", "deployment", "verifier", "manager", "server",
    "systemctl", "restart", "import", ".py",
])


# ── Internal helpers ──────────────────────────────────────────────────────────

def _text_signals(task: dict) -> str:
    """Return a single lowercase string from all text fields in the task."""
    parts = [
        str(task.get("goal", "")),
        str(task.get("project", "")),
        str(task.get("description", "")),
        str(task.get("context", "")),
    ]
    return " ".join(parts).lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public functions ───────────────────────────────────────────────────────────

def select_worker(task: dict) -> dict:
    """
    Decide which engineering worker should execute a task.

    Supported workers:
      - "cursor"      — IDE-integrated edits; preferred for Flutter/Dart UI work
                        and tasks needing large project context in the editor.
      - "claude_code" — Autonomous CLI worker; preferred for backend Python,
                        scripting, refactors, and server-side changes.

    Args:
        task: dict with at least a "goal" key. May also include "project",
              "description", "context", and "priority".

    Returns:
        {
            "worker": "cursor" | "claude_code",
            "reason": str,
            "confidence": "high" | "medium" | "low"
        }

    This function never executes work. It only recommends.
    """
    text = _text_signals(task)

    flutter_score = sum(1 for signal in _FLUTTER_SIGNALS if signal in text)
    backend_score = sum(1 for signal in _BACKEND_SIGNALS if signal in text)

    if flutter_score > backend_score:
        return {
            "worker": WORKER_CURSOR,
            "reason": (
                "Task signals indicate Flutter/Dart UI work "
                f"({flutter_score} Flutter signals vs {backend_score} backend signals). "
                "Cursor worker has IDE context for large Dart codebases."
            ),
            "confidence": "high" if flutter_score >= 2 else "medium",
        }

    if backend_score > flutter_score:
        return {
            "worker": WORKER_CLAUDE_CODE,
            "reason": (
                "Task signals indicate Python backend work "
                f"({backend_score} backend signals vs {flutter_score} Flutter signals). "
                "Claude Code worker is preferred for server-side autonomous changes."
            ),
            "confidence": "high" if backend_score >= 2 else "medium",
        }

    return {
        "worker": WORKER_CLAUDE_CODE,
        "reason": (
            "No strong signal for either worker "
            f"(Flutter={flutter_score}, backend={backend_score}). "
            "Defaulting to Claude Code as the general-purpose worker."
        ),
        "confidence": "low",
    }


def estimate_complexity(task: dict) -> dict:
    """
    Estimate the complexity of a task based on its description.

    Complexity levels:
      - trivial  — single-file, single-function change; no deployment impact.
      - small    — 1–3 files; straightforward logic; one deployment action at most.
      - medium   — multiple files or components; cross-module changes; may need
                   restart or APK build.
      - large    — architectural change; many files; multiple deployment steps;
                   risk of breaking other components.

    Args:
        task: dict with at least a "goal" key.

    Returns:
        {
            "complexity": "trivial" | "small" | "medium" | "large",
            "reasoning": str,
            "estimated_files": int (lower-bound estimate)
        }
    """
    text = _text_signals(task)
    goal = str(task.get("goal", "")).lower()
    priority = str(task.get("priority", "medium")).lower()

    _large_signals = [
        "refactor", "redesign", "rebuild", "migrate", "architecture",
        "rewrite", "overhaul", "replace", "rename across", "sprint",
    ]
    _medium_signals = [
        "add feature", "new endpoint", "new screen", "new module",
        "integrate", "connect", "fix and verify", "apk",
    ]
    _small_signals = [
        "fix", "update", "change", "adjust", "rename", "tweak",
        "correct", "patch", "edit",
    ]

    large_hits = sum(1 for s in _large_signals if s in text)
    medium_hits = sum(1 for s in _medium_signals if s in text)
    small_hits = sum(1 for s in _small_signals if s in text)

    if large_hits >= 1 or priority == "critical":
        return {
            "complexity": COMPLEXITY_LARGE,
            "reasoning": (
                f"Large-scope signals detected ({large_hits} large, "
                f"{medium_hits} medium, {small_hits} small). "
                "Expect multiple files and deployment steps."
            ),
            "estimated_files": 5,
        }

    if medium_hits >= 1:
        return {
            "complexity": COMPLEXITY_MEDIUM,
            "reasoning": (
                f"Medium-scope signals detected ({medium_hits} medium hits). "
                "Likely 2–4 files and one deployment action."
            ),
            "estimated_files": 3,
        }

    if small_hits >= 1:
        return {
            "complexity": COMPLEXITY_SMALL,
            "reasoning": (
                f"Small-scope signals detected ({small_hits} small hits). "
                "Likely 1–2 files and minimal deployment impact."
            ),
            "estimated_files": 2,
        }

    return {
        "complexity": COMPLEXITY_TRIVIAL,
        "reasoning": (
            "No strong complexity signals found. "
            "Assuming trivial single-file change."
        ),
        "estimated_files": 1,
    }


def produce_engineering_plan(task: dict) -> dict:
    """
    Produce a full Engineering Plan for a task.

    The plan tells the Engineering Worker exactly what to do and defines what
    counts as done. The Engineering Manager never executes the plan itself.

    Gerald OS flow (gerald_os.md, Section 4):
      Task Contract → Worker selection → Engineering Worker → Verifier → Deployment Manager

    Args:
        task: dict with at least "goal". May include "project", "description",
              "context", "priority", and "required_files".

    Returns:
        {
            "objective":             str,
            "project":               str,
            "priority":              str,
            "worker":                str,
            "worker_reason":         str,
            "complexity":            str,
            "estimated_steps":       list[str],
            "verification_required": list[str],
            "deployment_required":   list[str],
            "created_at":            str (ISO 8601 UTC)
        }
    """
    goal = str(task.get("goal", "")).strip()
    project = str(task.get("project", "Gerald")).strip()
    priority = str(task.get("priority", "medium")).lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    worker_result = select_worker(task)
    complexity_result = estimate_complexity(task)

    worker = worker_result["worker"]
    complexity = complexity_result["complexity"]
    text = _text_signals(task)

    # Derive verification steps from the task nature
    verification_required: list[str] = [
        "Confirm all required files exist on disk",
        "Confirm required functions/classes/endpoints are present",
    ]

    # Python files always get a syntax check
    is_python = any(s in text for s in ["python", ".py", "backend", "fastapi", "endpoint"])
    is_flutter = any(s in text for s in _FLUTTER_SIGNALS)

    if is_python:
        verification_required.append("Run python3 -m py_compile on all modified Python files")
    if is_flutter:
        verification_required.append("Run flutter analyze in gerald_app/")
    verification_required.append("Run build_verification_report() from task_completion_verifier.py")

    # Derive deployment steps
    deployment_required: list[str] = []
    if is_python and not is_flutter:
        deployment_required.append("Restart gerald service if backend Python changed")
    if "gerald_design_studio" in text:
        deployment_required.append("Restart gerald-design-studio service")
    if is_flutter:
        deployment_required.append("Build debug APK: flutter build apk --debug")
        deployment_required.append("Copy APK to apk_serve/gerald-latest.apk")
    if "dashboard" in text:
        deployment_required.append("Mark dashboard as changed (no APK build required)")
    if not deployment_required:
        deployment_required.append("No deployment action anticipated — verify after implementation")

    # Build estimated steps based on complexity
    if complexity == COMPLEXITY_TRIVIAL:
        estimated_steps = [
            f"Identify the single file that requires change for: {goal}",
            "Make the minimal required edit",
            "Verify change with task_completion_verifier",
        ]
    elif complexity == COMPLEXITY_SMALL:
        estimated_steps = [
            f"Review contract scope for: {goal}",
            "Identify 1–2 files to create or modify",
            "Implement the required change",
            "Run syntax/compile check",
            "Verify with task_completion_verifier",
        ]
    elif complexity == COMPLEXITY_MEDIUM:
        estimated_steps = [
            f"Review full context for: {goal}",
            "Identify all affected files (estimated: {n})".format(
                n=complexity_result["estimated_files"]
            ),
            "Implement changes file by file",
            "Run syntax/compile checks on all modified files",
            "Verify all required symbols/endpoints exist",
            "Run build_verification_report()",
            "Report deployment actions required",
        ]
    else:  # large
        estimated_steps = [
            f"Review full project context and dependencies for: {goal}",
            "Break into sub-tasks if needed",
            "Implement each sub-task in isolation",
            "Run syntax/compile checks after each sub-task",
            "Verify files, symbols, and endpoints at each stage",
            "Run build_verification_report() for full report",
            "Run deployment actions via deployment_manager",
            "Confirm service health after deployment",
        ]

    return {
        "objective": goal,
        "project": project,
        "priority": priority,
        "worker": worker,
        "worker_reason": worker_result["reason"],
        "complexity": complexity,
        "estimated_steps": estimated_steps,
        "verification_required": verification_required,
        "deployment_required": deployment_required,
        "created_at": _now_iso(),
    }
