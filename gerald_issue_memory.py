"""
Gerald Reasoning Layer V2 — Issue Memory

Tracks detected failures and Matt's manual corrections persistently.
Flags the same substantive issue on its 2nd+ occurrence as a recurring failure
and returns an alert dict so the caller can notify Matt.

Does NOT auto-patch or change any code. Notify only.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MEMORY_FILE = Path("/opt/Gerald/gerald_issue_memory.json")
MAX_OCCURRENCES_STORED = 50  # cap per issue to avoid unbounded growth

# Phrases that strongly suggest Matt is correcting Gerald
_CORRECTION_SIGNALS = [
    "you did this again",
    "stop doing",
    "i told you",
    "same mistake",
    "you keep",
    "again you",
    "didn't i say",
    "i already told you",
    "you already",
    "same error",
    "same problem",
    "same issue",
    "again with",
    "once again",
    "still doing",
    "doing it again",
    "this again",
    "already told",
    "keep making",
    "keep doing",
    "repeated this",
    "you repeated",
    "how many times",
    "told you not to",
    "warned you",
    "every time you",
]


# ─── Persistence ───────────────────────────────────────────────────────────────

def _load() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"issues": {}}


def _save(data: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── Fingerprinting ────────────────────────────────────────────────────────────

def _fingerprint(text: str) -> str:
    """Produce a stable short key from a text snippet.

    The key is: first 40 chars of normalized text + '_' + 8-char SHA-1 digest.
    This keeps keys human-readable while remaining collision-resistant.
    """
    normalized = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
    collapsed = " ".join(normalized.split())
    short = collapsed[:80]
    digest = hashlib.sha1(short.encode()).hexdigest()[:8]
    return f"{collapsed[:40].rstrip()}_{digest}"


# ─── Detection ─────────────────────────────────────────────────────────────────

def is_correction(text: str) -> bool:
    """Return True if the user text contains correction/complaint signals."""
    lower = text.lower()
    return any(signal in lower for signal in _CORRECTION_SIGNALS)


# ─── Recording ─────────────────────────────────────────────────────────────────

def check_correction(user_text: str, project: str) -> Optional[dict]:
    """
    Call this when Matt sends a message.  If it looks like a correction,
    record it as an issue and return an alert dict if this is the 2nd+
    occurrence of the same complaint.  Returns None if not a correction or
    if it is a first-time complaint.
    """
    if not is_correction(user_text):
        return None
    fp = _fingerprint(user_text)
    description = user_text[:200].strip()
    return _record(fp, description, project, "user_correction")


def record_task_failure(error_text: str, task: str, project: str) -> Optional[dict]:
    """
    Call this when a task ends with an error.  Fingerprints the error message
    so that repeated identical failures are detected.  Returns an alert dict
    on the 2nd+ occurrence; None otherwise.
    """
    if not error_text:
        return None
    fp = _fingerprint(error_text[:200])
    description = f"Task failure: {error_text[:120]}"
    return _record(fp, description, project, "task_failure", task=task)


# ─── Internal ──────────────────────────────────────────────────────────────────

def _record(fingerprint: str, description: str, project: str,
            issue_type: str, task: str = "") -> Optional[dict]:
    """Record one occurrence; return an alert dict when count reaches 2 or more."""
    data = _load()
    issues = data.setdefault("issues", {})
    now = datetime.now(timezone.utc).isoformat()

    if fingerprint not in issues:
        issues[fingerprint] = {
            "description": description,
            "project": project,
            "type": issue_type,
            "occurrences": [],
            "first_seen": now,
            "last_seen": now,
            "is_recurring": False,
        }

    entry = issues[fingerprint]
    occurrences = entry["occurrences"]

    # Cap stored occurrences so the file does not grow without bound
    if len(occurrences) < MAX_OCCURRENCES_STORED:
        occurrences.append({"timestamp": now, "task": task[:200]})

    entry["last_seen"] = now
    count = len(occurrences)

    alert: Optional[dict] = None
    if count >= 2:
        if not entry.get("is_recurring"):
            entry["is_recurring"] = True
        alert = {
            "fingerprint": fingerprint,
            "description": description,
            "project": project,
            "type": issue_type,
            "occurrence_count": count,
            "first_seen": entry["first_seen"],
            "last_seen": now,
        }

    _save(data)
    return alert


# ─── Query helpers ─────────────────────────────────────────────────────────────

def get_all_issues() -> dict:
    """Return the full raw issue memory dict."""
    return _load()


def get_recurring_issues(project: Optional[str] = None) -> list:
    """Return all recurring issues, optionally filtered to one project."""
    data = _load()
    result = []
    for fp, issue in data.get("issues", {}).items():
        if issue.get("is_recurring"):
            if project is None or issue.get("project") == project:
                result.append({**issue, "fingerprint": fp})
    result.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
    return result
