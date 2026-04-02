"""Loop continuation budget: soft cap vs diminishing returns (not output_config.task_budget)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

COMPLETION_THRESHOLD = 0.9
DIMINISHING_THRESHOLD = 500


@dataclass
class BudgetTracker:
    """Client-side policy for multi-iteration agentic loops inside one user turn."""

    continuation_count: int = 0
    last_global_turn_tokens: int = 0
    last_delta_tokens: int = 0
    started_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass
class CompletionEvent:
    """Emitted when the loop stops after at least one continuation or diminishing returns."""

    continuation_count: int
    pct: int
    turn_tokens: int
    budget: int
    diminishing_returns: bool
    duration_ms: int


def check_turn_budget(
    tracker: BudgetTracker,
    budget: int | None,
    global_turn_tokens: int,
    *,
    agent_id: str | None = None,
    now_ms: int | None = None,
) -> tuple[Literal["continue", "stop"], BudgetTracker, CompletionEvent | None]:
    """
    Mirrors production tokenBudget check: forked agents (truthy agent_id) do not continue.

    Returns (action, tracker, completion_event). completion_event is None when stopping
    before any continuation (or when disabled), matching a null completion payload.
    """
    if agent_id or budget is None or budget <= 0:
        return "stop", tracker, None

    clock = now_ms if now_ms is not None else int(time.time() * 1000)
    turn_tokens = global_turn_tokens
    pct = round((turn_tokens / budget) * 100)
    delta = global_turn_tokens - tracker.last_global_turn_tokens

    is_diminishing = (
        tracker.continuation_count >= 3
        and delta < DIMINISHING_THRESHOLD
        and tracker.last_delta_tokens < DIMINISHING_THRESHOLD
    )

    if not is_diminishing and turn_tokens < budget * COMPLETION_THRESHOLD:
        tracker.continuation_count += 1
        tracker.last_delta_tokens = delta
        tracker.last_global_turn_tokens = global_turn_tokens
        return "continue", tracker, None

    if is_diminishing or tracker.continuation_count > 0:
        return (
            "stop",
            tracker,
            CompletionEvent(
                continuation_count=tracker.continuation_count,
                pct=pct,
                turn_tokens=turn_tokens,
                budget=budget,
                diminishing_returns=is_diminishing,
                duration_ms=clock - tracker.started_at_ms,
            ),
        )

    return "stop", tracker, None


if __name__ == "__main__":
    bt = BudgetTracker(started_at_ms=0)
    action, bt, ev = check_turn_budget(bt, 100_000, 10_000, now_ms=1_000)
    assert action == "continue" and ev is None

    _, bt, ev = check_turn_budget(bt, 100_000, 95_000, agent_id="sub-1", now_ms=2_000)
    assert ev is None  # forked agent: no continuation path

    bt2 = BudgetTracker(started_at_ms=0)
    _, bt2, ev2 = check_turn_budget(bt2, 100_000, 50_000, now_ms=1)
    assert ev2 is None and bt2.continuation_count == 1
    _, bt2, ev2 = check_turn_budget(bt2, 100_000, 95_000, now_ms=10_000)
    assert ev2 is not None and not ev2.diminishing_returns
    print("token_budget ok")
