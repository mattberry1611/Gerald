import hashlib
import json as _json
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import List, Optional

# Provider/session/rate-limit error signals — mirrors gerald_openai_brain._CLAUDE_PROVIDER_ERROR_SIGNALS
_PROVIDER_ERROR_SIGNALS = [
    "authentication",
    "invalid api key",
    "invalid_api_key",
    "authentication_error",
    "permission_error",
    "rate limit",
    "rate_limit",
    "rate_limit_exceeded",
    "overloaded",
    "overloaded_error",
    "usage limit",
    "credit balance",
    "quota exceeded",
    "unauthorized",
    " 401 ",
    "error 401",
    " 403 ",
    "error 403",
    " 429 ",
    "error 429",
    " 529 ",
    "error 529",
    "service unavailable",
    "session expired",
    "session invalid",
    "billing",
    "api_error",
]

# Exact phrases that must appear in the original user request to qualify for a post-task APK build.
# Checked case-insensitively. No fuzzy matching — partial words do not qualify.
APK_BUILD_PHRASES = [
    "build apk",
    "build the apk",
    "create apk",
    "generate apk",
    "run apk build",
]


@dataclass
class RequestReview:
    intent: str
    risk: str
    should_ask_approval: bool
    should_delegate_to_claude: bool
    should_build_apk: bool
    reasons: List[str]


def _has_explicit_apk_phrase(text: str) -> bool:
    """Return True only if text contains one of the exact APK build phrases (case-insensitive)."""
    lower = (text or "").lower()
    return any(phrase in lower for phrase in APK_BUILD_PHRASES)


def _has_provider_error(output: str, error: str) -> bool:
    """Return True if any provider/session/rate-limit error signal appears in output or error."""
    combined = f"{output or ''} {error or ''}".lower()
    return any(sig in combined for sig in _PROVIDER_ERROR_SIGNALS)


def review_request(prompt: str) -> RequestReview:
    p = (prompt or "").lower()
    reasons = []

    build_words = [
        "build", "implement", "write code", "change the code", "edit",
        "fix the bug", "update the file", "create file", "delete",
        "run build", "build apk", "publish apk"
    ]

    risky_words = [
        "gerald_bridge.py", "delete", "replace entire", "rewrite entire",
        "database", "production", "nginx", "systemctl", "api key",
        "env", "payment", "auth", "security"
    ]

    design_words = [
        "screen", "ui", "layout", "redesign", "button", "look",
        "screenshot", "home screen", "voice", "microphone"
    ]

    # Use exact phrase matching for APK intent (condition 3 from post-task spec)
    if _has_explicit_apk_phrase(prompt):
        intent = "apk_build"
        should_build_apk = True
    elif any(w in p for w in build_words):
        intent = "implementation"
        should_build_apk = False
    elif any(w in p for w in design_words):
        intent = "design_or_app_review"
        should_build_apk = False
    else:
        intent = "conversation_or_planning"
        should_build_apk = False

    risk = "low"
    if any(w in p for w in risky_words):
        risk = "high"
        reasons.append("Request touches risky/core system area.")
    elif intent in ["implementation", "apk_build"]:
        risk = "medium"
        reasons.append("Request may modify code or trigger build workflow.")

    should_delegate_to_claude = intent in ["implementation", "apk_build"]
    should_ask_approval = risk in ["medium", "high"] or should_delegate_to_claude

    if intent == "design_or_app_review":
        reasons.append("Design/UI requests should be reviewed and planned before coding.")
    if intent == "conversation_or_planning":
        reasons.append("No implementation required yet.")

    return RequestReview(
        intent=intent,
        risk=risk,
        should_ask_approval=should_ask_approval,
        should_delegate_to_claude=should_delegate_to_claude,
        should_build_apk=should_build_apk,
        reasons=reasons,
    )


def should_trigger_apk_build(
    user_request: str,
    returncode: int,
    files_changed: list,
    output: str,
    error: str,
    is_readonly: bool,
    auto_build: bool = False,
) -> bool:
    """
    Post-task gate: return True if and only if ALL conditions are met.

    1. returncode == 0          — Claude task exited successfully
    2. files_changed non-empty  — at least one file was actually modified
    3. explicit APK phrase OR auto_build — user_request contains one of APK_BUILD_PHRASES,
                                           or the caller has enabled auto-build mode
    4. no provider/rate errors  — output/error contain no auth/rate/session failure signals
    5. not readonly             — task was an implementation task, not investigation-only
    """
    if returncode != 0:
        return False
    if not files_changed:
        return False
    if not (_has_explicit_apk_phrase(user_request) or auto_build):
        return False
    if _has_provider_error(output, error):
        return False
    if is_readonly:
        return False
    return True


def trigger_apk_build_if_warranted(
    user_request: str,
    returncode: int,
    files_changed: list,
    output: str,
    error: str,
    is_readonly: bool,
    project_path: str = "/opt/Gerald/gerald_app",
    flavor: str = "debug",
    auto_build: bool = False,
) -> bool:
    """
    Trigger a background APK build via the verified build system when all conditions pass.

    Uses build_verifier.run_build_verification_sequence — never a raw subprocess call.
    The build runs in a daemon thread so callers are not blocked.

    Returns True if the build was triggered, False if any condition was not met or
    if the build module could not be loaded.
    """
    if not should_trigger_apk_build(
        user_request, returncode, files_changed, output, error, is_readonly, auto_build
    ):
        return False

    try:
        import build_verifier  # imported lazily to avoid circular deps at module load
        t = threading.Thread(
            target=build_verifier.run_build_verification_sequence,
            args=(project_path, flavor),
            daemon=True,
        )
        t.start()
        return True
    except Exception:
        return False


def format_review_for_prompt(review: RequestReview) -> str:
    return f"""
REQUEST REVIEW:
- intent: {review.intent}
- risk: {review.risk}
- should_ask_approval: {review.should_ask_approval}
- should_delegate_to_claude: {review.should_delegate_to_claude}
- should_build_apk: {review.should_build_apk}
- reasons: {', '.join(review.reasons) if review.reasons else 'none'}
"""


# ─── Review Agent V1 ──────────────────────────────────────────────────────────

_GIT_ROOT = "/opt/Gerald"
_FLUTTER_WORKER = "/opt/Gerald/gerald_app"
_BACKEND_WORKER = "/opt/Gerald"

# Minimum output length to consider Claude's response non-trivial
_MIN_OUTPUT_CHARS = 30

# Flutter app path prefix relative to the git root
_FLUTTER_APP_PREFIX = "gerald_app/"

# Phrases in task_text that explicitly permit Flutter/frontend file changes on a backend task
_FLUTTER_ALLOW_PHRASES = [
    "allow flutter",
    "allow frontend",
    "allow gerald_app",
    "flutter changes allowed",
    "frontend changes allowed",
]


# File that stores the pre-task dirty-file snapshot for task-local change tracking.
_TASK_BASELINE_FILE = _Path("/opt/Gerald/gerald_task_baseline.json")


def _sha256_file(filepath: str, git_root: str = _GIT_ROOT) -> Optional[str]:
    """Return SHA256 hex digest of a file, or None if unreadable."""
    abs_path = os.path.join(git_root, filepath)
    try:
        with open(abs_path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        return None


def _compute_dirty_hashes(git_root: str) -> dict:
    """Return {filepath: sha256} for all currently-dirty files."""
    return {f: _sha256_file(f, git_root) for f in _git_changed_files(git_root)}


def snapshot_pre_task_files(git_root: str = _GIT_ROOT) -> dict:
    """Capture SHA256 hashes of all currently-dirty files before a task runs.

    Persists to _TASK_BASELINE_FILE. review_task_result() compares post-task
    hashes against this baseline so a file that was already dirty is still
    flagged as 'changed during the task' when its content actually changed.
    """
    hashes = _compute_dirty_hashes(git_root)
    try:
        _TASK_BASELINE_FILE.write_text(
            _json.dumps({"hashes": hashes, "git_root": git_root}),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[review] snapshot_pre_task_files error: {e}")
    return hashes


def _load_task_baseline() -> dict:
    """Load the pre-task hash snapshot. Returns empty dict if no baseline exists."""
    try:
        data = _json.loads(_TASK_BASELINE_FILE.read_text(encoding="utf-8"))
        if "hashes" in data:
            return data["hashes"]
        # Legacy format (list of filenames) — return empty to force full diff
        return {}
    except Exception:
        return {}


def _get_task_local_changes(git_root: str, baseline_hashes: dict) -> list:
    """Return files whose content changed during the current task.

    A file is included if it is currently dirty AND either:
      - it was not in the baseline (newly modified), or
      - its SHA256 hash differs from the baseline value (content changed).

    Files that were dirty before the task but whose hash is unchanged are
    excluded — they were already dirty and were not touched by this task.
    """
    current_hashes = _compute_dirty_hashes(git_root)
    changed = []
    for filepath, current_sha in current_hashes.items():
        if filepath not in baseline_hashes:
            changed.append(filepath)
        elif current_sha != baseline_hashes[filepath]:
            changed.append(filepath)
    return sorted(changed)


def _git_diff_file(git_root: str, filepath: str) -> str:
    """Return the unified diff for a single file."""
    try:
        r = subprocess.run(
            ["git", "diff", "--", filepath],
            cwd=git_root, capture_output=True, text=True, timeout=15,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _is_backend_only_task(task_text: str, worker_dir: str) -> bool:
    """Return True when the task is scoped to the backend root (no Flutter edits expected)."""
    if "backend-only" in (task_text or "").lower():
        return True
    return os.path.abspath(worker_dir) == os.path.abspath(_BACKEND_WORKER)


def _flutter_changes_explicitly_allowed(task_text: str) -> bool:
    lower = (task_text or "").lower()
    return any(phrase in lower for phrase in _FLUTTER_ALLOW_PHRASES)


def _flutter_paths_in_files(files: list) -> list:
    return [f for f in (files or []) if f.startswith(_FLUTTER_APP_PREFIX)]


def _git_diff_stat(git_root: str) -> str:
    """Return git diff --stat output (unstaged changes vs HEAD)."""
    try:
        r = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=git_root, capture_output=True, text=True, timeout=15
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _git_changed_files(git_root: str) -> list:
    """Return list of files with unstaged changes relative to the git root."""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=git_root, capture_output=True, text=True, timeout=15
        )
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _is_runtime_artifact(filename: str) -> bool:
    """Return True if filename is a known runtime state file that must never trigger scope violations."""
    base = os.path.basename(filename)
    if base == "active_task.json":
        return True
    if base.startswith("gerald_outbox_") and base.endswith(".json"):
        return True
    return False


def _is_in_contract_scope(filepath: str, allowed_paths) -> bool:
    """Return True if filepath is covered by any entry in the contract's likely_files."""
    for allowed in (allowed_paths or []):
        allowed = (allowed or "").strip()
        if not allowed:
            continue
        if filepath == allowed:
            return True
        # Suffix match: planner may list "app.js" when the real path is "dashboard/app.js"
        if filepath.endswith("/" + allowed):
            return True
        # Directory prefix: "dashboard" covers "dashboard/index.html"
        if filepath.startswith(allowed.rstrip("/") + "/"):
            return True
    return False


def _scope_prefix(worker_dir: str) -> Optional[str]:
    """Return the git-root-relative prefix expected for worker_dir, or None for root."""
    abs_worker = os.path.abspath(worker_dir)
    abs_root = os.path.abspath(_GIT_ROOT)
    if abs_worker == abs_root:
        return None  # backend root — all files in scope
    try:
        rel = os.path.relpath(abs_worker, abs_root)
        return rel.rstrip("/") + "/"
    except ValueError:
        return None


def review_task_result(
    task_text: str,
    project_name: str,
    worker_dir: str,
    claude_output: str,
    files_changed: list,
    returncode: int,
    error: str = "",
    edit_summary: Optional[dict] = None,
    contract: Optional[dict] = None,
) -> dict:
    """
    Review Agent V1: validate a completed Claude Code implementation task.

    Checks (in order):
      1. Non-zero exit code → FAIL
      2. Provider / API rate-limit error in output or stderr → FAIL
      3. No files changed (neither diff-tracker nor git agree anything changed) → FAIL
      4. Files changed outside the expected scope → FAIL
         Scope is sourced from the task contract's likely_files first;
         worker_dir-based prefix is used only when no contract is provided.
      5. Claude produced no meaningful output (silent failure) → FAIL

    Returns:
      {
        "verdict": "PASS" | "FAIL",
        "reasons": ["..."],          # empty on PASS
        "git_stat": "...",           # git diff --stat output
        "git_changed_files": [...],  # file paths from git diff --name-only
      }

    This function is read-only and never modifies task state.
    The caller (gerald_bridge.py) decides whether to mark the task complete.
    """
    reasons: list = []
    edit_summary = edit_summary or {}

    # 1. Non-zero return code
    if returncode != 0:
        reasons.append(
            f"Claude Code exited with non-zero return code ({returncode})."
        )

    # 2. Provider / rate-limit errors
    if _has_provider_error(claude_output, error):
        reasons.append(
            "Provider or API rate-limit error detected in Claude's output."
        )

    # 3. No changes detected
    # Combine files_changed (lib/ subset) with edit_summary totals
    summary_files = (
        edit_summary.get("files_changed", [])
        + edit_summary.get("files_added", [])
        + edit_summary.get("files_deleted", [])
    )
    diff_tracker_found_changes = bool(summary_files) or bool(
        edit_summary.get("total_lines_added", 0)
    ) or bool(edit_summary.get("total_lines_removed", 0))

    git_root = _GIT_ROOT
    git_stat = _git_diff_stat(git_root)
    # Task-local: use SHA256 hashes to detect content changes even for files
    # that were already dirty before the task started.
    _baseline_hashes = _load_task_baseline()
    git_changed = _get_task_local_changes(git_root, _baseline_hashes)

    any_lib_changes = bool(files_changed)
    any_git_changes = bool(git_changed)

    if not diff_tracker_found_changes and not any_lib_changes and not any_git_changes:
        reasons.append("No files were changed — Claude appears to have made no edits.")

    # 4. Files changed outside expected scope
    # Allowed scope is sourced from the task contract's likely_files.
    # Worker-dir prefix (e.g. "gerald_app/") is used as a fallback when no contract is present.
    scope_prefix = _scope_prefix(worker_dir)
    contract_likely = (contract or {}).get("likely_files", [])
    if scope_prefix is not None:
        # Only check when worker_dir is a subdirectory (non-backend tasks)
        for f in git_changed:
            if _is_runtime_artifact(f):
                continue
            if f.startswith(scope_prefix):
                continue
            # File is outside worker_dir prefix — check if the contract explicitly allows it
            if _is_in_contract_scope(f, contract_likely):
                continue
            allowed_desc = (
                f"contract allows: {contract_likely}" if contract_likely
                else f"worker: {scope_prefix.rstrip('/')}"
            )
            reasons.append(
                f"File changed outside expected scope ({allowed_desc}): {f}"
            )

    # 4b. Backend-only task must not touch Flutter (gerald_app/) files
    if _is_backend_only_task(task_text, worker_dir) and not _flutter_changes_explicitly_allowed(task_text):
        flutter_hits = list(set(_flutter_paths_in_files(files_changed) + _flutter_paths_in_files(git_changed)))
        if flutter_hits:
            reasons.append(
                f"Backend-only task modified Flutter (gerald_app/) paths: {flutter_hits}"
            )

    # 5. Silent failure — no meaningful output
    if not (claude_output or "").strip() or len((claude_output or "").strip()) < _MIN_OUTPUT_CHARS:
        reasons.append(
            "Claude produced no meaningful output (possible silent failure or provider error)."
        )

    verdict = "FAIL" if reasons else "PASS"

    # Collect per-file unified diffs for all task-local changes.
    file_diffs = {f: _git_diff_file(git_root, f) for f in git_changed}

    print(
        f"[review-agent-v1] verdict={verdict} project={project_name} "
        f"worker={worker_dir} reasons={reasons} changed={git_changed}"
    )

    return {
        "verdict": verdict,
        "reasons": reasons,
        "git_stat": git_stat,
        "git_changed_files": git_changed,
        "file_diffs": file_diffs,
    }


# ─── Inline tests ─────────────────────────────────────────────────────────────

def _test_backend_only_flutter_fail():
    """Backend-only task with a gerald_app/ file in files_changed must return FAIL."""
    result = review_task_result(
        task_text="Fix the backend API endpoint (backend-only)",
        project_name="CommuteCoder",
        worker_dir="/opt/Gerald",
        claude_output="Fixed the endpoint successfully with all the required changes.",
        files_changed=["gerald_app/lib/screens/home_screen.dart"],
        returncode=0,
        error="",
    )
    assert result["verdict"] == "FAIL", (
        f"Expected FAIL for backend-only task touching gerald_app/, got {result['verdict']}: {result['reasons']}"
    )
    flutter_reason = any("gerald_app/" in r for r in result["reasons"])
    assert flutter_reason, (
        f"Expected a reason mentioning gerald_app/, got: {result['reasons']}"
    )
    print("[test] _test_backend_only_flutter_fail PASSED")


if __name__ == "__main__":
    _test_backend_only_flutter_fail()
    print("All inline tests passed.")
