"""
Educational model of the pending-async shell hook path.

Production behavior (simplified): a command hook may print a first-line JSON
marker with "async": true so the subprocess keeps running. The runtime
registers the shell handle in a global pending map, applies a timeout, polls
stdout for JSON lines until a sync response appears, emits progress/final
outcomes, and clears the map on shutdown (finalize all).

This sample uses in-memory buffers instead of real processes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingHook:
    process_id: str
    hook_name: str
    start_time: float
    timeout_ms: float
    stdout_buffer: str = ""
    response_delivered: bool = False


@dataclass
class PendingAsyncHookRegistry:
    """Tracks long-running shell hooks until a JSON response line is consumed."""

    _pending: dict[str, PendingHook] = field(default_factory=dict)

    def register(
        self,
        process_id: str,
        hook_name: str,
        timeout_ms: float = 15_000.0,
    ) -> None:
        self._pending[process_id] = PendingHook(
            process_id=process_id,
            hook_name=hook_name,
            start_time=time.monotonic() * 1000,
            timeout_ms=timeout_ms,
        )

    def append_stdout(self, process_id: str, chunk: str) -> None:
        hook = self._pending.get(process_id)
        if hook:
            hook.stdout_buffer += chunk

    def poll_ready_responses(self) -> list[dict[str, Any]]:
        """Return parsed JSON objects from lines that look like sync responses."""
        out: list[dict[str, Any]] = []
        now = time.monotonic() * 1000
        for pid, hook in list(self._pending.items()):
            if hook.response_delivered:
                continue
            if now - hook.start_time > hook.timeout_ms:
                continue
            for line in hook.stdout_buffer.splitlines():
                line = line.strip()
                if line.startswith("{") and '"async"' not in line:
                    # Educational: real code validates with schemas.
                    out.append({"process_id": pid, "parsed": line})
                    hook.response_delivered = True
                    break
        return out

    def finalize_all(self) -> list[str]:
        """Clear pending entries (e.g. on shutdown); return ids removed."""
        ids = list(self._pending.keys())
        self._pending.clear()
        return ids


if __name__ == "__main__":
    reg = PendingAsyncHookRegistry()
    reg.register("p1", "my-hook", timeout_ms=60_000.0)
    reg.append_stdout("p1", '{"async": true}\n')
    reg.append_stdout("p1", '{"decision": "allow"}\n')
    ready = reg.poll_ready_responses()
    assert len(ready) == 1
    reg.finalize_all()
    print("async_pending_hooks ok")
