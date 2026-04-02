"""Attachments as user-facing content blocks: stable ids, dedupe, ordering hints."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ImageBlock(TypedDict):
    type: Literal["image"]
    source: dict[str, Any]  # e.g. {"type": "url", "url": "..."} or base64 payload
    attachment_id: str


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


type UserContentBlock = TextBlock | ImageBlock


def dedupe_images_by_attachment_id(blocks: list[UserContentBlock]) -> list[UserContentBlock]:
    """Keep first occurrence of each attachment_id (compaction can duplicate memory files)."""
    seen: set[str] = set()
    out: list[UserContentBlock] = []
    for b in blocks:
        if b["type"] == "image":
            aid = b["attachment_id"]
            if aid in seen:
                continue
            seen.add(aid)
        out.append(b)
    return out


def user_message_from_uploads(text: str, paths: list[tuple[str, str]]) -> dict[str, Any]:
    """
    Build one user row: optional lead text plus image blocks each with a stable id.

    paths: (attachment_id, url) pairs as a stand-in for prefetched or pasted files.
    """
    content: list[UserContentBlock] = []
    if text.strip():
        content.append(TextBlock(type="text", text=text))
    for aid, url in paths:
        content.append(
            ImageBlock(
                type="image",
                attachment_id=aid,
                source={"type": "url", "url": url},
            )
        )
    return {"role": "user", "content": content}


if __name__ == "__main__":
    dup_blocks: list[UserContentBlock] = [
        ImageBlock(type="image", attachment_id="m1", source={"type": "url", "url": "u1"}),
        TextBlock(type="text", text="see image"),
        ImageBlock(type="image", attachment_id="m1", source={"type": "url", "url": "u1"}),
    ]
    assert len(dedupe_images_by_attachment_id(dup_blocks)) == 2

    row = user_message_from_uploads("hi", [("a", "https://example.com/f.png")])
    assert row["content"][0]["type"] == "text"
    assert row["content"][1]["type"] == "image"
    print("attachments_pipeline ok")
