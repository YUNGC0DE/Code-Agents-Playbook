"""
Educational model of the stop phase at turn end.

Maps loosely to: build a hook context from messages + tool context, optionally
schedule non-hook side work (fire-and-forget), then run Stop matchers and
interpret streaming results (blocking user messages, prevent continuation).

Subagents use SubagentStop instead of Stop; agent-defined Stop hooks are
typically mapped to SubagentStop when registered for a nested run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuerySource(Enum):
    MAIN = "main"
    SUBAGENT = "subagent"


@dataclass
class HookContext:
    messages: list[dict[str, Any]]
    query_source: QuerySource
    agent_id: str | None = None


@dataclass
class StopRunResult:
    blocking_errors: list[str] = field(default_factory=list)
    prevent_continuation: bool = False
    stop_reason: str = ""


def stop_event_for_context(ctx: HookContext) -> str:
    if ctx.agent_id is not None:
        return "SubagentStop"
    return "Stop"


async def run_stop_hooks_educational(
    ctx: HookContext,
    matchers: dict[str, list[Any]],
) -> StopRunResult:
    """
    `matchers` maps event name -> list of async callables returning
    dict with optional keys: blocking_error, prevent_continuation, stop_reason.
    """
    event = stop_event_for_context(ctx)
    hooks = matchers.get(event, [])
    out = StopRunResult()
    for h in hooks:
        r = await h(ctx)
        if r.get("blocking_error"):
            out.blocking_errors.append(str(r["blocking_error"]))
        if r.get("prevent_continuation"):
            out.prevent_continuation = True
            out.stop_reason = str(r.get("stop_reason") or "hook prevented continuation")
    return out


if __name__ == "__main__":
    import asyncio

    async def allow_main(_: HookContext) -> dict[str, Any]:
        return {}

    async def block_main(_: HookContext) -> dict[str, Any]:
        return {"prevent_continuation": True, "stop_reason": "policy"}

    async def main_demo() -> None:
        r1 = await run_stop_hooks_educational(
            HookContext([], QuerySource.MAIN),
            {"Stop": [allow_main]},
        )
        assert not r1.prevent_continuation

        r2 = await run_stop_hooks_educational(
            HookContext([], QuerySource.MAIN, agent_id="a1"),
            {"SubagentStop": [allow_main]},
        )
        assert stop_event_for_context(HookContext([], QuerySource.MAIN, "a1")) == "SubagentStop"

        r3 = await run_stop_hooks_educational(
            HookContext([], QuerySource.MAIN),
            {"Stop": [block_main]},
        )
        assert r3.prevent_continuation and r3.stop_reason == "policy"

    asyncio.run(main_demo())
    print("stop_hooks_pipeline ok")
