"""In-process bridge: leader resolves a worker's permission wait by request id.

The same request_id is typically echoed in mailbox JSON when the worker
runs in another process. Here we only model the future map — enough to
show id-keyed resolution without a UI framework. Duplicate register() for
the same id should be rejected or overwrite explicitly in real code.
"""

from __future__ import annotations

import asyncio
from typing import Literal

Decision = Literal["allow", "deny"]


class LeaderPermissionBridge:
    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Future[Decision]] = {}

    def register(self, request_id: str) -> asyncio.Future[Decision]:
        fut: asyncio.Future[Decision] = asyncio.get_running_loop().create_future()
        self._waiters[request_id] = fut
        return fut

    def resolve(self, request_id: str, decision: Decision) -> None:
        fut = self._waiters.pop(request_id, None)
        if fut and not fut.done():
            fut.set_result(decision)


async def demo() -> None:
    bridge = LeaderPermissionBridge()
    fut = bridge.register("req-1")
    bridge.resolve("req-1", "allow")
    assert await fut == "allow"


if __name__ == "__main__":
    asyncio.run(demo())
    print("leader_permission_bridge ok")
