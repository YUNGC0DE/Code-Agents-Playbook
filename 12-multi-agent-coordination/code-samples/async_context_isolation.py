"""contextvars for per-task identity inside one process (AsyncLocalStorage in Node).

Teammate processes still get team_name / agent_name from env, CLI, or session
plus roster files; this pattern prevents async tasks in *one* interpreter from
clobbering each other's logical agent label.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar

current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)


async def worker(name: str) -> str:
    token = current_agent_id.set(name)
    try:
        await asyncio.sleep(0)
        return current_agent_id.get() or ""
    finally:
        current_agent_id.reset(token)


async def main() -> None:
    a, b = await asyncio.gather(worker("A"), worker("B"))
    assert a == "A" and b == "B"
    print("async_context_isolation ok")


if __name__ == "__main__":
    asyncio.run(main())
