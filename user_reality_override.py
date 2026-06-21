"""
User Reality Override — Supervisor-only fix for task completion disputes.

Detects when a user reports a task appears unchanged or wrong despite COMPLETE
status. Automatically flags the active task as suspect, emits a
user_reality_conflict event (in addition to the bridge's existing task_reopened),
and records structured verification evidence.

Called via the log_event() hook in gerald_session_state.py — no changes to
gerald_bridge.py required.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/opt/Gerald")
ACTIVE_TASK_FILE = BASE / "active_task.json"

# Phrases that signal the user sees no change despite a COMPLETE verdict.
# Distinct from the broader FAILURE_PHRASES list (which covers regression/crash).
USER_REALITY_PHRASES = [
    "still broken",
    "not what i asked for",
    "can't see it",
    "where is it",
    "looks the same",
]


# ── Detection helpers ──────────────────────────────────────────────────────────

def is_user_reality_conflict(text: str) -> bool:
    """Return True if text contains at least one User Reality Override phrase."""
    lower = (text or "").lower()
    return any(p in lower for p in USER_REALITY_PHRASES)


def get_matched_phrases(text: str) -> list:
    """Return all User Reality Override phrases found in text."""
    lower = (text or "").lower()
    return [p for p in USER_REALITY_PHRASES if p in lower]


# ── Active task helpers ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_active_task() -> dict:
    try:
        if ACTIVE_TASK_FILE.exists():
            return json.loads(ACTIVE_TASK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_active_task(data: dict):
    try:
        ACTIVE_TASK_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[user_reality_override] write_active_task error: {e}")


# ── Task flagging ──────────────────────────────────────────────────────────────

def flag_active_task_as_suspect(project: str, reason: str) -> dict:
    """
    Mark active_task.json as suspect if it belongs to this project.
    Works for any non-idle, non-suspect stage so that COMPLETE, partial, or
    executing tasks are all caught when the user disputes the outcome.

    Returns an evidence dict describing what changed.
    """
    task = _read_active_task()
    prev_stage = task.get("stage", "unknown")
    prev_audit_verdict = (task.get("audit") or {}).get("verdict", "")
    flagged = False

    # Determine if this task is for the right project and is not already suspect/idle
    task_project = task.get("project", "")
    skip_stages = {"idle", "suspect", ""}
    if task_project == project and prev_stage.lower() not in skip_stages:
        task["stage"] = "suspect"
        task["user_reality_dispute"] = {
            "disputed_at": _now(),
            "previous_stage": prev_stage,
            "previous_audit_verdict": prev_audit_verdict,
            "reason": reason,
        }
        _write_active_task(task)
        flagged = True

    return {
        "task_project": task_project,
        "matched_project": task_project == project,
        "previous_stage": prev_stage,
        "previous_audit_verdict": prev_audit_verdict,
        "new_stage": "suspect" if flagged else prev_stage,
        "flagged": flagged,
        "reason": reason,
        "flagged_at": _now(),
    }


# ── Main orchestrator ──────────────────────────────────────────────────────────

def handle_user_reality_override(project: str, text: str, log_event_fn) -> bool:
    """
    Orchestrate the User Reality Override flow.

    Steps:
    1. Check if text matches any USER_REALITY_PHRASES.
    2. Flag the active task as suspect in active_task.json.
    3. Emit user_reality_conflict event with full verification evidence.
       (task_reopened is already emitted by the bridge; not duplicated here.)

    Args:
        project:       The resolved project name.
        text:          The raw user feedback text.
        log_event_fn:  Callable matching log_event(project, event_type, **kwargs).

    Returns True if the override was triggered.
    """
    if not is_user_reality_conflict(text):
        return False

    matched = get_matched_phrases(text)
    reason = f"User reality phrase detected: {matched[0]!r}"

    # Flag the active task as suspect
    task_evidence = flag_active_task_as_suspect(project, reason)

    # Build structured verification evidence (satisfies all three evidence requirements)
    verification_evidence = {
        "trigger": "user_reality_override",
        "detection_ts": _now(),
        # Evidence for phrase detection
        "phrase_detection": {
            "matched_phrases": matched,
            "all_checked": USER_REALITY_PHRASES,
            "confidence": "exact_match",
            "source": "user_feedback",
            "original_text_excerpt": text[:300],
        },
        # Evidence for task reopening
        "task_reopening": {
            "project": project,
            "previous_stage": task_evidence["previous_stage"],
            "new_stage": task_evidence["new_stage"],
            "flagged": task_evidence["flagged"],
            "reason": reason,
            "flagged_at": task_evidence["flagged_at"],
        },
        # Evidence for status dispute
        "status_dispute": {
            "technical_verdict": task_evidence["previous_audit_verdict"] or task_evidence["previous_stage"],
            "user_reported_outcome": "not resolved",
            "conflict": True,
            "disputed_phrases": matched,
            "supervisor_notes": (
                "User experience contradicts technical completion status. "
                "Task flagged as suspect. Revalidation required before marking COMPLETE again."
            ),
        },
    }

    # Emit user_reality_conflict event (the bridge already emitted task_reopened)
    log_event_fn(
        project,
        "user_reality_conflict",
        detected_phrases=matched,
        user_text=text[:300],
        task_flagged=task_evidence["flagged"],
        previous_stage=task_evidence["previous_stage"],
        new_stage=task_evidence["new_stage"],
        evidence=verification_evidence,
    )

    print(
        f"[user_reality_override] project={project!r} "
        f"phrases={matched} flagged={task_evidence['flagged']}"
    )
    return True
