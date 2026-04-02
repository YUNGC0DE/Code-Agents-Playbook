"""
Stub for recoverable API errors withheld from the consumer stream until recovery fails.

Mirrors the production pattern: assistant error messages still enter the internal
buffer used for recovery classification, but are not yielded to thin SDK clients
until recovery is exhausted (avoids treating warnings as fatal).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AssistantError:
    """Stand-in for an API error assistant message."""

    code: str
    recoverable: bool


def classify_withheld(msg: Any) -> bool:
    """Production uses multiple subsystems; any match withholds."""
    return isinstance(msg, AssistantError) and msg.recoverable


def simulate_stream_events() -> list[AssistantError | str]:
    return [AssistantError("context_too_large", True)]


def demo_withhold_then_surface() -> list[Any]:
    """Consumer-visible events: empty until recovery fails, then error surfaces."""
    out: list[Any] = []
    internal: list[Any] = []
    for raw in simulate_stream_events():
        internal.append(raw)
        withheld = classify_withheld(raw)
        if not withheld:
            out.append(raw)

    # Recovery failed — surface buffered error
    if internal and not out:
        out.append(internal[-1])
    return out


if __name__ == "__main__":
    visible = demo_withhold_then_surface()
    assert len(visible) == 1
    assert isinstance(visible[0], AssistantError)
    print("withheld_stream_stub ok")
