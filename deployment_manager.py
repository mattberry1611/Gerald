"""
Gerald Deployment Manager V1 — plan and run deployment actions from git changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

GERALD_ROOT = "/opt/Gerald"
GERALD_APP_DIR = os.path.join(GERALD_ROOT, "gerald_app")
APK_BUILD_OUTPUT = os.path.join(
    GERALD_APP_DIR, "build/app/outputs/flutter-apk/app-debug.apk"
)
APK_SERVE_DIR = os.path.join(GERALD_ROOT, "apk_serve")
APK_SERVE_FILE = os.path.join(APK_SERVE_DIR, "gerald-latest.apk")
APK_MANIFEST_FILE = os.path.join(GERALD_ROOT, "apk_manifest.json")
APK_DOWNLOAD_PATH = "/apk-latest/download"


def _normalize_path(path: str) -> str:
    """Return a repo-relative path with forward slashes."""
    p = path.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    if p.startswith(GERALD_ROOT + "/"):
        p = p[len(GERALD_ROOT) + 1 :]
    elif p == GERALD_ROOT:
        p = ""
    return p


def get_git_changed_files(repo_root: str = GERALD_ROOT) -> list[str]:
    """Return changed file paths from `git status --short`."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return []

    if result.returncode != 0:
        return []

    files: list[str] = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line or len(line) < 4:
            continue
        entry = line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1].strip()
        if entry:
            files.append(_normalize_path(entry))
    return files


def _is_backend_py_file(path: str) -> bool:
    """True for root-level backend Python modules (not under gerald_app/)."""
    p = _normalize_path(path)
    if not p.endswith(".py"):
        return False
    if p.startswith("gerald_app/"):
        return False
    return "/" not in p


def _triggers_apk_build(path: str) -> bool:
    p = _normalize_path(path)
    return p.startswith("gerald_app/lib/") or p == "gerald_app/pubspec.yaml"


def _triggers_dashboard_changed(path: str) -> bool:
    p = _normalize_path(path)
    return p == "dashboard" or p.startswith("dashboard/")


def plan_deployment_actions(changed_files: list[str]) -> dict:
    """Decide which deployment actions are required for the given changed files."""
    normalized = [_normalize_path(f) for f in changed_files if f and f.strip()]

    restart_gerald = False
    restart_design_studio = False
    build_apk = False
    dashboard_changed = False

    triggering_files = {
        "restart_gerald": [],
        "restart_design_studio": [],
        "build_apk": [],
        "dashboard": [],
    }

    for path in normalized:
        basename = os.path.basename(path)

        if basename == "gerald_bridge.py" or _is_backend_py_file(path):
            restart_gerald = True
            triggering_files["restart_gerald"].append(path)

        if basename == "gerald_design_studio.py":
            restart_design_studio = True
            triggering_files["restart_design_studio"].append(path)

        if _triggers_apk_build(path):
            build_apk = True
            triggering_files["build_apk"].append(path)

        if _triggers_dashboard_changed(path):
            dashboard_changed = True
            triggering_files["dashboard"].append(path)

    actions_required: list[str] = []
    if restart_gerald:
        actions_required.append("restart_gerald")
    if restart_design_studio:
        actions_required.append("restart_gerald_design_studio")
    if build_apk:
        actions_required.append("build_apk")
    if dashboard_changed:
        actions_required.append("dashboard_changed")

    return {
        "changed_files": normalized,
        "actions_required": actions_required,
        "restart_gerald": restart_gerald,
        "restart_design_studio": restart_design_studio,
        "build_apk": build_apk,
        "dashboard_changed": dashboard_changed,
        "triggering_files": triggering_files,
    }


def _systemctl_restart_cmd(service_name: str) -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["systemctl", "restart", service_name]
    return ["sudo", "systemctl", "restart", service_name]


def _restart_service(service_name: str, *, background: bool = False) -> tuple[bool, str | None]:
    cmd = _systemctl_restart_cmd(service_name)

    if background:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, None
        except OSError as exc:
            return False, f"restart {service_name}: {exc}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"restart {service_name}: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        return False, f"restart {service_name} failed: {detail}"

    return True, None


def _write_apk_manifest(apk_path: str) -> None:
    with open(apk_path, "rb") as handle:
        body = handle.read()

    manifest = {
        "available": True,
        "hash": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "size_bytes": len(body),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flavor": "debug",
        "download_url": APK_DOWNLOAD_PATH,
    }
    with open(APK_MANIFEST_FILE, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)


def _build_apk() -> tuple[bool, str | None, str | None]:
    try:
        build = subprocess.run(
            ["flutter", "build", "apk", "--debug"],
            cwd=GERALD_APP_DIR,
            capture_output=True,
            text=True,
            timeout=1200,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"build_apk: {exc}", None

    if build.returncode != 0:
        detail = (build.stderr or build.stdout or "flutter build failed").strip()
        return False, f"build_apk failed: {detail[-2000:]}", None

    if not os.path.exists(APK_BUILD_OUTPUT):
        return False, f"build_apk failed: output not found at {APK_BUILD_OUTPUT}", None

    try:
        os.makedirs(APK_SERVE_DIR, exist_ok=True)
        shutil.copy2(APK_BUILD_OUTPUT, APK_SERVE_FILE)
        _write_apk_manifest(APK_SERVE_FILE)
    except OSError as exc:
        return False, f"build_apk copy failed: {exc}", None

    return True, None, APK_DOWNLOAD_PATH


def run_deployment_actions(plan: dict) -> dict:
    """Execute the actions described by a deployment plan."""
    actions_run: list[str] = []
    errors: list[str] = []
    apk_url: str | None = None

    if plan.get("restart_design_studio"):
        ok, err = _restart_service("gerald-design-studio")
        if ok:
            actions_run.append("restart_gerald_design_studio")
        elif err:
            errors.append(err)

    if plan.get("build_apk"):
        ok, err, url = _build_apk()
        if ok:
            actions_run.append("build_apk")
            apk_url = url
        elif err:
            errors.append(err)

    if plan.get("dashboard_changed"):
        actions_run.append("dashboard_changed")

    if plan.get("restart_gerald"):
        # Restart last in background so this endpoint can return before gerald stops.
        ok, err = _restart_service("gerald", background=True)
        if ok:
            actions_run.append("restart_gerald")
        elif err:
            errors.append(err)

    result = {
        "actions_required": plan.get("actions_required", []),
        "actions_run": actions_run,
        "success": len(errors) == 0,
        "errors": errors,
        "changed_files": plan.get("changed_files", []),
        "dashboard_changed": plan.get("dashboard_changed", False),
        "triggering_files": plan.get("triggering_files", {}),
    }
    if apk_url:
        result["apk_url"] = apk_url
    return result


def auto_deploy(repo_root: str = GERALD_ROOT) -> dict:
    """Read git changes, plan actions, and run them."""
    changed_files = get_git_changed_files(repo_root)
    plan = plan_deployment_actions(changed_files)
    return run_deployment_actions(plan)
