"""
gerald_orchestrator.py — Gerald OS Central Orchestrator

Part of Gerald OS (see gerald_os.md) and Gerald Company (see gerald_company.md).

Responsibility: Wire the Gerald OS pipeline together. Nothing else.

The Orchestrator is the heart of Gerald OS. It receives a user request and
drives it through every layer in sequence:

  1. Engineering Manager  → produce_engineering_plan()
  2. Engineering Worker   → execute_engineering_plan()
  3. Task Completion Verifier → verify_worker_result()
     ↳ if verification fails  → return status: "retry_required"
     ↳ if verification passes → return status: "ready_for_deployment"
  4. Deployment Manager   → auto_deploy()  (only if verified)
  5. Return final result to Gerald / Matt

Gerald OS flow (gerald_os.md, Section 4):
  Matt request → Supervisor → Task Contract → Worker selection
  → Engineering Worker → Verifier → Deployment Manager → Result to Matt

Gerald Company layer ownership (gerald_company.md):
  Planning    → Engineering Manager
  Execution   → Engineering Worker
  Verification→ Task Completion Verifier
  Deployment  → Deployment Manager

The Orchestrator does NOT:
  - write code       (→ Engineering Worker / adapters)
  - verify itself    (→ Task Completion Verifier)
  - deploy itself    (→ Deployment Manager)
  - plan itself      (→ Engineering Manager)

Dependency injection:
  Every department is injected via the OrchestratorDeps dataclass.
  This allows each department to be replaced independently (e.g. swap
  the Deployment Manager for a dry-run stub in tests) without modifying
  the orchestrator logic.

V1 status:
  Workers are not yet wired for live execution (engineering_worker
  dry_run=True by default). The pipeline structure is complete and every
  handoff is real; only the execution adapter is a stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Default department implementations ────────────────────────────────────────
# Imported lazily inside the defaults to keep the module importable even if a
# dependency has a syntax error during development.

def _default_plan(request: dict) -> dict:
    from engineering_manager import produce_engineering_plan
    return produce_engineering_plan(request)


def _default_execute(plan: dict, dry_run: bool) -> dict:
    from engineering_worker import execute_engineering_plan
    return execute_engineering_plan(plan, dry_run=dry_run)


def _default_verify(plan: dict, worker_result: dict) -> dict:
    from task_completion_verifier import verify_worker_result
    return verify_worker_result(plan, worker_result)


def _default_deploy(changed_files: list[str]) -> dict:
    from deployment_manager import plan_deployment_actions, run_deployment_actions
    plan = plan_deployment_actions(changed_files)
    return run_deployment_actions(plan)


# ── Dependency container ───────────────────────────────────────────────────────

@dataclass
class OrchestratorDeps:
    """
    Dependency injection container for the Gerald OS pipeline.

    Each field is a callable that performs one layer of the pipeline.
    Replace any field to swap out a department without touching orchestrator logic.

    Fields:
        plan_fn:    (request: dict) -> dict
                    Engineering Manager: produce an Engineering Plan.

        execute_fn: (plan: dict, dry_run: bool) -> dict
                    Engineering Worker: execute the plan via adapter.

        verify_fn:  (plan: dict, worker_result: dict) -> dict
                    Task Completion Verifier: inspect evidence.

        deploy_fn:  (changed_files: list[str]) -> dict
                    Deployment Manager: run deployment actions.
    """
    plan_fn:    Callable[[dict], dict]                    = field(default=_default_plan)
    execute_fn: Callable[[dict, bool], dict]              = field(default=_default_execute)
    verify_fn:  Callable[[dict, dict], dict]              = field(default=_default_verify)
    deploy_fn:  Callable[[list[str]], dict]               = field(default=_default_deploy)


# ── Pipeline stages (each stage is independently testable) ────────────────────

def run_planning_stage(request: dict, deps: OrchestratorDeps) -> dict:
    """
    Stage 1 — Planning.

    Pass the user request to the Engineering Manager and return an
    Engineering Plan.

    Returns:
        {
            "stage":   "planning",
            "status":  "ok" | "error",
            "plan":    dict,            # Engineering Plan (on ok)
            "error":   str,             # (on error only)
        }
    """
    try:
        plan = deps.plan_fn(request)
        return {"stage": "planning", "status": "ok", "plan": plan}
    except Exception as exc:
        return {"stage": "planning", "status": "error", "error": str(exc), "plan": {}}


def run_execution_stage(plan: dict, deps: OrchestratorDeps, dry_run: bool = True) -> dict:
    """
    Stage 2 — Execution.

    Pass the Engineering Plan to the Engineering Worker and return the
    raw worker result.

    Args:
        dry_run: If True (V1 default), no real commands are run.

    Returns:
        {
            "stage":         "execution",
            "status":        "ok" | "error",
            "worker_result": dict,   # raw Engineering Worker output (on ok)
            "error":         str,    # (on error only)
        }
    """
    try:
        worker_result = deps.execute_fn(plan, dry_run)
        return {"stage": "execution", "status": "ok", "worker_result": worker_result}
    except Exception as exc:
        return {"stage": "execution", "status": "error", "error": str(exc), "worker_result": {}}


def run_verification_stage(plan: dict, worker_result: dict, deps: OrchestratorDeps) -> dict:
    """
    Stage 3 — Verification.

    Pass the Engineering Plan and worker result to the Task Completion
    Verifier. Return the verification report.

    The verifier ignores worker_result["status"] entirely — evidence decides.

    Returns:
        {
            "stage":               "verification",
            "status":              "ok" | "error",
            "verification_report": dict,   # from task_completion_verifier (on ok)
            "error":               str,    # (on error only)
        }
    """
    try:
        report = deps.verify_fn(plan, worker_result)
        return {"stage": "verification", "status": "ok", "verification_report": report}
    except Exception as exc:
        return {
            "stage": "verification",
            "status": "error",
            "error": str(exc),
            "verification_report": {},
        }


def run_deployment_stage(changed_files: list[str], deps: OrchestratorDeps) -> dict:
    """
    Stage 4 — Deployment.

    Pass the changed files to the Deployment Manager, which determines
    and runs the required deployment actions (restarts, APK builds, etc.).

    Only called after verification passes.

    Returns:
        {
            "stage":             "deployment",
            "status":            "ok" | "error",
            "deployment_result": dict,   # from deployment_manager (on ok)
            "error":             str,    # (on error only)
        }
    """
    try:
        result = deps.deploy_fn(changed_files)
        return {"stage": "deployment", "status": "ok", "deployment_result": result}
    except Exception as exc:
        return {
            "stage": "deployment",
            "status": "error",
            "error": str(exc),
            "deployment_result": {},
        }


# ── Main orchestration function ────────────────────────────────────────────────

def run_pipeline(
    request: dict,
    deps: OrchestratorDeps | None = None,
    dry_run: bool = True,
) -> dict:
    """
    Drive a user request through the full Gerald OS pipeline.

    Gerald OS flow (gerald_os.md, Section 4):
      Planning → Execution → Verification → Deployment → Result

    Args:
        request:  dict with at least "goal". Should also include "project"
                  and "priority". This is the user's stated outcome.
        deps:     OrchestratorDeps instance. If None, uses all real
                  department defaults.
        dry_run:  Passed to the Engineering Worker. True (default) in V1
                  because execution adapters are not yet wired.

    Returns a single JSON-serialisable dict:
        {
            "status":              str,   see STATUS_* constants below
            "request":             dict,
            "stages":              dict,  per-stage results
            "plan":                dict,  Engineering Plan (if produced)
            "verification_report": dict,  Verifier output (if run)
            "deployment_result":   dict,  Deployment Manager output (if run)
            "apk_url":             str,   (if APK was built)
            "completed_at":        str,
            "dry_run":             bool,
        }

    Status values:
        "pipeline_error"       — a stage failed before verification
        "verification_failed"  — verification did not pass; no deployment run
        "ready_for_deployment" — verification passed; deployment was skipped
                                 (only possible if deploy_fn is stubbed)
        "complete"             — all stages passed; deployment ran
        "deployment_failed"    — verification passed but deployment errored
    """
    if deps is None:
        deps = OrchestratorDeps()

    stages: dict[str, Any] = {}
    result: dict[str, Any] = {
        "request":             request,
        "stages":              stages,
        "plan":                {},
        "verification_report": {},
        "deployment_result":   {},
        "completed_at":        "",
        "dry_run":             dry_run,
    }

    # ── Stage 1: Planning ─────────────────────────────────────────────────────
    planning = run_planning_stage(request, deps)
    stages["planning"] = planning
    if planning["status"] != "ok":
        result.update({"status": "pipeline_error", "completed_at": _now_iso()})
        return result

    plan = planning["plan"]
    result["plan"] = plan

    # ── Stage 2: Execution ────────────────────────────────────────────────────
    execution = run_execution_stage(plan, deps, dry_run=dry_run)
    stages["execution"] = execution
    if execution["status"] != "ok":
        result.update({"status": "pipeline_error", "completed_at": _now_iso()})
        return result

    worker_result = execution["worker_result"]

    # ── Stage 3: Verification ─────────────────────────────────────────────────
    verification = run_verification_stage(plan, worker_result, deps)
    stages["verification"] = verification
    if verification["status"] != "ok":
        result.update({"status": "pipeline_error", "completed_at": _now_iso()})
        return result

    report = verification["verification_report"]
    result["verification_report"] = report

    if not report.get("verified", False):
        result.update({
            "status": "verification_failed",
            "reason": "; ".join(report.get("missing", [])) or "verification did not pass",
            "completed_at": _now_iso(),
        })
        return result

    # ── Stage 4: Deployment ───────────────────────────────────────────────────
    changed_files: list[str] = (
        worker_result.get("changed_files")
        or plan.get("likely_files")
        or []
    )

    deployment = run_deployment_stage(changed_files, deps)
    stages["deployment"] = deployment
    result["deployment_result"] = deployment.get("deployment_result", {})

    if deployment["status"] != "ok":
        result.update({"status": "deployment_failed", "completed_at": _now_iso()})
        return result

    # Surface APK URL if deployment built one
    apk_url = result["deployment_result"].get("apk_url")
    if apk_url:
        result["apk_url"] = apk_url

    result.update({"status": "complete", "completed_at": _now_iso()})
    return result


# ── Simplified dry-run entry point ────────────────────────────────────────────

def orchestrate_request(request: dict, dry_run: bool = True) -> dict:
    """
    Run the Gerald OS pipeline for a user request and return one clean result.

    This is the primary entry point for Sprint 002 dry-run orchestration.
    It calls each Gerald OS component in order, enforces dependency boundaries,
    and returns a single JSON-serialisable dict describing every stage.

    Gerald OS flow (gerald_os.md, Section 4):
      request → Engineering Manager → Engineering Worker
              → Task Completion Verifier → (deployment_required reported)
              → result to caller

    This function does NOT:
      - decide worker details     (→ engineering_manager)
      - verify manually           (→ task_completion_verifier)
      - deploy or restart         (→ deployment_manager, not called in dry_run)
      - build APKs                (→ deployment_manager, not called in dry_run)

    Args:
        request:  dict with at least "goal". May include "project", "priority",
                  "description", "context", "required_files", "required_functions",
                  "required_endpoints".
        dry_run:  When True (default), no worker executes real code and no
                  deployment is triggered. The pipeline reports what would happen.

    Returns:
        {
            "status":              "dry_run_complete" | "verification_failed"
                                   | "pipeline_error",
            "request":             dict,   the original request
            "engineering_plan":    dict,   from engineering_manager
            "execution_result":    dict,   from engineering_worker
            "verification_report": dict,   from task_completion_verifier
            "deployment_required": dict,   extracted from verification_report
            "next_action":         str,    human-readable guidance for Matt
            "dry_run":             bool,
            "completed_at":        str,    ISO 8601 UTC
        }
    """
    from engineering_manager import produce_engineering_plan
    from engineering_worker import execute_engineering_plan
    from task_completion_verifier import build_verification_report

    base: dict = {
        "request":             request,
        "engineering_plan":    {},
        "execution_result":    {},
        "verification_report": {},
        "deployment_required": {},
        "dry_run":             dry_run,
        "completed_at":        "",
    }

    # ── Step 1: Engineering Manager → Engineering Plan ────────────────────────
    try:
        plan = produce_engineering_plan(request)
    except Exception as exc:
        base.update({
            "status":      "pipeline_error",
            "next_action": f"Engineering Manager failed to produce a plan: {exc}",
            "completed_at": _now_iso(),
        })
        return base

    base["engineering_plan"] = plan

    # ── Step 2: Engineering Worker → Execution Result ─────────────────────────
    try:
        execution_result = execute_engineering_plan(plan, dry_run=dry_run)
    except Exception as exc:
        base.update({
            "status":      "pipeline_error",
            "next_action": f"Engineering Worker failed during execution: {exc}",
            "completed_at": _now_iso(),
        })
        return base

    base["execution_result"] = execution_result

    # ── Step 3: Build verification contract from the plan ─────────────────────
    # Pull file and symbol requirements from the Engineering Plan first, then
    # fall back to whatever the caller supplied in the original request.
    # This ensures explicit request fields (likely_files, required_functions,
    # etc.) are honoured even when the Engineering Manager does not echo them.
    def _merge(key: str) -> list:
        return plan.get(key) or request.get(key) or []

    contract = {
        "required_files":     _merge("required_files"),
        "likely_files":       _merge("likely_files"),
        "required_functions": _merge("required_functions"),
        "required_classes":   _merge("required_classes"),
        "required_endpoints": _merge("required_endpoints"),
    }

    # Changed files: use whatever the worker reported, otherwise fall back to
    # the merged likely_files so the verifier still gets something to inspect.
    changed_files: list[str] = (
        execution_result.get("changed_files")
        or contract["likely_files"]
        or []
    )

    # ── Step 4: Task Completion Verifier → Verification Report ────────────────
    try:
        verification_report = build_verification_report(contract, changed_files)
    except Exception as exc:
        base.update({
            "status":      "pipeline_error",
            "next_action": f"Task Completion Verifier raised an error: {exc}",
            "completed_at": _now_iso(),
        })
        return base

    base["verification_report"] = verification_report
    deployment_required = verification_report.get("deployment_required", {})
    base["deployment_required"] = deployment_required

    # ── Step 5: Determine status and next_action ──────────────────────────────
    verified    = verification_report.get("verified", False)
    missing     = verification_report.get("missing", [])
    confidence  = verification_report.get("confidence", 0)

    if not verified:
        issues = "; ".join(missing) if missing else "verification did not pass"
        base.update({
            "status":      "verification_failed",
            "next_action": (
                f"Verification failed (confidence {confidence}%). "
                f"Missing: {issues}. "
                "Fix the issues above, then re-run the pipeline."
            ),
            "completed_at": _now_iso(),
        })
        return base

    # Build next_action from deployment_required
    deploy_steps: list[str] = []
    if deployment_required.get("restart_backend"):
        deploy_steps.append("restart gerald service")
    if deployment_required.get("restart_design_studio"):
        deploy_steps.append("restart gerald-design-studio service")
    if deployment_required.get("build_apk"):
        deploy_steps.append("build and serve APK")
    if deployment_required.get("dashboard_changed"):
        deploy_steps.append("note dashboard updated")

    if deploy_steps:
        next_action = (
            f"Verification passed (confidence {confidence}%). "
            f"Deployment required: {', '.join(deploy_steps)}. "
            "Call POST /deploy/auto or run deployment_manager.auto_deploy() to proceed."
        )
    else:
        next_action = (
            f"Verification passed (confidence {confidence}%). "
            "No deployment actions required. Pipeline complete."
        )

    base.update({
        "status":      "dry_run_complete",
        "next_action": next_action,
        "completed_at": _now_iso(),
    })
    return base
