"""
Pre/post compact hooks wrapping a compaction function.

Same lifecycle idea as PreCompact / PostCompact in the product: run side
effects around a mutating step, always invoke post in a finally block.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


async def with_compact_hooks(
    pre: Callable[[], Coroutine[Any, Any, None]],
    post: Callable[[], Coroutine[Any, Any, None]],
    compact: Callable[[], Coroutine[Any, Any, T]],
) -> T:
    await pre()
    try:
        return await compact()
    finally:
        await post()


if __name__ == "__main__":
    log: list[str] = []

    async def pre() -> None:
        log.append("pre")

    async def post() -> None:
        log.append("post")

    async def compact() -> str:
        log.append("compact")
        return "ok"

    async def main() -> None:
        r = await with_compact_hooks(pre, post, compact)
        assert r == "ok"

    import asyncio

    asyncio.run(main())
    assert log == ["pre", "compact", "post"]
    print("lifecycle_hooks ok")
