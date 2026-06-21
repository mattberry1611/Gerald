import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

BASE = "/opt/Gerald"
CANONICAL_PATH = os.path.join(BASE, "gerald_canonical_task_state.json")

VALID_STAGES = {
    "received",
    "classified",
    "planned",
    "planning",
    "executing",
    "verifying",
    "completed",
    "failed",
    "contract_failed",
    "partial",
    "timed_out",
    "error",
    "needs_clarification",
    "user_disputed",
    "idle",
}

TERMINAL_FAIL_STAGES = {"failed", "contract_failed", "timed_out", "error"}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalise_stage(stage: str) -> str:
    stage = (stage or "idle").strip()
    return stage if stage in VALID_STAGES else "error"

def read_canonical_state() -> Dict[str, Any]:
    if not os.path.exists(CANONICAL_PATH):
        return {
            "schema": "gerald.v4.canonical_task_state.v1",
            "task_id": "",
            "task": "",
            "project": "",
            "stage": "idle",
            "detail": "",
            "files_changed": [],
            "output": "",
            "error": "",
            "contract": None,
            "audit": None,
            "updated": now_iso(),
            "started": now_iso(),
            "source_of_truth": "canonical",
        }

    try:
        with open(CANONICAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {
            "schema": "gerald.v4.canonical_task_state.v1",
            "task_id": "",
            "task": "",
            "project": "",
            "stage": "error",
            "detail": "Canonical task state could not be read",
            "files_changed": [],
            "output": "",
            "error": str(e),
            "contract": None,
            "audit": None,
            "updated": now_iso(),
            "started": now_iso(),
            "source_of_truth": "canonical",
        }

def write_canonical_state(
    task: str,
    project: str,
    stage: str,
    detail: str = "",
    files_changed=None,
    output: str = "",
    error: str = "",
    contract=None,
    audit=None,
    task_id: str = None,
) -> Dict[str, Any]:
    previous = read_canonical_state()
    stage = normalise_stage(stage)

    existing_task_id = previous.get("task_id") or ""
    existing_started = previous.get("started") or now_iso()

    state = {
        "schema": "gerald.v4.canonical_task_state.v1",
        "task_id": task_id or existing_task_id or "",
        "task": task or previous.get("task", ""),
        "project": project or previous.get("project", ""),
        "stage": stage,
        "detail": detail or "",
        "files_changed": files_changed or [],
        "output": output or "",
        "error": error or "",
        "contract": contract if contract is not None else previous.get("contract"),
        "audit": audit if audit is not None else previous.get("audit"),
        "updated": now_iso(),
        "started": existing_started,
        "source_of_truth": "canonical",
    }

    tmp = CANONICAL_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, CANONICAL_PATH)
    return state

def mark_user_disputed(reason: str = "") -> Dict[str, Any]:
    state = read_canonical_state()
    state["stage"] = "user_disputed"
    state["detail"] = reason or "User disputed the task outcome"
    state["updated"] = now_iso()
    state["source_of_truth"] = "canonical"

    tmp = CANONICAL_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, CANONICAL_PATH)
    return state
