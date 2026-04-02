"""Minimal SSE-style line parser (Python 3).

Educational analogue to the read side of an SSE stream:
  event: <name>
  data: <json or text>
  (optional) id: <cursor for Last-Event-ID>
A blank line ends one logical event.

Production clients also handle retries, comments, and network errors; this
sample keeps the core line state machine only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class SseEvent:
    event: str
    data: str
    event_id: str | None = None

    def parsed_json(self) -> Any:
        return json.loads(self.data)


def parse_sse_blocks(text: str) -> list[SseEvent]:
    """Split *text* into events separated by blank lines."""
    blocks = text.split("\n\n")
    out: list[SseEvent] = []
    for block in blocks:
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        ev_name = "message"
        ev_id: str | None = None
        data_parts: list[str] = []
        for line in lines:
            if line.startswith("event:"):
                ev_name = line[len("event:") :].strip()
            elif line.startswith("id:"):
                ev_id = line[len("id:") :].strip() or None
            elif line.startswith("data:"):
                data_parts.append(line[len("data:") :].lstrip())
        if data_parts:
            out.append(
                SseEvent(event=ev_name, data="\n".join(data_parts), event_id=ev_id)
            )
    return out


if __name__ == "__main__":
    sample = (
        "id: 42\n"
        "event: client_event\n"
        'data: {"type":"ping","seq":1}\n'
        "\n"
        "event: client_event\n"
        'data: {"type":"pong","seq":2}\n'
    )
    events = parse_sse_blocks(sample)
    assert len(events) == 2
    assert events[0].event_id == "42"
    assert events[0].parsed_json()["type"] == "ping"
    assert events[1].event == "client_event"
    print("sse_event_parser ok")
