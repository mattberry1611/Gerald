"""
UI / User Reality Verifier — cross-checks technical completion claims against
user-reported reality via the session event log.

Provides:
  check_uro_conflict(project) → {conflict, uro_event, last_completed_ts,
                                  new_request_ts, evidence}

Called by gerald_session_state.handle_user_reality_verification() and
directly by the auditor post-parse gate in gerald_bridge.audit_task_contract().
No imports from gerald_session_state — avoids circular dependency.
"""

import json
from pathlib import Path

BASE = Path("/opt/Gerald")
_CONVERSATIONS_DIR = BASE / "conversations"


def _safe(project: str) -> str:
    return (project or "CommuteCoder").replace(" ", "_").replace("/", "_").replace("\\", "_")


def _read_session_log(project: str) -> list:
    path = _CONVERSATIONS_DIR / f"{_safe(project)}_session_log.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def check_uro_conflict(project: str) -> dict:
    """
    Return whether there is an unresolved User Reality Override conflict for
    this project.

    An unresolved conflict exists when a user_reality_conflict event appears in
    the session log AFTER the last outcome(completed) event and BEFORE the most
    recent user_request event — meaning the user disputed the previous COMPLETE
    and then issued a new task to fix it, but we haven't yet confirmed the fix
    resolved the user-visible problem.

    Returns:
        {
            "conflict": bool,
            "uro_event": dict | None,
            "last_completed_ts": str | None,
            "new_request_ts": str | None,
            "evidence": {
                "project": str,
                "uro_phrases": list,
                "disputed_at": str | None,
                "previous_stage": str | None,
            },
        }
    """
    events = _read_session_log(project)

    # Most recent user_request (the task currently being evaluated).
    last_request_idx = None
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("type") == "user_request":
            last_request_idx = i
            break

    if last_request_idx is None:
        return {
            "conflict": False,
            "uro_event": None,
            "last_completed_ts": None,
            "new_request_ts": None,
            "evidence": {"reason": "no user_request in session log"},
        }

    last_request = events[last_request_idx]

    # Most recent outcome(completed) BEFORE the last user_request.
    last_completed = None
    last_completed_idx = None
    for i in range(last_request_idx - 1, -1, -1):
        e = events[i]
        if e.get("type") == "outcome" and e.get("status") == "completed":
            last_completed = e
            last_completed_idx = i
            break

    # Search for a user_reality_conflict between last_completed and last_request.
    search_start = (last_completed_idx + 1) if last_completed_idx is not None else 0
    uro_event = None
    for i in range(last_request_idx - 1, search_start - 1, -1):
        if events[i].get("type") == "user_reality_conflict":
            uro_event = events[i]
            break

    return {
        "conflict": uro_event is not None,
        "uro_event": uro_event,
        "last_completed_ts": last_completed.get("ts") if last_completed else None,
        "new_request_ts": last_request.get("ts") if last_request else None,
        "evidence": {
            "project": project,
            "uro_phrases": (uro_event or {}).get("detected_phrases", []),
            "disputed_at": (uro_event or {}).get("ts"),
            "previous_stage": (uro_event or {}).get("previous_stage"),
        },
    }
