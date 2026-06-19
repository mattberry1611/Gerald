# Gerald Lessons

## Format
Each lesson should record:
- Problem
- Root cause
- Fix
- Outcome
- Reuse rule

---

## Lesson 001 - Flutter Routing Beats Backend Exclusion Text
Problem:
A Flutter UI task was routed to /opt/Gerald because the prompt included "do not modify backend files".

Root cause:
should_use_backend_root checked backend keywords before Flutter/UI keywords.

Fix:
Flutter/UI keywords must be checked first.

Outcome:
Flutter text-input bug routed correctly to /opt/Gerald/gerald_app.

Reuse rule:
If a task is clearly about UI, widgets, screens, APK behaviour, keyboard, layout, or Flutter files, route to /opt/Gerald/gerald_app even if the task says "do not modify backend files".

---

## Lesson 002 - Text Input Keyboard Flicker
Problem:
On Android, tapping the Gerald text input bar did not open the keyboard and the screen flickered/shook.

Root cause:
The TextField moved to a different widget-tree branch when the keyboard became visible, causing EditableText to unmount/remount and break the Android IME connection.

Fix:
Keep the TextField mounted in a stable widget-tree location and do not branch it into a separate keyboard-visible layout.

Outcome:
Verified fixed on Android device.

Reuse rule:
For Flutter text inputs, keep TextField, controller, and FocusNode stable across keyboard visibility changes.

---

## Lesson 003 - Claude Code Session Limits
Problem:
Gerald showed "You've hit your session limit · resets 3:10am (UTC)".

Root cause:
Claude Code CLI, running as user geraldbuild, hit its provider/session limit.

Fix:
Not a Gerald code fix. Wait for reset or upgrade the Claude account/session capacity.

Outcome:
Confirmed by running: sudo -u geraldbuild -H bash -lc 'claude -p "Say OK only"'

Reuse rule:
If Claude returns session/rate/quota/auth errors, classify as provider/runtime failure, not as a normal task failure.
