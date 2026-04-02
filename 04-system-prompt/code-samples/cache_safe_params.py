"""Normalize parameters that participate in prompt-cache keys to avoid accidental churn."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def cache_key_prefix(
    model: str,
    system_prompt_blocks: tuple[str, ...],
    tool_names: tuple[str, ...],
    user_context: dict[str, str] | None = None,
    system_context: dict[str, str] | None = None,
    thinking_signature: str | None = None,
) -> str:
    """
    Fingerprint the stable prefix of a request. Same inputs -> same bytes -> cache hit.

    Production cache identity also depends on user/system context maps (prepended or
    appended to messages/system), tool schemas, message prefix, and thinking/output
    limits — include anything your provider keys on.
    """
    payload = stable_json(
        {
            "model": model,
            "system": list(system_prompt_blocks),
            "tools": list(tool_names),
            "user_ctx": user_context or {},
            "system_ctx": system_context or {},
            "thinking": thinking_signature or "",
        }
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


if __name__ == "__main__":
    k1 = cache_key_prefix("model-v1", ("sys",), ("bash", "read"))
    k2 = cache_key_prefix("model-v1", ("sys",), ("bash", "read"))
    k3 = cache_key_prefix("model-v1", ("sys",), ("bash",))
    assert k1 == k2
    assert k1 != k3
    k4 = cache_key_prefix(
        "model-v1",
        ("sys",),
        ("bash", "read"),
        user_context={"cwd": "/a"},
    )
    assert k4 != k1
    print("cache_safe_params:", k1)
