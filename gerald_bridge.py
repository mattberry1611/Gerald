import os
import re
import json
import subprocess
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

import build_verifier
import multi_ai_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = r"C:\CommuteCoder"
OUTBOX_FILE = os.path.join(BASE, "gerald_outbox.json")
STATUS_FILE = os.path.join(BASE, "gerald_status.json")
DEVICES_FILE = os.path.join(BASE, "gerald_devices.json")
PROJECTS_FILE = os.path.join(BASE, "gerald_projects.json")
APK_MANIFEST_FILE = os.path.join(BASE, "apk_manifest.json")
APK_SERVE_FILE = os.path.join(BASE, "apk_serve", "gerald-latest.apk")

CLAUDE_PS1 = r"C:\Users\Matt\AppData\Roaming\npm\claude.ps1"

BRAIN_FILES = ["project_brain.md", "roadmap.md", "current_status.md", "architecture.md"]

BUILTIN_PROJECTS = [
    {"name": "CommuteCoder", "path": r"C:\CommuteCoder", "description": "Voice-driven AI coding supervisor"},
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


def resolve_project(project_name: str):
    """Return (path, canonical_name) for a project name."""
    if not project_name:
        return BASE, "CommuteCoder"
    for p in load_projects():
        if p["name"].lower() == project_name.lower():
            return p["path"], p["name"]
    return BASE, "CommuteCoder"


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
    for fname, content in stubs.items():
        fpath = os.path.join(project_path, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)


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


def write_outbox(data, outbox_file=None):
    target = outbox_file or OUTBOX_FILE
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # Mirror to primary outbox so /read always works regardless of project
    if outbox_file and outbox_file != OUTBOX_FILE:
        with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


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

    ps_command = f"""
Set-Location '{project_path}';
& '{CLAUDE_PS1}' --dangerously-skip-permissions -p @'
{prompt}
'@
"""

    project_outbox = get_project_outbox_file(project_name)

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command", ps_command
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=900
        )

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()

        data = {
            "task": task_text,
            "project": project_name,
            "status": "done" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        write_outbox(data, project_outbox)
        write_status(
            data["status"],
            "Claude finished" if result.returncode == 0 else "Claude returned error"
        )

        print("✅ CLAUDE FINISHED")
        print(output)
        if error:
            print("STDERR:", error)

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
            proj_path = f"C:\\{detected_name}"
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

    background_tasks.add_task(run_claude, text, project_path, resolved_name)
    write_status("working", "Claude is working on task")
    return {"ok": True}


@app.get("/read")
def read():
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

    background_tasks.add_task(run_claude, prompt, project_path, resolved_name)
    write_status("working", f"Claude is working on: {resolved_name}")

    return {"ok": True, "message": "Task received. Gerald is on it."}


@app.get("/status")
def get_status():
    """Return current Gerald status for mobile polling."""
    if not os.path.exists(STATUS_FILE):
        return {"status": "idle", "detail": "Gerald ready", "updated": ""}
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.loads(f.read())


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

    if not path:
        path = f"C:\\{name}"

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
    """Trigger the approved task injection into an active Claude Code terminal."""
    message = payload.get("message", "APPROVED TO EDIT")
    write_status("executing", "Approved — Claude is editing")
    write_outbox({
        "task": message,
        "status": "approved",
        "output": "Approval sent to Claude Code.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"ok": True, "message": "Approval forwarded to Claude Code."}


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
