"""Collect user and system context key-value maps (conceptual; not a wire format)."""

from __future__ import annotations


def build_user_context(
    cwd: str,
    shell: str,
    *,
    claude_md_aggregated: str | None = None,
    extras: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    User-side context often includes cwd, shell, current date, and aggregated
    project instruction files (CLAUDE.md-style). Keys are stable labels for
    tests and logging.
    """
    ctx: dict[str, str] = {
        "cwd": cwd,
        "shell": shell,
    }
    if claude_md_aggregated:
        ctx["claudeMd"] = claude_md_aggregated
    if extras:
        ctx.update(extras)
    return ctx


def build_system_context(
    *,
    git_status_summary: str | None = None,
    extras: dict[str, str] | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    if git_status_summary:
        out["gitStatus"] = git_status_summary
    if extras:
        out.update(extras)
    return out


def merge_instruction_layers(
    *layers: dict[str, str],
) -> dict[str, str]:
    """
    Later dicts override earlier keys. Model filesystem discovery as ordered
    layers: managed -> user-global -> project (root to cwd) -> local-private.
    """
    merged: dict[str, str] = {}
    for layer in layers:
        merged.update(layer)
    return merged


def merge_context(
    base: dict[str, str],
    project: dict[str, str] | None,
    local: dict[str, str] | None,
) -> dict[str, str]:
    """Later layers override earlier: local > project > base."""
    out = dict(base)
    if project:
        out.update(project)
    if local:
        out.update(local)
    return out


def append_system_context_lines(system_blocks: list[str], ctx: dict[str, str]) -> list[str]:
    """Toy: flatten map into labeled lines after existing system blocks."""
    if not ctx:
        return system_blocks
    lines = "\n".join(f"{k}: {v}" for k, v in sorted(ctx.items()))
    return [*system_blocks, lines]


if __name__ == "__main__":
    u = build_user_context("/repo", "zsh", claude_md_aggregated="# Rules\nBe concise.")
    assert "claudeMd" in u
    s = build_system_context(git_status_summary="## main")
    assert s["gitStatus"].startswith("##")

    layers = merge_instruction_layers(
        {"tone": "formal"},
        {"tone": "casual", "scope": "repo"},
    )
    assert layers["tone"] == "casual" and layers["scope"] == "repo"

    m = merge_context({"a": "1"}, {"a": "2", "b": "x"}, {"a": "3"})
    assert m["a"] == "3"

    sys_plus = append_system_context_lines(["base prompt"], {"gitStatus": "clean"})
    assert "gitStatus" in sys_plus[-1]

    print("context_builder ok")
