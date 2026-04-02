"""Run independent startup tasks concurrently with per-task timeouts.

Product pattern: schedule subprocess or Keychain IO at the entrypoint so it
overlaps with heavy static imports; here we model that with async tasks only.
"""

from __future__ import annotations

import asyncio
from typing import Any


async def load_config() -> dict[str, Any]:
    await asyncio.sleep(0.01)
    return {"theme": "dark"}


async def load_credentials() -> str:
    await asyncio.sleep(0.01)
    return "token"


async def flaky_optional_warmup() -> None:
    """Non-critical task: may time out without failing the whole boot."""
    await asyncio.sleep(0.5)


async def with_timeout(coro: Any, seconds: float, default: Any) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except TimeoutError:
        return default


async def boot() -> tuple[dict[str, Any], str, str | None]:
    cfg_task = load_config()
    creds_task = load_credentials()
    warmup_task = with_timeout(flaky_optional_warmup(), 0.02, default=None)

    cfg, creds, warm = await asyncio.gather(cfg_task, creds_task, warmup_task)
    return cfg, creds, warm


if __name__ == "__main__":
    c, t, w = asyncio.run(boot())
    assert c["theme"] == "dark" and t == "token" and w is None
    print("parallel_boot ok")
