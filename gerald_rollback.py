#!/usr/bin/env python3
"""
gerald_rollback.py — Restore files from a pre-edit Gerald snapshot.

Usage:
  python3 /opt/Gerald/gerald_rollback.py               # list recent snapshots
  python3 /opt/Gerald/gerald_rollback.py {task_id}     # restore from snapshot
  python3 /opt/Gerald/gerald_rollback.py latest        # restore from newest snapshot
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gerald_diff_tracker


def main():
    if len(sys.argv) < 2:
        snaps = gerald_diff_tracker.list_recent_snapshots(limit=10)
        if not snaps:
            print("No snapshots found in /opt/Gerald/edit_snapshots/")
            return
        print("Recent snapshots (newest first):")
        for s in snaps:
            print(
                f"  task_id={s['task_id']}  "
                f"dir={s['worker_dir']}  "
                f"files={s['file_count']}  "
                f"at={s['timestamp']}"
            )
        return

    task_id = sys.argv[1].strip()

    if task_id == "latest":
        snaps = gerald_diff_tracker.list_recent_snapshots(limit=1)
        if not snaps:
            print("No snapshots available to restore.")
            sys.exit(1)
        task_id = snaps[0]["task_id"]
        print(f"Using most recent snapshot: {task_id}")

    result = gerald_diff_tracker.rollback_snapshot(task_id)
    print(result["message"])
    if result["restored"]:
        print("Restored files:")
        for f in result["restored"]:
            print(f"  {f}")
    if result["skipped"]:
        print("Could not restore:")
        for f in result["skipped"]:
            print(f"  {f}")

    sys.exit(0 if not result["skipped"] else 1)


if __name__ == "__main__":
    main()
