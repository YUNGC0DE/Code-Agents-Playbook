"""
Toy merge order for prompt commands — bundled, builtin-plugin skills, skill-dir,
workflows, plugin commands, plugin skills, then host builtins.

Use this to reason about name shadowing when two sources define the same skill name.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCommand:
    name: str
    source: str  # e.g. bundled, skills, plugin


def merge_skill_slices(
    bundled: list[PromptCommand],
    builtin_plugin_skills: list[PromptCommand],
    skill_dir: list[PromptCommand],
    workflows: list[PromptCommand],
    plugin_commands: list[PromptCommand],
    plugin_skills: list[PromptCommand],
    builtins: list[PromptCommand],
) -> list[PromptCommand]:
    """Same concatenation order as loadAllCommands for skill-related slices."""
    return [
        *bundled,
        *builtin_plugin_skills,
        *skill_dir,
        *workflows,
        *plugin_commands,
        *plugin_skills,
        *builtins,
    ]


def first_index_by_name(commands: list[PromptCommand], name: str) -> int:
    for i, c in enumerate(commands):
        if c.name == name:
            return i
    raise KeyError(name)


if __name__ == "__main__":
    merged = merge_skill_slices(
        bundled=[PromptCommand("docs", "bundled")],
        builtin_plugin_skills=[PromptCommand("extra", "bundled")],
        skill_dir=[PromptCommand("project-skill", "skills")],
        workflows=[],
        plugin_commands=[],
        plugin_skills=[PromptCommand("vendor", "plugin")],
        builtins=[],
    )
    assert merged[0].name == "docs"
    assert merged[-1].name == "vendor"
    # Earlier slice wins if findCommand returns first match
    dup = merge_skill_slices(
        [PromptCommand("x", "bundled")],
        [],
        [PromptCommand("x", "skills")],
        [],
        [],
        [],
        [],
    )
    assert first_index_by_name(dup, "x") == 0
    print("load_skills_merge ok")
