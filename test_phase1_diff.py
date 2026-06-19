"""
test_phase1_diff.py — Phase 1 review-and-diff simulation test.

Simulates a Claude file edit on a temporary Python file, runs
take_snapshot + compute_edit_summary, writes the result to a test outbox,
and verifies that all required Phase 1 fields are present and correct.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/opt/Gerald")
import gerald_diff_tracker

OUTBOX_PATH = "/tmp/gerald_test_outbox_phase1.json"

# 20+ line file so a 1-line change is <20% (low risk)
ORIGINAL_CODE = """\
\"\"\"sample module\"\"\"


def greet(name):
    print(f"Hello, {name}!")


def farewell(name):
    print(f"Goodbye, {name}!")


def count_up(n):
    for i in range(n):
        print(i)


def count_down(n):
    for i in range(n, 0, -1):
        print(i)


def no_op():
    pass
"""

# Small patch: 1 line changed out of 22 = ~4.5% — low risk
PATCHED_CODE_LOW = """\
\"\"\"sample module\"\"\"


def greet(name):
    print(f"Hi, {name}!")


def farewell(name):
    print(f"Goodbye, {name}!")


def count_up(n):
    for i in range(n):
        print(i)


def count_down(n):
    for i in range(n, 0, -1):
        print(i)


def no_op():
    pass
"""

# Large rewrite: many lines changed — high risk (>50%)
PATCHED_CODE_HIGH = """\
\"\"\"sample module — rewritten\"\"\"
import logging

log = logging.getLogger(__name__)


def greet(name, formal=False):
    msg = f"Good day, {name}." if formal else f"Hi there, {name}! Welcome!"
    log.info(msg)
    print(msg)
    return msg


def farewell(name, formal=False):
    msg = f"Farewell, {name}." if formal else f"See you later, {name}. Take care!"
    log.info(msg)
    print(msg)
    return msg


def count_up(n, step=1):
    for i in range(0, n, step):
        print(i)


def count_down(n, step=1):
    for i in range(n, 0, -step):
        print(i)


def both(name, formal=False):
    greet(name, formal)
    farewell(name, formal)


def no_op():
    pass
"""


def run_test(label: str, original: str, patched: str, expected_risk: str):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory(prefix="gerald_test_") as tmpdir:
        # Write a temp Python file so _collect_files picks it up
        test_file = Path(tmpdir) / "sample.py"
        test_file.write_text(original, encoding="utf-8")

        # Override extension detection by temporarily pointing at /opt/Gerald root pattern
        # Patch _extensions_for to include .py for any directory during test
        original_fn = gerald_diff_tracker._extensions_for
        gerald_diff_tracker._extensions_for = lambda d: (".py",)

        task_id = f"test-phase1-{label.lower().replace(' ', '-')}"
        snapshot = gerald_diff_tracker.take_snapshot(tmpdir, task_id)

        print(f"[snapshot] captured {len(snapshot['files'])} file(s)")
        print(f"[snapshot] backup files: {snapshot.get('backups', [])}")

        # Verify backup file was created
        backups = snapshot.get("backups", [])
        assert len(backups) >= 1, f"Expected at least 1 backup, got {backups}"
        backup_path = Path(backups[0])
        assert backup_path.exists(), f"Backup file not found: {backup_path}"
        assert backup_path.read_text(encoding="utf-8") == original, "Backup content mismatch"
        print(f"[OK] Backup file created and content matches original: {backup_path}")

        # Simulate Claude editing the file
        test_file.write_text(patched, encoding="utf-8")
        print(f"[sim] File patched to simulate Claude edit")

        edit_summary = gerald_diff_tracker.compute_edit_summary(snapshot)

        gerald_diff_tracker._extensions_for = original_fn  # restore

        print(f"[summary] {edit_summary['summary']}")
        print(f"[risk] overall_risk_level = {edit_summary['overall_risk_level']}")
        print(f"[lines] +{edit_summary['total_lines_added']} -{edit_summary['total_lines_removed']}")

        for rel, info in edit_summary["diffs"].items():
            print(f"  [{rel}] type={info['type']}, risk={info['risk_level']}, "
                  f"+{info['lines_added']} -{info['lines_removed']}")

        # Assertions
        assert edit_summary["files_changed"], "Expected files_changed to be non-empty"
        assert "overall_risk_level" in edit_summary, "Missing overall_risk_level"
        assert edit_summary["overall_risk_level"] == expected_risk, (
            f"Expected risk={expected_risk}, got {edit_summary['overall_risk_level']}"
        )
        for rel, info in edit_summary["diffs"].items():
            assert "risk_level" in info, f"Missing risk_level in diff for {rel}"
            assert "type" in info, f"Missing type in diff for {rel}"
            assert info["type"] in ("patch", "rewrite", "added", "deleted"), \
                f"Unexpected type: {info['type']}"

        # Build outbox payload (mirrors what run_claude_code_worker does)
        outbox_data = {
            "task": f"Simulate Claude edit ({label})",
            "project": "CommuteCoder",
            "status": "done",
            "returncode": 0,
            "output": f"Simulated edit complete. Risk level: {edit_summary['overall_risk_level']}",
            "error": "",
            "edit_summary": edit_summary,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }

        with open(OUTBOX_PATH, "w", encoding="utf-8") as f:
            json.dump(outbox_data, f, indent=2)

        print(f"[OK] Outbox written to {OUTBOX_PATH}")

        # Verify outbox
        with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert "edit_summary" in loaded, "edit_summary missing from outbox"
        es = loaded["edit_summary"]
        assert "files_changed" in es
        assert "total_lines_added" in es
        assert "total_lines_removed" in es
        assert "overall_risk_level" in es
        assert "diffs" in es
        assert "summary" in es
        for rel, info in es["diffs"].items():
            assert "type" in info
            assert "risk_level" in info
            assert "lines_added" in info
            assert "lines_removed" in info

        print(f"[OK] Outbox verified — all Phase 1 fields present")
        print(f"[PASS] {label}")
        return True


if __name__ == "__main__":
    failures = []

    try:
        run_test("low-risk patch", ORIGINAL_CODE, PATCHED_CODE_LOW, "low")
    except AssertionError as e:
        print(f"[FAIL] low-risk patch: {e}")
        failures.append("low-risk patch")

    try:
        run_test("high-risk rewrite", ORIGINAL_CODE, PATCHED_CODE_HIGH, "high")
    except AssertionError as e:
        print(f"[FAIL] high-risk rewrite: {e}")
        failures.append("high-risk rewrite")

    print(f"\n{'='*60}")
    if failures:
        print(f"FAILED: {failures}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED — Phase 1 diff reporting verified.")
        print(f"Outbox at {OUTBOX_PATH} contains correct edit_summary with risk levels.")
