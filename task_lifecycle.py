"""
TaskLifecycleController — sole owner of task stage transitions.

Allowed transitions:
  idle        → received
  received    → classified
  classified  → planned
  planned     → executing
  executing   → verifying
  verifying   → completed
  any active (received/classified/planned/executing/verifying) → failed
  executing   → executing   (heartbeat updates within the same stage)
  completed   → user_disputed
  failed      → user_disputed
"""

from canonical_task_state import read_canonical_state, write_canonical_state

ACTIVE_STAGES = frozenset({"received", "classified", "planned", "executing", "verifying"})

# Maps from_stage → allowed to_stages
ALLOWED_TRANSITIONS: dict = {
    "idle":          frozenset({"received", "failed"}),
    "received":      frozenset({"classified", "failed"}),
    "classified":    frozenset({"planned", "failed"}),
    "planned":       frozenset({"executing", "failed"}),
    "executing":     frozenset({"verifying", "failed", "executing"}),  # executing→executing for heartbeats
    "verifying":     frozenset({"completed", "failed"}),
    "completed":     frozenset({"user_disputed"}),
    "failed":        frozenset({"user_disputed"}),
    "user_disputed": frozenset(),
}

LIFECYCLE_STAGES = frozenset(ALLOWED_TRANSITIONS.keys())


class TransitionError(ValueError):
    """Raised when a stage transition is not permitted by the lifecycle rules."""
    pass


class TaskLifecycleController:
    """
    Single point of control for canonical task state transitions.

    All writes to lifecycle stages must go through this controller.
    Reads current stage from canonical state, validates the requested transition,
    then delegates the write to write_canonical_state.
    """

    def validate(self, from_stage: str, to_stage: str) -> None:
        """Raise TransitionError if the transition is not in ALLOWED_TRANSITIONS."""
        allowed = ALLOWED_TRANSITIONS.get(from_stage, frozenset())
        if to_stage not in allowed:
            allowed_list = sorted(allowed) if allowed else ["none"]
            raise TransitionError(
                f"Invalid transition: {from_stage!r} → {to_stage!r}. "
                f"Allowed from {from_stage!r}: {allowed_list}"
            )

    def transition(self, to_stage: str, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        """
        Validate and apply a lifecycle transition. Raises TransitionError if invalid.

        Reads current stage from canonical state, validates, then writes.
        All extra kwargs are forwarded to write_canonical_state.
        """
        current = read_canonical_state()
        from_stage = current.get("stage", "idle")
        self.validate(from_stage, to_stage)
        return write_canonical_state(
            task=task or current.get("task", ""),
            project=project or current.get("project", ""),
            stage=to_stage,
            detail=detail,
            **kwargs
        )

    def try_transition(self, to_stage: str, task: str = "", project: str = "", detail: str = "", **kwargs):
        """
        Attempt a transition without raising. Returns (state_dict, None) on success
        or (None, error_str) if the transition is invalid.
        """
        try:
            return self.transition(to_stage, task, project, detail, **kwargs), None
        except TransitionError as e:
            return None, str(e)

    # Convenience methods for each lifecycle stage

    def mark_received(self, task: str, project: str, detail: str = "", **kwargs) -> dict:
        return self.transition("received", task, project, detail, **kwargs)

    def mark_classified(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("classified", task, project, detail, **kwargs)

    def mark_planned(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("planned", task, project, detail, **kwargs)

    def mark_executing(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("executing", task, project, detail, **kwargs)

    def mark_verifying(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("verifying", task, project, detail, **kwargs)

    def mark_completed(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("completed", task, project, detail, **kwargs)

    def mark_failed(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("failed", task, project, detail, **kwargs)

    def mark_user_disputed(self, task: str = "", project: str = "", detail: str = "", **kwargs) -> dict:
        return self.transition("user_disputed", task, project, detail, **kwargs)
