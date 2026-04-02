"""
Canonical hook event names for registry design.

Mirrors the public SDK HOOK_EVENTS list (single source for schemas and docs).

**Broadcast vs opt-in:** hook execution telemetry always includes SessionStart
and Setup for subscribers; emitting the full HOOK_EVENTS set to clients
typically requires opting in so lower-signal events do not spam by default.
"""

from __future__ import annotations

# Canonical HOOK_EVENTS — public hook name union (product SDK)
HOOK_EVENTS: tuple[str, ...] = (
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Notification",
    "UserPromptSubmit",
    "SessionStart",
    "SessionEnd",
    "Stop",
    "StopFailure",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "PostCompact",
    "PermissionRequest",
    "PermissionDenied",
    "Setup",
    "TeammateIdle",
    "TaskCreated",
    "TaskCompleted",
    "Elicitation",
    "ElicitationResult",
    "ConfigChange",
    "WorktreeCreate",
    "WorktreeRemove",
    "InstructionsLoaded",
    "CwdChanged",
    "FileChanged",
)


def list_hook_events_for_docs() -> list[str]:
    return list(HOOK_EVENTS)


if __name__ == "__main__":
    assert "PreCompact" in HOOK_EVENTS
    assert "Setup" in HOOK_EVENTS
    assert len(HOOK_EVENTS) == 27
    print("hook_event_surface ok")
