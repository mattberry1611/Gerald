"""
Command Evidence Capture — permanent log capture for verification commands.

Runs a shell command, redirects stdout+stderr to a log file, writes the exit
code to a companion .exit file, and returns structured evidence that can be
attached to audit results.
"""
import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional


_EXCERPT_LINES = 50  # head + tail lines included in the excerpt


def run_with_evidence(
    command: str,
    cwd: str,
    log_path: str,
    exit_path: str,
    timeout: int = 300,
) -> Dict:
    """
    Run *command* (shell string) in *cwd*, capturing all output to *log_path*
    and the integer exit code to *exit_path*.

    Returns a dict with:
        command       — the command string that was run
        cwd           — working directory used
        exit_code     — integer exit code (or -1 on timeout/error)
        log_path      — absolute path to the full log file
        exit_path     — absolute path to the exit-code file
        passed        — True if exit_code == 0
        excerpt       — first+last _EXCERPT_LINES lines of the log
        timestamp     — ISO-8601 UTC timestamp of when the run started
        error         — set only if the runner itself raised an exception
    """
    started = datetime.now(timezone.utc).isoformat()
    log_path = os.path.abspath(log_path)
    exit_path = os.path.abspath(exit_path)

    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        exit_code = -1
        with open(log_path, "a", encoding="utf-8") as log_fh:
            log_fh.write(f"\n[command_evidence_capture] TIMEOUT after {timeout}s\n")
    except Exception as exc:
        exit_code = -1
        with open(log_path, "w", encoding="utf-8") as log_fh:
            log_fh.write(f"[command_evidence_capture] ERROR: {exc}\n")
        return {
            "command": command,
            "cwd": cwd,
            "exit_code": exit_code,
            "log_path": log_path,
            "exit_path": exit_path,
            "passed": False,
            "excerpt": f"Runner error: {exc}",
            "timestamp": started,
            "error": str(exc),
        }

    # Write exit code file
    with open(exit_path, "w", encoding="utf-8") as ef:
        ef.write(str(exit_code) + "\n")

    excerpt = _make_excerpt(log_path)

    return {
        "command": command,
        "cwd": cwd,
        "exit_code": exit_code,
        "log_path": log_path,
        "exit_path": exit_path,
        "passed": exit_code == 0,
        "excerpt": excerpt,
        "timestamp": started,
    }


def read_evidence(log_path: str, exit_path: str) -> Optional[Dict]:
    """
    Re-read previously captured evidence from log and exit files.
    Returns None if either file does not exist.
    """
    if not os.path.exists(log_path) or not os.path.exists(exit_path):
        return None
    try:
        with open(exit_path, encoding="utf-8") as ef:
            exit_code = int(ef.read().strip())
    except (ValueError, OSError):
        return None

    return {
        "log_path": os.path.abspath(log_path),
        "exit_path": os.path.abspath(exit_path),
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "excerpt": _make_excerpt(log_path),
    }


def _make_excerpt(log_path: str, n: int = _EXCERPT_LINES) -> str:
    """Return up to n head lines + n tail lines from the log file."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return "(log not readable)"

    if not lines:
        return "(empty log)"

    if len(lines) <= n * 2:
        return "".join(lines)

    head = lines[:n]
    tail = lines[-n:]
    omitted = len(lines) - n * 2
    return (
        "".join(head)
        + f"\n... [{omitted} lines omitted] ...\n\n"
        + "".join(tail)
    )
