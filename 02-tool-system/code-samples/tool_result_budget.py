"""
Per-tool and per-message tool result budgets.

Typical stacks clamp each tool output, declare per-tool max sizes, and also
enforce an aggregate cap on all tool_result blocks in one user message (parallel
batch) — largest blocks get persisted/replaced first until the message fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_MAX_CHARS = 50_000
# Order-of-magnitude defaults for a single batch (tune to your model limits)
DEFAULT_AGGREGATE_MESSAGE_CHARS = 250_000


@dataclass(frozen=True)
class BudgetResult:
    content: str
    truncated: bool
    original_chars: int


def apply_tool_result_budget(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> BudgetResult:
    n = len(text)
    if n <= max_chars:
        return BudgetResult(content=text, truncated=False, original_chars=n)
    head = max_chars // 2
    tail = max_chars - head - 80
    snippet = (
        text[:head]
        + f"\n... [{n - max_chars} chars omitted] ...\n"
        + text[-tail:]
    )
    return BudgetResult(content=snippet, truncated=True, original_chars=n)


def shrink_parallel_results_to_aggregate_cap(
    blocks: list[str],
    aggregate_cap: int = DEFAULT_AGGREGATE_MESSAGE_CHARS,
) -> list[str]:
    """
    If sum(len(b)) > cap, replace largest blocks with short placeholders until under cap.
    Full implementations often persist full output to disk and inject path + preview.
    """
    out = list(blocks)
    while sum(len(b) for b in out) > aggregate_cap and out:
        idx = max(range(len(out)), key=lambda i: len(out[i]))
        out[idx] = "[Output moved to storage — preview omitted]\n"
    return out


@dataclass
class ContentReplacementState:
    """
    Per-thread state for aggregate enforcement and stable replay across turns.

    - seen_ids: tool_use_ids that already passed budget; fate is frozen for the thread.
    - replacements: mapping from tool_use_id to the exact preview string shown to the model
      so re-application is a Map lookup (stable cache prefix).
    """

    seen_ids: set[str] = field(default_factory=set)
    replacements: dict[str, str] = field(default_factory=dict)


def apply_aggregate_with_stable_state(
    *,
    tool_use_id: str,
    content: str,
    state: ContentReplacementState,
    per_tool_cap: int,
    aggregate_cap: int,
    running_total: int,
) -> tuple[str, int]:
    """
    Skip re-budgeting for ids already in seen_ids; record replacement preview when shrinking.

    `running_total` is the sum of lengths already committed for this user message batch.
    """
    if tool_use_id in state.seen_ids:
        return state.replacements.get(tool_use_id, content), running_total

    br = apply_tool_result_budget(content, per_tool_cap)
    text = br.content
    if running_total + len(text) > aggregate_cap:
        text = "[Output moved to storage — preview omitted]\n"
    state.seen_ids.add(tool_use_id)
    state.replacements[tool_use_id] = text
    return text, running_total + len(text)


if __name__ == "__main__":
    long = "x" * 100_000
    br = apply_tool_result_budget(long, 500)
    assert br.truncated
    assert len(br.content) < len(long)
    big = ["a" * 200_000, "b" * 200_000]
    shrunk = shrink_parallel_results_to_aggregate_cap(big, aggregate_cap=150_000)
    assert sum(len(x) for x in shrunk) <= 150_000
    st = ContentReplacementState()
    t1, total = apply_aggregate_with_stable_state(
        tool_use_id="u1",
        content="x" * 100_000,
        state=st,
        per_tool_cap=50_000,
        aggregate_cap=40_000,
        running_total=0,
    )
    assert "u1" in st.seen_ids
    assert total <= 40_000
    t2, _ = apply_aggregate_with_stable_state(
        tool_use_id="u1",
        content="y" * 100_000,
        state=st,
        per_tool_cap=50_000,
        aggregate_cap=40_000,
        running_total=0,
    )
    assert t1 == t2
    print("budget ok, truncated=", br.truncated)
