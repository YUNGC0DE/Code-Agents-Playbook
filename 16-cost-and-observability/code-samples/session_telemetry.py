"""Session-scoped trace id + monotonic event sequence; optional parent session for nesting."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)

AgentKind = Literal["main", "subagent", "teammate"]


@dataclass(frozen=True)
class TelemetryContext:
    trace: str
    session: str
    parent_session: str | None
    agent_kind: AgentKind


_event_seq = 0


def next_event_sequence() -> int:
    """Order events within a session (OTel-style sequence on log records)."""
    global _event_seq
    _event_seq += 1
    return _event_seq


def start_session_span(
    session_id: str,
    *,
    parent_session_id: str | None = None,
    agent_kind: AgentKind = "main",
) -> TelemetryContext:
    tid = str(uuid.uuid4())
    trace_id_var.set(tid)
    session_id_var.set(session_id)
    return TelemetryContext(
        trace=tid,
        session=session_id,
        parent_session=parent_session_id,
        agent_kind=agent_kind,
    )


if __name__ == "__main__":
    sp = start_session_span("sess-1")
    assert trace_id_var.get() == sp.trace
    assert session_id_var.get() == "sess-1"
    nested = start_session_span(
        "sess-child",
        parent_session_id="sess-1",
        agent_kind="subagent",
    )
    assert nested.parent_session == "sess-1"
    assert next_event_sequence() == 1
    print("session_telemetry ok")
