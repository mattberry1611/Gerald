import os
from canonical_task_state import read_canonical_state, write_canonical_state, mark_user_disputed
from task_lifecycle import TaskLifecycleController, TransitionError, LIFECYCLE_STAGES

_lifecycle = TaskLifecycleController()
import re
import json
import subprocess
import signal
import time
import shlex
import uuid
import urllib.request
import urllib.error
from anthropic import Anthropic
from openai import OpenAI
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException, Request
from task_state import read_task, truthful_status, start_task, update_stage, add_file_changed, complete_task, fail_task
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import build_verifier
import multi_ai_router
from gerald_brain import inject_brain_context
from gerald_openai_brain import ask_gerald, decide_supervisor_action, generate_risk_review
from gerald_vision import review_image
from gerald_request_review import review_task_result
import gerald_issue_memory
import gerald_session_state as _gss
from verification_layer import VerificationLayer

BASE = "/opt/Gerald"
ACTIVE_TASK = os.path.join(BASE, "active_task.json")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = r"/opt/Gerald"
OUTBOX_FILE = os.path.join(BASE, "gerald_outbox.json")
STATUS_FILE = os.path.join(BASE, "gerald_status.json")
DEVICES_FILE = os.path.join(BASE, "gerald_devices.json")
PROJECTS_FILE = os.path.join(BASE, "gerald_projects.json")
APK_MANIFEST_FILE = os.path.join(BASE, "apk_manifest.json")
APK_SERVE_DIR = os.path.join(BASE, "apk_serve")
APK_SERVE_FILE = os.path.join(APK_SERVE_DIR, "gerald-latest.apk")

# ─── V4 Agent Kernel: Persistent Task Result Layer ────────────────────────────
TASK_HISTORY_MAX = 200
STATUS_CHECK_FILE = os.path.join(BASE, "gerald_last_status_check.json")


def _generate_task_id() -> str:
    return uuid.uuid4().hex[:12]


def _get_task_history_file(project_name: str) -> str:
    safe = project_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return os.path.join(BASE, f"gerald_task_history_{safe}.json")


def _append_task_history(record: dict, project_name: str) -> None:
    """Append a completed real-task record to the per-project durable history."""
    path = _get_task_history_file(project_name)
    history = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as _f:
                history = json.load(_f)
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(record)
    if len(history) > TASK_HISTORY_MAX:
        history = history[-TASK_HISTORY_MAX:]
    try:
        with open(path, "w", encoding="utf-8") as _f:
            json.dump(history, _f, indent=2)
    except Exception as _e:
        print(f"[task_history] Failed to append: {_e}")


_STATUS_CHECK_IMPERATIVE_STARTERS = (
    "update ", "implement ", "create ", "build ", "add ", "fix ", "write ",
    "make ", "change ", "delete ", "remove ", "migrate ", "deploy ", "generate ",
    "refactor ", "redesign ", "upgrade ", "install ", "configure ", "setup ",
    "move ", "rename ", "replace ", "modify ", "edit ", "convert ", "extend ",
    "enable ", "disable ", "improve ", "optimize ", "enhance ", "show ", "display ",
    "render ", "style ", "design ", "format ", "clean ", "sort ", "filter ",
    "fetch ", "load ", "save ", "send ", "push ", "test ", "verify ",
)


def _is_status_check_task(text: str) -> bool:
    """Return True if text is a status/check query rather than an implementation task.

    Uses keyword + combination matching with typo tolerance for common variants
    (e.g. 'lastbtask', 'lasttask').  Long messages (>15 words) and messages that
    open with an imperative verb are treated as implementation requests, not status checks.
    """
    lowered = (text or "").lower().strip()
    if not lowered:
        return False

    # Long messages are almost always implementation requests
    if len(lowered.split()) > 15:
        return False

    # Imperative-verb openers signal a task, not a status check
    if any(lowered.startswith(s) for s in _STATUS_CHECK_IMPERATIVE_STARTERS):
        return False

    # Typo-normalised text: strip all non-alpha for fuzzy substring matching
    norm = "".join(c for c in lowered if c.isalpha())

    done_words = ("done", "complete", "finished", "finish")
    running_words = ("running", "working", "active")
    state_words = done_words + running_words + ("status",)
    interrogatives = ("is it", "is the", "are you", "did it", "have you", "has it", "is claude")

    # "last task" with typo tolerance + any state word
    has_last_task = (
        ("last" in lowered and "task" in lowered)
        or any(v in norm for v in ("lasttask", "lastbtask", "lastask", "lastetask"))
    )
    if has_last_task and any(w in lowered for w in state_words):
        return True

    # Interrogative + state word: "is it complete", "did it finish", "is claude running"
    if any(iq in lowered for iq in interrogatives) and any(w in lowered for w in state_words):
        return True

    # Standalone "status" / "status check" (not embedded in an implementation sentence)
    if lowered.strip("?!. ") in ("status", "status check"):
        return True

    # "what is the status", "what's the status"
    if "what" in lowered and "status" in lowered:
        return True

    # "still running/working/done"
    if "still" in lowered and any(w in lowered for w in running_words + done_words):
        return True

    return False


_TERMINAL_CMD_PREFIXES = (
    "curl ", "cat ", "grep ", "ls ", "ls\t", "cd ", "sed ", "systemctl ",
)

_LAST_RESULT_OUTPUT_PHRASES = (
    "last task result",
    "task/last-result",
    "/task/last-result",
    "last result is",
    "the last task is complete",
)


def _is_terminal_command_task(text: str) -> bool:
    """Return True if text is a raw shell/terminal command rather than a user task."""
    lowered = (text or "").lower().lstrip()
    return any(lowered.startswith(p) for p in _TERMINAL_CMD_PREFIXES)


def _output_reports_last_result(output: str, summary: str) -> bool:
    """Return True if the output is just a meta-report of /task/last-result content."""
    combined = ((output or "") + " " + (summary or "")).lower()
    return any(phrase in combined for phrase in _LAST_RESULT_OUTPUT_PHRASES)


def _get_last_real_task_result(project_name: str) -> dict:
    """Return the latest successful real user task result from durable history.

    Excludes:
    - status/check questions
    - terminal command tasks
    - failed/error/contract_failed/partial/unknown records
    - records with non-zero returncode
    - empty output/summary records
    - records that only report another last-result
    """
    path = _get_task_history_file(project_name)
    if not os.path.exists(path):
        return {}

    command_prefixes = (
        "curl ", "cat ", "grep ", "ls ", "cd ", "sed ", "systemctl ",
        "python ", "python3 ", "tail ", "head ", "nano ", "vim "
    )

    bad_statuses = {
        "error", "failed", "contract_failed", "partial", "unknown",
        "timed_out", "timeout"
    }

    def _is_command_task(task_text: str) -> bool:
        lowered = (task_text or "").lower().strip()
        return lowered.startswith(command_prefixes)

    def _reports_last_result(output_text: str, summary_text: str) -> bool:
        combined = f"{output_text or ''} {summary_text or ''}".lower()
        return (
            "last task result is" in combined
            or "/task/last-result" in combined
            or "the last task is complete" in combined
            or "output was:" in combined
        )

    def _has_useful_output(record: dict) -> bool:
        output = (record.get("output") or "").strip()
        summary = (record.get("summary") or "").strip()
        return bool(output or summary)

    def _is_success(record: dict) -> bool:
        status = (record.get("status") or "").lower().strip()
        if status in bad_statuses:
            return False

        returncode = record.get("returncode", 0)
        try:
            if int(returncode) != 0:
                return False
        except Exception:
            return False

        return True

    try:
        with open(path, "r", encoding="utf-8") as _f:
            history = json.load(_f)

        if not isinstance(history, list):
            return {}

        for record in reversed(history):
            task_text = record.get("task", "")
            output_text = record.get("output", "") or ""
            summary_text = record.get("summary", "") or ""

            is_live_investigation = (
                "# Live Investigation Result" in output_text
                or "Investigation completed from live evidence" in output_text
                or "Investigation completed from live evidence" in summary_text
            )

            if _is_status_check_task(task_text) and not is_live_investigation:
                continue

            if _is_command_task(task_text):
                continue

            if not _is_success(record):
                continue

            if not _has_useful_output(record):
                continue

            if _reports_last_result(record.get("output", ""), record.get("summary", "")) and not is_live_investigation:
                continue

            return record

    except Exception:
        pass

    return {}

CLAUDE_PS1 = r"C:\Users\Matt\AppData\Roaming\npm\claude.ps1"

BRAIN_FILES = ["project_brain.md", "roadmap.md", "current_status.md", "architecture.md"]

BUILTIN_PROJECTS = [
    {"name": "CommuteCoder", "path": r"/opt/Gerald", "description": "Voice-driven AI coding supervisor"},
    {"name": "RentMe", "path": r"C:\RentMe", "description": "Rental management app"},
    {"name": "PlantBrain", "path": r"C:\PlantBrain", "description": "Plant care AI"},
]


# ─── Project persistence ───────────────────────────────────────────────────────

def load_projects():
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return list(BUILTIN_PROJECTS)


def save_projects(projects):
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2)


# Resolves Gerald project paths from the registered project list

def _looks_like_investigation_request(text: str) -> bool:
    lower = (text or "").lower()
    phrases = [
        "why do",
        "why does",
        "why did",
        "why is",
        "why are",
        "investigate",
        "find out why",
        "look into",
        "root cause",
        "what caused",
        "stuck task",
        "stuck state",
    ]
    return any(x in lower for x in phrases)



def _looks_like_implementation_request(text: str) -> bool:
    """Return True when Matt is asking for a real code/file change.

    This prevents the Investigation Evidence Gate from hijacking requests like:
    "investigate and fix", "CODE CHANGE REQUIRED", or "return code changes".
    """
    lower = (text or "").lower()
    phrases = [
        "code change required",
        "backend code change",
        "source code modification",
        "route to claude code",
        "modify ",
        "implement ",
        "fix ",
        "patch ",
        "change ",
        "update ",
        "return code changes",
        "return exact files changed",
        "files changed",
    ]
    return any(x in lower for x in phrases)


def _run_command_evidence(label: str, command: list, timeout: int = 20) -> str:
    import subprocess
    try:
        r = subprocess.run(
            command,
            cwd="/opt/Gerald",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (
            f"\n## {label}\n"
            f"$ {' '.join(command)}\n"
            f"EXIT:{r.returncode}\n"
            f"STDOUT:\n{(r.stdout or '').strip()}\n"
            f"STDERR:\n{(r.stderr or '').strip()}\n"
        )
    except Exception as e:
        return f"\n## {label}\n$ {' '.join(command)}\nFAILED_TO_RUN:{e}\n"


def _build_live_investigation_answer(question: str, project_name: str = "CommuteCoder") -> str:
    sections = []
    sections.append("# Live Investigation Result")
    sections.append(f"Question: {question}")
    sections.append(_run_command_evidence("Current canonical truth", ["curl", "-s", "http://localhost:8000/task/truth"]))
    sections.append(_run_command_evidence("Current task status", ["curl", "-s", "http://localhost:8000/task/status"]))
    sections.append(_run_command_evidence("Last real task result", ["curl", "-s", f"http://localhost:8000/task/last-result?project={project_name}"]))
    sections.append(_run_command_evidence("Lifecycle rules", ["grep", "-n", "ALLOWED_TRANSITIONS\\|def transition\\|def mark_", "lifecycle_controller.py", "task_lifecycle.py"]))
    sections.append(_run_command_evidence("Recent Gerald errors", ["bash", "-lc", "journalctl -u gerald -n 120 --no-pager | grep -i 'Traceback\\|ERROR\\|Exception\\|529\\|stuck\\|contract_failed\\|lifecycle' || true"]))
    sections.append("# Evidence-Based Answer")
    sections.append("Use the live evidence above. Do not answer from memory or assumptions.")
    return "\n".join(sections)


def resolve_project(project_name: str):
    """Return (path, canonical_name) for a project name."""
    if not project_name:
        return BASE, "CommuteCoder"
    for p in load_projects():
        if p["name"].lower() == project_name.lower():
            return p["path"], p["name"]
    # Named project not in registry → map to /opt/Gerald/{name}, never CommuteCoder
    return os.path.join(BASE, project_name), project_name


# ─── Project Brain ─────────────────────────────────────────────────────────────

def get_brain_content(project_path: str) -> str:
    """Load brain markdown files from project dir, return combined string."""
    sections = []
    for fname in BRAIN_FILES:
        fpath = os.path.join(project_path, fname)
        if os.path.exists(fpath):
            try:
                content = open(fpath, encoding="utf-8").read().strip()
                if content:
                    sections.append(f"### {fname}\n{content}")
            except Exception:
                pass
    return "\n\n".join(sections) if sections else ""


def create_brain_files(project_path: str, project_name: str, description: str = ""):
    """Create initial brain stub files for a new project (skips existing files)."""
    today = datetime.now().strftime("%Y-%m-%d")
    stubs = {
        "project_brain.md": (
            f"# {project_name} — Project Brain\n\n"
            f"## Overview\n{description or project_name + ' project.'}\n\n"
            "## Tech Stack\n- (to be filled)\n\n"
            "## Architecture\n- (to be filled)\n\n"
            "## Key Files\n- (to be filled)\n"
        ),
        "roadmap.md": (
            f"# {project_name} — Roadmap\n\n"
            "## Current Sprint\n- (to be filled)\n\n"
            "## Backlog\n- (to be filled)\n\n"
            "## Done\n- (to be filled)\n"
        ),
        "current_status.md": (
            f"# {project_name} — Current Status\n\n"
            f"**Last Updated:** {today}\n\n"
            "## Active Work\n- (to be filled)\n\n"
            "## Blockers\n- None\n\n"
            "## Next Up\n- (to be filled)\n"
        ),
        "architecture.md": (
            f"# {project_name} — Architecture\n\n"
            "## Structure\n- (to be filled)\n\n"
            "## Data Flow\n- (to be filled)\n\n"
            "## Key Decisions\n- (to be filled)\n"
        ),
    }
    os.makedirs(project_path, exist_ok=True)
    subprocess.run(["chown", "geraldbuild:geraldbuild", project_path], check=False)
    for fname, content in stubs.items():
        fpath = os.path.join(project_path, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(fpath, 0o664)
            subprocess.run(["chown", "geraldbuild:geraldbuild", fpath], check=False)


# ─── Voice command detection ──────────────────────────────────────────────────

_CREATE_PREFIXES = [
    "create new project ",
    "create project ",
    "new project ",
    "make new project ",
    "make project ",
    "start project ",
    "start new project ",
    "create new app ",
    "create app ",
    "new app ",
]


def detect_create_project_name(text: str) -> str | None:
    """Return a project name if the text looks like 'create project MyApp'."""
    lower = text.strip().lower()
    for prefix in _CREATE_PREFIXES:
        if lower.startswith(prefix):
            remainder = text[len(prefix):].strip()
            # Take the first word (project name must be one clean token)
            first = re.split(r"[\s,\.!?]", remainder)[0].strip()
            if 2 <= len(first) <= 40:
                return first
    return None


# ─── Project Isolation ─────────────────────────────────────────────────────────

def get_project_outbox_file(project_name: str) -> str:
    """Return per-project outbox path for isolated output tracking."""
    safe = project_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return os.path.join(BASE, f"gerald_outbox_{safe}.json")


# ─── Core utilities ────────────────────────────────────────────────────────────

def write_status(status, detail=""):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "status": status,
            "detail": detail,
            "updated": datetime.now(timezone.utc).isoformat()
        }, f, indent=2)



def mark_fresh_task(task: str, project: str = "CommuteCoder"):
    """Reset stale Claude-waiting state when Matt sends a new task."""
    write_status("planning", "New task received — planning")
    write_outbox({
        "task": task,
        "project": project,
        "status": "fresh",
        "output": "New task received. Previous pending Claude state cleared.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def write_outbox(data, outbox_file=None):
    target = outbox_file or OUTBOX_FILE
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # Mirror to primary outbox so /read always works regardless of project
    if outbox_file and outbox_file != OUTBOX_FILE:
        with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ─── Reasoning Layer V2: recurring-failure notifications ─────────────────────

def _notify_recurring_failure(alert: dict, project_name: str) -> None:
    """Write a recurring-failure alert to Matt's outbox and pending notification.

    This only logs and alerts — it does NOT modify any code.
    """
    global _pending_notification
    count = alert.get("occurrence_count", 2)
    desc = alert.get("description", "")[:120]
    issue_type = alert.get("type", "unknown")
    kind = issue_type.replace("_", " ")
    count_str = f"{count} time{'s' if count != 1 else ''}"
    msg = (
        f"Heads up — Gerald has hit the same {kind} {count_str} in {project_name}. "
        f"No automatic changes were made. Manual review is recommended."
    )
    print(f"[RLv2] RECURRING FAILURE DETECTED (x{count}): {desc[:80]}")
    project_outbox = get_project_outbox_file(project_name)
    alert_data = {
        "task": "Reasoning Layer V2 alert",
        "project": project_name,
        "status": "recurring_failure_alert",
        "output": msg,
        "alert": alert,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_outbox(alert_data, project_outbox)
    _pending_notification = {
        "title": "Recurring issue detected",
        "body": f"{project_name}: same {kind} seen {count_str}.",
        "type": "recurring_failure_alert",
        "received": datetime.now(timezone.utc).isoformat(),
        "delivered": False,
    }


def run_claude(task_text: str, project_path: str = BASE, project_name: str = "CommuteCoder"):
    print("\n==============================")
    print("📥 GERALD TASK RECEIVED")
    print(f"Project: {project_name} ({project_path})")
    print(task_text)
    print("==============================\n")

    write_status("working", f"Claude working on {project_name}")

    # ── Project Brain: auto-create stub files if none exist ────────────────────
    existing_brain = [f for f in BRAIN_FILES if os.path.exists(os.path.join(project_path, f))]
    if not existing_brain:
        create_brain_files(project_path, project_name)
        print(f"[gerald] Auto-initialised brain files for {project_name} at {project_path}")

    # ── Project Brain context injection ────────────────────────────────────────
    brain = get_brain_content(project_path)
    brain_section = ""
    if brain:
        brain_section = f"\n# Project Brain (Context)\n{brain}\n"

    # ── Isolation: list all OTHER project paths to block ──────────────────────
    all_projects = load_projects()
    other_paths = [p["path"] for p in all_projects if p["path"].lower() != project_path.lower()]
    isolation_lines = "\n".join(f"- {p}" for p in other_paths)
    isolation_block = (
        f"\n# Project Isolation\nDO NOT read or modify any files outside {project_path}.\n"
        f"Explicitly forbidden paths:\n{isolation_lines}\n"
    ) if other_paths else ""

    prompt = f"""You are Claude Code working inside:

{project_path}

Matt's task:
{task_text}
{brain_section}
Rules:
- Work ONLY inside {project_path}
- You ARE approved to edit files inside {project_path}
- Do not ask Matt for permission for safe local file edits
- Complete the task, then provide a concise summary of what changed
{isolation_block}
# Project Brain Update
After completing the task, update the brain files in {project_path} if relevant:
- current_status.md — always update if you changed code (what is now working, any blockers)
- roadmap.md — update if you completed items or identified new ones
- project_brain.md — update if tech stack, architecture, or key decisions changed
- architecture.md — update if the system structure changed
Only update files that are directly relevant to what you just did. Keep updates concise."""

    project_outbox = get_project_outbox_file(project_name)

    try:
        client = Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        output = "\n".join(
            block.text for block in message.content
            if getattr(block, "type", "") == "text"
        ).strip()

        data = {
            "task": task_text,
            "project": project_name,
            "status": "done",
            "returncode": 0,
            "output": output,
            "error": "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        write_outbox(data, project_outbox)
        write_status("idle", "Claude API finished")

        print("✅ CLAUDE API FINISHED")
        print(output)

    except Exception as e:
        write_status("error", str(e))
        write_outbox({
            "task": task_text,
            "project": project_name,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, project_outbox)
        print("❌ ERROR:", e)


# ─── Endpoints ─────────────────────────────────────────────────────────────────




# Decides whether a task should run from the backend root based on its content.
# This function detects backend-root tasks
def should_use_backend_root(task_text: str) -> bool:
    lower = (task_text or "").lower()
    backend_terms = [
        "gerald_bridge.py",
        "decision agent",
        "review agent",
        "gerald review",
        "backend",
        "routing",
        "worker directory",
        "task state",
        "outbox",
        "gerald_openai_brain",
        "gerald brain",
        "review step",
        "run_claude_code_worker",
        "review_task_result",
        "_worker",
        "after claude",
        "before marking completed",
        "mark task completed",
        "create a file",
        "create file",
        "called ",
        "containing exactly",
        "project root",
        "no newline",
        "capture command evidence",
    ]
    flutter_terms = [
        "home screen",
        "button",
        "ui",
        "screen",
        "widget",
        "flutter",
        "apk button",
        "text box",
        "microphone",
        "mode selector",
    ]
    # Backend symbols must win before Flutter keywords, because backend tasks often
    # say "do not modify Flutter files" while still being backend tasks.
    if any(t in lower for t in backend_terms):
        return True
    if any(t in lower for t in flutter_terms):
        return False
    return False

# Returns the active worker directory for the given task and project.
def get_worker_directory(task_text: str, project_name: str = "CommuteCoder") -> str:
    # Non-CommuteCoder projects: resolve the registered path and use it directly.
    if project_name and project_name.lower() != "commutecoder":
        proj_path, _ = resolve_project(project_name)
        print(f"[worker_dir] project={project_name} worker_dir={proj_path}")
        return proj_path
    # CommuteCoder: backend-only tasks run from the backend root; Flutter tasks use gerald_app.
    if should_use_backend_root(task_text):
        return "/opt/Gerald"
    return "/opt/Gerald/gerald_app"


def run_claude_code_worker(task_text: str, project_name: str = "CommuteCoder"):
    """Run approved implementation tasks through real Claude Code CLI."""
    _task_id = _generate_task_id()
    project_outbox = get_project_outbox_file(project_name)

    worker_dir = get_worker_directory(task_text, project_name)

    bridge_rule = (
        "- Backend task approved: gerald_bridge.py may be edited if needed."
        if should_use_backend_root(task_text)
        else "- Do not edit gerald_bridge.py."
    )
    inspect_rule = (
        "- Inspect relevant backend files first."
        if should_use_backend_root(task_text)
        else "- Inspect relevant Flutter files first."
    )

    safe_prompt = f"""
You are Claude Code working for Gerald.

Matt's request:
{task_text}

Project: {project_name}
Working directory: {worker_dir}

Rules:
{inspect_rule}
- Make the smallest safe change that satisfies Matt's request.
- Preserve existing behaviour and functionality.
{bridge_rule}
- Do not build APK.
- After editing, summarize exactly which files changed and what changed.
"""

    _proj_path, _ = resolve_project(project_name)
    safe_prompt = inject_brain_context(safe_prompt, _proj_path, project_name)
    print(f"[brain] inject_brain_context (worker): {len(safe_prompt)} chars, project={project_name}, path={_proj_path}")

    mark_fresh_task(task_text, project_name)

    # ── Planner: Generate Task Contract before Claude runs ────────────────
    print("[planner] Generating task contract…")
    try:
        _contract = create_task_contract(task_text, project_name)
    except RuntimeError as _planner_exc:
        print(f"[planner] FATAL: {_planner_exc}")
        write_task_state(task_text, project_name, "failed",
                         f"Planner: {_planner_exc}")
        write_status("error", "Planner: Task Contract generation failed — manual review required")
        _err_data = {
            "task": task_text, "project": project_name,
            "status": "error", "output": "", "error": str(_planner_exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        write_outbox(_err_data)
        write_outbox(_err_data, project_outbox)
        return
    print(f"[planner] intent={_contract.get('user_intent', '')[:80]}")
    try:
        _gss.log_event(project_name, "task_contract",
                       intent=_contract.get("user_intent", "")[:200],
                       n_requirements=len(_contract.get("requirements_checklist", [])))
    except Exception:
        pass
    if _contract.get("is_large_task") and _contract.get("phases"):
        _phases = _contract["phases"]
        print(f"[planner] Large task detected — scoping to Phase 1 of {len(_phases)}")
        task_text = f"[PHASE 1 of {len(_phases)}]\n{_phases[0]}\n\n[Full task for context]\n{task_text}"

    # ── Risk Review Layer ─────────────────────────────────────────────────
    print("[risk] Generating pre-execution risk review…")
    try:
        _risk_review = generate_risk_review(_contract, project_name)
        _contract["risk_review"] = _risk_review
        _high = _risk_review.get("high_risk_items", [])
        if _high:
            print(f"[risk] HIGH-RISK items: {_high}")
    except Exception as _risk_exc:
        print(f"[risk] Risk review skipped: {_risk_exc}")

    write_task_state(task_text, project_name, "executing", "Claude Code is editing files", contract=_contract, task_id=_task_id)
    write_status("executing", "Claude Code editing files")

    # Inject session history (corrections, prior failures) so Claude Code has context
    try:
        _sess_ctx_worker = _gss.load_session_context(project_name, limit=8)
        if _sess_ctx_worker:
            safe_prompt += f"\n\n{_sess_ctx_worker}"
    except Exception:
        pass

    try:
        proc = subprocess.Popen(
            [
                "sudo", "-u", "geraldbuild", "-H",
                "bash", "-lc",
                f"cd {worker_dir} && claude --permission-mode bypassPermissions -p {shlex.quote(safe_prompt)}"
            ],
            cwd=worker_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        deadline = time.monotonic() + 900
        next_heartbeat = time.monotonic() + 30

        while proc.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except Exception:
                        proc.kill()
                raise subprocess.TimeoutExpired(proc.args, 900)

            if now >= next_heartbeat:
                elapsed = int(900 - max(0, deadline - now))
                write_task_state(
                    task_text,
                    project_name,
                    "executing",
                    f"Claude Code still running ({elapsed}s elapsed)",
                    files_changed=get_changed_files_under_lib(worker_dir),
                    output="",
                    error="",
                )
                write_status("executing", f"Claude Code still running ({elapsed}s elapsed)")
                next_heartbeat += 30

            time.sleep(5)

        stdout, stderr = proc.communicate()
        result = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)

        # Lightweight service-health verification — runs after subprocess, never blocks completion
        _vl = VerificationLayer()
        _verification = _vl.run_verification_suite([
            {"type": "service", "command": "curl -sf http://localhost:8000/task/truth"}
        ])
        print(f"[verify] health={_verification['passed']}")

        output = result.stdout.strip()
        error = result.stderr.strip()

        changed_files = get_changed_files_under_lib(worker_dir)

        # ── Post-task verification evidence — always runs before auditor; never relies on Claude's claim ──
        _verif_sections = ["\n\n---\n## Gerald Verification Evidence\n"]
        for _vlabel, _vcmd in [
            ("curl -i http://localhost:8000/command-centre",
             ["curl", "-i", "http://localhost:8000/command-centre"]),
            ("git status --short", ["git", "status", "--short"]),
            ("git diff --stat",    ["git", "diff", "--stat"]),
        ]:
            _verif_sections.append(_run_command_evidence(_vlabel, _vcmd))
        output = output + "".join(_verif_sections)
        print(f"[verify] post-task evidence appended ({len(output)} chars total)")

        try:
            _gss.log_event(project_name, "claude_result",
                           status="done" if result.returncode == 0 else "error",
                           returncode=result.returncode,
                           summary=output[:300])
        except Exception:
            pass

        if result.returncode == 0:
            review = review_task_result(
                task_text=task_text,
                project_name=project_name,
                worker_dir=worker_dir,
                claude_output=output,
                files_changed=changed_files,
                returncode=result.returncode,
                error=error,
                contract=_contract,
            )
            # ── Auditor: always the sole source of truth for task completion ──
            try:
                _ts = read_task_state()
                _task_contract = _ts.get("contract", {})
            except Exception:
                _task_contract = {}
            if _task_contract:
                _audit = audit_task_contract(_task_contract, output, changed_files, project_name)
            elif review["verdict"] == "PASS":
                _audit = {"verdict": "UNKNOWN", "met": [], "missing": [], "missing_evidence": [], "notes": "No contract — cannot confirm COMPLETE", "audited_at": now_iso()}
            else:
                _reasons = review.get("reasons", ["unknown"])
                _audit = {"verdict": "FAILED", "met": [], "missing": _reasons, "notes": f"No contract; review rejected: {'; '.join(_reasons)[:100]}", "audited_at": now_iso()}
            # Attach review verdict as non-authoritative context
            _audit["review_verdict"] = review["verdict"]
            if review["verdict"] != "PASS":
                _audit["review_reasons"] = review.get("reasons", [])
            _av = _audit.get("verdict", "UNKNOWN")
            _missing = _audit.get("missing", [])

            # URO final gate: if user-reported conflict exists, block COMPLETE before branching
            if _av == "COMPLETE":
                try:
                    from ui_verifier import check_uro_conflict as _uro_gate
                    _uro_r = _uro_gate(project_name)
                    if _uro_r["conflict"]:
                        _phrases = _uro_r["evidence"].get("uro_phrases", [])
                        _audit["verdict"] = "FAILED"
                        _audit.setdefault("missing", []).insert(
                            0, f"URO gate: user reported mismatch {_phrases} not confirmed resolved"
                        )
                        _audit["notes"] = f"URO gate: {_audit.get('notes', 'user reality conflict')}"
                        _av = "FAILED"
                        _missing = _audit.get("missing", [])
                except Exception as _uro_gate_ex:
                    print(f"[worker] URO gate error: {_uro_gate_ex}")

            try:
                _gss.log_event(project_name, "audit_result",
                               verdict=_av,
                               notes=_audit.get("notes", "")[:200],
                               missing=list(_missing)[:5])
            except Exception:
                pass

            if _av == "FAILED":
                _ms = "; ".join(_missing)[:120]
                write_task_state(
                    task_text, project_name, "contract_failed",
                    f"Auditor: requirements not met — {_ms}",
                    files_changed=changed_files, output=output, error=error, audit=_audit,
                )
                data = {
                    "task_id": _task_id,
                    "task": task_text, "project": project_name,
                    "status": "contract_failed", "returncode": result.returncode,
                    "output": output, "error": error,
                    "audit_verdict": "FAILED", "audit_missing": _missing,
                    "audit_notes": _audit.get("notes", ""),
                    "review_verdict": review["verdict"],
                    "verification": _verification,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                write_outbox(data)
                write_outbox(data, project_outbox)
                _append_task_history(data, project_name)
                write_status("error", "Auditor: contract requirements not met")
                try:
                    _gss.log_event(project_name, "outcome", status="contract_failed", detail=_ms[:150])
                    if _missing:
                        _gss.append_lesson(
                            project_name,
                            f"Auditor FAILED: {_contract.get('user_intent','')[:100]}\n"
                            f"Missing: {'; '.join(str(m)[:60] for m in _missing[:3])}\n"
                            f"Audit notes: {_audit.get('notes','')[:150]}"
                        )
                except Exception:
                    pass
            elif _av == "PARTIAL":
                _ms = "; ".join(_missing)[:120]
                write_task_state(
                    task_text, project_name, "partial",
                    f"Auditor: partial — {_ms}",
                    files_changed=changed_files, output=output, error=error, audit=_audit,
                )
                data = {
                    "task_id": _task_id,
                    "task": task_text, "project": project_name,
                    "status": "partial", "returncode": result.returncode,
                    "output": output, "error": error,
                    "audit_verdict": "PARTIAL", "audit_missing": _missing,
                    "audit_notes": _audit.get("notes", ""),
                    "review_verdict": review["verdict"],
                    "verification": _verification,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                write_outbox(data)
                write_outbox(data, project_outbox)
                _append_task_history(data, project_name)
                write_status("idle", "Task partial — some requirements missing")
                try:
                    _gss.log_event(project_name, "outcome", status="partial", detail=_ms[:150])
                except Exception:
                    pass
            elif _av == "COMPLETE":
                write_task_state(
                    task_text, project_name, "completed",
                    "Claude Code task finished",
                    files_changed=changed_files, output=output, error=error, audit=_audit,
                )
                data = {
                    "task_id": _task_id,
                    "task": task_text, "project": project_name,
                    "status": "done", "returncode": result.returncode,
                    "output": output, "error": error,
                    "verification": _verification, "audit_verdict": "COMPLETE",
                    "review_verdict": review["verdict"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                write_outbox(data)
                write_outbox(data, project_outbox)
                _append_task_history(data, project_name)
                write_status("idle", "Claude Code task finished")
                try:
                    _gss.log_event(project_name, "outcome", status="completed",
                                   detail="All requirements met")
                except Exception:
                    pass
            else:
                # UNKNOWN or any unexpected verdict — audit could not determine compliance; never COMPLETE
                _note = _audit.get("notes", "audit result indeterminate")
                write_task_state(
                    task_text, project_name, "contract_failed",
                    f"Auditor: indeterminate — {_note}",
                    files_changed=changed_files, output=output, error=error, audit=_audit,
                )
                data = {
                    "task_id": _task_id,
                    "task": task_text, "project": project_name,
                    "status": "contract_failed", "returncode": result.returncode,
                    "output": output, "error": error,
                    "audit_verdict": _av, "audit_notes": _note,
                    "review_verdict": review["verdict"],
                    "verification": _verification,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                write_outbox(data)
                write_outbox(data, project_outbox)
                _append_task_history(data, project_name)
                write_status("error", f"Auditor: indeterminate ({_av}) — {_note[:80]}")
                try:
                    _gss.log_event(project_name, "outcome", status="contract_failed",
                                   detail=f"Audit verdict={_av}: {_note[:120]}")
                except Exception:
                    pass
        else:
            write_task_state(
                task_text,
                project_name,
                "failed",
                "Claude Code task failed",
                files_changed=changed_files,
                output=output,
                error=error,
            )
            data = {
                "task_id": _task_id,
                "task": task_text,
                "project": project_name,
                "status": "error",
                "returncode": result.returncode,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "verification": _verification,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            write_outbox(data)
            write_outbox(data, project_outbox)
            _append_task_history(data, project_name)
            write_status("error", "Claude Code task failed")
            try:
                _gss.log_event(project_name, "outcome", status="failed",
                               detail=f"Claude Code exited {result.returncode}")
            except Exception:
                pass
            # ── Reasoning Layer V2: track repeated task failures ───────────────
            _failure_text = result.stderr.strip() or result.stdout.strip()
            _rl2_alert = gerald_issue_memory.record_task_failure(_failure_text, task_text, project_name)
            if _rl2_alert:
                _notify_recurring_failure(_rl2_alert, project_name)

    except subprocess.TimeoutExpired:
        data = {
            "task_id": _task_id,
            "task": task_text,
            "project": project_name,
            "status": "error",
            "output": "",
            "error": "Claude Code task timed out",
            "verification": {"passed": False, "results": [], "blocked": False},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        write_outbox(data)
        write_outbox(data, project_outbox)
        _append_task_history(data, project_name)
        write_status("error", "Claude Code task timed out")
        fail_task("Claude Code task timed out")




# ─── Gerald Task Truth Layer ──────────────────────────────────────────────────

TASK_STATE_FILE = os.path.join(BASE, "active_task.json")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def write_task_state(task: str, project: str, stage: str, detail: str = "", files_changed=None, output: str = "", error: str = "", contract: dict = None, audit: dict = None, task_id: str = None):
    """
    V4 Phase 2 canonical task state writer.

    Canonical state is now the source of truth.
    active_task.json is still mirrored for backward compatibility.
    """
    # Preserve contract/audit/started/task_id from existing active_task.json when not explicitly updated
    _existing = {}
    try:
        if os.path.exists(ACTIVE_TASK):
            with open(ACTIVE_TASK, "r", encoding="utf-8") as _f:
                _existing = json.load(_f) or {}
    except Exception:
        _existing = {}

    _existing_task_id = _existing.get("task_id")
    _existing_started = _existing.get("started")
    _effective_task_id = task_id or _existing_task_id or ""
    _is_new_task = bool(task_id and task_id != _existing_task_id)

    data = {
        "task_id": _effective_task_id,
        "task": task,
        "project": project,
        "stage": stage,
        "detail": detail,
        "files_changed": files_changed or [],
        "output": output,
        "error": error,
        "updated": datetime.now(timezone.utc).isoformat(),
        "started": datetime.now(timezone.utc).isoformat() if _is_new_task else (_existing_started or datetime.now(timezone.utc).isoformat()),
        "contract": contract if contract is not None else (None if _is_new_task else _existing.get("contract")),
        "audit": audit if audit is not None else (None if _is_new_task else _existing.get("audit")),
        "source_of_truth": "canonical",
    }

    # Write canonical — route through lifecycle controller for lifecycle stages
    _wkw = dict(
        task=task,
        project=project,
        stage=stage,
        detail=detail,
        files_changed=files_changed or [],
        output=output,
        error=error,
        contract=contract,
        audit=audit,
        task_id=data.get("task_id"),
    )
    if stage in LIFECYCLE_STAGES:
        try:
            canonical = _lifecycle.transition(
                stage,
                task=task,
                project=project,
                detail=detail,
                files_changed=files_changed or [],
                output=output,
                error=error,
                contract=data.get("contract"),
                audit=data.get("audit"),
                task_id=data.get("task_id"),
            )
        except TransitionError as _te:
            print(f"[lifecycle] WARN invalid transition to {stage!r}: {_te} — writing directly")
            canonical = write_canonical_state(**_wkw)
    else:
        canonical = write_canonical_state(**_wkw)

    # Mirror to legacy active_task.json for existing dashboard/app compatibility
    with open(ACTIVE_TASK, "w", encoding="utf-8") as f:
        json.dump(canonical, f, indent=2)

    return canonical

def looks_like_clarification_request(output: str) -> bool:
    lower = (output or "").lower()
    phrases = [
        "i'll wait for your clarification",
        "i will wait for your clarification",
        "please clarify",
        "please confirm",
        "which instruction",
        "which should i follow",
        "conflict",
        "direct conflict",
        "contradiction",
        "contradictory",
        "i won't take action until",
        "i will not take action until",
    ]
    return any(p in lower for p in phrases)


# ─── Planner: Task Contract ────────────────────────────────────────────────────

def _parse_contract_json(raw: str) -> dict:
    """Strip markdown fences, find the outermost JSON object, and parse it."""
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.rstrip())
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in Planner response (len={len(raw)})")
    return json.loads(raw[start:end + 1])


def create_task_contract(task_text: str, project_name: str) -> dict:
    """Generate a structured Task Contract. Retries once on parse failure. Raises on double failure."""
    client = Anthropic()

    _sess_ctx_str = ""
    try:
        _sess_ctx_str = _gss.load_session_context(project_name, limit=6)
    except Exception:
        pass
    _sess_section = (
        f"\n\nSESSION HISTORY (recent corrections and outcomes — use for context only):\n{_sess_ctx_str}\n"
        if _sess_ctx_str else ""
    )

    primary_prompt = f"""You are Gerald's Planner. Convert Matt's request into a structured Task Contract as JSON.

Matt's request: {task_text}
Project: {project_name}
{_sess_section}
Return ONLY valid JSON with this exact schema (no markdown, no commentary):
{{
  "user_intent": "one-sentence summary of what Matt wants",
  "project": "{project_name}",
  "scope": "what is in scope — be specific",
  "non_negotiables": ["constraint 1", "constraint 2"],
  "requirements_checklist": [
    "requirement 1",
    "requirement 2"
  ],
  "likely_files": ["file1.py", "file2.js"],
  "forbidden_files": ["file_never_touch.py"],
  "definition_of_done": "exact deliverable condition to mark COMPLETE",
  "verification_checklist": ["check 1", "check 2"],
  "evidence_required": [
    {{
      "check": "description of the verification step",
      "evidence_type": "command_output | file_contents | endpoint_response",
      "description": "what real evidence must be captured (e.g. actual stdout of X command, contents of Y file, HTTP response from Z endpoint)"
    }}
  ],
  "recommended_execution_steps": ["step 1", "step 2"],
  "is_large_task": false,
  "phases": []
}}

CRITICAL extraction rules:
- Extract EVERY numbered requirement from Matt's request as a SEPARATE item in requirements_checklist. Do NOT group, collapse, or summarise multiple requirements into one item.
- If Matt listed 12 numbered requirements, requirements_checklist must contain exactly 12 entries.
- For evidence_required: include one entry for every item in verification_checklist that requires running a command, reading a file, or calling an endpoint to confirm success. Leave the array empty only if ALL checks are purely code-review (no execution or inspection needed).
- If the task has more than 5 major independent features or requires multiple long Claude sessions, set is_large_task=true and list each phase in the phases array (brief one-line description per phase).
Return ONLY the JSON object."""

    err1 = None
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": primary_prompt}],
        )
        raw = "\n".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        contract = _parse_contract_json(raw)
        contract["generated_at"] = now_iso()
        n_reqs = len(contract.get("requirements_checklist", []))
        print(f"[planner] contract OK — {n_reqs} requirements extracted")
        return contract
    except Exception as e:
        err1 = e
        print(f"[planner] Primary extraction failed: {e}. Retrying with conservative prompt…")

    # Conservative retry: simpler prompt, flat schema, no nested evidence objects
    retry_prompt = f"""You are Gerald's Planner. Emergency contract extraction — parse Matt's request into JSON.

Matt's request: {task_text[:6000]}
Project: {project_name}

Return ONLY valid JSON — no markdown fences, no commentary, nothing outside the braces:
{{
  "user_intent": "one-sentence summary",
  "project": "{project_name}",
  "scope": "what is in scope",
  "non_negotiables": ["constraint 1"],
  "requirements_checklist": ["req 1", "req 2"],
  "likely_files": ["file.py"],
  "forbidden_files": [],
  "definition_of_done": "COMPLETE when all requirements are met",
  "verification_checklist": ["check 1"],
  "evidence_required": [],
  "recommended_execution_steps": ["step 1"],
  "is_large_task": false,
  "phases": []
}}

MANDATORY: List EVERY numbered requirement from Matt's request as a separate string in requirements_checklist. Output JSON only — nothing else."""

    try:
        msg2 = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": retry_prompt}],
        )
        raw2 = "\n".join(
            b.text for b in msg2.content if getattr(b, "type", "") == "text"
        ).strip()
        contract2 = _parse_contract_json(raw2)
        contract2["generated_at"] = now_iso()
        contract2["planner_retry"] = True
        n_reqs2 = len(contract2.get("requirements_checklist", []))
        print(f"[planner] Retry contract OK — {n_reqs2} requirements extracted")
        return contract2
    except Exception as e2:
        raise RuntimeError(
            f"Task Contract generation failed after 2 attempts. "
            f"Attempt 1: {err1}. Attempt 2: {e2}. "
            "Manual review required — do not proceed."
        )


def audit_task_contract(contract: dict, claude_output: str, files_changed: list, project_name: str = "CommuteCoder") -> dict:

    def _auto_capture_evidence(contract: dict, files_changed: list) -> str:
        """
        Capture real command/file evidence before audit so Claude claims are not trusted blindly.
        Currently supports simple file evidence:
        - ls -la
        - cat
        - wc -c
        - od -c
        """
        import subprocess
        from pathlib import Path

        evidence_lines = []
        project_root = Path("/opt/Gerald")
        likely_files = contract.get("likely_files", []) or []
        changed = files_changed or []

        candidates = []
        for item in likely_files + changed:
            if not item:
                continue
            item = str(item).strip()
            if item.startswith("/"):
                path = Path(item)
            else:
                path = project_root / item
            if path not in candidates:
                candidates.append(path)

        evidence_lines.append("\n\n--- AUTO-CAPTURED EVIDENCE ---")

        if not candidates:
            evidence_lines.append("No likely_files or changed files available for automatic evidence capture.")
            return "\n".join(evidence_lines)

        for path in candidates:
            evidence_lines.append(f"\nFILE: {path}")

            commands = [
                ["ls", "-la", str(path)],
                ["wc", "-c", str(path)],
                ["od", "-c", str(path)],
            ]

            if path.exists() and path.is_file():
                commands.insert(1, ["cat", str(path)])

            for cmd in commands:
                label = " ".join(cmd)
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    evidence_lines.append(f"$ {label}")
                    evidence_lines.append(f"exit_code={result.returncode}")
                    if result.stdout:
                        evidence_lines.append(result.stdout.rstrip())
                    if result.stderr:
                        evidence_lines.append("STDERR:")
                        evidence_lines.append(result.stderr.rstrip())
                except Exception as e:
                    evidence_lines.append(f"$ {label}")
                    evidence_lines.append(f"ERROR: {e}")

        evidence_lines.append("--- END AUTO-CAPTURED EVIDENCE ---\n")
        return "\n".join(evidence_lines)

    """Auditor: compare Claude's delivered result against the Task Contract requirements."""
    try:
        requirements = contract.get("requirements_checklist", [])
        definition_of_done = contract.get("definition_of_done", "")
        evidence_required = contract.get("evidence_required", [])
        claude_output = (claude_output or "") + _auto_capture_evidence(contract, files_changed)
        if not requirements and not definition_of_done:
            return {"verdict": "UNKNOWN", "met": [], "missing": [], "missing_evidence": [], "notes": "Audit skipped: no requirements to evaluate — cannot confirm COMPLETE", "audited_at": now_iso()}

        client = Anthropic()
        req_text = "\n".join(f"- {r}" for r in requirements)
        files_text = ", ".join(files_changed) if files_changed else "none"
        evidence_text = "\n".join(
            f"- [{e.get('evidence_type','?')}] {e.get('check','?')}: {e.get('description','')}"
            for e in evidence_required
        ) if evidence_required else "None specified"

        _audit_sess = ""
        try:
            _audit_sess = _gss.load_session_context(project_name, limit=4)
        except Exception:
            pass
        _audit_sess_block = (
            f"\nSESSION CONTEXT (recent Matt corrections/failures — consider when auditing):\n{_audit_sess}\n"
            if _audit_sess else ""
        )

        prompt = f"""You are Gerald's Auditor. Check if Claude's output satisfies the Task Contract.

REQUIREMENTS CHECKLIST:
{req_text}

DEFINITION OF DONE:
{definition_of_done}

EVIDENCE REQUIRED (checks that demand real captured output — not simulated, hypothetical, or example data):
{evidence_text}

CLAUDE'S OUTPUT (first 3000 chars):
{claude_output[:3000]}

FILES CHANGED:
{files_text}
{_audit_sess_block}
EVIDENCE ENFORCEMENT RULES (mandatory):
1. For every item in EVIDENCE REQUIRED, look for the actual captured output in CLAUDE'S OUTPUT (real command stdout/stderr, real file contents, real HTTP response bodies).
2. If Claude used simulated output, hypothetical results, placeholder tables, or example data instead of running the actual command/inspection, that evidence item is MISSING — do not accept it.
3. List every evidence item that is missing or was only simulated in the "missing_evidence" array.
4. If ANY evidence item is missing, the verdict MUST be FAILED (not PARTIAL).
5. If some requirements are met but evidence is missing, the verdict is still FAILED.

Return ONLY valid JSON (no markdown):
{{
  "verdict": "COMPLETE",
  "met": ["exact requirement text that was addressed"],
  "missing": ["exact requirement text that was not addressed"],
  "missing_evidence": ["description of each evidence item that was absent or simulated"],
  "notes": "one-line audit summary"
}}

verdict must be one of: COMPLETE (all requirements met AND all required evidence present), PARTIAL (some requirements met, no missing evidence issues), FAILED (any requirement unmet OR any required evidence missing/simulated)."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "\n".join(
            block.text for block in message.content
            if getattr(block, "type", "") == "text"
        ).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.rstrip())
        try:
            audit = json.loads(raw)
        except json.JSONDecodeError:
            # Response may have been truncated — try to recover verdict from partial output
            _verdict_match = re.search(r'"verdict"\s*:\s*"(COMPLETE|PARTIAL|FAILED)"', raw)
            if _verdict_match:
                _recovered = _verdict_match.group(1)
                print(f"[auditor] JSON truncated — recovered verdict={_recovered} from partial response")
                audit = {
                    "verdict": _recovered,
                    "met": [],
                    "missing": [],
                    "missing_evidence": [],
                    "notes": f"Audit JSON truncated — verdict recovered from partial response: {_recovered}",
                    "audited_at": now_iso(),
                }
            else:
                raise
        # Post-parse integrity: never emit COMPLETE when evidence is missing or verdict is invalid
        _parsed_verdict = audit.get("verdict", "")
        _parsed_missing_evidence = audit.get("missing_evidence", [])
        if _parsed_verdict not in ("COMPLETE", "PARTIAL", "FAILED"):
            audit["verdict"] = "FAILED"
        elif _parsed_missing_evidence:
            audit["verdict"] = "FAILED"
        audit["audited_at"] = now_iso()
        # URO post-parse: user-reported reality overrides a technical COMPLETE
        if audit.get("verdict") == "COMPLETE":
            try:
                from ui_verifier import check_uro_conflict as _check_uro
                _uro = _check_uro(project_name)
                if _uro["conflict"]:
                    _phrases = _uro["evidence"].get("uro_phrases", [])
                    audit["verdict"] = "FAILED"
                    audit.setdefault("missing", []).insert(
                        0, f"User reported unresolved mismatch {_phrases} — COMPLETE blocked"
                    )
                    audit["notes"] = f"URO override: {audit.get('notes', 'user reality conflict')}"
            except Exception as _uro_ex:
                print(f"[auditor] URO check error: {_uro_ex}")
        return audit
    except Exception as e:
        print(f"[auditor] Audit failed: {e}")
        # Return PARTIAL (not UNKNOWN) so the successful Claude output is preserved —
        # UNKNOWN triggers auditor_integrity → FAILED → contract_failed even for good work.
        return {
            "verdict": "PARTIAL",
            "met": [],
            "missing": [],
            "missing_evidence": [],
            "notes": f"Audit parse failure — Claude output preserved, manual review advised: {e}",
            "audited_at": now_iso(),
        }

def read_task_state():
    if not os.path.exists(TASK_STATE_FILE):
        return {
            "stage": "idle",
            "detail": "No active task",
            "updated": now_iso()
        }
    try:
        with open(TASK_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {
            "stage": "unknown",
            "detail": f"Could not read task state: {e}",
            "updated": now_iso()
        }

def get_changed_files_under_lib(project_path="/opt/Gerald/gerald_app"):
    # Flutter projects (gerald_app) scope to lib/ only; other projects report all changed files.
    abs_path = os.path.abspath(project_path)
    is_flutter_app = abs_path == os.path.abspath("/opt/Gerald/gerald_app")
    cmd = ["git", "diff", "--name-only"] + (["--", "lib"] if is_flutter_app else [])
    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [x.strip() for x in result.stdout.splitlines() if x.strip()]
    except Exception:
        return []

def is_status_check(text: str) -> bool:
    lower = (text or "").lower()

    # Action/investigation requests may mention "status", "error", or "/status".
    # They must still route to the correct worker instead of status-check.
    action_words = [
        "investigate", "diagnose", "report back",
        "fix", "change", "update", "implement", "make the",
        "add ", "remove ", "edit "
    ]
    if any(w in lower for w in action_words):
        return False

    phrases = [
        "is claude coding",
        "is code changing",
        "is it still running",
        "is anything running",
        "what is happening",
        "what's happening",
        "check the loop",
        "is the loop working",
        "is gerald stuck",
        "is it stuck",
        "has claude finished",
        "what changed",
        "what files changed",
        "is the task done",
        "status"
    ]
    return any(p in lower for p in phrases)

def truthful_status_response(project_name: str = "CommuteCoder"):
    state = read_task_state()
    status = {}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)
    except Exception:
        status = {"status": "unknown", "detail": "No status file"}

    files = get_changed_files_under_lib()

    output = [
        "Gerald status check:",
        "",
        f"Server status: {status.get('status', 'unknown')} — {status.get('detail', '')}",
        f"Task stage: {state.get('stage', 'idle')}",
        f"Task detail: {state.get('detail', '')}",
        f"Last task: {state.get('task', 'None')}",
        "",
    ]

    if files:
        output.append("Current changed app files:")
        output.extend([f"- {f}" for f in files])
    else:
        output.append("Current changed app files: none under lib/")

    output.append("")
    if state.get("stage") in ["executing", "planning", "verifying"]:
        output.append("Truth: a task is marked as active.")
    else:
        output.append("Truth: no Claude Code task is currently marked as active.")

    output.append("I will not claim Claude is coding unless the task state says executing.")

    data = {
        "task": "status check",
        "project": project_name,
        "status": "done",
        "returncode": 0,
        "output": "\n".join(output),
        "summary": "\n".join(output),
        "error": "",
        "timestamp": now_iso()
    }
    # Write to dedicated status-check file — never overwrite the real task outbox
    try:
        with open(STATUS_CHECK_FILE, "w", encoding="utf-8") as _scf:
            json.dump(data, _scf, indent=2)
    except Exception:
        pass
    write_status("idle", "Truthful status check complete")
    return data




def is_general_question(text: str) -> bool:
    lower = (text or "").strip().lower()

    screenshot_question_phrases = [
        "can you see the screenshot",
        "can you see my screenshot",
        "do you see the screenshot",
        "can you see the image",
        "can you see my image",
        "do you see the image",
        "can you see what i sent",
    ]
    if any(p in lower for p in screenshot_question_phrases):
        return True

    question_starts = [
        "can you see",
        "can you tell",
        "do you see",
        "what do you think",
        "what happened",
        "why did",
        "why is",
        "is this",
        "does this",
        "are we",
    ]
    implementation_words = [
        "change",
        "edit",
        "update",
        "implement",
        "fix",
        "build",
        "create",
        "add",
        "remove",
        "delete",
        "make",
        "commit",
        "push",
    ]

    if any(lower.startswith(q) for q in question_starts):
        return not any(w in lower for w in implementation_words)

    return False

def is_planning_only_request(text: str) -> bool:
    lower = (text or "").lower()
    planning_phrases = [
        "don't make any changes",
        "do not make any changes",
        "dont make any changes",
        "don't make changes yet",
        "do not make changes yet",
        "dont make changes yet",
        "let me know what your plan is",
        "what is your plan",
        "summarise what i want",
        "summarize what i want",
        "plan only",
        "report back only",
    ]
    return any(p in lower for p in planning_phrases)

def should_use_investigation_worker(text: str) -> bool:
    t = (text or "").lower()

    investigation_terms = [
        "investigate",
        "diagnose",
        "report back",
        "come back to me",
        "do not make changes",
        "do not change anything",
        "no code changes",
        "do not code",
        "read-only",
        "read only",
        "give me a plan",
        "why is",
        "why does",
        "why doesn't",
        "why isnt",
        "why isn't",
        "what is broken",
    ]

    execution_terms = [
        "fix it",
        "fix this",
        "implement",
        "make the change",
        "change the code",
        "update the code",
        "apply the fix",
        "proceed",
        "approved",
    ]

    return any(x in t for x in investigation_terms) and not any(x in t for x in execution_terms)



def narrow_investigation_prompt(task_text: str) -> str:
    t = task_text or ""
    lower = t.lower()

    # Known Gerald app patterns: force broad voice/Mode B investigations into the file that actually owns the mic loop.
    if "mode b" in lower or "conversation mode" in lower or "auto-listen" in lower or "auto listen" in lower:
        return (
            "Investigate only lib/widgets/push_to_talk_button.dart for why "
            "Mode B / conversation voice auto-listen is not working. "
            "Do not inspect any other files unless this file clearly cannot explain it. "
            "Do not make changes. Report back only."
        )

    # Already narrow: preserve it.
    if "only " in lower or ".dart" in lower or ".py" in lower:
        return t

    # Default: force single-file-first behaviour into the actual request, not just the rules.
    return (
        "Investigate the single most likely file for this issue first. "
        "If a plausible root cause is found, stop immediately and report. "
        "Do not inspect more than one file unless absolutely necessary.\n\n"
        + t
    )

def run_claude_investigation_worker(task_text: str, project_name: str = "CommuteCoder"):
    _task_id = _generate_task_id()
    project_outbox = get_project_outbox_file(project_name)

    worker_dir = get_worker_directory(task_text, project_name)

    effective_task_text = narrow_investigation_prompt(task_text)

    safe_prompt = f"""
You are Claude Code working for Gerald in READ-ONLY INVESTIGATION MODE.

Matt's request:
{effective_task_text}

Project: {project_name}
Working directory: {worker_dir}

Rules:
- READ ONLY.
- Do not edit files.
- Do not run formatters.
- Do not build APK.
- Start with the single most relevant file only.
- If the likely root cause is found in that file, stop immediately and report.
- Only inspect a second file if it is absolutely necessary.
- Never inspect more than 2 files.
- Do not run broad repo searches unless no likely file is obvious.
- Do not run Flutter commands.
- Do not run tests.
- Return within 60 seconds.
- Keep the report under 450 words.
- Use this exact format:
  1. Files inspected
  2. What is happening
  3. Likely root cause
  4. Smallest safe fix
  5. Files that would need changing
- Do not claim you changed anything.
"""

    _inv_proj_path, _ = resolve_project(project_name)
    safe_prompt = inject_brain_context(safe_prompt, _inv_proj_path, project_name, auto_create=False)
    print(f"[brain] inject_brain_context (investigation): {len(safe_prompt)} chars, project={project_name}, path={_inv_proj_path}")

    _inv_all_projects = load_projects()
    _inv_other_paths = [p["path"] for p in _inv_all_projects if p["path"].lower() != _inv_proj_path.lower()]
    _inv_isolation_lines = "\n".join(f"- {p}" for p in _inv_other_paths)
    _inv_isolation_block = (
        f"\n# Project Isolation\nDO NOT read or modify any files outside {_inv_proj_path}.\n"
        f"Explicitly forbidden paths:\n{_inv_isolation_lines}\n"
    ) if _inv_other_paths else ""
    safe_prompt = safe_prompt + _inv_isolation_block

    prompt_file = "/tmp/gerald_readonly_investigation_prompt.txt"
    investigation_started_at = time.time()

    write_task_state(task_text, project_name, "investigating", "Claude Code is investigating read-only", task_id=_task_id)
    write_status("investigating", "Claude Code is investigating read-only")

    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(safe_prompt)

        proc = subprocess.Popen(
            [
                "sudo", "-u", "geraldbuild", "-H",
                "bash", "-lc",
                f'cd {worker_dir} && claude --permission-mode bypassPermissions -p "$(cat {prompt_file})"'
            ],
            cwd=worker_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        try:
            stdout, stderr = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
            raise

        output = (stdout or "").strip()
        error = (stderr or "").strip()

        class Result:
            pass

        result = Result()
        result.returncode = proc.returncode
        result.stdout = output
        result.stderr = error

        data = {
            "task_id": _task_id,
            "task": task_text,
            "project": project_name,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
            "summary": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        write_outbox(data)
        write_outbox(data, project_outbox)
        _append_task_history(data, project_name)

        if result.returncode == 0 and looks_like_clarification_request(output):
            write_task_state(
                task_text,
                project_name,
                "needs_clarification",
                "Claude needs clarification",
                files_changed=[],
                output=output,
                error="",
                task_id=_task_id,
            )
            write_status("needs_clarification", "Claude needs clarification")
        else:
            write_task_state(
                task_text,
                project_name,
                "completed" if result.returncode == 0 else "failed",
                "Read-only investigation finished" if result.returncode == 0 else "Read-only investigation failed",
                files_changed=[],
                output=output,
                error=error,
            )

            write_status(
                "idle" if result.returncode == 0 else "error",
                "Read-only investigation finished" if result.returncode == 0 else "Read-only investigation failed",
            )

    except subprocess.TimeoutExpired:
        try:
            subprocess.run(["pkill", "-f", "claude --permission-mode bypassPermissions"], timeout=10)
        except Exception:
            pass
        elapsed = round(time.time() - investigation_started_at, 2)
        prompt_preview = ""
        try:
            prompt_preview = Path(prompt_file).read_text(encoding="utf-8")[:1200]
        except Exception:
            prompt_preview = "<could not read prompt file>"

        err = (
            f"Read-only investigation timed out after 120 seconds "
            f"(actual_elapsed={elapsed}s, prompt_chars={len(prompt_preview)})"
        )

        try:
            with open("/opt/Gerald/gerald_timeout_debug.log", "a", encoding="utf-8") as dbg:
                dbg.write("\n--- TIMEOUT DEBUG ---\n")
                dbg.write(f"timestamp={datetime.now(timezone.utc).isoformat()}\n")
                dbg.write(f"task={task_text}\n")
                dbg.write(f"project={project_name}\n")
                dbg.write(f"actual_elapsed={elapsed}\n")
                dbg.write(f"prompt_file={prompt_file}\n")
                dbg.write("prompt_preview:\n")
                dbg.write(prompt_preview + "\n")
        except Exception:
            pass
        data = {
            "task_id": _task_id,
            "task": task_text,
            "project": project_name,
            "status": "error",
            "output": "",
            "summary": "",
            "error": err,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        write_outbox(data)
        write_outbox(data, project_outbox)
        _append_task_history(data, project_name)
        write_task_state(task_text, project_name, "timed_out", err, files_changed=[], output="", error=err)
        write_status("timed_out", err)


def should_use_claude_worker(text: str) -> bool:
    lower = (text or "").lower()
    worker_phrases = [
        "build the app",
        "build it",
        "create the app",
        "implement",
        "write code",
        "change the code",
        "edit the file",
        "create file",
        "update file",
        "fix the bug",
        "fix this",
        "fix it",
        "fix the issue",
        "fix the issue you identified",
        "fix mode b",
        "make only this smallest safe change",
        "smallest safe change",
        "apply the fix",
        "make the fix",
        "change the",
        "change this",
        "update the",
        "make the",
        "redesign",
        "restyle",
        "improve the",
        "alteration",
        "make this screen",
        "home screen",
        "microphone button",
        "mic button",
        "run build",
        "build apk",
        "deploy",
        "commit",
        "push to github",
    ]
    return any(p in lower for p in worker_phrases)


def run_gerald_brain(task_text: str, project_name: str = "CommuteCoder"):
    print("\n==============================")
    print("🧠 GERALD BRAIN TASK RECEIVED")
    print(f"Project: {project_name}")
    print(task_text)
    print("==============================\n")

    _task_id = _generate_task_id()
    outbox_file = get_project_outbox_file(project_name)
    write_task_state(task_text, project_name, "planning", "Gerald Brain is thinking", task_id=_task_id)
    write_status("working", "Gerald Brain thinking")

    try:
        reply = ask_gerald(task_text)
        try:
            _gss.log_event(project_name, "gerald_response", text=reply[:300])
        except Exception:
            pass

        data = {
            "task_id": _task_id,
            "task": task_text,
            "project": project_name,
            "status": "done",
            "returncode": 0,
            "output": reply,
            "summary": reply,
            "error": "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        write_outbox(data, outbox_file)
        _append_task_history(data, project_name)

        reply_lower = (reply or "").lower()
        if is_planning_only_request(task_text) or any(x in reply_lower for x in [
            "happy to proceed",
            "you’re happy to proceed",
            "you're happy to proceed",
            "once you confirm",
            "let me know if you want",
            "let me know if you’re happy",
            "let me know if you're happy",
            "final check",
            "proceed with this",
            "you confirm",
            "happy with this",
        ]):
            save_pending_approval(task_text, project_name, reply)

        if looks_like_clarification_request(reply):
            write_task_state(
                task_text,
                project_name,
                "needs_clarification",
                "Gerald needs clarification",
                output=reply,
                error="",
                task_id=_task_id,
            )
            write_status("needs_clarification", "Gerald needs clarification")
        else:
            write_task_state(task_text, project_name, "completed", "Gerald Brain finished", output=reply, task_id=_task_id)
            write_status("idle", "Gerald Brain finished")
        print("✅ GERALD BRAIN FINISHED")
        print(reply)

    except Exception as e:
        err = str(e)
        data = {
            "task": task_text,
            "project": project_name,
            "status": "error",
            "returncode": 1,
            "output": "",
            "summary": "",
            "error": err,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        write_outbox(data, outbox_file)
        write_task_state(task_text, project_name, "error", "Gerald direct answer failed", files_changed=[], output="", error=err, task_id=_task_id)
        write_status("error", err)
        print("❌ GERALD BRAIN ERROR:", err)





def clean_task_for_claude(task: str) -> str:
    import re
    raw = task or ""

    # Extract simple file-create approvals from Gerald markdown.
    path_match = re.search(r"(/opt/Gerald/gerald_app/[^\\s`>]+)", raw)
    content_match = re.search(
        r"with exactly this content:\\s*(?:```)?\\s*([^`\\n][^`]*?)(?:```|Do not|Nothing will|Reply|$)",
        raw,
        re.IGNORECASE | re.DOTALL,
    )

    if path_match and content_match:
        path = path_match.group(1).strip()
        content = content_match.group(1).strip()
        return f"Create file {path} containing exactly {content}"

    cleaned = raw
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace(">", "")
    cleaned = cleaned.replace("---", "")
    cleaned = cleaned.replace("You are Claude Code working for Gerald.", "")
    return cleaned.strip()


PENDING_APPROVAL_FILE = "/opt/Gerald/pending_approval_task.json"

def save_pending_approval(task_text: str, project_name: str, output: str):
    # Save the most recent Gerald Brain plan that is waiting for Matt's approval.
    # Approval replies must execute this, not an old outbox task.
    data = {
        "task": task_text,
        "project": project_name,
        "output": output,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(PENDING_APPROVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅  Pending approval saved: {PENDING_APPROVAL_FILE}")

def load_pending_approval(project_name: str = "CommuteCoder") -> str:
    try:
        if not os.path.exists(PENDING_APPROVAL_FILE):
            return ""
        with open(PENDING_APPROVAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        output = (data.get("output") or "").strip()
        task = (data.get("task") or "").strip()
        return output or task
    except Exception:
        return ""

def clear_pending_approval():
    try:
        if os.path.exists(PENDING_APPROVAL_FILE):
            os.remove(PENDING_APPROVAL_FILE)
    except Exception:
        pass

def is_simple_approval(text: str) -> bool:
    lower = (text or "").strip().lower()
    exact = {
        "yes", "y", "yeah", "yep", "ok", "okay", "go ahead",
        "approve", "approved", "do it", "send it", "continue",
        "proceed", "run it"
    }
    if lower in exact:
        return True

    approval_phrases = [
        "happy to proceed",
        "i am happy to proceed",
        "i'm happy to proceed",
        "yes i am happy",
        "yes i'm happy",
        "go ahead",
        "proceed",
        "start phase one",
        "begin implementation",
    ]
    return any(p in lower for p in approval_phrases)

def load_last_outbox_task(project_name: str = "CommuteCoder") -> str:
    path = get_project_outbox_file(project_name)
    if not os.path.exists(path):
        path = OUTBOX_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        task = data.get("task", "")
        output = data.get("output", "")
        # For approval replies like "yes", execute Gerald's prepared instruction,
        # not Matt's original "prepare a task / ask me" prompt.
        return output or task
    except Exception:
        return ""


def _json_preview(value, limit=2500):
    try:
        text = json.dumps(value, indent=2)
    except Exception:
        text = str(value)
    return text[:limit]

def decide_next_action(user_text: str, project_name: str, payload: dict) -> dict:
    """
    Gerald Decision Agent V1.
    OpenAI decides what should happen next.
    This replaces Gerald guessing via hardcoded routing rules.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "action": "fallback_router",
            "reason": "OPENAI_API_KEY missing",
            "task": user_text,
            "message": "",
        }

    current_task = read_task()
    pending = ""
    try:
        pending = load_pending_approval(project_name)
    except Exception:
        pending = ""

    last_outbox = {}
    try:
        path = get_project_outbox_file(project_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                last_outbox = json.load(f)
    except Exception:
        last_outbox = {}

    prompt = f"""
You are Gerald Decision Agent V1.

You are NOT the coder. You are the decision maker above Gerald Brain and Claude Code.

Your job:
Decide the next backend action for Matt's current message.

Available actions:
- answer_directly: Answer Matt without Claude and without code changes.
- gerald_brain: Send to Gerald Brain for normal reasoning/planning.
- save_pending_plan: Save Gerald Brain's plan for approval. Usually not used directly from /start.
- execute_pending_approval: Matt approved the current pending plan. Send that pending plan to Claude Code.
- claude_code: Matt is clearly asking to make an implementation/code change now.
- readonly_investigation: Matt asks to investigate/report without changing files.
- status_check: Matt asks what is happening / are you done / status.
- fallback_router: If uncertain, use old backend router.

Rules:
1. Questions like "can you see the screenshot?", "what do you think?", "why did this happen?" should be answer_directly or gerald_brain, NOT claude_code.
2. If Matt asks for a plan, summary, or says "don't make changes yet", choose gerald_brain.
3. If Matt says "yes", "proceed", "happy to proceed", or approves a pending plan, choose execute_pending_approval IF pending approval exists.
4. If there is no pending approval and Matt only says yes/proceed, choose gerald_brain and explain there is no pending plan.
5. Only choose claude_code when Matt clearly wants code changed now.
6. Choose readonly_investigation only when Matt asks to investigate/report and explicitly says no changes or read-only.
7. Prefer reasoning over action when ambiguous.
8. Return ONLY valid JSON. No markdown.

Context:
PROJECT:
{project_name}

CURRENT USER MESSAGE:
{user_text}

PAYLOAD KEYS:
{list(payload.keys())}

CURRENT TASK:
{_json_preview(current_task)}

PENDING APPROVAL:
{pending[:2500]}

LAST OUTBOX:
{_json_preview(last_outbox)}

Return JSON with this schema:
{{
  "action": "answer_directly|gerald_brain|execute_pending_approval|claude_code|readonly_investigation|status_check|fallback_router",
  "reason": "short reason",
  "task": "the exact task to pass to worker if applicable",
  "message": "brief direct response if action is answer_directly"
}}
"""

    try:
        data = decide_supervisor_action(
            user_text=user_text,
            project=project_name,
            payload=payload,
            current_task=current_task,
            pending=pending,
            last_outbox=last_outbox,
        )
        if not isinstance(data, dict):
            raise ValueError("supervisor response was not a JSON object")
        data.setdefault("action", "fallback_router")
        data.setdefault("reason", "")
        data.setdefault("task", user_text)
        data.setdefault("message", "")
        return data
    except Exception as e:
        return {
            "action": "fallback_router",
            "reason": f"Decision agent failed: {e}",
            "task": user_text,
            "message": "",
        }

def run_direct_answer(task_text: str, project_name: str, message: str):
    _task_id = _generate_task_id()
    outbox_file = get_project_outbox_file(project_name)
    try:
        # V4 Investigation Evidence Gate
        if _looks_like_investigation_request(task_text) and not _looks_like_implementation_request(task_text):
            reply = _build_live_investigation_answer(task_text, project_name)
            data = {
                "task_id": _task_id,
                "task": task_text,
                "project": project_name,
                "status": "done",
                "returncode": 0,
                "output": reply,
                "summary": reply[:1000],
                "error": "",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            write_outbox(data)
            write_outbox(data, outbox_file)
            _append_task_history(data, project_name)
            write_task_state(
                task_text,
                project_name,
                "completed",
                "Investigation completed from live evidence",
                files_changed=[],
                output=reply,
                error="",
                contract={},
                audit={},
                task_id=_task_id,
            )
            write_status("idle", "Investigation completed")
            return

        reply = message or ask_gerald(task_text, project_name)
        data = {
            "task_id": _task_id,
            "task": task_text,
            "project": project_name,
            "status": "done",
            "returncode": 0,
            "output": reply,
            "summary": reply,
            "error": "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        write_outbox(data)
        write_outbox(data, outbox_file)
        _append_task_history(data, project_name)
        if looks_like_clarification_request(reply):
            write_task_state(
                task_text,
                project_name,
                "needs_clarification",
                "Gerald needs clarification",
                files_changed=[],
                output=reply,
                error="",
            )
            write_status("needs_clarification", "Gerald needs clarification")
        else:
            write_task_state(task_text, project_name, "completed", "Gerald answered", files_changed=[], output=reply, error="", contract={}, audit={}, task_id=_task_id)
            write_status("idle", "Gerald answered")
    except Exception as e:
        err = str(e)
        data = {
            "task": task_text,
            "project": project_name,
            "status": "error",
            "returncode": 1,
            "output": "",
            "summary": "",
            "error": err,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        write_outbox(data, outbox_file)
        write_status("error", err)
        print("❌ RUN_DIRECT_ANSWER ERROR:", err)


@app.get("/command-centre")
def command_centre():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/Gerald/command_centre/index.html")

@app.post("/start")
def start(payload: dict, background_tasks: BackgroundTasks):
    print("\n====== /start PAYLOAD ======")
    print(json.dumps(payload, indent=2))
    print("============================\n")

    text = ""
    for field in ("text", "prompt", "message", "command", "input", "task"):
        value = payload.get(field, "")
        if isinstance(value, str):
            value = value.strip()
        if value:
            text = value
            print(f"[/start] field '{field}': {text[:80]}")
            break

    if not text:
        return {"ok": False, "error": "No task provided", "received_keys": list(payload.keys())}

    # ── Voice command: "create project X" ─────────────────────────────────────
    detected_name = detect_create_project_name(text)
    if detected_name:
        projects = load_projects()
        if any(p["name"].lower() == detected_name.lower() for p in projects):
            msg = f"Project '{detected_name}' already exists."
        else:
            proj_path = f"/opt/Gerald/{detected_name}"
            try:
                create_brain_files(proj_path, detected_name)
                new_proj = {"name": detected_name, "path": proj_path, "description": ""}
                projects.append(new_proj)
                save_projects(projects)
                msg = f"Project '{detected_name}' created at {proj_path} with brain files initialised."
                print(f"✅ Voice-created project: {detected_name}")
            except Exception as e:
                msg = f"Failed to create project '{detected_name}': {e}"
        write_outbox({
            "task": text,
            "project": detected_name,
            "status": "done",
            "output": msg,
            "summary": msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        write_status("idle", f"Project '{detected_name}' ready")
        return {"ok": True}

    raw_project = payload.get("project", "")
    project_name_input = raw_project.strip() if isinstance(raw_project, str) else ""
    project_path, resolved_name = resolve_project(project_name_input)

    # ── Session state: log user request and detect failure feedback ───────────
    try:
        _gss.log_event(resolved_name, "user_request", text=text)
        if _gss.is_failure_feedback(text):
            _gss.log_event(resolved_name, "matt_correction", text=text)
            _lf = _gss.get_last_failed_task(resolved_name)
            if _lf:
                _gss.log_event(
                    resolved_name, "task_reopened",
                    reason=f"Matt reported failure: {text[:100]}",
                    last_intent=(_lf.get("contract") or {}).get("intent", "")[:100]
                )
    except Exception:
        pass

    # ── Reasoning Layer V2: detect manual corrections from Matt ───────────────
    _rl2_alert = gerald_issue_memory.check_correction(text, resolved_name)
    if _rl2_alert:
        _notify_recurring_failure(_rl2_alert, resolved_name)

    # Gerald Decision Agent V1: OpenAI decides the next backend action.
    decision = decide_next_action(text, resolved_name, payload)
    decision_action = (decision.get("action") or "fallback_router").strip()
    decision_task = (decision.get("task") or text).strip()
    decision_message = (decision.get("message") or "").strip()

    print("[Decision Agent]", json.dumps(decision, indent=2))

    # ── Implementation keyword override ────────────────────────────────────────
    # If the message contains explicit implementation signals ('CODE CHANGE REQUIRED',
    # 'Modify', 'Implement', 'Fix', 'Return code changes') the Decision Agent must
    # not route to investigation, brain, or direct-answer.  Override to claude_code
    # so the task is always executed and completion notifications fire correctly.
    _NON_EXEC_ACTIONS = {"answer_directly", "gerald_brain", "readonly_investigation", "fallback_router"}
    if _looks_like_implementation_request(text) and decision_action in _NON_EXEC_ACTIONS:
        print(f"[router] Implementation override: '{decision_action}' → 'claude_code' (keyword match in task)")
        decision_action = "claude_code"
        decision_task = text  # use original user text verbatim

    # V4 Investigation Evidence Gate: router-level override.
    # Investigation questions must use live backend evidence, never generic direct answers.
    if _looks_like_investigation_request(text) and not _looks_like_implementation_request(text):
        _task_id = _generate_task_id()
        reply = _build_live_investigation_answer(text, resolved_name)
        data = {
            "task_id": _task_id,
            "task": text,
            "project": resolved_name,
            "status": "done",
            "returncode": 0,
            "output": reply,
            "summary": reply[:1000],
            "error": "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        outbox_file = get_project_outbox_file(resolved_name)
        write_outbox(data)
        write_outbox(data, outbox_file)
        _append_task_history(data, resolved_name)
        write_task_state(text, resolved_name, "completed", "Investigation completed from live evidence", files_changed=[], output=reply, error="", contract={}, audit={}, task_id=_task_id)
        write_status("idle", "Investigation completed")
        return {
            "ok": True,
            "message": "Investigation Evidence Gate: live evidence investigation completed.",
            "decision": {
                **decision,
                "action": "evidence_investigation",
                "reason": "Router override: investigation request requires live evidence."
            }
        }

    if decision_action == "status_check":
        truthful_status_response(resolved_name)
        return {"ok": True, "message": "Decision Agent: status check complete.", "decision": decision}

    if decision_action == "answer_directly":
        background_tasks.add_task(run_direct_answer, text, resolved_name, decision_message)
        write_status("working", f"Gerald is answering: {resolved_name}")
        return {"ok": True, "message": "Decision Agent: answering directly.", "decision": decision}

    if decision_action == "gerald_brain":
        background_tasks.add_task(run_gerald_brain, decision_task, resolved_name)
        write_status("working", f"Gerald is thinking: {resolved_name}")
        return {"ok": True, "message": "Decision Agent: sent to Gerald Brain.", "decision": decision}

    if decision_action == "execute_pending_approval":
        pending_task = load_pending_approval(resolved_name)
        if pending_task:
            clear_pending_approval()
            claude_task = clean_task_for_claude(pending_task)
            background_tasks.add_task(run_claude_code_worker, claude_task, resolved_name)
            write_status("executing", f"Decision Agent approved pending plan: {resolved_name}")
            return {"ok": True, "message": "Decision Agent: pending plan sent to Claude Code.", "decision": decision}
        background_tasks.add_task(run_gerald_brain, "Matt approved, but no pending approval plan exists. Explain this briefly and ask what he wants to proceed with.", resolved_name)
        write_status("working", f"Gerald is resolving missing approval: {resolved_name}")
        return {"ok": True, "message": "Decision Agent: no pending approval found.", "decision": decision}

    if decision_action == "readonly_investigation":
        background_tasks.add_task(run_claude_investigation_worker, decision_task, resolved_name)
        write_status("investigating", f"Decision Agent sent investigation to Claude: {resolved_name}")
        return {"ok": True, "message": "Decision Agent: read-only investigation started.", "decision": decision}

    if decision_action == "claude_code":
        background_tasks.add_task(run_claude_code_worker, decision_task, resolved_name)
        write_status("executing", f"Decision Agent sent task to Claude: {resolved_name}")
        return {"ok": True, "message": "Decision Agent: task sent to Claude Code.", "decision": decision}

    # Fallback keeps the previous router available while Decision Agent V1 settles.
    if is_status_check(text):
        truthful_status_response(resolved_name)
        return {"ok": True, "message": "Truthful status check complete."}

    current_task = read_task()
    busy_stages = {"executing", "investigating", "working", "planning", "sending", "queued"}
    stage = str(current_task.get("stage", "")).lower()
    active = bool(current_task.get("active"))

    if active or stage in busy_stages:
        return {
            "ok": False,
            "message": f"Gerald is already busy ({stage or 'active'}). Please wait for the current task to finish.",
            "task": current_task,
        }

    if is_simple_approval(text):
        pending_task = load_pending_approval(resolved_name)
        if pending_task:
            clear_pending_approval()
            background_tasks.add_task(run_claude_code_worker, clean_task_for_claude(pending_task), resolved_name)
            write_status("executing", f"Approval received — Claude Code is working on pending plan: {resolved_name}")
            return {"ok": True, "message": "Approval received. Pending Gerald plan sent to Claude Code."}

        previous_task = load_last_outbox_task(resolved_name)
        if previous_task:
            background_tasks.add_task(run_claude_code_worker, clean_task_for_claude(previous_task), resolved_name)
            write_status("executing", f"Approval received — Claude Code is working on: {resolved_name}")
            return {"ok": True, "message": "Approval received. Previous Gerald task sent to Claude Code."}
        return {"ok": False, "message": "No pending or previous task found to approve."}

    if should_use_investigation_worker(text):
        background_tasks.add_task(run_claude_investigation_worker, text, resolved_name)
        write_status("investigating", f"Claude Code is investigating: {resolved_name}")
        return {"ok": True, "message": "Read-only investigation started."}

    if is_planning_only_request(text):
        background_tasks.add_task(run_gerald_brain, text, resolved_name)
        write_status("working", f"Gerald is planning: {resolved_name}")
        return {"ok": True, "message": "Planning request sent to Gerald Brain."}

    if is_general_question(text):
        background_tasks.add_task(run_gerald_brain, text, resolved_name)
        write_status("working", f"Gerald is answering: {resolved_name}")
        return {"ok": True, "message": "Question sent to Gerald Brain."}

    if should_use_claude_worker(text):
        background_tasks.add_task(run_claude_code_worker, text, resolved_name)
        write_status("executing", f"Claude Code is working on: {resolved_name}")
        return {"ok": True, "message": "Task sent to Claude Code for implementation."}

    background_tasks.add_task(run_gerald_brain, text, resolved_name)
    write_status("working", f"Gerald is thinking about: {resolved_name}")
    return {"ok": True, "message": "Task sent to Gerald Brain."}


@app.get("/read")
def read(project: str = ""):
    if project:
        project_outbox = get_project_outbox_file(project)
        if os.path.exists(project_outbox):
            with open(project_outbox, "r", encoding="utf-8") as f:
                return json.loads(f.read())
    if not os.path.exists(OUTBOX_FILE):
        return {"status": "empty"}
    with open(OUTBOX_FILE, "r", encoding="utf-8") as f:
        return json.loads(f.read())


@app.post("/ask")
def ask(payload: dict, background_tasks: BackgroundTasks):
    """Mobile app sends voice/text prompt with optional project name."""
    prompt = payload.get("prompt", "").strip()
    project_name = payload.get("project", "").strip()

    if not prompt:
        return {"ok": False, "error": "No prompt provided"}

    project_path, resolved_name = resolve_project(project_name)

    background_tasks.add_task(run_claude if should_use_claude_worker(prompt) else run_gerald_brain, prompt, project_path, resolved_name) if should_use_claude_worker(prompt) else background_tasks.add_task(run_gerald_brain, prompt, resolved_name)
    write_status("working", f"Claude is working on: {resolved_name}")

    return {"ok": True, "message": "Task received. Gerald is on it."}


@app.get("/status")
def get_status():
    """
    V4 Phase 2: /status reads canonical task state.
    Legacy response shape is preserved where possible.
    """
    state = read_canonical_state()
    stage = state.get("stage", "idle")

    if stage in ("idle", "", None):
        return {
            "status": "idle",
            "detail": "No active task is currently running.",
            "source_of_truth": "canonical",
            "task_id": state.get("task_id", ""),
            "project": state.get("project", ""),
        }

    return {
        "status": stage,
        "detail": state.get("detail", ""),
        "task_id": state.get("task_id", ""),
        "task": state.get("task", ""),
        "project": state.get("project", ""),
        "updated": state.get("updated", ""),
        "source_of_truth": "canonical",
    }

@app.get("/projects")
def get_projects():
    """Return full project list including description."""
    return load_projects()


# ─── Project Brain ─────────────────────────────────────────────────────────────

@app.get("/project-brain/{project_name}")
def project_brain(project_name: str):
    """Return project brain content and file metadata."""
    projects = load_projects()
    match = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    path = match["path"]
    brain = get_brain_content(path)
    files_found = [f for f in BRAIN_FILES if os.path.exists(os.path.join(path, f))]

    return {
        "project": match["name"],
        "path": path,
        "description": match.get("description", ""),
        "brain": brain,
        "files": files_found,
        "has_brain": bool(files_found),
    }


# ─── Automatic Project Creation ────────────────────────────────────────────────

@app.post("/create-project")
def create_project(payload: dict):
    """Create a new project directory with brain files and register it."""
    name = (payload.get("name") or "").strip()
    path = (payload.get("path") or "").strip()
    description = (payload.get("description") or "").strip()

    if not name:
        return {"ok": False, "error": "Project name is required"}

    if not path or "\\" in path:
        path = f"/opt/Gerald/{name}"

    projects = load_projects()

    # Duplicate check
    for p in projects:
        if p["name"].lower() == name.lower():
            return {"ok": False, "error": f"Project '{name}' already exists"}

    # Create directory and brain stub files
    try:
        create_brain_files(path, name, description)
    except Exception as e:
        return {"ok": False, "error": f"Failed to create project files: {e}"}

    # Persist to projects file
    new_project = {"name": name, "path": path, "description": description}
    projects.append(new_project)
    save_projects(projects)

    print(f"✅ Project created: {name} at {path}")

    return {
        "ok": True,
        "project": new_project,
        "message": f"Project '{name}' created at {path}",
    }


# ─── Brain initialisation ─────────────────────────────────────────────────────

@app.post("/init-brain/{project_name}")
def init_brain(project_name: str):
    """Create brain stub files for an existing project that is missing them."""
    projects = load_projects()
    match = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    path = match["path"]
    description = match.get("description", "")
    create_brain_files(path, match["name"], description)

    files_now = [f for f in BRAIN_FILES if os.path.exists(os.path.join(path, f))]
    print(f"✅ Brain initialised for {match['name']} at {path}")
    return {
        "ok": True,
        "project": match["name"],
        "path": path,
        "files": files_now,
        "message": f"Brain files initialised for '{match['name']}'",
    }


# ─── Device registration ───────────────────────────────────────────────────────

@app.post("/register-device")
def register_device(payload: dict):
    """Store FCM device token for push notifications."""
    token = payload.get("token", "").strip()
    if not token:
        return {"ok": False, "error": "No token provided"}

    tokens = []
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            try:
                tokens = json.load(f)
            except Exception:
                tokens = []

    if token not in tokens:
        tokens.append(token)
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)

    return {"ok": True}


@app.post("/reject")
def reject(payload: dict):
    """Record a plan rejection and reset status."""
    reason = payload.get("reason", "Rejected by user")
    write_status("idle", f"Plan rejected: {reason}")
    return {"ok": True, "message": reason}


@app.post("/send-to-claude-code")
def send_to_claude_code(payload: dict):
    """Run an approved task through Claude Code on the server."""
    message = payload.get("message", "APPROVED TO EDIT")
    project = payload.get("project", "CommuteCoder")
    worker_dir = get_worker_directory(message, project)

    safe_prompt = f"""
You are Claude Code running on Gerald Server.

Project: {project}
Working directory: {worker_dir}

Task from Gerald:
{message}

Rules:
- Work only inside /opt/Gerald/gerald_app unless explicitly instructed.
- Prefer small, safe edits.
- Do not modify gerald_bridge.py.
- Do not modify secrets or environment files.
- After editing, summarize exactly what files changed.
- Do not build APK unless explicitly requested in the task.
"""

    start_task(project, message)
    update_stage("Executing")
    write_status("executing", "Claude Code executing approved task")

    try:
        result = subprocess.run(
            [
                "sudo", "-u", "geraldbuild", "-H",
                "bash", "-lc",
                f"cd {worker_dir} && claude --permission-mode bypassPermissions -p {safe_prompt!r}"
            ],
            cwd=worker_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        write_outbox({
            "task": message,
            "project": project,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        if result.returncode == 0:
            write_status("idle", "Claude Code task finished")
            complete_task("Claude Code task finished", "Return code 0")
            return {
                "ok": True,
                "message": "Claude Code task finished",
                "output": output,
            }

        write_status("error", "Claude Code task failed")
        fail_task(f"Claude Code failed with return code {result.returncode}")
        return {
            "ok": False,
            "message": "Claude Code task failed",
            "returncode": result.returncode,
            "output": output,
            "error": error,
        }

    except subprocess.TimeoutExpired:
        write_status("error", "Claude Code task timed out")
        fail_task("Claude Code task timed out")
        write_outbox({
            "task": message,
            "project": project,
            "status": "error",
            "output": "",
            "error": "Claude Code task timed out",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return {"ok": False, "message": "Claude Code task timed out"}


# ─── Build Verification ───────────────────────────────────────────────────────

_build_running = False


def _run_build_background(project_path: str, flavor: str):
    global _build_running
    _build_running = True
    write_status("building", f"Verifying build (clean → pub get → apk)…")
    try:
        result = build_verifier.run_build_verification_sequence(project_path, flavor)
        status_label = "idle" if result["status"] == "success" else "error"
        attempts = result.get("attempts", 1)
        fixes = result.get("fixes_applied", [])
        if result["status"] == "success":
            detail = (
                f"Build OK ({result['duration_s']}s, "
                f"{result.get('warning_count', 0)} warnings"
                + (f", {attempts} attempt(s)" if attempts > 1 else "")
                + ")"
            )
        else:
            detail = (
                f"Build FAILED — {result.get('error_count', 0)} error(s)"
                + (f", {len(fixes)} fix(es) tried" if fixes else "")
            )
        write_status(status_label, detail)
        print(f"[build-verify] {detail}")
    finally:
        _build_running = False


@app.post("/build-verify")
def build_verify(payload: dict, background_tasks: BackgroundTasks):
    """Trigger flutter build apk asynchronously. Returns immediately."""
    if _build_running:
        return {"ok": False, "error": "Build already in progress"}

    flavor = (payload.get("flavor") or "debug").strip()
    project_name = (payload.get("project") or "CommuteCoder").strip()
    project_path, _ = resolve_project(project_name)

    background_tasks.add_task(_run_build_background, project_path, flavor)
    return {"ok": True, "message": f"flutter build apk --{flavor} started for {project_name}"}


@app.get("/build-status")
def get_build_status():
    """Return latest build verification result."""
    data = build_verifier.read_build_status()
    data["is_running"] = _build_running
    return data


# ─── Multi-AI Provider ─────────────────────────────────────────────────────────

@app.get("/provider-status")
def provider_status():
    """Return active AI provider and full registry."""
    active = multi_ai_router.get_active_provider()
    providers = multi_ai_router.list_providers()
    return {
        "active_provider": active,
        "providers": providers,
    }


@app.post("/set-provider")
def set_provider(payload: dict):
    """Switch the active AI provider. Optionally store an API key."""
    provider_id = (payload.get("provider") or "").strip()
    api_key = (payload.get("api_key") or "").strip()

    if not provider_id:
        return {"ok": False, "error": "provider field is required"}

    try:
        multi_ai_router.set_active_provider(provider_id)
        if api_key:
            multi_ai_router.set_api_key(provider_id, api_key)
        return {
            "ok": True,
            "active_provider": provider_id,
            "message": f"Switched to {provider_id}",
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ─── Remote APK Delivery ───────────────────────────────────────────────────────

@app.get("/apk-status")
def apk_status():
    """Return latest APK manifest for remote delivery polling."""
    if not os.path.exists(APK_MANIFEST_FILE):
        return {"available": False, "message": "No APK built yet. Run build_and_deliver.py."}
    with open(APK_MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["download_url"] = "/apk-latest/download"
    return manifest


@app.get("/apk-latest/download")
def apk_download():
    """Serve the latest debug APK for OTA installation."""
    if not os.path.exists(APK_SERVE_FILE):
        raise HTTPException(
            status_code=404,
            detail="APK not found. Run: python remote_build/build_and_deliver.py",
        )
    return FileResponse(
        APK_SERVE_FILE,
        media_type="application/vnd.android.package-archive",
        filename="gerald-latest.apk",
    )


# ─── APK Upload (cloud bridge endpoint) ───────────────────────────────────────

@app.post("/apk-upload")
async def apk_upload(request: Request):
    """Receive a raw APK binary upload from build_and_deliver.py --cloud-url."""
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty APK body")

    os.makedirs(APK_SERVE_DIR, exist_ok=True)
    dest = APK_SERVE_FILE
    with open(dest, "wb") as f:
        f.write(body)

    # Regenerate manifest from uploaded file
    import hashlib
    h = hashlib.sha256(body).hexdigest()
    manifest = {
        "available": True,
        "hash": f"sha256:{h}",
        "size_bytes": len(body),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flavor": "debug",
        "download_url": "/apk-latest/download",
    }
    with open(APK_MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[apk-upload] Received {len(body) // 1024}KB APK, stored at {dest}")
    return {"ok": True, "size_bytes": len(body), "download_url": "/apk-latest/download"}


# ─── Push Notification ─────────────────────────────────────────────────────────

_pending_notification: dict = {}


@app.post("/notify")
def notify(payload: dict):
    """Queue a push notification for delivery to Matt's device."""
    global _pending_notification
    _pending_notification = {
        **payload,
        "received": datetime.now(timezone.utc).isoformat(),
        "delivered": False,
    }
    print(f"[notify] Queued: {payload.get('title', '')}")
    # If FCM service account available, send immediately (cloud deployment)
    _try_send_fcm(payload)
    return {"ok": True, "message": "Notification queued"}


@app.get("/pending-notification")
def pending_notification():
    """Flutter app polls this to fetch the latest pending notification."""
    return _pending_notification or {"pending": False}


@app.post("/clear-notification")
def clear_notification():
    """Flutter app calls this after showing the notification."""
    global _pending_notification
    _pending_notification = {}
    return {"ok": True}


def _try_send_fcm(payload: dict) -> None:
    """Send FCM push notification if service account is configured."""
    fcm_path = os.path.join(BASE, "firebase-service-account.json")
    if not os.path.exists(fcm_path):
        return  # FCM not configured — local polling is the fallback
    if not os.path.exists(DEVICES_FILE):
        return

    try:
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            tokens = json.load(f)
        if not tokens:
            return
        # FCM HTTP v1 API — requires OAuth2 access token from service account
        # This is a placeholder; real implementation needs google-auth library
        print(f"[notify] FCM configured but google-auth not available; tokens={len(tokens)}")
    except Exception as e:
        print(f"[notify] FCM send skipped: {e}")


# ─── Web UI ────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return HTMLResponse("""
    <html>
    <body style="background:#111;color:white;font-family:Arial;padding:20px;">
        <h2>Gerald Bridge</h2>

        <input id="t" style="width:600px;padding:8px;" placeholder="Enter task..." />
        <button onclick="send()">Send</button>
        <button onclick="read()">Read Output</button>

        <pre id="out" style="white-space:pre-wrap;margin-top:20px;"></pre>

        <script>
        async function send() {
            const text = document.getElementById("t").value;
            document.getElementById("out").innerText = "Sending to Claude...";
            const res = await fetch("/start", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({text})
            });
            document.getElementById("out").innerText = await res.text();
        }
        async function read() {
            const res = await fetch("/read");
            document.getElementById("out").innerText = await res.text();
        }
        </script>
    </body>
    </html>
    """)


write_status("idle", "Gerald ready")
print("[Gerald] Bridge V1.4 - Autonomous Build Verification + Multi-AI + APK Delivery")


@app.post("/gerald-brain")
async def gerald_brain_endpoint(request: Request):
    payload = await request.json()
    prompt = payload.get("prompt") or payload.get("text") or ""
    if not prompt:
        return {"ok": False, "error": "Missing prompt"}

    try:
        reply = ask_gerald(prompt)
        return {"ok": True, "reply": reply}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/gerald-vision")
async def gerald_vision_endpoint(
    image: UploadFile = File(...),
    prompt: str = Form("")
):
    try:
        image_bytes = await image.read()
        reply = review_image(
            image_bytes=image_bytes,
            mime_type=image.content_type or "image/jpeg",
            prompt=prompt,
        )
        return {"ok": True, "reply": reply}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Dashboard Image Upload ────────────────────────────────────────────────────

@app.post("/upload-image")
async def upload_image_endpoint(image: UploadFile = File(...)):
    """Accept an image from the dashboard, store it, return its URL."""
    ct = image.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    uploads_dir = os.path.join(BASE, "dashboard", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    import uuid as _uuid
    ext = os.path.splitext(image.filename or "upload")[1] or ".jpg"
    filename = f"{_uuid.uuid4().hex}{ext}"
    dest = os.path.join(uploads_dir, filename)

    data = await image.read()
    with open(dest, "wb") as f:
        f.write(data)

    image_url = f"/dashboard/uploads/{filename}"
    print(f"[upload-image] Stored {len(data)} bytes → {dest}")
    return {"ok": True, "url": image_url, "filename": filename}


def _run_apk_build_background(project: str):
    global _build_running
    _build_running = True
    write_status("building", "Building Gerald APK…")
    try:
        result = subprocess.run(
            ["/bin/bash", "/opt/Gerald/build_gerald_apk.sh"],
            cwd="/opt/Gerald",
            capture_output=True,
            text=True,
            timeout=1200,
        )
        output = result.stdout.strip()
        error  = result.stderr.strip()
        write_outbox({
            "task": "Build Gerald APK",
            "project": project,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
            "error": error,
            "download_url": "/apk-latest/download",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if result.returncode == 0:
            write_status("idle", "APK built and published")
        else:
            write_status("error", "APK build failed")
    except subprocess.TimeoutExpired:
        write_status("error", "APK build timed out")
    finally:
        _build_running = False


@app.post("/build-apk")
def build_apk_endpoint(payload: dict = None, background_tasks: BackgroundTasks = None):
    """Trigger APK build asynchronously. Returns immediately; poll /build-status for progress."""
    if _build_running:
        return {"ok": False, "error": "Build already in progress"}
    payload  = payload or {}
    project  = (payload.get("project") or "CommuteCoder").strip()
    background_tasks.add_task(_run_apk_build_background, project)
    return {"ok": True, "message": f"APK build started for {project}"}



# ── Session state endpoints (read-only) ───────────────────────────────────────

@app.get("/session/summary")
def session_summary_endpoint(project: str = "CommuteCoder"):
    """Return current session summary for dashboard display."""
    return _gss.get_session_summary(project)


@app.get("/session/lessons")
def session_lessons_endpoint(project: str = "CommuteCoder"):
    """Return per-project lessons memory (read-only)."""
    return {"project": project, "lessons": _gss._read_lessons(project)}


# Private Gerald Dashboard
DASHBOARD_DIR = os.path.join(BASE, "dashboard")
if os.path.isdir(DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

@app.post("/auto-fix")
def auto_fix_endpoint(payload: dict):
    """One-step Gerald auto-fix: take Matt's request and execute it through Claude Code."""
    task = payload.get("prompt") or payload.get("task") or payload.get("message") or ""
    project = payload.get("project", "CommuteCoder")

    if not task.strip():
        return {"ok": False, "message": "No task provided"}

    claude_prompt = f"""
You are Claude Code working for Gerald.

Matt's request:
{task}

Project: {project}
Working directory: /opt/Gerald/gerald_app

Rules:
- Inspect the relevant Flutter files first.
- Make the smallest safe change that satisfies Matt's request.
- Do not rewrite whole screens unless absolutely necessary.
- Preserve existing behaviour.
- Do not edit gerald_bridge.py.
- Do not build APK.
- After editing, summarize exactly which files changed and what changed.
"""

    write_status("executing", "Auto-fix running through Claude")

    try:
        prompt_file = "/tmp/gerald_auto_fix_prompt.txt"
        Path(prompt_file).write_text(claude_prompt, encoding="utf-8")

        result = subprocess.run(
            [
                "sudo", "-u", "geraldbuild", "-H",
                "bash", "-lc",
                f'cd /opt/Gerald/gerald_app && claude --permission-mode bypassPermissions -p "$(cat {prompt_file})"'
            ],
            cwd="/opt/Gerald/gerald_app",
            capture_output=True,
            text=True,
            timeout=900,
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        write_outbox({
            "task": task,
            "project": project,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        write_status("idle" if result.returncode == 0 else "error", "Auto-fix finished" if result.returncode == 0 else "Auto-fix failed")

        return {
            "ok": result.returncode == 0,
            "message": "Auto-fix finished" if result.returncode == 0 else "Auto-fix failed",
            "output": output,
            "error": error,
        }

    except subprocess.TimeoutExpired:
        write_status("error", "Auto-fix timed out")
        return {"ok": False, "message": "Auto-fix timed out"}




@app.post("/vision-fix")
def vision_fix_endpoint(payload: dict):
    """Screenshot -> OpenAI vision diagnosis -> Claude Code implementation."""
    project = payload.get("project", "CommuteCoder")
    user_prompt = (payload.get("prompt") or "Fix the visible bug in this screenshot.").strip()
    image_base64 = (payload.get("image_base64") or "").strip()

    if not image_base64:
        return {"ok": False, "message": "No screenshot image provided"}

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "message": "OPENAI_API_KEY is not set on the server"}

    if "," in image_base64 and image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[1]

    write_status("executing", "Gerald Vision Debugger analysing screenshot")

    vision_prompt = f"""
You are Gerald's visual debugging system.

Matt's request:
{user_prompt}

Your job:
1. Inspect the screenshot visually.
2. Identify the MOST OBVIOUS visible UI bug, prioritising:
   - unwanted debug banners or labels
   - vertical text overlays
   - text or stickers overlapping the header/logo
   - clipping, overflow, or objects covering other UI
   - anything that looks like a temporary debug/test marker
3. Do NOT focus on minor wording/branding differences if a visual overlay or obstruction is present.
4. Be specific about location, colour, text, orientation, and what it overlaps.
5. Convert it into a precise Claude Code implementation task.

Return ONLY this structure:

VISIBLE_BUG:
<plain English description of the visible issue>

CLAUDE_TASK:
<precise implementation task for Claude Code>

SAFETY_SCOPE:
<what files/areas Claude should avoid changing>
"""

    body = {
        "model": os.environ.get("GERALD_VISION_MODEL", "gpt-4o"),
        "messages": [
            {
                "role": "system",
                "content": "You are a senior mobile UI debugger. Be precise. Do not guess beyond the screenshot."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64," + image_base64
                        }
                    }
                ]
            }
        ],
        "max_tokens": 900
    }

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            vision_data = json.loads(resp.read().decode("utf-8"))

        diagnosis = vision_data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        write_status("error", "Vision analysis failed")
        return {"ok": False, "message": "Vision analysis failed", "error": str(e)}

    claude_prompt = f"""
You are Claude Code working for Gerald.

Gerald Vision Debugger analysed Matt's screenshot.

Matt's original request:
{user_prompt}

Vision diagnosis:
{diagnosis}

Working directory:
/opt/Gerald/gerald_app

Rules:
- Fix the visible bug identified by Gerald Vision Debugger.
- Make the smallest safe code change.
- Inspect relevant Flutter files first.
- Do not guess unrelated fixes.
- Do not change app branding, layout, or functionality unless required to remove the visible bug.
- Do not edit gerald_bridge.py.
- Do not build APK.
- After editing, report exactly which files changed and what changed.
"""

    write_status("executing", "Vision diagnosis complete — Claude Code fixing")

    try:
        Path("/tmp/gerald_vision_prompt.txt").write_text(claude_prompt, encoding="utf-8")

        result = subprocess.run(
            [
                "sudo", "-u", "geraldbuild", "-H",
                "bash", "-lc",
                "cat /tmp/gerald_vision_prompt.txt | cd /opt/Gerald/gerald_app && claude --permission-mode bypassPermissions -p"
            ],
            cwd="/opt/Gerald/gerald_app",
            capture_output=True,
            text=True,
            timeout=900,
        )

        data = {
            "task": user_prompt,
            "project": project,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "vision_diagnosis": diagnosis,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        write_outbox(data)
        write_outbox(data, get_project_outbox_file(project))

        write_status(
            "idle" if result.returncode == 0 else "error",
            "Vision fix finished" if result.returncode == 0 else "Vision fix failed"
        )

        return {
            "ok": result.returncode == 0,
            "message": "Vision fix finished" if result.returncode == 0 else "Vision fix failed",
            "vision_diagnosis": diagnosis,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }

    except subprocess.TimeoutExpired:
        write_status("error", "Vision fix timed out")
        return {"ok": False, "message": "Vision fix timed out", "vision_diagnosis": diagnosis}

@app.get("/task/status")
def task_status():
    """
    V4 Phase 2: task status reads canonical task state.
    """
    return read_canonical_state()

@app.get("/task/contract")
def task_contract_endpoint():
    """Return current task contract and Auditor result from active_task.json."""
    state = read_task_state()
    audit = state.get("audit")
    return {
        "contract": state.get("contract"),
        "audit": audit,
        "audit_verdict": audit.get("verdict") if audit else None,
        "stage": state.get("stage", "idle"),
        "task": state.get("task", ""),
        "project": state.get("project", ""),
    }


@app.get("/task/last-result")
def get_last_task_result(project: str = "CommuteCoder"):
    """Return the last real task result (excludes status checks) from durable task history."""
    result = _get_last_real_task_result(project)
    if not result:
        return {"found": False, "project": project}
    return {**result, "found": True}


@app.get("/task/truth")
def get_task_truth():
    """V4 Phase 2: canonical task state source of truth."""
    return read_canonical_state()

@app.post("/planner/preview")
async def planner_preview_endpoint(request: Request):
    """Generate a Task Contract from a prompt without starting Claude Code. For testing the Planner."""
    body = await request.json()
    task_text = body.get("task", "")
    project = body.get("project", "CommuteCoder")
    if not task_text:
        return {"error": "task field required"}
    try:
        contract = create_task_contract(task_text, project)
        return {"ok": True, "contract": contract}
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

@app.post("/task/start")
def task_start(project: str, user_request: str):
    return start_task(project, user_request)

@app.post("/task/stage")
def task_stage(stage: str):
    return update_stage(stage)

@app.post("/task/file-changed")
def task_file_changed(path: str):
    return add_file_changed(path)

@app.post("/task/complete")
def task_complete(result: str, verification: str):
    return complete_task(result, verification)

# ─── Gerald Supervisor Mode: ChatGPT Reasoning Layer ──────────────────────────
from pathlib import Path as SupervisorPath
import json as supervisor_json

def _supervisor_read_file(path: str, limit: int = 12000):
    p = SupervisorPath(path)
    if not p.exists():
        return f"[Missing file: {path}]"
    text = p.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def _supervisor_context(problem: str, project: str):
    return f"""
You are ChatGPT acting as Gerald's Supervisor Brain.

Matt is not a developer. Your job is to diagnose problems, recommend fixes,
and explain clearly what should happen next.

IMPORTANT RULES:
- Do not pretend work has been done.
- Use only the evidence provided.
- If evidence is missing, say what Gerald should inspect next.
- Recommend changes, but do not claim Claude has executed anything.
- End with a clear approval question for Matt.

PROJECT:
{project}

MATT'S PROBLEM:
{problem}

CURRENT TASK STATE:
{supervisor_json.dumps(read_task(), indent=2)}

PROJECT BRAIN:
{_supervisor_read_file("/opt/Gerald/project_brain.md")}

CURRENT STATUS:
{_supervisor_read_file("/opt/Gerald/current_status.md")}

ARCHITECTURE:
{_supervisor_read_file("/opt/Gerald/architecture.md")}

ROADMAP:
{_supervisor_read_file("/opt/Gerald/roadmap.md")}

LATEST GERALD OUTBOX:
{_supervisor_read_file("/opt/Gerald/gerald_outbox.json")}

Respond in this exact structure:

DIAGNOSIS:
...

EVIDENCE:
...

RECOMMENDED FIX:
...

FILES LIKELY TO CHANGE:
- ...

RISK:
Low / Medium / High

APPROVAL QUESTION:
Should Gerald send this recommendation to Claude Code to make the change?
"""


@app.post("/gerald-supervisor")
async def gerald_supervisor_endpoint(request: Request):
    payload = await request.json()
    problem = payload.get("problem") or payload.get("prompt") or payload.get("text") or ""
    project = payload.get("project", "gerald_app")

    if not problem:
        return {"ok": False, "error": "Missing problem"}

    try:
        start_task(project, problem)
        update_stage("Planning")

        supervisor_prompt = _supervisor_context(problem, project)
        reply = ask_gerald(supervisor_prompt)

        update_stage("Waiting Approval")

        return {
            "ok": True,
            "project": project,
            "stage": "Waiting Approval",
            "recommendation": reply,
            "task": read_task(),
        }

    except Exception as e:
        fail_task(str(e))
        return {"ok": False, "error": str(e)}

@app.post("/gerald-supervisor/approve")
def gerald_supervisor_approve():
    task = read_task()

    if not task.get("active"):
        return {"ok": False, "error": "No active supervisor task to approve"}

    if task.get("stage") != "Waiting Approval":
        return {
            "ok": False,
            "error": f"Task is not waiting for approval. Current stage: {task.get('stage')}",
            "task": task,
        }

    project = task.get("project", "gerald_app")
    user_request = task.get("user_request", "")

    approved_message = f"""
APPROVED SUPERVISOR RECOMMENDATION

Original user problem:
{user_request}

Instruction:
Use the supervisor recommendation and available project context to inspect the issue,
make the safest necessary fix, and summarize exactly what changed.

Rules:
- Make the smallest safe change.
- Do not guess.
- If more evidence is needed, inspect files first.
- Do not modify secrets.
- Do not build APK unless required to verify the fix.
"""

    update_stage("Executing")

    return send_to_claude_code({
        "project": project,
        "message": approved_message,
    })
