"""
Recovery cascade: structural collapse, optional reactive compact (once),
full compact, then capped max_output_tokens retries — production agents bound
each expensive path so failures cannot burn unbounded API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class FailureKind(Enum):
    CONTEXT_TOO_LARGE = "context_too_large"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    OTHER = "other"


MAX_OUTPUT_RECOVERY_LIMIT = 3


@dataclass
class RecoveryContext:
    collapse_attempts: int = 0
    compact_attempts: int = 0
    max_output_recovery_count: int = 0
    # Reactive summarization of history — try at most once per failure episode
    has_attempted_reactive_compact: bool = False


def try_recover(
    kind: FailureKind,
    ctx: RecoveryContext,
    collapse: Callable[[], bool],
    compact: Callable[[], bool],
    reactive_compact: Callable[[], bool] | None = None,
) -> tuple[str | None, RecoveryContext]:
    """
    Returns (parameter_patch, updated_ctx) or (None, ctx) if unrecoverable.
    Production ordering for "too much context" is typically:
    1) cheap structural fixes (collapse / snip-style trims),
    2) reactive compact (model summarizes) — gated so it is not retried blindly,
    3) escalate max_output_tokens with a hard cap (see MAX_OUTPUT_RECOVERY_LIMIT).
    """
    if kind == FailureKind.CONTEXT_TOO_LARGE:
        if ctx.collapse_attempts == 0 and collapse():
            ctx.collapse_attempts += 1
            return "collapsed_intermediate_messages", ctx
        if (
            reactive_compact
            and not ctx.has_attempted_reactive_compact
            and reactive_compact()
        ):
            ctx.has_attempted_reactive_compact = True
            return "reactive_compact", ctx
        if ctx.compact_attempts == 0 and compact():
            ctx.compact_attempts += 1
            return "compacted_transcript", ctx
        return None, ctx

    if kind == FailureKind.MAX_OUTPUT_TOKENS:
        if ctx.max_output_recovery_count < MAX_OUTPUT_RECOVERY_LIMIT:
            ctx.max_output_recovery_count += 1
            return "increase_max_output_tokens", ctx
        return None, ctx

    return None, ctx


def demo() -> None:
    ctx = RecoveryContext()

    def collapse_ok() -> bool:
        return True

    def compact_ok() -> bool:
        return True

    def reactive_ok() -> bool:
        return True

    action, ctx = try_recover(
        FailureKind.CONTEXT_TOO_LARGE,
        ctx,
        collapse_ok,
        compact_ok,
        reactive_compact=reactive_ok,
    )
    assert action == "collapsed_intermediate_messages"

    action, ctx = try_recover(
        FailureKind.CONTEXT_TOO_LARGE,
        ctx,
        lambda: False,
        compact_ok,
        reactive_compact=reactive_ok,
    )
    assert action == "reactive_compact"

    action, ctx = try_recover(
        FailureKind.CONTEXT_TOO_LARGE,
        ctx,
        lambda: False,
        compact_ok,
        reactive_compact=lambda: False,
    )
    assert action == "compacted_transcript"

    for i in range(MAX_OUTPUT_RECOVERY_LIMIT):
        action, ctx = try_recover(
            FailureKind.MAX_OUTPUT_TOKENS, ctx, collapse_ok, compact_ok
        )
        assert action == "increase_max_output_tokens", i
    action, _ = try_recover(FailureKind.MAX_OUTPUT_TOKENS, ctx, collapse_ok, compact_ok)
    assert action is None
    print("recovery_cascade ok")


if __name__ == "__main__":
    demo()
