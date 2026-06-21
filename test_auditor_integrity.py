#!/usr/bin/env python3
"""
Auditor Integrity Validation — simulates audit parse failure and review FAIL
to confirm the corrected workflow produces correct status transitions.

Run: python3 /opt/Gerald/test_auditor_integrity.py
"""
import json
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "CommuteCoder"
_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_failures = []


def _now():
    return datetime.now(timezone.utc).isoformat()


def _assert(label, condition, got, expected):
    if condition:
        print(f"    {_PASS}  {label}: {got!r}")
    else:
        msg = f"    {_FAIL}  {label}: expected {expected!r}, got {got!r}"
        print(msg)
        _failures.append(msg)


# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("AUDITOR INTEGRITY SIMULATION TEST")
print("=" * 65)

# Use a temp directory so tests don't need root write access to /opt/Gerald
tmpdir = Path(tempfile.mkdtemp(prefix="gerald_test_"))

try:
    import auditor_integrity as _ai_mod

    # Monkey-patch module-level path constants so functions read/write to tmpdir
    _ai_mod.BASE = tmpdir
    _ai_mod._TASK_STATE_FILE = tmpdir / "active_task.json"
    _ai_mod._STATUS_FILE = tmpdir / "gerald_status.json"

    # Re-import functions to pick up patched globals via closure
    from auditor_integrity import (
        handle_audit_unknown_verdict,
        handle_review_fail_enforcement,
        handle_scope_check,
    )

    def _write_task(state):
        (tmpdir / "active_task.json").write_text(json.dumps(state, indent=2), "utf-8")

    def _write_outbox(project, data):
        safe = project.replace(" ", "_")
        (tmpdir / f"gerald_outbox_{safe}.json").write_text(json.dumps(data, indent=2), "utf-8")

    def _read_task():
        return json.loads((tmpdir / "active_task.json").read_text("utf-8"))

    def _read_outbox(project):
        safe = project.replace(" ", "_")
        p = tmpdir / f"gerald_outbox_{safe}.json"
        return json.loads(p.read_text("utf-8")) if p.exists() else {}

    # ── TEST 1: Audit parse failure → UNKNOWN verdict upgraded to FAILED ──────
    print()
    print("TEST 1: Audit parse failure (UNKNOWN verdict → FAILED)")
    print("-" * 50)

    _write_task({
        "task": "Fix something in the backend",
        "project": PROJECT,
        "stage": "contract_failed",
        "audit": {
            "verdict": "UNKNOWN",
            "met": [],
            "missing": [],
            "missing_evidence": [],
            "notes": "Audit parse/execution failure — cannot confirm COMPLETE: Unterminated string starting at: line 1 column 512 (char 511)",
            "review_verdict": "PASS",
            "audited_at": _now(),
        },
        "files_changed": [],
        "updated": _now(),
    })
    _write_outbox(PROJECT, {"status": "contract_failed", "audit_verdict": "UNKNOWN", "project": PROJECT})

    corrected = handle_audit_unknown_verdict(PROJECT)
    task = _read_task()
    outbox = _read_outbox(PROJECT)
    verdict = task.get("audit", {}).get("verdict")
    is_complete = verdict == "COMPLETE"

    print(f"  Input:  audit.verdict=UNKNOWN, stage=contract_failed")
    print(f"  Output: audit.verdict={verdict!r}, stage={task.get('stage')!r}")
    print(f"  Outbox: audit_verdict={outbox.get('audit_verdict')!r}")
    print(f"  Notes:  {task.get('audit', {}).get('notes', '')[:80]!r}")
    _assert("Correction applied", corrected is True, corrected, True)
    _assert("verdict not COMPLETE", not is_complete, verdict, "not COMPLETE")
    _assert("verdict is FAILED", verdict == "FAILED", verdict, "FAILED")
    _assert("outbox patched", outbox.get("audit_verdict") == "FAILED", outbox.get("audit_verdict"), "FAILED")

    # ── TEST 2: review_verdict FAIL + audit COMPLETE → PARTIAL ────────────────
    print()
    print("TEST 2: review_verdict=FAIL with audit verdict=COMPLETE → PARTIAL")
    print("-" * 50)

    _write_task({
        "task": "Backend changes only",
        "project": PROJECT,
        "stage": "completed",
        "audit": {
            "verdict": "COMPLETE",
            "met": ["Requirement A met"],
            "missing": [],
            "missing_evidence": [],
            "notes": "All requirements satisfied",
            "review_verdict": "FAIL",
            "review_reasons": ["Files changed outside expected scope", "Flutter app files modified"],
            "audited_at": _now(),
        },
        "files_changed": ["lib/main.dart", "gerald_bridge.py"],
        "updated": _now(),
    })
    _write_outbox(PROJECT, {"status": "done", "audit_verdict": "COMPLETE", "project": PROJECT})

    corrected = handle_review_fail_enforcement(PROJECT)
    task = _read_task()
    outbox = _read_outbox(PROJECT)
    verdict = task.get("audit", {}).get("verdict")
    stage = task.get("stage")

    print(f"  Input:  audit.verdict=COMPLETE, review_verdict=FAIL")
    print(f"  Output: audit.verdict={verdict!r}, stage={stage!r}")
    print(f"  Outbox: status={outbox.get('status')!r}, audit_verdict={outbox.get('audit_verdict')!r}")
    print(f"  Notes:  {task.get('audit', {}).get('notes', '')[:80]!r}")
    print(f"  Missing[0]: {task.get('audit', {}).get('missing', ['none'])[0][:70]!r}")
    _assert("Correction applied", corrected is True, corrected, True)
    _assert("verdict not COMPLETE", verdict != "COMPLETE", verdict, "not COMPLETE")
    _assert("verdict is PARTIAL or FAILED", verdict in ("PARTIAL", "FAILED"), verdict, "PARTIAL or FAILED")
    _assert("stage is partial or contract_failed", stage in ("partial", "contract_failed"), stage, "partial or contract_failed")
    _assert("outbox status not done", outbox.get("status") != "done", outbox.get("status"), "not done")

    # ── TEST 3: Forbidden files changed (mix) → PARTIAL ───────────────────────
    print()
    print("TEST 3: Out-of-scope/forbidden files changed (some allowed) → PARTIAL")
    print("-" * 50)

    _write_task({
        "task": "Fix auditor backend logic only",
        "project": PROJECT,
        "stage": "completed",
        "contract": {
            "forbidden_files": ["gerald_app/*", "dashboard/*"],
        },
        "audit": {
            "verdict": "COMPLETE",
            "met": ["Backend logic fixed"],
            "missing": [],
            "missing_evidence": [],
            "notes": "All requirements met",
            "review_verdict": "PASS",
            "audited_at": _now(),
        },
        "files_changed": [
            "gerald_app/lib/providers/app_state.dart",
            "gerald_app/lib/screens/home_screen.dart",
            "verification_layer.py",         # allowed
        ],
        "updated": _now(),
    })
    _write_outbox(PROJECT, {"status": "done", "audit_verdict": "COMPLETE", "project": PROJECT})

    corrected = handle_scope_check(PROJECT)
    task = _read_task()
    outbox = _read_outbox(PROJECT)
    verdict = task.get("audit", {}).get("verdict")
    stage = task.get("stage")
    missing = task.get("audit", {}).get("missing", [])

    print(f"  Input:  2 forbidden (gerald_app/*) + 1 allowed file changed")
    print(f"  Output: audit.verdict={verdict!r}, stage={stage!r}")
    print(f"  Outbox: status={outbox.get('status')!r}, audit_verdict={outbox.get('audit_verdict')!r}")
    print(f"  Missing[0]: {missing[0][:70] if missing else 'none'!r}")
    _assert("Correction applied", corrected is True, corrected, True)
    _assert("verdict not COMPLETE", verdict != "COMPLETE", verdict, "not COMPLETE")
    _assert("verdict is PARTIAL (some allowed files)", verdict == "PARTIAL", verdict, "PARTIAL")
    _assert("stage is partial", stage == "partial", stage, "partial")
    _assert("missing contains scope note", any("Out-of-scope" in str(m) or "forbidden" in str(m).lower() for m in missing), bool(missing), True)

    # ── TEST 4: ALL files forbidden → FAILED ──────────────────────────────────
    print()
    print("TEST 4: ALL changed files forbidden → FAILED (not PARTIAL)")
    print("-" * 50)

    _write_task({
        "task": "Backend only task",
        "project": PROJECT,
        "stage": "completed",
        "contract": {
            "forbidden_files": ["gerald_app/*", "dashboard/*"],
        },
        "audit": {
            "verdict": "COMPLETE",
            "met": [],
            "missing": [],
            "missing_evidence": [],
            "notes": "Looks complete",
            "review_verdict": "PASS",
            "audited_at": _now(),
        },
        "files_changed": [
            "gerald_app/lib/providers/app_state.dart",
            "dashboard/app.js",
        ],
        "updated": _now(),
    })
    _write_outbox(PROJECT, {"status": "done", "audit_verdict": "COMPLETE", "project": PROJECT})

    corrected = handle_scope_check(PROJECT)
    task = _read_task()
    outbox = _read_outbox(PROJECT)
    verdict = task.get("audit", {}).get("verdict")
    stage = task.get("stage")

    print(f"  Input:  ALL files_changed are forbidden (no allowed files at all)")
    print(f"  Output: audit.verdict={verdict!r}, stage={stage!r}")
    print(f"  Outbox: audit_verdict={outbox.get('audit_verdict')!r}")
    _assert("Correction applied", corrected is True, corrected, True)
    _assert("verdict is FAILED (all files forbidden)", verdict == "FAILED", verdict, "FAILED")
    _assert("stage is contract_failed", stage == "contract_failed", stage, "contract_failed")
    _assert("outbox audit_verdict is FAILED", outbox.get("audit_verdict") == "FAILED", outbox.get("audit_verdict"), "FAILED")

    # ── TEST 5: Legitimate COMPLETE → no change ────────────────────────────────
    print()
    print("TEST 5: Legitimate COMPLETE (PASS review, no scope violations) → unchanged")
    print("-" * 50)

    _write_task({
        "task": "Backend only task",
        "project": PROJECT,
        "stage": "completed",
        "contract": {
            "forbidden_files": ["gerald_app/*"],
        },
        "audit": {
            "verdict": "COMPLETE",
            "met": ["All backend requirements met"],
            "missing": [],
            "missing_evidence": [],
            "notes": "Task verified complete",
            "review_verdict": "PASS",
            "audited_at": _now(),
        },
        "files_changed": ["verification_layer.py", "auditor_integrity.py"],
        "updated": _now(),
    })
    _write_outbox(PROJECT, {"status": "done", "audit_verdict": "COMPLETE", "project": PROJECT})

    r1 = handle_audit_unknown_verdict(PROJECT)
    r2 = handle_review_fail_enforcement(PROJECT)
    r3 = handle_scope_check(PROJECT)
    task = _read_task()
    verdict = task.get("audit", {}).get("verdict")
    stage = task.get("stage")

    print(f"  Input:  audit=COMPLETE, review=PASS, no forbidden files changed")
    print(f"  Output: audit.verdict={verdict!r}, stage={stage!r}")
    _assert("No correction from unknown_verdict guard", r1 is False, r1, False)
    _assert("No correction from review_fail guard", r2 is False, r2, False)
    _assert("No correction from scope_check guard", r3 is False, r3, False)
    _assert("verdict still COMPLETE", verdict == "COMPLETE", verdict, "COMPLETE")
    _assert("stage still completed", stage == "completed", stage, "completed")

    # ── TEST 6: No contract forbidden_files → scope check skipped ─────────────
    print()
    print("TEST 6: No forbidden_files in contract → scope check is a no-op")
    print("-" * 50)

    _write_task({
        "task": "Anything goes",
        "project": PROJECT,
        "stage": "completed",
        "contract": {"forbidden_files": []},
        "audit": {"verdict": "COMPLETE", "review_verdict": "PASS"},
        "files_changed": ["gerald_app/lib/main.dart"],
        "updated": _now(),
    })

    r3 = handle_scope_check(PROJECT)
    task = _read_task()
    verdict = task.get("audit", {}).get("verdict")

    print(f"  Input:  forbidden_files=[], any files changed")
    print(f"  Output: audit.verdict={verdict!r}, correction={r3!r}")
    _assert("No correction (no forbidden patterns)", r3 is False, r3, False)
    _assert("verdict unchanged", verdict == "COMPLETE", verdict, "COMPLETE")

except Exception as ex:
    print(f"\n[ERROR] Test crashed: {ex}")
    import traceback
    traceback.print_exc()
    _failures.append(f"Test crashed: {ex}")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# ── Summary ────────────────────────────────────────────────────────────────────
print()
print("=" * 65)
if _failures:
    print(f"RESULT: {len(_failures)} test(s) FAILED")
    for f in _failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED — corrected workflow confirmed")
print("=" * 65)
