"""Group transcript rows by API round: boundary when assistant response_id changes."""

from __future__ import annotations

from typing import TypedDict


class Row(TypedDict, total=False):
    role: str
    response_id: str | None


def group_by_api_round(messages: list[Row]) -> list[list[Row]]:
    """
    One group per model round-trip: a new group starts when an assistant message
    appears whose response_id differs from the last assistant seen. All chunks
    that share one response_id stay in one group even if user/tool_result rows
    are interleaved in delivery order.
    """
    groups: list[list[Row]] = []
    current: list[Row] = []
    last_assistant_id: str | None = None

    for msg in messages:
        if (
            msg.get("role") == "assistant"
            and msg.get("response_id") is not None
            and msg.get("response_id") != last_assistant_id
            and len(current) > 0
        ):
            groups.append(current)
            current = [msg]
        else:
            current.append(msg)
        if msg.get("role") == "assistant":
            last_assistant_id = msg.get("response_id")

    if current:
        groups.append(current)
    return groups


if __name__ == "__main__":
    sample: list[Row] = [
        {"role": "user"},
        {"role": "assistant", "response_id": "a1"},
        {"role": "user"},
        {"role": "assistant", "response_id": "a1"},
        {"role": "assistant", "response_id": "a2"},
    ]
    g = group_by_api_round(sample)
    # First assistant flushes the leading user turn into its own group; same response_id
    # keeps later chunks and interleaved user rows in one group until id changes.
    assert len(g) == 3
    assert len(g[0]) == 1 and g[0][0]["role"] == "user"
    assert len(g[1]) == 3
    assert g[2][0]["response_id"] == "a2"
    print("assistant_api_rounds ok")
