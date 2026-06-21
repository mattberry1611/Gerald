"""
Auditor Integrity Enforcer — post-outcome hooks that enforce correctness
constraints the auditor may fail to uphold due to parse errors, review
conflicts, or out-of-scope file changes.

Called from gerald_session_state.log_event() after every outcome event.
Does NOT import from gerald_bridge.py or gerald_session_state.py.

Three independent guards:
  handle_audit_unknown_verdict(project)  — UNKNOWN verdict → FAILED
  handle_review_fail_enforcement(project) — review FAIL + audit COMPLETE → PARTIAL
  handle_scope_check(project)            — forbidden files changed → PARTIAL/FAILED
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/opt/Gerald")
_TASK_STATE_FILE = BASE / "active_task.json"
_STATUS_FILE = BASE / "gerald_status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_task() -> dict:
    if not _TASK_STATE_FILE.exists():
        return {}
    try:
        return json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_task(state: dict) -> None:
    try:
        _TASK_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[auditor_integrity] write_task error: {e}")


def _write_status(status: str, detail: str) -> None:
    try:
        _STATUS_FILE.write_text(
            json.dumps({"status": status, "detail": detail, "updated": _now()}),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[auditor_integrity] write_status error: {e}")


def _patch_outbox(project: str, patch: dict) -> None:
    """Merge patch into both the global and project-specific outbox files."""
    safe = (project or "CommuteCoder").replace(" ", "_").replace("/", "_").replace("\\", "_")
    for path in [BASE / "gerald_outbox.json", BASE / f"gerald_outbox_{safe}.json"]:
        try:
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                existing.update(patch)
                path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[auditor_integrity] patch_outbox {path.name}: {e}")


def _is_forbidden_file(filepath: str, forbidden_patterns: list) -> bool:
    """Return True if filepath matches any forbidden pattern from the contract."""
    import fnmatch
    for pattern in forbidden_patterns:
        # fnmatch: * matches any chars including / on Unix — handles "gerald_app/*"
        if fnmatch.fnmatch(filepath, pattern):
            return True
        # Prefix match: "gerald_app/*" → prefix "gerald_app/"
        prefix = pattern.rstrip("*")
        if not prefix.endswith("/"):
            prefix += "/"
        if filepath.startswith(prefix):
            return True
    return False


# ── Guard 1: UNKNOWN verdict → FAILED ─────────────────────────────────────────

def handle_audit_unknown_verdict(project: str) -> bool:
    """
    When audit_task_contract() raises an exception (e.g. JSON parse failure),
    the exception handler stores verdict="UNKNOWN". This guard upgrades UNKNOWN
    to FAILED so the dashboard never shows an indeterminate verdict and the
    constraint "audit parse failure cannot be COMPLETE" is visibly enforced.

    Runs on every outcome event (not just completed), because UNKNOWN verdicts
    land in the contract_failed path, not the completed path.

    Returns True if a correction was applied.
    """
    state = _read_task()
    audit = state.get("audit") or {}
    if audit.get("verdict") != "UNKNOWN":
        return False

    now = _now()
    notes = audit.get("notes", "audit result indeterminate")
    audit["verdict"] = "FAILED"
    audit["notes"] = f"Integrity: UNKNOWN verdict upgraded to FAILED — {notes}"
    state["audit"] = audit
    state["updated"] = now

    _write_task(state)
    _patch_outbox(project, {"audit_verdict": "FAILED"})
    print(f"[auditor_integrity] UNKNOWN → FAILED: {notes[:80]}")
    return True


# ── Guard 2: review FAIL + audit COMPLETE → PARTIAL ───────────────────────────

def handle_review_fail_enforcement(project: str) -> bool:
    """
    If audit verdict is COMPLETE but review_verdict is FAIL, downgrade to PARTIAL.

    The auditor is authoritative (V1.9.1) and CAN override a review FAIL when
    valid parsed evidence supports COMPLETE. However, a review FAIL signals a
    concern the auditor's requirements list may not have covered (e.g. scope
    violations). Defaulting to PARTIAL preserves partial credit while requiring
    explicit re-verification before marking COMPLETE.

    Only fires when stage=completed. Returns True if a correction was applied.
    """
    state = _read_task()
    if state.get("stage") not in ("completed",):
        return False

    audit = state.get("audit") or {}
    if audit.get("verdict") != "COMPLETE":
        return False
    if audit.get("review_verdict") != "FAIL":
        return False

    now = _now()
    reasons = audit.get("review_reasons", [])
    reason_text = "; ".join(str(r)[:80] for r in reasons[:3]) if reasons else "review rejected"

    audit["verdict"] = "PARTIAL"
    missing = audit.setdefault("missing", [])
    missing.insert(0, f"Review FAIL not overridden by audit evidence: {reason_text}")
    audit["notes"] = (
        f"Integrity: review FAIL conflicts with COMPLETE audit — downgraded to PARTIAL. "
        f"Review reason: {reason_text}"
    )
    state["audit"] = audit
    state["stage"] = "partial"
    state["detail"] = f"Review FAIL enforcement: {reason_text[:120]}"
    state["updated"] = now

    _write_task(state)
    _write_status("idle", f"Task partial — review FAIL: {reason_text[:80]}")
    _patch_outbox(project, {
        "status": "partial",
        "audit_verdict": "PARTIAL",
        "audit_notes": audit["notes"],
    })
    print(f"[auditor_integrity] review FAIL enforcement: COMPLETE → PARTIAL ({reason_text[:60]})")
    return True


# ── Guard 3: forbidden/out-of-scope files → PARTIAL or FAILED ─────────────────

def handle_scope_check(project: str) -> bool:
    """
    If files_changed includes paths matching contract.forbidden_files, downgrade
    the task verdict: PARTIAL when some changed files were allowed, FAILED when
    ALL changed files were forbidden (nothing legitimate was accomplished).

    Runs after review FAIL enforcement so it may augment an already-downgraded
    verdict. Returns True if a correction was applied.
    """
    state = _read_task()
    contract = state.get("contract") or {}
    forbidden_patterns = contract.get("forbidden_files", [])

    if not forbidden_patterns:
        return False

    files_changed = state.get("files_changed", [])
    if not files_changed:
        return False

    forbidden_changed = [
        f for f in files_changed
        if _is_forbidden_file(f, forbidden_patterns)
    ]
    if not forbidden_changed:
        return False

    now = _now()
    audit = state.get("audit") or {}

    allowed_changed = [f for f in files_changed if f not in forbidden_changed]
    new_verdict = "FAILED" if not allowed_changed else "PARTIAL"
    forbidden_text = ", ".join(forbidden_changed[:5])
    if len(forbidden_changed) > 5:
        forbidden_text += f" (+{len(forbidden_changed) - 5} more)"

    missing = audit.setdefault("missing", [])
    scope_note = f"Out-of-scope files changed ({len(forbidden_changed)}): {forbidden_text}"
    if scope_note not in missing:
        missing.insert(0, scope_note)
    audit["verdict"] = new_verdict
    audit["notes"] = (
        f"Scope violation: {len(forbidden_changed)} forbidden file(s) modified — {forbidden_text[:100]}"
    )
    state["audit"] = audit
    new_stage = "contract_failed" if new_verdict == "FAILED" else "partial"
    state["stage"] = new_stage
    state["detail"] = f"Scope check: {len(forbidden_changed)} forbidden file(s): {forbidden_text[:100]}"
    state["updated"] = now

    _write_task(state)
    _write_status(
        "error" if new_verdict == "FAILED" else "idle",
        f"Scope violation: {forbidden_text[:80]}",
    )
    _patch_outbox(project, {
        "status": new_stage,
        "audit_verdict": new_verdict,
        "audit_notes": audit["notes"],
    })
    print(
        f"[auditor_integrity] SCOPE CHECK: {new_verdict} — "
        f"{len(forbidden_changed)} forbidden file(s): {forbidden_text[:60]}"
    )
    return True
