"""
Minimal async-generator agent loop: mock model returns tool calls, tools execute, loop continues.

Production-style ideas reflected here:
- The outer function is an async generator consumed by UI/SDK (same idea as yield* in TS).
- Optional "request start" event before work so clients can show spinners / correlate spans.
- Query chain depth increments per nested logical call (parent/child query tracking).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class AssistantMessage:
    content: list[dict[str, Any]]


@dataclass
class UserMessage:
    content: list[dict[str, Any]]


type Message = AssistantMessage | UserMessage


@dataclass
class MockModel:
    """Returns scripted assistant messages (tool calls then final text)."""

    _script: list[AssistantMessage] = field(default_factory=list)
    _i: int = 0

    async def complete(self, messages: list[Message]) -> AssistantMessage:
        if self._i >= len(self._script):
            return AssistantMessage(content=[{"type": "text", "text": "done"}])
        msg = self._script[self._i]
        self._i += 1
        return msg


async def run_tool(name: str, input: dict[str, Any]) -> str:
    if name == "echo":
        return f"echo:{input.get('text', '')}"
    return f"unknown_tool:{name}"


async def agent_loop(
    model: MockModel,
    initial_messages: list[Message],
    max_turns: int = 8,
    chain_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yields events: stream_request_start, assistant_message, tool_result, done.
    """
    messages = list(initial_messages)
    turns = 0
    depth = 0
    cid = chain_id or str(uuid.uuid4())
    while turns < max_turns:
        turns += 1
        depth += 1
        yield {
            "type": "stream_request_start",
            "query_chain": {"chain_id": cid, "depth": depth},
        }
        assistant = await model.complete(messages)
        messages.append(assistant)
        yield {"type": "assistant_message", "message": assistant}

        # Authoritative follow-up signal: tool_use blocks observed during streaming,
        # not stop_reason (which can be inconsistent across providers).
        tool_blocks = [b for b in assistant.content if b.get("type") == "tool_use"]
        if not tool_blocks:
            yield {"type": "done", "reason": "end_turn"}
            return

        for block in tool_blocks:
            tid = block["id"]
            name = block["name"]
            inp = block.get("input") or {}
            result = await run_tool(name, inp)
            user_msg = UserMessage(
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": result,
                        "is_error": False,
                    }
                ]
            )
            messages.append(user_msg)
            yield {"type": "tool_result", "tool_use_id": tid, "content": result}

    yield {"type": "done", "reason": "max_turns"}


async def main() -> None:
    script = [
        AssistantMessage(
            content=[
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "echo",
                    "input": {"text": "hello"},
                }
            ]
        ),
        AssistantMessage(content=[{"type": "text", "text": "Finished."}]),
    ]
    model = MockModel(_script=script)
    events: list[dict[str, Any]] = []
    async for ev in agent_loop(model, []):
        events.append(ev)
    assert any(e["type"] == "tool_result" for e in events)
    assert events[-1]["type"] == "done"
    print("agent_loop:", events)


if __name__ == "__main__":
    asyncio.run(main())
