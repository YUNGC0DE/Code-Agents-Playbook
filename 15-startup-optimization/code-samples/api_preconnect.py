"""Shared HTTP client and optional warm request (TLS overlap).

Call preconnect only after trust material and proxy settings are applied; skip
when the real SDK uses a different dispatcher or endpoint family.

The __main__ block stays offline-friendly; install httpx to run: pip install httpx
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx


async def preconnect_head(client: httpx.AsyncClient, base_url: str) -> None:
    try:
        await client.head(base_url, timeout=2.0)
    except httpx.HTTPError:
        pass


async def boot_with_preconnect(
    base_url: str,
    other_tasks: list[Callable[[], Awaitable[object]]],
) -> None:
    async with httpx.AsyncClient() as client:
        await asyncio.gather(
            preconnect_head(client, base_url),
            *(t() for t in other_tasks),
        )


if __name__ == "__main__":

    async def cheap_task() -> None:
        await asyncio.sleep(0.01)

    async def _demo() -> None:
        # Offline: only exercises client construction + parallel gather shape.
        async with httpx.AsyncClient() as client:
            _ = client.is_closed
        await asyncio.gather(cheap_task(), cheap_task())

    asyncio.run(_demo())
    print("api_preconnect ok")
