"""
Dispatch hook backends (educational stubs).

Production shape:
- **command** — spawn bash or PowerShell; write JSON to stdin; read stdout for
  sync JSON or an async marker, then optionally register a pending shell hook.
- **http** — POST the same JSON string to a URL; enforce allowlist / timeout /
  optional SSRF safeguards; parse JSON body as hook output.
- **agent** / **prompt** / **callback** / **function** — other paths in the same
  orchestration layer (not shown here).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

Backend = Literal["agent", "http", "command"]


@dataclass(frozen=True)
class HookSpec:
    name: str
    backend: Backend
    target: str


def encode_hook_input(payload: dict[str, Any]) -> str:
    """Same idea as production: one JSON blob per invocation on stdin or HTTP body."""
    return json.dumps(payload, separators=(",", ":"))


async def run_hook(spec: HookSpec, payload: dict[str, Any]) -> dict[str, Any]:
    if spec.backend == "agent":
        return {"ran": "agent", "target": spec.target, "payload_keys": list(payload)}
    if spec.backend == "command":
        body = encode_hook_input(payload)
        return {
            "ran": "command",
            "would_spawn": spec.target,
            "stdin_bytes": len(body.encode()),
            "note": "subprocess writes JSON to stdin; stdout parsed for hook JSON",
        }
    if spec.backend == "http":
        return {
            "ran": "http",
            "url": spec.target,
            "method": "POST",
            "body_preview": encode_hook_input(payload)[:120],
            "note": "HTTP hook POSTs JSON; response body must be hook JSON",
        }
    raise ValueError(spec.backend)


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        r_http = await run_hook(
            HookSpec("x", "http", "https://example.com/hook"), {"a": 1}
        )
        assert r_http["ran"] == "http"
        r_cmd = await run_hook(HookSpec("y", "command", "/usr/local/bin/my-hook.sh"), {})
        assert r_cmd["ran"] == "command"

    asyncio.run(main())
    print("hook_execution_backends ok")
