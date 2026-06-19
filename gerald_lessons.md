# Gerald Lessons

## Lesson 001 - Flutter Routing vs Backend Routing
UI and Flutter tasks must be routed to /opt/Gerald/gerald_app.
Backend tasks only route to /opt/Gerald when the task is genuinely about backend code.

## Lesson 002 - Heartbeat Updates Reduce User Anxiety
Long-running Claude tasks must update status every 30 seconds.

## Lesson 003 - Clarification Is Not Completion
If an AI asks Matt a question or requests clarification, task state must be needs_clarification, not completed.

## Lesson 004 - Text Input Keyboard Bug
Cause:
TextField moved to a different widget tree location when keyboard opened.

Fix:
Keep TextField mounted in the same location and avoid rebuilding it into a different branch.

Outcome:
Verified fixed on Android device.

## Lesson 005 - Claude Provider Limits
Claude Code CLI may return provider/session-limit errors.
These are provider failures, not Gerald failures.
They should eventually be classified separately from normal task failures.
