"""Tool scope per agent: tiers, global blocklist for subagents, pool resolution from parent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgentTier = Literal["system", "custom", "background"]


# Tools that must never be exposed to nested/sub-agents (chapter 11 tie-in).
GLOBAL_SUBAGENT_BLOCKLIST: frozenset[str] = frozenset(
    {
        "spawn_subagent",
        "ask_user",
        "plan_task",
        "delegate",
    }
)

BACKGROUND_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "edit_file",
        "write_file",
        "glob",
        "grep",
        "web_search",
        "web_fetch",
        "bash",
    }
)


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    tools: list[str]  # ["*"] = all parent tools minus blocklists (system tier only)
    disallowed_tools: list[str]
    max_turns: int | None = None
    permission_mode: str | None = None
    tier: AgentTier = "custom"


def resolve_tool_pool(
    parent_tool_names: frozenset[str],
    definition: AgentDefinition,
    *,
    apply_subagent_blocklist: bool,
) -> frozenset[str]:
    """Parent pool → agent list → subtract global (optional) → subtract agent blocklist."""
    if definition.tools == ["*"]:
        pool = set(parent_tool_names)
    else:
        wanted = set(definition.tools)
        pool = wanted & parent_tool_names

    if apply_subagent_blocklist:
        pool -= GLOBAL_SUBAGENT_BLOCKLIST

    pool -= set(definition.disallowed_tools)
    return frozenset(pool)


def tools_for_tier(
    parent_tool_names: frozenset[str],
    definition: AgentDefinition,
) -> frozenset[str]:
    """Apply tier defaults: background gets strict allowlist; system/custom use definition."""
    if definition.tier == "background":
        base = resolve_tool_pool(
            parent_tool_names,
            AgentDefinition(
                name=definition.name,
                tools=sorted(BACKGROUND_ALLOWED_TOOLS & parent_tool_names),
                disallowed_tools=list(definition.disallowed_tools),
                max_turns=definition.max_turns,
                permission_mode=definition.permission_mode,
                tier="background",
            ),
            apply_subagent_blocklist=True,
        )
        return base & BACKGROUND_ALLOWED_TOOLS

    apply_block = definition.tier != "system"
    return resolve_tool_pool(parent_tool_names, definition, apply_subagent_blocklist=apply_block)


if __name__ == "__main__":
    parent = frozenset(
        {
            "read_file",
            "edit_file",
            "bash",
            "spawn_subagent",
            "ask_user",
            "grep",
        }
    )
    custom = AgentDefinition(
        name="reviewer",
        tools=["read_file", "grep", "spawn_subagent"],
        disallowed_tools=[],
        tier="custom",
    )
    r = resolve_tool_pool(parent, custom, apply_subagent_blocklist=True)
    assert "spawn_subagent" not in r
    assert r == frozenset({"read_file", "grep"})

    sys_def = AgentDefinition(
        name="orchestrator",
        tools=["*"],
        disallowed_tools=["spawn_subagent"],
        tier="system",
    )
    sys_pool = tools_for_tier(parent, sys_def)
    assert "spawn_subagent" not in sys_pool and "bash" in sys_pool

    bg = AgentDefinition(name="bg", tools=[], disallowed_tools=[], tier="background")
    bg_pool = tools_for_tier(parent, bg)
    assert "spawn_subagent" not in bg_pool
    print("tool_scope ok")
