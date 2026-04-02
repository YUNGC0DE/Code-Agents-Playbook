"""Fold streaming events into buffers; merge assistant chunks that share one response id."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class StreamAssembler:
    """Accumulates text from content_block_delta / text_delta events."""

    text_buffer: str = ""

    def on_text_delta(self, s: str) -> None:
        self.text_buffer += s

    def finalize_text_block(self) -> dict[str, str]:
        block = {"type": "text", "text": self.text_buffer}
        self.text_buffer = ""
        return block


@dataclass
class AssistantMergeState:
    """Chunks from the same HTTP response share a stable assistant message id."""

    response_id: str | None = None
    blocks: list[dict] = field(default_factory=list)

    def merge(self, response_id: str, new_blocks: list[dict]) -> None:
        if self.response_id is None:
            self.response_id = response_id
        if self.response_id != response_id:
            raise ValueError("response_id changed mid-stream")
        self.blocks.extend(new_blocks)


def merge_assistant_chunks(chunks: list[tuple[str, list[dict]]]) -> AssistantMergeState:
    """(response_id, partial content blocks) -> single logical assistant message."""
    state = AssistantMergeState()
    for rid, blocks in chunks:
        state.merge(rid, blocks)
    return state


async def fake_sse(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def consume_stream() -> dict[str, str]:
    asm = StreamAssembler()
    async for chunk in fake_sse(["Hel", "lo", " world"]):
        asm.on_text_delta(chunk)
    return asm.finalize_text_block()


async def main() -> None:
    b = await consume_stream()
    assert b["text"] == "Hello world"

    merged = merge_assistant_chunks(
        [
            ("mid-1", [{"type": "thinking", "thinking": "…"}]),
            ("mid-1", [{"type": "text", "text": "ok"}]),
        ]
    )
    assert merged.response_id == "mid-1"
    assert len(merged.blocks) == 2

    print("stream_handler ok")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
