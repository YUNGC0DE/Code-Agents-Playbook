"""Micro-compaction: replace a range of messages with a boundary note (educational)."""

from __future__ import annotations

from typing import Any

# Production stacks often allowlist tool types that are safe to compact in place
# (large file reads, shell logs, grep output) — keep business logic in one place.
COMPACTABLE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "file_read",
        "bash",
        "grep",
        "glob",
        "web_fetch",
        "web_search",
        "file_edit",
        "file_write",
    },
)


def is_compactable_tool(name: str) -> bool:
    return name in COMPACTABLE_TOOL_NAMES


def apply_micro_compact(
    messages: list[dict[str, Any]],
    start_idx: int,
    end_idx: int,
    summary_text: str,
) -> list[dict[str, Any]]:
    """Replace messages[start_idx:end_idx] with a single user-facing boundary note."""
    head = messages[:start_idx]
    tail = messages[end_idx:]
    boundary = {
        "role": "user",
        "content": [{"type": "text", "text": f"[Compacted turns]\n{summary_text}"}],
    }
    return [*head, boundary, *tail]


if __name__ == "__main__":
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    out = apply_micro_compact(msgs, 0, 2, "previous work summarized.")
    assert len(out) == 1
    assert is_compactable_tool("grep")
    print("micro_compaction ok")
