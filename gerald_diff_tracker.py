"""
gerald_diff_tracker.py — File snapshot and diff tracking for Claude edit tasks.

Snapshots source files before a Claude Code run, then computes a unified diff
and change summary after the run completes. The summary is attached to the
outbox result but does not alter approval or workflow gating.

Phase 2 enhancements:
- Individual .bak backup files written to BACKUP_DIR before each Claude run.
- Risk level (low/medium/high) computed per-file and overall.
  high:   >50% of file lines changed
  medium: >20% and <=50%
  low:    <=20%
- Change classification: small_patch / large_patch / full_rewrite (>80% changed
  or file size shrinks dramatically to <20% of original).
- Forbidden-file detection: flags any edit to files in FORBIDDEN_FILES.
- Excessively large diff detection (>500 total lines changed).
- Top-level high_risk_flag and high_risk_reasons in every edit summary.
"""

import os
import json
import difflib
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_DIR = Path("/opt/Gerald/edit_snapshots")
BACKUP_DIR = Path("/opt/Gerald/edit_backups")

_BACKEND_EXTENSIONS = (".py",)
_FLUTTER_EXTENSIONS = (".dart",)
_BACKEND_ROOT = "/opt/Gerald"
_FLUTTER_ROOT = "/opt/Gerald/gerald_app"

# Files that should never be touched by a Claude Code worker run
FORBIDDEN_FILES = {
    "gerald_bridge.py",
    ".env",
    ".env.local",
    "firebase-service-account.json",
    "gerald_devices.json",
}

_LARGE_DIFF_THRESHOLD = 500   # total lines added+removed = "excessively large"
_REWRITE_THRESHOLD = 0.8      # pct_changed fraction above which → full_rewrite
_DRAMATIC_SHRINK_RATIO = 0.2  # after < 20% of before line-count → dramatic shrink

# Skip noise-heavy directories that aren't user-edited source
_SKIP_DIRS = {
    "__pycache__", ".dart_tool", "build", ".flutter-plugins",
    ".flutter-plugins-dependencies", ".pub-cache", "android", "ios",
    "linux", "macos", "windows", "web",
}


def _extensions_for(worker_dir: str) -> tuple:
    return _BACKEND_EXTENSIONS if worker_dir == _BACKEND_ROOT else _FLUTTER_EXTENSIONS


def _risk_level(lines_added: int, lines_removed: int, total_before: int, total_after: int) -> str:
    """Return 'high', 'medium', or 'low' based on fraction of file lines touched."""
    max_lines = max(total_before, total_after, 1)
    fraction = (lines_added + lines_removed) / max_lines
    if fraction > 0.5:
        return "high"
    if fraction > 0.2:
        return "medium"
    return "low"


def _classify_change(pct_changed: float, n_before: int, n_after: int) -> str:
    """Classify a modified file as small_patch, large_patch, or full_rewrite.

    full_rewrite when >80% of lines changed OR the file shrank to <20% of
    its original size (dramatic delete).
    """
    dramatic_shrink = n_before > 0 and n_after < n_before * _DRAMATIC_SHRINK_RATIO
    if pct_changed > _REWRITE_THRESHOLD or dramatic_shrink:
        return "full_rewrite"
    if pct_changed > 0.2:
        return "large_patch"
    return "small_patch"


def _write_backups(task_id: str, files: dict) -> list:
    """Write individual .bak files for every snapshotted file.

    Backup path: BACKUP_DIR/<task_id>/<relative_path>.bak
    Returns list of (src_path, backup_path) tuples that succeeded.
    """
    created = []
    for abs_path, content in files.items():
        try:
            rel = Path(abs_path).name
            dest = BACKUP_DIR / task_id / rel
            dest = dest.with_suffix(dest.suffix + ".bak")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            created.append((abs_path, str(dest)))
        except OSError:
            pass
    return created


def _collect_files(root: str, extensions: tuple) -> dict:
    """Return {abs_path: content} for all source files under root."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if any(fn.endswith(ext) for ext in extensions):
                fpath = os.path.join(dirpath, fn)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        result[fpath] = f.read()
                except OSError:
                    pass
    return result


def take_snapshot(worker_dir: str, task_id: str) -> dict:
    """Snapshot all source files in worker_dir before a Claude run.

    Returns a snapshot dict that must be passed to compute_edit_summary().
    Also persists to SNAPSHOT_DIR for durability and writes individual .bak
    backup files to BACKUP_DIR/<task_id>/ for each snapshotted source file.
    """
    extensions = _extensions_for(worker_dir)
    files = _collect_files(worker_dir, extensions)
    backups = _write_backups(task_id, files)
    snapshot = {
        "task_id": task_id,
        "worker_dir": worker_dir,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "backups": [b for _, b in backups],
    }
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snap_path = SNAPSHOT_DIR / f"{task_id}.json"
        snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    except OSError:
        pass  # disk write failure is non-fatal; in-memory snapshot still usable
    return snapshot


def compute_edit_summary(snapshot: dict) -> dict:
    """Diff current filesystem state against the pre-run snapshot.

    Returns a dict with:
      - files_changed / files_added / files_deleted  (lists of rel paths)
      - total_lines_added / total_lines_removed       (int counts)
      - overall_risk_level                            ('low'/'medium'/'high')
      - diffs  {rel_path: {type, lines_added, lines_removed, risk_level, patch}}
      - summary  (human-readable one-liner)
    """
    worker_dir = snapshot["worker_dir"]
    extensions = _extensions_for(worker_dir)
    before_files: dict = snapshot.get("files", {})

    after_files = _collect_files(worker_dir, extensions)

    all_paths = sorted(set(before_files) | set(after_files))
    diffs: dict = {}
    files_changed: list = []
    files_added: list = []
    files_deleted: list = []
    total_added = 0
    total_removed = 0
    risk_levels: list = []

    for path in all_paths:
        before_text = before_files.get(path)
        after_text = after_files.get(path)

        if before_text == after_text:
            continue

        before_lines = (before_text or "").splitlines(keepends=True)
        after_lines = (after_text or "").splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{os.path.relpath(path, worker_dir)}",
            tofile=f"b/{os.path.relpath(path, worker_dir)}",
        ))

        added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
        total_added += added
        total_removed += removed

        rel_path = os.path.relpath(path, worker_dir)
        patch_text = "".join(diff_lines)
        file_name = os.path.basename(path)
        is_forbidden = file_name in FORBIDDEN_FILES

        if before_text is None:
            files_added.append(rel_path)
            change_type = "added"
            file_risk = "low"
            pct_changed = 1.0
        elif after_text is None:
            files_deleted.append(rel_path)
            change_type = "deleted"
            file_risk = "high"
            pct_changed = 1.0
        else:
            files_changed.append(rel_path)
            n_before = len(before_lines)
            n_after = len(after_lines)
            max_lines = max(n_before, n_after, 1)
            pct_changed = min((added + removed) / max_lines, 1.0)
            change_type = _classify_change(pct_changed, n_before, n_after)
            file_risk = _risk_level(added, removed, n_before, n_after)

        # Per-file high-risk reasons
        file_high_risk_reasons: list = []
        if change_type == "full_rewrite":
            file_high_risk_reasons.append("full_rewrite")
        if change_type == "deleted":
            file_high_risk_reasons.append("file_deleted")
        if is_forbidden:
            file_high_risk_reasons.append("forbidden_file")

        risk_levels.append(file_risk)
        diffs[rel_path] = {
            "type": change_type,
            "lines_added": added,
            "lines_removed": removed,
            "pct_changed": round(pct_changed * 100, 1),
            "risk_level": file_risk,
            "high_risk": bool(file_high_risk_reasons),
            "high_risk_reasons": file_high_risk_reasons,
            "patch": patch_text,
        }

    # Overall risk is the highest individual risk level observed
    _risk_order = {"low": 0, "medium": 1, "high": 2}
    overall_risk = max(risk_levels, key=lambda r: _risk_order.get(r, 0)) if risk_levels else "low"

    # Aggregate high-risk reasons across all files
    high_risk_reasons: list = []
    for rel, d in diffs.items():
        for reason in d.get("high_risk_reasons", []):
            high_risk_reasons.append(f"{rel}: {reason}")

    total_diff_lines = total_added + total_removed
    if total_diff_lines > _LARGE_DIFF_THRESHOLD:
        high_risk_reasons.append(
            f"excessively_large_diff ({total_diff_lines} lines changed, threshold={_LARGE_DIFF_THRESHOLD})"
        )

    high_risk_flag = bool(high_risk_reasons)

    summary = _format_summary(files_changed, files_added, files_deleted,
                              total_added, total_removed, overall_risk, high_risk_flag)
    return {
        "files_changed": files_changed,
        "files_added": files_added,
        "files_deleted": files_deleted,
        "total_lines_added": total_added,
        "total_lines_removed": total_removed,
        "overall_risk_level": overall_risk,
        "high_risk_flag": high_risk_flag,
        "high_risk_reasons": high_risk_reasons,
        "diffs": diffs,
        "summary": summary,
    }


def rollback_snapshot(task_id_or_snapshot) -> dict:
    """Restore all files in a snapshot back to their pre-edit content.

    Accepts either a snapshot dict (from take_snapshot()) or a task_id string
    to load the snapshot from disk.

    Returns a dict with restored (list), skipped (list), and message (str).
    """
    if isinstance(task_id_or_snapshot, str):
        snap_path = SNAPSHOT_DIR / f"{task_id_or_snapshot}.json"
        if not snap_path.exists():
            return {
                "restored": [],
                "skipped": [],
                "message": f"Snapshot '{task_id_or_snapshot}' not found on disk.",
            }
        try:
            snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"restored": [], "skipped": [], "message": f"Could not load snapshot: {e}"}
    else:
        snapshot = task_id_or_snapshot

    files: dict = snapshot.get("files", {})
    worker_dir = snapshot.get("worker_dir", "unknown")
    restored: list = []
    skipped: list = []

    for abs_path, content in files.items():
        try:
            Path(abs_path).write_text(content, encoding="utf-8")
            restored.append(abs_path)
        except Exception as e:
            skipped.append(f"{abs_path} ({e})")

    if not restored and not skipped:
        message = "No files were in the snapshot to restore."
    else:
        message = (
            f"Rollback complete. Restored {len(restored)} file(s) to pre-edit state in {worker_dir}."
        )
        if skipped:
            message += f" Could not restore: {', '.join(skipped)}."

    return {"restored": restored, "skipped": skipped, "message": message}


def list_recent_snapshots(limit: int = 5) -> list:
    """Return metadata about the most recent snapshots, newest first."""
    try:
        snaps = sorted(SNAPSHOT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []

    result = []
    for p in snaps[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            result.append({
                "task_id": data.get("task_id", p.stem),
                "worker_dir": data.get("worker_dir", "unknown"),
                "timestamp": data.get("timestamp", "unknown"),
                "file_count": len(data.get("files", {})),
            })
        except Exception:
            continue
    return result


def _format_summary(changed: list, added: list, deleted: list,
                    lines_added: int, lines_removed: int,
                    risk: str = "low", high_risk_flag: bool = False) -> str:
    parts = []
    if high_risk_flag:
        parts.append("⚠️ HIGH RISK")
    if changed:
        parts.append(f"Modified: {', '.join(changed)}")
    if added:
        parts.append(f"Added: {', '.join(added)}")
    if deleted:
        parts.append(f"Deleted: {', '.join(deleted)}")
    if not parts or (len(parts) == 1 and parts[0] == "⚠️ HIGH RISK"):
        return "No source files changed."
    parts.append(f"+{lines_added} lines, -{lines_removed} lines")
    parts.append(f"risk={risk}")
    return " | ".join(parts)
