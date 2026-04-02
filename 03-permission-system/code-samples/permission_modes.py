"""Permission modes: coarse presets layered under deny/ask rules and tool checks."""

from __future__ import annotations

from enum import Enum


class PermissionMode(str, Enum):
    """User-visible modes (simplified subset for education).

    Production also includes dontAsk (map ask→deny) and auto (classifier instead of UI)
    when the corresponding product features are enabled.
    """

    DEFAULT = "default"
    PLAN = "plan"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS = "bypassPermissions"


def mode_allows_without_prompt(mode: PermissionMode, tool_name: str) -> bool:
    """Orientation only: the mode hint before merged rules and per-tool permission.

    Real stacks still apply deny lists, content-specific ask rules, safety checks,
    and tools that require human interaction—even in bypass.
    """
    if mode == PermissionMode.BYPASS:
        return True
    if mode == PermissionMode.PLAN and tool_name in {"Read", "Glob", "Grep"}:
        return True
    return False


if __name__ == "__main__":
    assert mode_allows_without_prompt(PermissionMode.BYPASS, "Bash")
    assert not mode_allows_without_prompt(PermissionMode.PLAN, "Bash")
    print("permission_modes ok")
