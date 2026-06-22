from typing import Dict, Any, Optional
from canonical_task_state import read_canonical_state, write_canonical_state

ACTIVE_STAGES = {
    "received",
    "classified",
    "planned",
    "planning",
    "executing",
    "verifying",
}

TERMINAL_STAGES = {
    "completed",
    "failed",
    "contract_failed",
    "partial",
    "timed_out",
    "error",
}

ALLOWED_TRANSITIONS = {
    "idle": {"received", "planning", "planned", "executing", "completed", "failed", "error"},
    "received": {"classified", "planned", "planning", "executing", "failed", "error"},
    "classified": {"planned", "planning", "executing", "failed", "error"},
    "planned": {"executing", "verifying", "completed", "failed", "error"},
    "planning": {"planned", "executing", "verifying", "completed", "needs_clarification", "failed", "error"},
    "executing": {"verifying", "completed", "partial", "failed", "contract_failed", "timed_out", "error"},
    "verifying": {"completed", "partial", "failed", "contract_failed", "error"},
    "needs_clarification": {"received", "planning", "executing", "completed", "failed", "error", "user_disputed"},
    "completed": {"received", "planning", "executing", "user_disputed"},
    "failed": {"received", "planning", "executing", "user_disputed"},
    "contract_failed": {"received", "planning", "executing", "user_disputed"},
    "partial": {"received", "planning", "executing", "user_disputed"},
    "timed_out": {"received", "planning", "executing", "user_disputed"},
    "error": {"received", "planning", "executing", "user_disputed"},
    "user_disputed": {"received", "planning", "executing", "failed", "error"},
}

def current_stage() -> str:
    return (read_canonical_state().get("stage") or "idle").strip()

def can_transition(from_stage: str, to_stage: str) -> bool:
    from_stage = (from_stage or "idle").strip()
    to_stage = (to_stage or "idle").strip()
    return to_stage in ALLOWED_TRANSITIONS.get(from_stage, set())

def transition(
    to_stage: str,
    *,
    task: str = "",
    project: str = "",
    detail: str = "",
    files_changed=None,
    output: str = "",
    error: str = "",
    contract: Optional[dict] = None,
    audit: Optional[dict] = None,
    task_id: str = None,
    force: bool = False,
) -> Dict[str, Any]:
    previous = read_canonical_state()
    from_stage = previous.get("stage") or "idle"
    to_stage = (to_stage or "idle").strip()

    if not force and not can_transition(from_stage, to_stage):
        return {
            "ok": False,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "error": f"Invalid lifecycle transition: {from_stage} -> {to_stage}",
            "state": previous,
        }

    state = write_canonical_state(
        task=task or previous.get("task", ""),
        project=project or previous.get("project", ""),
        stage=to_stage,
        detail=detail,
        files_changed=files_changed if files_changed is not None else previous.get("files_changed", []),
        output=output,
        error=error,
        contract=contract,
        audit=audit,
        task_id=task_id or previous.get("task_id", ""),
    )

    return {
        "ok": True,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "state": state,
    }

def mark_received(task: str, project: str, task_id: str = None, detail: str = "Task received"):
    return transition("received", task=task, project=project, task_id=task_id, detail=detail, force=True)

def mark_classified(task: str = "", project: str = "", task_id: str = None, detail: str = "Task classified"):
    return transition("classified", task=task, project=project, task_id=task_id, detail=detail)

def mark_planned(task: str = "", project: str = "", task_id: str = None, detail: str = "Task planned", contract: dict = None):
    return transition("planned", task=task, project=project, task_id=task_id, detail=detail, contract=contract)

def mark_planning(task: str = "", project: str = "", task_id: str = None, detail: str = "Planning"):
    return transition("planning", task=task, project=project, task_id=task_id, detail=detail, force=True)

def mark_executing(task: str = "", project: str = "", task_id: str = None, detail: str = "Executing", contract: dict = None):
    return transition("executing", task=task, project=project, task_id=task_id, detail=detail, contract=contract)

def mark_verifying(task: str = "", project: str = "", task_id: str = None, detail: str = "Verifying", files_changed=None, contract: dict = None):
    return transition("verifying", task=task, project=project, task_id=task_id, detail=detail, files_changed=files_changed, contract=contract)

def mark_completed(task: str = "", project: str = "", task_id: str = None, detail: str = "Completed", files_changed=None, output: str = "", audit: dict = None):
    return transition("completed", task=task, project=project, task_id=task_id, detail=detail, files_changed=files_changed, output=output, audit=audit)

def mark_failed(task: str = "", project: str = "", task_id: str = None, detail: str = "Failed", error: str = "", audit: dict = None):
    return transition("failed", task=task, project=project, task_id=task_id, detail=detail, error=error, audit=audit, force=True)

def mark_user_disputed(reason: str = "User disputed task outcome"):
    state = read_canonical_state()
    return transition(
        "user_disputed",
        task=state.get("task", ""),
        project=state.get("project", ""),
        task_id=state.get("task_id", ""),
        detail=reason,
        force=True,
    )
