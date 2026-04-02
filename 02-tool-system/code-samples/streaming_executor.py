"""
Streaming tool executor: concurrency-safe tools may run in parallel;
non-safe tools hold the queue until exclusive execution completes.

Full systems also: resolve unknown names to immediate error results; derive
parallel-safe flags only after input validation; propagate sibling cancellation
on selected tool classes (e.g. shell) only; interleave progress vs final
results. This file keeps a minimal queue + discard for teaching.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


def is_parallel_safe_after_validation(
    parse_ok: bool, tool_allows_parallel: bool
) -> bool:
    """
    If parsing failed, never treat the call as parallel-safe (no guessing from
    malformed input). If parsing succeeded, defer to the tool's policy.
    """
    return parse_ok and tool_allows_parallel


@dataclass
class PendingTool:
    id: str
    name: str
    is_concurrency_safe: bool
    run: Callable[[], Awaitable[str]]


@dataclass
class StreamingToolExecutor:
    """
    Simplified queue: processes tools in arrival order, parallelizing only when allowed.

    Call discard() when the outer loop abandons a streaming attempt or retries, so
    stale tool_use_ids cannot produce orphan tool_results. This sample does not
    implement sibling error propagation or unknown-tool short-circuiting.
    """

    _queue: list[PendingTool] = field(default_factory=list)
    _running: list[asyncio.Task[str]] = field(default_factory=list)
    discarded: bool = False

    def discard(self) -> None:
        """Abandon queued work (e.g. streaming fallback)."""
        self.discarded = True

    def add_tool(self, tool: PendingTool) -> None:
        if self.discarded:
            return
        self._queue.append(tool)

    async def drain(self) -> list[tuple[str, str]]:
        """Returns (tool_use_id, result) in submission order."""
        if self.discarded:
            return []
        results: list[tuple[str, str]] = []
        while self._queue:
            # Peek: if front is exclusive, wait until nothing runs
            head = self._queue[0]
            if not head.is_concurrency_safe:
                await self._await_running()
                t = self._queue.pop(0)
                results.append((t.id, await t.run()))
                continue

            # Start all consecutive concurrency-safe tools until exclusive or empty
            batch: list[PendingTool] = []
            while self._queue and self._queue[0].is_concurrency_safe:
                batch.append(self._queue.pop(0))
            if not batch:
                continue
            self._running = [asyncio.create_task(b.run()) for b in batch]
            ids = [b.id for b in batch]
            outs = await asyncio.gather(*self._running)
            self._running.clear()
            results.extend(zip(ids, outs, strict=True))
        return results

    async def _await_running(self) -> None:
        if self._running:
            await asyncio.gather(*self._running)
            self._running.clear()


def synthetic_unknown_tool_result(tool_use_id: str, name: str) -> tuple[str, str]:
    """Structured error for a missing name; same id the model used for the call."""
    msg = f"Error: No such tool available: {name}"
    return tool_use_id, msg


async def _run_a() -> str:
    await asyncio.sleep(0)
    return "a"


async def _run_b() -> str:
    await asyncio.sleep(0)
    return "b"


async def _run_c() -> str:
    await asyncio.sleep(0)
    return "c"


async def main() -> None:
    assert is_parallel_safe_after_validation(False, True) is False
    assert is_parallel_safe_after_validation(True, True) is True
    assert is_parallel_safe_after_validation(True, False) is False

    ex = StreamingToolExecutor()
    ex.add_tool(PendingTool("1", "fast", True, _run_a))
    ex.add_tool(PendingTool("2", "fast", True, _run_b))
    ex.add_tool(PendingTool("3", "exclusive", False, _run_c))
    r = await ex.drain()
    assert [x[0] for x in r] == ["1", "2", "3"]
    abandoned = StreamingToolExecutor()
    abandoned.add_tool(PendingTool("x", "fast", True, _run_a))
    abandoned.discard()
    assert await abandoned.drain() == []

    uid, err = synthetic_unknown_tool_result("call-9", "nonexistent_tool")
    assert uid == "call-9" and "nonexistent" in err

    print("streaming_executor:", r)


if __name__ == "__main__":
    asyncio.run(main())
