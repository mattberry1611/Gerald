"""
engineering_adapters/adapter_base.py — Gerald OS Adapter Base Interface

Part of Gerald OS (see gerald_os.md).

Defines the contract every execution adapter must satisfy.

An adapter is the thin layer between the Engineering Worker and a specific
execution backend (Cursor IDE, Claude Code CLI, or future tools). Each adapter
has exactly one job: receive a prompt and return a structured result.

Adapters do NOT:
  - plan work           (→ engineering_manager)
  - verify results      (→ task_completion_verifier)
  - deploy              (→ deployment_manager)
  - decide the worker   (→ engineering_worker)

Gerald OS role reference (gerald_os.md, Section 3):
  "Cursor Worker — IDE-integrated edits and refactors."
  "Claude Code Worker — Autonomous file edits, scripts, and backend/Flutter changes."

All adapter methods return JSON-serialisable dicts only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AdapterBase(Protocol):
    """
    Protocol (structural interface) that every Gerald OS execution adapter
    must satisfy.

    Using Protocol means adapters do not need to inherit from this class —
    they only need to implement the three methods. This keeps adapters
    independently replaceable without import coupling.
    """

    def adapter_name(self) -> str:
        """
        Return the unique name for this adapter.

        Used by the Engineering Worker to log which adapter was selected
        and by the Orchestrator to include in the pipeline result.

        Returns:
            str — e.g. "cursor", "claude_code"
        """
        ...

    def is_available(self) -> dict:
        """
        Report whether this adapter is currently able to accept work.

        Does not attempt to run any command. Returns a structured dict
        so callers can make routing decisions or surface the reason to Matt.

        Returns:
            {
                "available":  bool,
                "adapter":    str,   # adapter_name()
                "reason":     str,   # human-readable explanation
                "requires_pc": bool, # True if Matt's PC must be online
            }
        """
        ...

    def execute_prompt(
        self,
        prompt: str,
        context: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """
        Execute a prompt through this adapter's backend.

        Args:
            prompt:   The execution prompt built by
                      engineering_worker.build_execution_prompt().
            context:  Optional extra context (project name, file list, etc.).
            dry_run:  If True, return what would be sent without executing.
                      If False, attempt real execution (may return
                      "not_implemented" in V1 adapters).

        Returns:
            {
                "status":      str,    "dry_run" | "not_implemented" | "ok" | "error"
                "adapter":     str,    adapter_name()
                "prompt":      str,    the prompt that was (or would be) sent
                "output":      str,    execution output (empty if dry_run)
                "dry_run":     bool,
                "executed_at": str,    ISO 8601 UTC timestamp
            }
        """
        ...
