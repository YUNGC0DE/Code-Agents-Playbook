"""Message type hierarchy with discriminated unions (content blocks)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


class ThinkingBlock(TypedDict):
    type: Literal["thinking"]
    thinking: str


class RedactedThinkingBlock(TypedDict):
    type: Literal["redacted_thinking"]
    data: str


class ToolUseBlock(TypedDict):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict


class ToolResultBlock(TypedDict):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str
    is_error: bool


type ContentBlock = (
    TextBlock | ThinkingBlock | RedactedThinkingBlock | ToolUseBlock | ToolResultBlock
)


@dataclass
class UserMessage:
    content: list[ContentBlock]
    role: Literal["user"] = "user"


@dataclass
class AssistantMessage:
    """Assistant turn; `response_id` models the provider message id shared across stream chunks."""

    content: list[ContentBlock]
    response_id: str
    role: Literal["assistant"] = "assistant"
    stop_reason: str | None = None


def is_thinking_only_assistant(msg: AssistantMessage) -> bool:
    """True when every block is thinking or redacted_thinking (UI/API special-cases this)."""
    if not msg.content:
        return False
    return all(
        b["type"] == "thinking" or b["type"] == "redacted_thinking" for b in msg.content
    )


if __name__ == "__main__":
    um = UserMessage(
        content=[ToolResultBlock(type="tool_result", tool_use_id="1", content="ok", is_error=False)]
    )
    assert um.content[0]["type"] == "tool_result"

    think_only = AssistantMessage(
        response_id="m1",
        content=[ThinkingBlock(type="thinking", thinking="plan")],
    )
    assert is_thinking_only_assistant(think_only) is True
    print("message_types ok")
