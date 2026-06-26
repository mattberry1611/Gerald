"""
engineering_adapters — Gerald OS Execution Adapter Package

Part of Gerald OS (see gerald_os.md).

Exports the execution adapters available to the Engineering Worker.
Add new adapters here as they are implemented.

Current adapters (V1):
  CursorAdapter      — Cursor IDE on Matt's PC (dry_run only in V1)
  ClaudeCodeAdapter  — Claude Code CLI on the server (dry_run only in V1)

Usage:
    from engineering_adapters import CursorAdapter, ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    result = adapter.execute_prompt(prompt, dry_run=True)
"""

from engineering_adapters.cursor_adapter import CursorAdapter
from engineering_adapters.claude_code_adapter import ClaudeCodeAdapter

__all__ = ["CursorAdapter", "ClaudeCodeAdapter"]
