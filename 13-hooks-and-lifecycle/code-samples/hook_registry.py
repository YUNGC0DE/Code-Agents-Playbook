"""
Generic async fan-out registry: many handlers per named event.

Production separates this idea from the *pending subprocess* registry used when
a command hook prints an initial {"async": true} line and keeps running — that
tracker is modeled in async_pending_hooks.py.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

HookFn: TypeAlias = Callable[[dict[str, Any]], Awaitable[None]]


class MultiHandlerHookRegistry:
    """Subscribe async callables; emit runs all subscribers for an event in parallel."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = defaultdict(list)

    def on(self, event: str, fn: HookFn) -> None:
        self._hooks[event].append(fn)

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        await asyncio.gather(*(h(payload) for h in self._hooks.get(event, [])))


if __name__ == "__main__":
    reg = MultiHandlerHookRegistry()
    seen: list[str] = []

    async def h1(_: dict[str, Any]) -> None:
        seen.append("a")

    async def h2(_: dict[str, Any]) -> None:
        seen.append("b")

    reg.on("session_start", h1)
    reg.on("session_start", h2)

    async def main() -> None:
        await reg.emit("session_start", {})

    asyncio.run(main())
    assert set(seen) == {"a", "b"}
    print("hook_registry ok")
