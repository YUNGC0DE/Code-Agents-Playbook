"""Normalize internal messages toward an API-safe list (simplified teaching model)."""

from __future__ import annotations

from typing import Any


def strip_thinking_blocks(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop thinking / redacted_thinking when replaying history without extended thinking."""
    return [b for b in content if b.get("type") not in {"thinking", "redacted_thinking"}]


def split_assistant_one_block_per_message(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    One assistant row per content block keeps ordering and pairs UUIDs cleanly
    when the UI stores multiple blocks in one envelope.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") != "assistant":
            out.append(m)
            continue
        content = m.get("content")
        if not isinstance(content, list) or len(content) <= 1:
            out.append(m)
            continue
        base_uuid = m.get("uuid", "msg")
        for i, block in enumerate(content):
            out.append(
                {
                    **m,
                    "uuid": f"{base_uuid}:{i}",
                    "content": [block],
                }
            )
    return out


def filter_orphan_thinking_only_assistants(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove assistant rows that contain only thinking blocks when no other row
    with the same response_id carries non-thinking content (e.g. after compaction
    sliced away the sibling chunk). Prevents consecutive mismatched thinking
    signatures on replay.
    """
    ids_with_body: set[str] = set()
    for m in messages:
        if m.get("role") != "assistant":
            continue
        rid = m.get("response_id")
        if not rid:
            continue
        content = m.get("content")
        if not isinstance(content, list):
            continue
        if any(b.get("type") not in ("thinking", "redacted_thinking") for b in content):
            ids_with_body.add(rid)

    def keep(m: dict[str, Any]) -> bool:
        if m.get("role") != "assistant":
            return True
        rid = m.get("response_id")
        content = m.get("content")
        if not isinstance(content, list) or not content:
            return True
        only_thinking = all(
            b.get("type") in ("thinking", "redacted_thinking") for b in content
        )
        if not only_thinking:
            return True
        if rid and rid in ids_with_body:
            return True
        return False

    return [m for m in messages if keep(m)]


def normalize_messages_for_api(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip virtual rows, then thinking blocks for a minimal replay payload."""
    no_virtual = [m for m in messages if not m.get("is_virtual")]
    out: list[dict[str, Any]] = []
    for m in no_virtual:
        role = m.get("role")
        row = {k: v for k, v in m.items() if k != "is_virtual"}
        content = m.get("content")
        if role == "assistant" and isinstance(content, list):
            row["content"] = strip_thinking_blocks(content)
        elif "content" in m:
            row["content"] = content
        out.append(row)
    return out


if __name__ == "__main__":
    raw = [
        {
            "role": "assistant",
            "response_id": "r1",
            "content": [
                {"type": "thinking", "thinking": "x"},
                {"type": "text", "text": "hi"},
            ],
        }
    ]
    norm = normalize_messages_for_api(raw)
    assert len(norm[0]["content"]) == 1
    assert norm[0]["content"][0]["type"] == "text"

    split = split_assistant_one_block_per_message(
        [
            {
                "role": "assistant",
                "uuid": "a",
                "content": [{"type": "text", "text": "1"}, {"type": "text", "text": "2"}],
            }
        ]
    )
    assert len(split) == 2

    orphan_case = filter_orphan_thinking_only_assistants(
        [
            {"role": "assistant", "response_id": "z", "content": [{"type": "thinking", "thinking": "only"}]},
        ]
    )
    assert orphan_case == []

    print("message_normalization ok")
