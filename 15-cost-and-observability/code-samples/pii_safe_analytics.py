"""Verbose metadata types so call sites acknowledge non-PII analytics fields."""

from __future__ import annotations

from typing import Literal, TypedDict


class AnalyticsMetadataVerifiedNotPaths(TypedDict, total=False):
    """
    Only add keys after verifying values are not file paths or code snippets.
    """

    feature_flag: str
    session_bucket: str


AgentKind = Literal["standalone", "subagent", "teammate"]


class EventMetadataCore(TypedDict, total=False):
    """
    Core coarse fields: model + session + agent attribution.
    agent_kind is intentionally low-cardinality for dashboards.
    """

    model: str
    session_id: str
    agent_kind: AgentKind
    parent_session_id: str


def log_event(name: str, meta: AnalyticsMetadataVerifiedNotPaths) -> None:
    _ = (name, meta)


def log_event_with_core(name: str, core: EventMetadataCore, extra: AnalyticsMetadataVerifiedNotPaths) -> None:
    _ = (name, core, extra)


if __name__ == "__main__":
    log_event("startup", {"feature_flag": "x", "session_bucket": "prod"})
    log_event_with_core(
        "nested_done",
        {
            "model": "example-model",
            "session_id": "sess-child",
            "agent_kind": "subagent",
            "parent_session_id": "sess-root",
        },
        {"session_bucket": "prod"},
    )
    print("pii_safe_analytics ok")
