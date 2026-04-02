"""
Streaming exit semantics: do not rely on stop_reason == 'tool_use' alone.

Some APIs inconsistently set stop_reason when tool blocks are present; the robust
signal is whether any executable tool blocks were assembled (e.g. tool_use in the
Anthropic-style wire format; map your provider's server-tool blocks the same way).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ToolUseBlock:
    id: str
    name: str


@dataclass
class AssistantMessage:
    stop_reason: str | None
    tool_use_blocks: list[ToolUseBlock]


def should_continue_for_tools(msg: AssistantMessage) -> bool:
    """Authoritative: pending tools mean another model call after tool_result."""
    return len(msg.tool_use_blocks) > 0


def naive_stop_reason_only(msg: AssistantMessage) -> bool:
    """Fragile: stop_reason may omit 'tool_use' even when tools are present."""
    return msg.stop_reason == "tool_use"


if __name__ == "__main__":
    ambiguous = AssistantMessage(
        stop_reason="end_turn",  # or null — observed in the wild
        tool_use_blocks=[ToolUseBlock("1", "bash")],
    )
    assert should_continue_for_tools(ambiguous) is True
    assert naive_stop_reason_only(ambiguous) is False
    print("tool_use_exit_signal ok")
