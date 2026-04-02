"""
Fork-style message prefix for prompt cache sharing (conceptual wire shape).

Fork children keep the assistant message identical, use the SAME placeholder
string for every tool_result, and only differ in the final directive text —
maximizing cache hits on the shared prefix.

Structure: [ ...history , assistant(all tool_uses), user(placeholder results + directive) ]
"""

from __future__ import annotations

from dataclasses import dataclass


PLACEHOLDER_TOOL_RESULT = "Fork started — processing in background"


@dataclass(frozen=True)
class ToolUse:
    tool_use_id: str


@dataclass(frozen=True)
class AssistantTurn:
    """Simplified assistant row: only tool_use ids matter for pairing."""

    tool_uses: tuple[ToolUse, ...]


@dataclass(frozen=True)
class ForkUserTurn:
    """Placeholder tool_result blocks share one string; directive is unique per child."""

    placeholder_results: tuple[tuple[str, str], ...]
    directive_text: str


def build_fork_user_turn(tool_uses: list[ToolUse], directive: str) -> ForkUserTurn:
    pairs = tuple((u.tool_use_id, PLACEHOLDER_TOOL_RESULT) for u in tool_uses)
    return ForkUserTurn(placeholder_results=pairs, directive_text=directive)


def fork_prefix_messages(
    assistant: AssistantTurn,
    directive: str,
) -> tuple[AssistantTurn, ForkUserTurn]:
    """Returns (assistant_snapshot, user_turn) appended after shared history."""
    user_turn = build_fork_user_turn(list(assistant.tool_uses), directive)
    return assistant, user_turn


if __name__ == "__main__":
    uses = (ToolUse("call_1"), ToolUse("call_2"))
    asst = AssistantTurn(tool_uses=uses)
    _, a_user = fork_prefix_messages(asst, "/fork: summarize src")
    _, b_user = fork_prefix_messages(asst, "/fork: fix tests")
    assert all(text == PLACEHOLDER_TOOL_RESULT for _, text in a_user.placeholder_results)
    assert a_user.placeholder_results == b_user.placeholder_results
    assert a_user.directive_text != b_user.directive_text
    print("fork_message_prefix ok")
