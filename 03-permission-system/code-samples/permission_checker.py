"""Rule-based permission checker: returns allow, deny, or ask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PermissionBehavior = Literal["allow", "deny", "ask"]


@dataclass(frozen=True)
class PermissionRule:
    tool_name: str
    behavior: PermissionBehavior
    rule_content: str | None = None


@dataclass(frozen=True)
class FrozenPermissionContext:
    """Snapshot for one resolution; tools must not mutate live policy mid-flight."""

    mode: str
    rules: tuple[PermissionRule, ...]


def resolve_tool_permission(
    tool_name: str,
    ctx: FrozenPermissionContext,
) -> PermissionBehavior:
    """First matching tool-wide rule wins; deny is checked before allow/ask."""

    matching = [r for r in ctx.rules if r.tool_name == tool_name and r.rule_content is None]
    for behavior in ("deny", "ask", "allow"):
        for rule in matching:
            if rule.behavior == behavior:
                return rule.behavior
    return "ask"


if __name__ == "__main__":
    ctx = FrozenPermissionContext(
        mode="default",
        rules=(
            PermissionRule("bash", "allow"),
            PermissionRule("bash", "deny"),
            PermissionRule("read_file", "allow"),
        ),
    )
    assert resolve_tool_permission("read_file", ctx) == "allow"
    assert resolve_tool_permission("bash", ctx) == "deny"
    ctx2 = FrozenPermissionContext(
        mode="default",
        rules=(PermissionRule("other", "allow"),),
    )
    assert resolve_tool_permission("other", ctx2) == "allow"
    assert resolve_tool_permission("unknown", ctx2) == "ask"
    print("permission_checker ok")
