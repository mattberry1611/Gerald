"""
UI Component Verifier — supervisor-only.

Detects duplicate or missing required UI components in dashboard/app.js.
Called by the session-state auditor hook when a task completes with a
COMPLETE verdict and the task appears to be UI-related.

Not wired into the dashboard UI. No user-visible output.
"""
import re
from pathlib import Path
from typing import Dict, List

APP_JS_PATH = Path("/opt/Gerald/dashboard/app.js")

# Exactly one JSX render of TaskInput is expected in the home panel path.
TASK_INPUT_JSX_PATTERN = re.compile(r"<\$\{TaskInput\}")

# At least one of these class names must be present as the composer/input wrapper.
INPUT_WRAPPER_CLASSES = ["conversation-input-area", "composer-bar"]

# Keywords used to decide whether a completed task is UI-related.
UI_TASK_KEYWORDS = [
    "dashboard", "app.js", "taskinput", "task input",
    "composer", "conversation-input", "conversation input",
    "ui component", "input area",
]


def verify_ui_components(app_js_path: str = None) -> Dict:
    """
    Inspect dashboard/app.js for duplicate or missing required UI components.

    Checks performed:
    1. <${TaskInput} renders — must be exactly 1.
    2. Input wrapper class (conversation-input-area OR composer-bar) — must be present.
    3. TaskInput must appear within 10 lines of an input wrapper (coherence).

    Returns:
        {
            "verdict": "PASS" | "FAILED",
            "issues": [str, ...],
            "evidence": {
                "task_input_render_count": int,
                "input_wrapper_classes_found": [str, ...],
                "task_input_inside_wrapper": bool,
            },
            "checked_file": str,
        }
    """
    path = Path(app_js_path) if app_js_path else APP_JS_PATH
    if not path.exists():
        return {
            "verdict": "FAILED",
            "issues": [f"dashboard/app.js not found at {path}"],
            "evidence": {},
            "checked_file": str(path),
        }

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    issues: List[str] = []
    evidence: Dict = {}

    # ── Check 1: TaskInput render count ──────────────────────────────────────
    # Find every line containing <${TaskInput} (JSX render in htm template literals).
    # Skips import statements and comments.
    render_lines = [
        i for i, ln in enumerate(lines)
        if TASK_INPUT_JSX_PATTERN.search(ln)
        and not ln.lstrip().startswith("//")
        and "import" not in ln
    ]
    count = len(render_lines)
    evidence["task_input_render_count"] = count
    evidence["task_input_render_lines"] = [i + 1 for i in render_lines]  # 1-based for readability

    if count == 0:
        issues.append(
            "MISSING: TaskInput component has zero renders in dashboard/app.js "
            "(expected exactly 1 in the home panel path)"
        )
    elif count > 1:
        issues.append(
            f"DUPLICATE: TaskInput rendered {count} times in dashboard/app.js "
            f"(lines {[i + 1 for i in render_lines]}) — expected exactly 1"
        )

    # ── Check 2: Input wrapper class presence ─────────────────────────────────
    found_wrappers = []
    for cls in INPUT_WRAPPER_CLASSES:
        # Match className="..." or className={...} patterns
        if re.search(rf'["\']{{0,1}}{re.escape(cls)}["\']{{0,1}}', content):
            found_wrappers.append(cls)

    evidence["input_wrapper_classes_found"] = found_wrappers

    if not found_wrappers:
        issues.append(
            "MISSING: No input area wrapper found in dashboard/app.js — "
            f"composer removed without replacement. Expected one of: "
            f"{', '.join(INPUT_WRAPPER_CLASSES)}"
        )

    # ── Check 3: TaskInput inside a wrapper (coherence) ───────────────────────
    task_input_in_wrapper = False
    if render_lines and found_wrappers:
        wrapper_line_indices = {
            i for i, ln in enumerate(lines)
            if any(f'"{cls}"' in ln or f"'{cls}'" in ln for cls in INPUT_WRAPPER_CLASSES)
        }
        for ti_idx in render_lines:
            for w_idx in wrapper_line_indices:
                if 0 <= ti_idx - w_idx <= 10:
                    task_input_in_wrapper = True
                    break
            if task_input_in_wrapper:
                break

    evidence["task_input_inside_wrapper"] = task_input_in_wrapper

    if render_lines and found_wrappers and not task_input_in_wrapper:
        issues.append(
            "STRUCTURE: TaskInput render not within 10 lines of a "
            "conversation-input-area or composer-bar wrapper — "
            "composer may have been removed and TaskInput left floating"
        )

    verdict = "FAILED" if issues else "PASS"
    return {
        "verdict": verdict,
        "issues": issues,
        "evidence": evidence,
        "checked_file": str(path),
    }


def is_ui_related_task(task_text: str, files_changed: list) -> bool:
    """Return True if the task or changed files are UI/dashboard related."""
    text_lower = (task_text or "").lower()
    if any(kw in text_lower for kw in UI_TASK_KEYWORDS):
        return True
    for f in (files_changed or []):
        f_lower = (f or "").lower()
        if "dashboard" in f_lower or "app.js" in f_lower:
            return True
    return False
