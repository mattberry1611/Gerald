"""
engineering_adapters/claude_code_adapter.py — Gerald OS Claude Code Adapter V1

Part of Gerald OS (see gerald_os.md).

Implements the Claude Code Worker adapter for the Gerald OS Engineering Worker.

The Claude Code adapter routes engineering work to the Claude Code CLI, which
runs autonomously on the Gerald server without requiring Matt's PC to be online.

Gerald OS role reference (gerald_os.md, Section 3):
  "Claude Code Worker — Autonomous file edits, scripts, and backend/Flutter
   changes via Claude Code."

V1 status:
  Live Claude Code execution is NOT yet wired.
  dry_run=True  → returns the prompt and metadata; nothing is run.
  dry_run=False → returns status "not_implemented"; no subprocess is called.

This adapter is pure and safe:
  - no subprocess calls
  - no file reads or writes
  - no network calls
  - no service restarts
"""

from __future__ import annotations

from datetime import datetime, timezone

_ADAPTER_NAME = "claude_code"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClaudeCodeAdapter:
    """
    Gerald OS Claude Code Worker adapter.

    Routes engineering prompts to the Claude Code CLI on the Gerald server.
    Satisfies the AdapterBase protocol defined in adapter_base.py.

    V1: dry_run only. Live subprocess execution wired in a future sprint.
    """

    def adapter_name(self) -> str:
        """Return the canonical adapter identifier."""
        return _ADAPTER_NAME

    def is_available(self) -> dict:
        """
        Report Claude Code adapter availability.

        Claude Code runs server-side and does not require Matt's PC.
        In V1, the subprocess integration is not yet wired, so this
        returns available=False with an explanatory reason.

        Returns:
            {
                "available":   False,
                "adapter":     "claude_code",
                "reason":      str,
                "requires_pc": False,
            }
        """
        return {
            "available":   False,
            "adapter":     _ADAPTER_NAME,
            "reason": (
                "Claude Code adapter V1 is not yet wired for live execution. "
                "The adapter is server-side and does not require Matt's PC, "
                "but the subprocess call to the Claude Code CLI has not been "
                "implemented yet. Live execution will be added in a future sprint."
            ),
            "requires_pc": False,
        }

    def execute_prompt(
        self,
        prompt: str,
        context: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """
        Execute a prompt through the Claude Code CLI adapter.

        V1 behaviour:
          dry_run=True  — returns the prompt and what would be run.
                          No subprocess is called.
          dry_run=False — returns status "not_implemented".
                          No subprocess is called.

        Args:
            prompt:   Execution prompt from engineering_worker.build_execution_prompt().
            context:  Optional dict with extra context (project, files, etc.).
            dry_run:  True (default) is safe for all V1 usage.

        Returns:
            {
                "status":      "dry_run" | "not_implemented",
                "adapter":     "claude_code",
                "prompt":      str,
                "output":      str,
                "context":     dict,
                "dry_run":     bool,
                "executed_at": str,
            }
        """
        base = {
            "adapter":     _ADAPTER_NAME,
            "prompt":      prompt,
            "output":      "",
            "context":     context or {},
            "dry_run":     dry_run,
            "executed_at": _now_iso(),
        }

        if dry_run:
            return {**base, "status": "dry_run"}

        return {
            **base,
            "status": "not_implemented",
            "note": (
                "Live Claude Code execution is not implemented in V1. "
                "The prompt above is ready to send to the Claude Code CLI. "
                "Wire subprocess execution in a future sprint to enable "
                "dry_run=False."
            ),
        }
