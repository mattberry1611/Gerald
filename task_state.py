import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

TASK_FILE = Path("/opt/Gerald/active_task.json")

VALID_STAGES = [
    "Understanding",
    "Planning",
    "Waiting Approval",
    "Executing",
    "Verifying",
    "Completed",
    "Failed",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def _write(state):
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASK_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state

def read_task():
    if not TASK_FILE.exists():
        return {
            "active": False,
            "message": "No active task.",
        }

    try:
        return json.loads(TASK_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "active": False,
            "stage": "Failed",
            "error": f"Could not read active_task.json: {e}",
        }

def start_task(project, user_request):
    state = {
        "active": True,
        "task_id": str(uuid.uuid4()),
        "project": project,
        "user_request": user_request,
        "stage": "Understanding",
        "start_time": now_iso(),
        "end_time": None,
        "goal": None,
        "plan": [],
        "approval_required": True,
        "approved": False,
        "files_changed": [],
        "result": None,
        "verification": None,
        "error": None,
    }
    return _write(state)

def update_stage(stage):
    if stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage: {stage}")

    state = read_task()
    state["stage"] = stage
    return _write(state)

def set_goal_and_plan(goal, plan):
    state = read_task()
    state["goal"] = goal
    state["plan"] = plan
    state["stage"] = "Planning"
    return _write(state)

def mark_waiting_approval():
    state = read_task()
    state["stage"] = "Waiting Approval"
    state["approval_required"] = True
    state["approved"] = False
    return _write(state)

def mark_approved():
    state = read_task()
    state["approved"] = True
    state["stage"] = "Executing"
    return _write(state)

def add_file_changed(path):
    state = read_task()
    files = state.get("files_changed", [])
    if path not in files:
        files.append(path)
    state["files_changed"] = files
    return _write(state)

def mark_verifying():
    state = read_task()
    state["stage"] = "Verifying"
    return _write(state)

def complete_task(result, verification):
    state = read_task()
    state["stage"] = "Completed"
    state["active"] = False
    state["end_time"] = now_iso()
    state["result"] = result
    state["verification"] = verification
    return _write(state)

def fail_task(error):
    state = read_task()
    state["stage"] = "Failed"
    state["active"] = False
    state["end_time"] = now_iso()
    state["error"] = error
    return _write(state)

def truthful_status():
    state = read_task()

    if not state.get("active"):
        return "No active task is currently running."

    stage = state.get("stage", "Unknown")
    task_id = state.get("task_id", "Unknown")
    project = state.get("project", "Unknown")
    files = state.get("files_changed", [])

    if stage == "Executing":
        return f"Yes. A task is currently in Executing stage. Task ID: {task_id}. Project: {project}."

    if stage == "Waiting Approval":
        return f"No. Claude is not coding yet. Gerald is waiting for approval. Task ID: {task_id}."

    return f"Current task stage is {stage}. Task ID: {task_id}. Project: {project}. Files changed so far: {files}."
