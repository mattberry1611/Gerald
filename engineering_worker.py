"""
engineering_worker.py — Gerald OS Engineering Worker V1

Part of Gerald OS (see gerald_os.md).

Responsibility: Execute an Engineering Plan. Nothing else.

The Engineering Worker sits between the Engineering Manager and the coding
tools (Cursor, Claude Code). It receives a plan produced by
engineering_manager.produce_engineering_plan(), selects the appropriate
execution adapter, builds the prompt that will be sent to that adapter, and
drives execution.

Gerald OS role reference (gerald_os.md, Section 3):
  "Engineering Worker — Generic execution layer; may delegate to Claude Code
   or Cursor based on contract."

Gerald OS constraint (gerald_os.md, Section 5):
  "Claude Code / Cursor Worker: Implement per contract — not self-certify
   completion."

The Engineering Worker does NOT:
  - verify whether the work was done correctly (→ task_completion_verifier)
  - decide if the task is complete (→ task_completion_verifier)
  - deploy, restart services, or build APKs (→ deployment_manager)
  - produce Engineering Plans (→ engineering_manager)

V1 status:
  dry_run=True  — returns what would be executed, nothing is run.
  dry_run=False — execution adapters are not yet wired; returns "not_implemented".
                  This will be replaced in a future sprint when Cursor Worker
                  and Claude Code Worker adapters are connected.

This module is pure and safe:
  - no subprocess calls
  - no file reads or writes
  - no service restarts
  - no APK builds
  All functions return JSON-serialisable dicts or plain strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

ADAPTER_CURSOR = "cursor"
ADAPTER_CLAUDE_CODE = "claude_code"

_EXECUTION_STATUS_DRY_RUN = "dry_run"
_EXECUTION_STATUS_NOT_IMPLEMENTED = "not_implemented"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plan_text(plan: dict) -> str:
    """Return a single lowercase string covering all meaningful plan fields."""
    parts = [
        str(plan.get("objective", "")),
        str(plan.get("project", "")),
        str(plan.get("worker_reason", "")),
        " ".join(plan.get("estimated_steps", [])),
        " ".join(plan.get("deployment_required", [])),
    ]
    return " ".join(parts).lower()


# ── Public functions ───────────────────────────────────────────────────────────

def select_execution_adapter(plan: dict) -> dict:
    """
    Choose the execution adapter for a given Engineering Plan.

    Reads the "worker" field set by engineering_manager.produce_engineering_plan()
    and enriches it with execution-specific metadata.

    Adapter meanings:
      "cursor"      — Runs inside the Cursor IDE. Requires Matt's PC to be
                      online and Cursor to be open with the project loaded.
                      Best for Flutter/Dart and tasks needing full IDE context.
      "claude_code" — Runs as an autonomous CLI process on the server.
                      Does not require Matt's PC. Best for backend Python
                      and server-side scripting.

    Args:
        plan: dict produced by engineering_manager.produce_engineering_plan().
              Must contain a "worker" key ("cursor" | "claude_code").

    Returns:
        {
            "adapter":     "cursor" | "claude_code",
            "reason":      str,
            "requires_pc": bool   # True if Cursor (PC must be online)
        }
    """
    worker = str(plan.get("worker", "")).strip().lower()
    worker_reason = str(plan.get("worker_reason", "")).strip()

    if worker == ADAPTER_CURSOR:
        return {
            "adapter": ADAPTER_CURSOR,
            "reason": (
                f"Engineering Manager selected cursor: {worker_reason} "
                "Cursor adapter requires the IDE to be open on Matt's PC."
            ),
            "requires_pc": True,
        }

    if worker == ADAPTER_CLAUDE_CODE:
        return {
            "adapter": ADAPTER_CLAUDE_CODE,
            "reason": (
                f"Engineering Manager selected claude_code: {worker_reason} "
                "Claude Code adapter runs autonomously on the server."
            ),
            "requires_pc": False,
        }

    # Unknown worker — fall back to claude_code with a warning
    return {
        "adapter": ADAPTER_CLAUDE_CODE,
        "reason": (
            f"Unknown worker value '{worker}' in plan. "
            "Defaulting to claude_code adapter as safe fallback."
        ),
        "requires_pc": False,
    }


def build_execution_prompt(plan: dict) -> str:
    """
    Build the execution prompt to be sent to a Cursor or Claude Code adapter.

    The prompt contains everything the adapter needs to implement the task:
      - Objective and project
      - Why this worker was selected
      - Ordered steps to execute
      - What verification will be run afterwards (worker must NOT do this)
      - What deployment steps will follow (worker must NOT do this)
      - Explicit instruction NOT to verify or deploy

    Args:
        plan: dict produced by engineering_manager.produce_engineering_plan().

    Returns:
        A plain-text prompt string ready to be sent to the execution adapter.
    """
    objective = str(plan.get("objective", "")).strip() or "(no objective provided)"
    project = str(plan.get("project", "Gerald")).strip()
    worker = str(plan.get("worker", "")).strip()
    worker_reason = str(plan.get("worker_reason", "")).strip()
    complexity = str(plan.get("complexity", "")).strip()
    priority = str(plan.get("priority", "medium")).strip()

    steps = plan.get("estimated_steps") or []
    verification = plan.get("verification_required") or []
    deployment = plan.get("deployment_required") or []

    steps_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))
    verification_text = "\n".join(f"  - {v}" for v in verification)
    deployment_text = "\n".join(f"  - {d}" for d in deployment)

    prompt = f"""=== GERALD OS — ENGINEERING WORKER TASK ===

PROJECT:    {project}
OBJECTIVE:  {objective}
PRIORITY:   {priority}
COMPLEXITY: {complexity}
WORKER:     {worker}

WORKER SELECTION REASON:
  {worker_reason}

STEPS TO EXECUTE:
{steps_text}

─── IMPORTANT BOUNDARY INSTRUCTIONS ──────────────────────────────────────────

DO NOT VERIFY YOUR OWN WORK.
  Verification will be performed separately by the Task Completion Verifier
  (task_completion_verifier.py). Do not run build_verification_report() or
  declare the task complete based on your own assessment.

DO NOT DEPLOY.
  Deployment will be performed separately by the Deployment Manager
  (deployment_manager.py / POST /deploy/auto). Do not restart services,
  build APKs, or run systemctl commands unless the objective explicitly
  requires it as a directly deliverable outcome.

DO NOT EXPAND SCOPE.
  Implement only what the objective and steps describe. If you discover
  adjacent issues, note them but do not fix them in this task.

──────────────────────────────────────────────────────────────────────────────

FOR REFERENCE ONLY — VERIFICATION THAT WILL RUN AFTER YOU FINISH:
{verification_text}

FOR REFERENCE ONLY — DEPLOYMENT THAT WILL RUN AFTER VERIFICATION PASSES:
{deployment_text}

=== END OF TASK ==="""

    return prompt


def execute_engineering_plan(plan: dict, dry_run: bool = True) -> dict:
    """
    Execute an Engineering Plan using the appropriate adapter.

    V1 behaviour:
      dry_run=True  — No execution. Returns the adapter selection and the
                      prompt that would be sent. Safe to call at any time.
      dry_run=False — Real execution is not yet implemented. Returns status
                      "not_implemented" with the prompt ready for when adapters
                      are wired. This will be replaced in a future sprint.

    Gerald OS note: This function only drives execution. It does not verify
    the result and does not deploy. Callers must pass the raw result to
    task_completion_verifier.build_verification_report() separately.

    Args:
        plan:     dict produced by engineering_manager.produce_engineering_plan().
        dry_run:  If True (default), return what would run without executing.
                  If False, attempt real execution (not yet implemented in V1).

    Returns:
        {
            "status":        "dry_run" | "not_implemented",
            "adapter":       str,
            "requires_pc":   bool,
            "prompt":        str,
            "plan_summary":  dict,
            "executed_at":   str (ISO 8601 UTC),
            "dry_run":       bool,
            "note":          str   (present when status is "not_implemented")
        }
    """
    adapter_info = select_execution_adapter(plan)
    prompt = build_execution_prompt(plan)

    plan_summary = {
        "objective": plan.get("objective", ""),
        "project": plan.get("project", ""),
        "priority": plan.get("priority", ""),
        "worker": plan.get("worker", ""),
        "complexity": plan.get("complexity", ""),
        "step_count": len(plan.get("estimated_steps") or []),
        "verification_step_count": len(plan.get("verification_required") or []),
        "deployment_step_count": len(plan.get("deployment_required") or []),
        "created_at": plan.get("created_at", ""),
    }

    if dry_run:
        return {
            "status": _EXECUTION_STATUS_DRY_RUN,
            "adapter": adapter_info["adapter"],
            "requires_pc": adapter_info["requires_pc"],
            "prompt": prompt,
            "plan_summary": plan_summary,
            "executed_at": _now_iso(),
            "dry_run": True,
        }

    # V1: real execution not yet wired
    return {
        "status": _EXECUTION_STATUS_NOT_IMPLEMENTED,
        "adapter": adapter_info["adapter"],
        "requires_pc": adapter_info["requires_pc"],
        "prompt": prompt,
        "plan_summary": plan_summary,
        "executed_at": _now_iso(),
        "dry_run": False,
        "note": (
            "Real execution is not implemented in Engineering Worker V1. "
            "The prompt above is ready to send. "
            "Wire a Cursor Worker or Claude Code Worker adapter in a future sprint "
            "to enable live execution via dry_run=False."
        ),
    }
