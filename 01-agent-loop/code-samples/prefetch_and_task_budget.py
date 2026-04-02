"""
Overlap speculative work with streaming/tools, and keep API-side task budget honest
after compaction — patterns common in production agent stacks.

Typical layout: start a memory/context prefetch once per user submission (the
prompt stack is stable across inner model rounds), and optionally start
per-iteration discovery work so it runs concurrently with streaming and tool
execution instead of blocking the attachment path.

Educational stub: no network, no real I/O.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class TaskBudgetState:
    """Tracks how much of the task token budget the model should still 'see'."""

    total: int
    remaining: int | None = None

    def __post_init__(self) -> None:
        if self.remaining is None:
            self.remaining = self.total

    def subtract_pre_compact_window(self, final_context_tokens: int) -> None:
        """
        After autocompact, the API may only see a summary and under-count spend.
        Subtract the last full context size so remaining reflects reality.
        """
        assert self.remaining is not None
        self.remaining = max(0, self.remaining - final_context_tokens)


@dataclass
class PrefetchHandles:
    """User-controlled resources cleaned up on all generator exit paths."""

    tasks: list[asyncio.Task[object]] = field(default_factory=list)

    def cancel_all(self) -> None:
        for t in self.tasks:
            if not t.done():
                t.cancel()


async def start_relevant_memory_prefetch() -> asyncio.Task[str]:
    """Placeholder: would scan cwd / memory files while the model streams."""

    async def _fake() -> str:
        await asyncio.sleep(0)
        return "memory_snippets"

    return asyncio.create_task(_fake())


async def start_skill_discovery_prefetch() -> asyncio.Task[str]:
    """Placeholder: mirrors per-iteration skill discovery hidden under stream/tools."""

    async def _fake() -> str:
        await asyncio.sleep(0)
        return "skill_hints"

    return asyncio.create_task(_fake())


async def consume_prefetch(task: asyncio.Task[str]) -> str:
    return await task


@dataclass
class MemoryPrefetchStub:
    """
    Once-per-turn memory prefetch: may settle after one or more loop iterations.
    Consume only when settled and not yet consumed (mirrors settle/consume gating).
    """

    settle_delay_s: float = 0.0
    _task: asyncio.Task[str] | None = None
    settled_at: int | None = None
    consumed_on_iteration: int = -1

    def start(self) -> None:
        if self._task is None:
            delay = self.settle_delay_s

            async def _work() -> str:
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(0)
                return "memory_snippets"

            self._task = asyncio.create_task(_work())

    def mark_settled_if_done(self, iteration: int) -> None:
        if self._task and self._task.done() and self.settled_at is None:
            self.settled_at = iteration

    async def consume_if_ready(self, iteration: int) -> str | None:
        if (
            self.settled_at is None
            or self.consumed_on_iteration >= 0
            or self._task is None
        ):
            return None
        text = await self._task
        self.consumed_on_iteration = iteration
        return text


async def demo_loop_body() -> None:
    handles = PrefetchHandles()
    mem_task = await start_relevant_memory_prefetch()
    skill_task = await start_skill_discovery_prefetch()
    handles.tasks.extend([mem_task, skill_task])

    # ... stream model, run tools ...
    snippets = await consume_prefetch(mem_task)
    skills = await consume_prefetch(skill_task)
    assert snippets == "memory_snippets"
    assert skills == "skill_hints"

    handles.cancel_all()


async def demo_memory_prefetch_multistep() -> None:
    """Settle on iteration 1, consume on iteration 1 (iteration 0 skips)."""
    mp = MemoryPrefetchStub(settle_delay_s=0.02)
    mp.start()
    mp.mark_settled_if_done(0)
    assert await mp.consume_if_ready(0) is None
    await asyncio.sleep(0.03)
    mp.mark_settled_if_done(1)
    got = await mp.consume_if_ready(1)
    assert got == "memory_snippets"
    assert await mp.consume_if_ready(2) is None


if __name__ == "__main__":
    asyncio.run(demo_loop_body())
    asyncio.run(demo_memory_prefetch_multistep())
    budget = TaskBudgetState(total=100_000)
    budget.subtract_pre_compact_window(42_000)
    assert budget.remaining == 58_000
    print("prefetch_and_task_budget ok")
