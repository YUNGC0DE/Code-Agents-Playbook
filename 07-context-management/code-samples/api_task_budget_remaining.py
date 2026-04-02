"""
output_config.task_budget.remaining after compact.

When history is summarized, the model's view of spend can diverge. Subtract the
**final pre-compact context window** (input + output from last response iteration,
no cache when that is how you count) from `remaining` each time you compact —
cumulative across compacts.

Uses the same method name as Chapter 01 `prefetch_and_task_budget.py` for a
consistent mental model across samples.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskBudgetParam:
    type: str = "tokens"
    total: int = 0
    remaining: int | None = None


@dataclass
class TaskBudgetState:
    """Loop-local state for API-visible task budget (distinct from turn continuation)."""

    total: int
    remaining: int | None = field(default=None)

    def __post_init__(self) -> None:
        if self.remaining is None:
            self.remaining = self.total

    def subtract_pre_compact_window(self, final_context_tokens: int) -> None:
        """Call immediately before replacing messages with the post-compact summary."""
        assert self.remaining is not None
        self.remaining = max(0, self.remaining - final_context_tokens)

    def to_output_config(self) -> TaskBudgetParam:
        return TaskBudgetParam(
            type="tokens",
            total=self.total,
            remaining=self.remaining,
        )


def build_output_task_budget(state: TaskBudgetState) -> TaskBudgetParam:
    return state.to_output_config()


if __name__ == "__main__":
    t = TaskBudgetState(total=200_000)
    t.subtract_pre_compact_window(42_000)
    assert t.remaining == 158_000
    t.subtract_pre_compact_window(8_000)
    assert t.remaining == 150_000
    p = build_output_task_budget(t)
    assert p.remaining == 150_000
    print("api_task_budget_remaining ok")
