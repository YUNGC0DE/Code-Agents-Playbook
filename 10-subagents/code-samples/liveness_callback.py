"""
Optional progress callback during nested query() — detects liveness when the model
emits long single-block streams (e.g. extended thinking) with no new assistant
message for tens of seconds.

Low-level transports often yield stream_event / delta rows before a full assistant
message exists; a runner may drop those for transcript logic but still forward
liveness to the parent UI (time-to-first-token, spinner refresh).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable


async def consume_subagent_stream(
    events: AsyncIterator[Any],
    on_progress: Callable[[], None] | None = None,
) -> list[Any]:
    out: list[Any] = []
    async for ev in events:
        if on_progress:
            on_progress()
        out.append(ev)
    return out


if __name__ == "__main__":
    ticks = [0]

    def bump() -> None:
        ticks[0] += 1

    async def gen() -> AsyncIterator[int]:
        yield 1

    import asyncio

    asyncio.run(consume_subagent_stream(gen(), bump))
    assert ticks[0] == 1
    print("liveness_callback ok")
