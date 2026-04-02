"""Subagent tool surface: allowlist vs exact parent tools, session allow rules, depth guard.

Mirrors the idea of a nested runner that either:
- resolves tools for an agent definition (subset / policy), or
- passes the parent's tool list verbatim for cache-identical serialization.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubagentSpec:
    name: str
    allowed_tools: frozenset[str] | None
    max_turns: int = 16


def filter_tools_by_allowlist(
    all_tools: dict[str, str],
    allowlist: frozenset[str],
) -> dict[str, str]:
    return {k: v for k, v in all_tools.items() if k in allowlist}


def resolve_tools_for_nested_run(
    parent_tools: dict[str, str],
    spec: SubagentSpec,
    *,
    use_exact_parent_tools: bool,
) -> dict[str, str]:
    """When use_exact_parent_tools is True, skip re-filtering (fork / cache parity path)."""
    if use_exact_parent_tools:
        return dict(parent_tools)
    if spec.allowed_tools is None:
        raise ValueError("allowed_tools required when not using exact parent tools")
    return filter_tools_by_allowlist(parent_tools, spec.allowed_tools)


def replace_session_allow_rules(
    existing_session_allow: list[str],
    explicit_allow: list[str] | None,
) -> list[str]:
    """When explicit allow list is provided, it replaces session rules (no parent leakage)."""
    if explicit_allow is None:
        return list(existing_session_allow)
    return list(explicit_allow)


def allow_nested_spawn(current_depth: int, max_depth: int = 3) -> bool:
    """Reject unbounded recursion (policy mirror: fork-in-history guard + caps)."""
    return current_depth < max_depth


if __name__ == "__main__":
    reg = {"read": "x", "bash": "y", "grep": "z"}
    spec = SubagentSpec("research", frozenset({"read", "grep"}))
    sub = resolve_tools_for_nested_run(reg, spec, use_exact_parent_tools=False)
    assert "bash" not in sub
    fork_child = resolve_tools_for_nested_run(reg, spec, use_exact_parent_tools=True)
    assert fork_child == reg
    assert replace_session_allow_rules(["parent_grant"], ["read"]) == ["read"]
    assert allow_nested_spawn(0) and not allow_nested_spawn(3)
    print("subagent_spawner ok")
