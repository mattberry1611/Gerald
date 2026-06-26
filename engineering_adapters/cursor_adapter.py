"""
engineering_adapters/cursor_adapter.py — Gerald OS Cursor Adapter V1

Part of Gerald OS (see gerald_os.md).

Implements the Cursor Worker adapter for the Gerald OS Engineering Worker.

The Cursor adapter routes engineering work into the Cursor IDE on Matt's PC.
It requires Matt's PC to be online and Cursor to be open with the relevant
project loaded.

Gerald OS role reference (gerald_os.md, Section 3):
  "Cursor Worker — IDE-integrated edits and refactors on the Gerald server
   or connected dev machine."

V1 status:
  Live Cursor execution is NOT yet wired.
  dry_run=True  → returns the prompt and metadata; nothing is sent to Cursor.
  dry_run=False → returns status "not_implemented"; no command is run.

This adapter is pure and safe:
  - no subprocess calls
  - no file reads or writes
  - no network calls
  - no service restarts
"""

from __future__ import annotations

from datetime import datetime, timezone

_ADAPTER_NAME = "cursor"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CursorAdapter:
    """
    Gerald OS Cursor Worker adapter.

    Routes engineering prompts to the Cursor IDE on Matt's PC.
    Satisfies the AdapterBase protocol defined in adapter_base.py.

    V1: dry_run only. Live execution wired in a future sprint.
    """

    def adapter_name(self) -> str:
        """Return the canonical adapter identifier."""
        return _ADAPTER_NAME

    def is_available(self) -> dict:
        """
        Report Cursor adapter availability.

        Cursor execution requires Matt's PC to be online with Cursor open.
        This cannot be determined server-side in V1 — always returns
        available=False with an explanatory reason.

        Returns:
            {
                "available":   False,
                "adapter":     "cursor",
                "reason":      str,
                "requires_pc": True,
            }
        """
        return {
            "available":   False,
            "adapter":     _ADAPTER_NAME,
            "reason": (
                "Cursor adapter V1 is not yet wired for live execution. "
                "Cursor requires Matt's PC to be online with the project "
                "open in the IDE. Live Cursor routing will be implemented "
                "in a future sprint."
            ),
            "requires_pc": True,
        }

    def execute_prompt(
        self,
        prompt: str,
        context: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """
        Execute a prompt through the Cursor IDE adapter.

        V1 behaviour:
          dry_run=True  — returns the prompt and what would be sent.
                          Nothing is transmitted to Cursor.
          dry_run=False — returns status "not_implemented".
                          No subprocess or network call is made.

        Args:
            prompt:   Execution prompt from engineering_worker.build_execution_prompt().
            context:  Optional dict with extra context (project, files, etc.).
            dry_run:  True (default) is safe for all V1 usage.

        Returns:
            {
                "status":      "dry_run" | "not_implemented",
                "adapter":     "cursor",
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
                "Live Cursor execution is not implemented in V1. "
                "The prompt above is ready to send. "
                "Wire Cursor IDE integration in a future sprint to "
                "enable dry_run=False."
            ),
        }
