"""
Gerald Brain V3 — Per-project persistent session/conversation state.

Logs every user request, Gerald response, task contract, Claude result,
audit result, Matt correction, and outcome to a per-project JSON log.

Provides:
  - load_session_context()  → compact text block for prompt injection
  - log_event()             → append to session log
  - is_failure_feedback()   → detect Matt corrections
  - get_last_failed_task()  → surface last task for reopen
  - append_lesson()         → write to per-project lessons file
  - get_session_summary()   → dashboard read-only summary
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE = Path("/opt/Gerald")
CONVERSATIONS_DIR = BASE / "conversations"
PROJECT_MEMORIES_DIR = BASE / "project_memories"

CONVERSATIONS_DIR.mkdir(exist_ok=True)
PROJECT_MEMORIES_DIR.mkdir(exist_ok=True)

# ── Failure feedback detection ─────────────────────────────────────────────────

FAILURE_PHRASES = [
    "still broken",
    "still not working",
    "still failing",
    "didn't work",
    "that didn't work",
    "doesn't work",
    "not fixed",
    "still the same",
    "still an issue",
    "it's broken",
    "it broke",
    "failed again",
    "still wrong",
    "broke again",
    "broken again",
    "still a problem",
    "same issue",
    "same problem",
    "same bug",
    "not working still",
    "still not fixed",
    "hasn't changed",
    "nothing changed",
    # User Reality Override phrases — user sees no visible change despite COMPLETE verdict
    "not what i asked for",
    "can't see it",
    "where is it",
    "looks the same",
]

# Subset of FAILURE_PHRASES that specifically signal a User Reality Override conflict
# (user experience contradicts technical completion status).
from user_reality_override import (
    USER_REALITY_PHRASES,
    is_user_reality_conflict,
    handle_user_reality_override,
)

from ui_component_verifier import verify_ui_components, is_ui_related_task
from ui_verifier import check_uro_conflict as _check_uro_conflict

# Paths written by the bridge — session state overrides these when a UI conflict is found.
_TASK_STATE_FILE = BASE / "active_task.json"
_STATUS_FILE = BASE / "gerald_status.json"

# ── Path helpers ───────────────────────────────────────────────────────────────

def _safe(project: str) -> str:
    return (project or "CommuteCoder").replace(" ", "_").replace("/", "_").replace("\\", "_")


def _session_log_file(project: str) -> Path:
    return CONVERSATIONS_DIR / f"{_safe(project)}_session_log.json"


def _lessons_file(project: str) -> Path:
    return PROJECT_MEMORIES_DIR / f"{_safe(project)}_lessons.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Event log I/O ──────────────────────────────────────────────────────────────

def _read_log(project: str) -> list:
    path = _session_log_file(project)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_log(project: str, events: list):
    path = _session_log_file(project)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[session_state] write_log error: {e}")


def handle_ui_component_verification(project: str) -> None:
    """
    Supervisor-only UI component check fired when an 'outcome' event with
    status='completed' is logged.  Reads active_task.json to decide whether
    the completed task touched the dashboard UI.  If it did AND
    verify_ui_components() finds issues, overrides active_task.json stage to
    'contract_failed' and gerald_status.json to 'error', then logs a
    ui_component_conflict event so the supervisor (Matt) sees the failure.

    Runs AFTER the bridge writes its 'completed' state so the overrides are final.
    Does not edit dashboard/app.js or any Flutter files.
    """
    now = _now()

    # Read the task state the bridge just wrote.
    try:
        current_state = json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8")) if _TASK_STATE_FILE.exists() else {}
    except Exception:
        current_state = {}

    task_text = current_state.get("task", "")
    files_changed = current_state.get("files_changed", [])

    # Only run for UI-related tasks to avoid false positives on unrelated completions.
    if not is_ui_related_task(task_text, files_changed):
        return

    ui_result = verify_ui_components()
    if ui_result["verdict"] == "PASS":
        return

    # Issues found — override COMPLETE with contract_failed.
    issues_text = "; ".join(ui_result.get("issues", []))[:300]
    print(f"[ui_verifier] OVERRIDE: UI component issues detected — {issues_text}")

    # Patch the stored audit verdict so the dashboard shows the real state.
    if "audit" in current_state and isinstance(current_state["audit"], dict):
        current_state["audit"]["verdict"] = "FAILED"
        current_state["audit"]["notes"] = f"UI Verifier override: {issues_text}"
        missing = current_state["audit"].get("missing", [])
        missing.append(f"UI component check: {issues_text}")
        current_state["audit"]["missing"] = missing

    current_state["stage"] = "contract_failed"
    current_state["detail"] = f"UI component check failed: {issues_text}"
    current_state["updated"] = now

    try:
        _TASK_STATE_FILE.write_text(json.dumps(current_state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ui_verifier] failed to write task state: {e}")

    try:
        _STATUS_FILE.write_text(
            json.dumps({
                "status": "error",
                "detail": f"UI component check: {issues_text[:120]}",
                "updated": now,
            }),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[ui_verifier] failed to write status: {e}")

    # Log the conflict so it appears in /session/summary.
    log_event(
        project,
        "ui_component_conflict",
        verdict="FAILED",
        issues=ui_result.get("issues", []),
        evidence=ui_result.get("evidence", {}),
        checked_file=ui_result.get("checked_file", ""),
        override="COMPLETE → contract_failed",
    )


def handle_user_reality_verification(project: str) -> None:
    """
    Hook fired on outcome(completed) events. Checks for an unresolved URO
    conflict via ui_verifier.check_uro_conflict(). If one exists, overrides
    active_task.json stage to contract_failed and emits a
    user_reality_conflict event — ensuring user-reported reality beats a
    technical COMPLETE verdict when no confirmation of resolution exists.
    """
    result = _check_uro_conflict(project)
    if not result["conflict"]:
        return

    now = _now()
    uro = result["uro_event"] or {}
    phrases = result["evidence"].get("uro_phrases", [])
    reason = (
        f"URO verification override: user reported mismatch {phrases} "
        f"at {uro.get('ts', '?')} — COMPLETE blocked until user confirms resolution"
    )
    print(f"[ui_verifier] URO OVERRIDE project={project!r}: {reason}")

    try:
        current_state = json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8")) if _TASK_STATE_FILE.exists() else {}
    except Exception:
        current_state = {}

    if "audit" in current_state and isinstance(current_state["audit"], dict):
        current_state["audit"]["verdict"] = "FAILED"
        current_state["audit"]["notes"] = f"URO override: {reason[:200]}"
        missing = current_state["audit"].get("missing", [])
        missing.insert(0, f"User reality not confirmed: {'; '.join(str(p) for p in phrases)}")
        current_state["audit"]["missing"] = missing

    current_state["stage"] = "contract_failed"
    current_state["detail"] = reason[:200]
    current_state["updated"] = now

    try:
        _TASK_STATE_FILE.write_text(json.dumps(current_state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ui_verifier] failed to write task state: {e}")

    try:
        _STATUS_FILE.write_text(
            json.dumps({
                "status": "error",
                "detail": f"URO override: {'; '.join(str(p) for p in phrases)}",
                "updated": now,
            }),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[ui_verifier] failed to write status: {e}")

    log_event(
        project,
        "user_reality_conflict",
        source="uro_verification_hook",
        detected_phrases=phrases,
        task_flagged=True,
        previous_stage="completed",
        new_stage="contract_failed",
        evidence=result["evidence"],
    )


def log_event(project: str, event_type: str, **kwargs):
    """Append one event to the project's session log. Keeps last 100 entries."""
    try:
        events = _read_log(project)
        events.append({"ts": _now(), "type": event_type, **kwargs})
        events = events[-100:]
        _write_log(project, events)

        # Task-local file baseline: snapshot dirty files at the moment Matt's
        # request is logged — before the background worker starts.  The review
        # layer subtracts this baseline so only task-local file changes are evaluated.
        if event_type == "user_request":
            try:
                from gerald_request_review import snapshot_pre_task_files
                snapshot_pre_task_files()
            except Exception as _snap_err:
                print(f"[session_state] task_baseline_snapshot error: {_snap_err}")

        # User Reality Override hook: when the bridge logs a matt_correction,
        # check for user-reality phrases and emit user_reality_conflict + flag task.
        # Runs AFTER the event is persisted so evidence is captured in order.
        if event_type == "matt_correction":
            _text = kwargs.get("text", "")
            try:
                handle_user_reality_override(project, _text, log_event)
            except Exception as _uro_err:
                print(f"[session_state] user_reality_override error: {_uro_err}")

        # UI Component Verifier hook: when the bridge logs an outcome with
        # status='completed', check dashboard/app.js for duplicate or missing
        # required UI components.  Runs AFTER the event is persisted so any
        # override writes are the final state on disk.
        if event_type == "outcome" and kwargs.get("status") == "completed":
            try:
                handle_ui_component_verification(project)
            except Exception as _uiv_err:
                print(f"[session_state] ui_component_verifier error: {_uiv_err}")
            try:
                handle_user_reality_verification(project)
            except Exception as _urv_err:
                print(f"[session_state] user_reality_verifier error: {_urv_err}")

        # Auditor Integrity guards — run on every outcome event.
        # Guard 1 (UNKNOWN → FAILED) covers the contract_failed path from parse failures.
        # Guards 2 and 3 (review FAIL enforcement, scope check) cover the completed path.
        if event_type == "outcome":
            try:
                from auditor_integrity import handle_audit_unknown_verdict
                handle_audit_unknown_verdict(project)
            except Exception as _ai1_err:
                print(f"[session_state] audit_unknown_verdict error: {_ai1_err}")
            if kwargs.get("status") == "completed":
                try:
                    from auditor_integrity import handle_review_fail_enforcement
                    handle_review_fail_enforcement(project)
                except Exception as _ai2_err:
                    print(f"[session_state] review_fail_enforcement error: {_ai2_err}")
                try:
                    from auditor_integrity import handle_scope_check
                    handle_scope_check(project)
                except Exception as _ai3_err:
                    print(f"[session_state] scope_check error: {_ai3_err}")
    except Exception as e:
        print(f"[session_state] log_event error: {e}")


# ── Failure feedback detection ─────────────────────────────────────────────────

def is_failure_feedback(text: str) -> bool:
    """Return True if Matt's message signals the last task failed or regressed."""
    lower = (text or "").lower()
    return any(p in lower for p in FAILURE_PHRASES)


# ── Context retrieval ──────────────────────────────────────────────────────────

def get_last_failed_task(project: str) -> Optional[dict]:
    """Return the last task contract and result events for reopen context."""
    try:
        events = _read_log(project)
        last_contract = None
        last_result = None
        for e in reversed(events):
            if not last_contract and e.get("type") == "task_contract":
                last_contract = e
            if not last_result and e.get("type") in ("claude_result", "audit_result"):
                last_result = e
            if last_contract and last_result:
                break
        if not last_contract and not last_result:
            return None
        return {"contract": last_contract, "result": last_result}
    except Exception:
        return None


def load_session_context(project: str, limit: int = 10) -> str:
    """
    Return a compact text block summarising recent session history.
    Injected into Planner, Decision Agent, Auditor, and Claude prompts.
    Includes user requests, Gerald responses, contracts, results, audits, corrections.
    """
    try:
        events = _read_log(project)
        recent = events[-limit:]
        lessons = _read_lessons(project)

        if not recent and not lessons:
            return ""

        lines = []

        if recent:
            lines.append("# Session History (Recent)")
            for e in recent:
                ts = e.get("ts", "")[:16].replace("T", " ")
                etype = e.get("type", "?")
                if etype == "user_request":
                    lines.append(f"[{ts}] Matt: {(e.get('text') or '')[:200]}")
                elif etype == "gerald_response":
                    lines.append(f"[{ts}] Gerald: {(e.get('text') or '')[:250]}")
                elif etype == "task_contract":
                    intent = (e.get("intent") or "")[:180]
                    n = e.get("n_requirements", "?")
                    lines.append(f"[{ts}] Contract ({n} reqs): {intent}")
                elif etype == "claude_result":
                    status = e.get("status", "?")
                    summary = (e.get("summary") or "")[:200]
                    lines.append(f"[{ts}] Claude: {status} — {summary}")
                elif etype == "audit_result":
                    verdict = e.get("verdict", "?")
                    notes = (e.get("notes") or "")[:150]
                    missing = e.get("missing", [])
                    lines.append(f"[{ts}] Audit: {verdict} — {notes}")
                    if missing:
                        lines.append(f"  Missing: {'; '.join(str(m)[:80] for m in missing[:3])}")
                elif etype == "matt_correction":
                    lines.append(f"[{ts}] ⚠ MATT CORRECTION: {(e.get('text') or '')[:200]}")
                elif etype == "task_reopened":
                    reason = (e.get("reason") or "")[:150]
                    intent = (e.get("last_intent") or "")[:100]
                    lines.append(f"[{ts}] ↩ Task reopened: {reason}")
                    if intent:
                        lines.append(f"  Last task intent: {intent}")
                elif etype == "outcome":
                    lines.append(f"[{ts}] Outcome: {e.get('status','?')} — {(e.get('detail') or '')[:150]}")
                elif etype == "lesson_learned":
                    lines.append(f"[{ts}] Lesson: {(e.get('lesson') or '')[:100]}")

        if lessons:
            lines.append("\n# Project Lessons (Memory)")
            lines.append(lessons[:1500])

        return "\n".join(lines)
    except Exception as e:
        print(f"[session_state] load_session_context error: {e}")
        return ""


# ── Lessons memory ─────────────────────────────────────────────────────────────

def _read_lessons(project: str) -> str:
    path = _lessons_file(project)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    # Fall back to global gerald_lessons.md (CommuteCoder legacy)
    global_lessons = BASE / "gerald_lessons.md"
    if global_lessons.exists():
        try:
            return global_lessons.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def append_lesson(project: str, lesson: str):
    """Append a new lesson entry to the per-project lessons file."""
    try:
        if not lesson.strip():
            return
        path = _lessons_file(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except Exception:
                pass
        if not existing:
            existing = (
                f"# {project} — Project Lessons\n\n"
                "## Format\nEach lesson records: Problem, Root cause, Fix, Outcome, Reuse rule\n\n---\n"
            )
        entry = f"\n## Lesson — {_now()[:10]}\n{lesson.strip()}\n"
        path.write_text(existing + entry, encoding="utf-8")
        log_event(project, "lesson_learned", lesson=lesson[:200])
    except Exception as e:
        print(f"[session_state] append_lesson error: {e}")


# ── Dashboard helpers ──────────────────────────────────────────────────────────

def get_session_summary(project: str) -> dict:
    """Return session summary for dashboard display (read-only)."""
    try:
        events = _read_log(project)
        corrections = [e for e in events if e.get("type") == "matt_correction"]
        last_outcome = next((e for e in reversed(events) if e.get("type") == "outcome"), None)
        last_contract = next((e for e in reversed(events) if e.get("type") == "task_contract"), None)
        last_audit = next((e for e in reversed(events) if e.get("type") == "audit_result"), None)
        return {
            "project": project,
            "total_events": len(events),
            "recent_events": events[-20:],
            "correction_count": len(corrections),
            "last_outcome": last_outcome,
            "last_contract": last_contract,
            "last_audit": last_audit,
        }
    except Exception as e:
        return {"project": project, "error": str(e), "total_events": 0}
