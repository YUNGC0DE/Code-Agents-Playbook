"""
How skills appear in the model context: discovery listing vs full body.

Aligned with product behavior (Skill tool prompt + skill listing attachment):
- Listing: names plus short descriptions, capped per entry then fitted to a global
  char budget (~1% of context window; optional env override in dev builds).
- Full body: produced on demand when the user runs a slash command, the model
  invokes the Skill tool, or a subagent preloads skills — not pasted into the
  static system prompt as a full tree.

This file is a readable stand-in: width uses len(); the app uses Unicode-aware
string width for CJK/emoji in listing lines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Mirrors SkillTool listing budget constants
SKILL_BUDGET_CONTEXT_PERCENT = 0.01
CHARS_PER_TOKEN = 4
DEFAULT_CHAR_BUDGET = 8000
MAX_LISTING_DESC_CHARS = 250
MIN_DESC_LENGTH = 20
FILTERED_LISTING_MAX = 30


def swidth(s: str) -> int:
    """Display width stand-in (product uses Unicode-aware width)."""
    return len(s)


def get_char_budget(context_window_tokens: int | None) -> int:
    override = os.environ.get("SLASH_COMMAND_TOOL_CHAR_BUDGET")
    if override:
        return int(override)
    if context_window_tokens:
        return int(
            context_window_tokens * CHARS_PER_TOKEN * SKILL_BUDGET_CONTEXT_PERCENT
        )
    return DEFAULT_CHAR_BUDGET


@dataclass(frozen=True)
class ListingCommand:
    """Minimal fields used by listing formatters."""

    name: str
    description: str
    when_to_use: str | None = None
    type: str = "prompt"
    source: str = "skills"  # "bundled" => preserve full line when global budget is tight
    loaded_from: str = "skills"  # "bundled" | "mcp" | "skills" | "plugin" — used for search filter


def get_command_description(cmd: ListingCommand) -> str:
    desc = (
        f"{cmd.description} - {cmd.when_to_use}"
        if cmd.when_to_use
        else cmd.description
    )
    if swidth(desc) > MAX_LISTING_DESC_CHARS:
        return desc[: MAX_LISTING_DESC_CHARS - 1] + "\u2026"
    return desc


def format_command_line(cmd: ListingCommand) -> str:
    return f"- {cmd.name}: {get_command_description(cmd)}"


def truncate_desc(desc: str, max_width: int) -> str:
    """Width-aware stand-in: product uses grapheme-safe truncation + ellipsis."""
    if swidth(desc) <= max_width:
        return desc
    if max_width < 1:
        return ""
    return desc[: max_width - 1] + "\u2026"


def format_commands_within_budget(
    commands: list[ListingCommand],
    context_window_tokens: int | None,
) -> str:
    """Two-phase fit: try full lines; if over budget, keep bundled lines full and trim the rest."""
    if not commands:
        return ""

    budget = get_char_budget(context_window_tokens)
    full_entries = [(cmd, format_command_line(cmd)) for cmd in commands]
    full_total = sum(swidth(e[1]) for e in full_entries) + max(0, len(full_entries) - 1)

    if full_total <= budget:
        return "\n".join(e[1] for e in full_entries)

    bundled_indices: set[int] = set()
    rest_commands: list[ListingCommand] = []
    for i, cmd in enumerate(commands):
        if cmd.type == "prompt" and cmd.source == "bundled":
            bundled_indices.add(i)
        else:
            rest_commands.append(cmd)

    bundled_chars = sum(
        swidth(full_entries[i][1]) + 1 for i in bundled_indices
    )
    remaining_budget = budget - bundled_chars

    if not rest_commands:
        return "\n".join(e[1] for e in full_entries)

    rest_name_overhead = sum(swidth(c.name) + 4 for c in rest_commands) + max(
        0, len(rest_commands) - 1
    )
    available_for_descs = remaining_budget - rest_name_overhead
    max_desc_len = available_for_descs // len(rest_commands)

    if max_desc_len < MIN_DESC_LENGTH:
        return "\n".join(
            full_entries[i][1] if i in bundled_indices else f"- {commands[i].name}"
            for i in range(len(commands))
        )

    return "\n".join(
        full_entries[i][1]
        if i in bundled_indices
        else f"- {cmd.name}: {truncate_desc(get_command_description(cmd), max_desc_len)}"
        for i, cmd in enumerate(commands)
    )


def filter_to_bundled_and_mcp(commands: list[ListingCommand]) -> list[ListingCommand]:
    """When skill-search is on: small turn-0 listing; long tail via discovery."""
    filtered = [c for c in commands if c.loaded_from in ("bundled", "mcp")]
    if len(filtered) > FILTERED_LISTING_MAX:
        return [c for c in commands if c.loaded_from == "bundled"]
    return filtered


@dataclass
class SkillListingTracker:
    """Per-agent delta: only skills not yet sent in this process get a listing attachment."""

    sent_by_agent: dict[str, set[str]] = field(default_factory=dict)
    suppress_next: bool = False

    def suppress_next_for_resume(self) -> None:
        """Skip one injection when the transcript already contains a listing from a prior run."""
        self.suppress_next = True

    def next_attachment_content(
        self,
        agent_id: str,
        all_commands: list[ListingCommand],
        context_window_tokens: int | None,
    ) -> tuple[str, int, bool] | None:
        if self.suppress_next:
            self.suppress_next = False
            for cmd in all_commands:
                self._sent(agent_id).add(cmd.name)
            return None

        sent = self._sent(agent_id)
        new_skills = [c for c in all_commands if c.name not in sent]
        if not new_skills:
            return None

        is_initial = len(sent) == 0
        for cmd in new_skills:
            sent.add(cmd.name)
        content = format_commands_within_budget(new_skills, context_window_tokens)
        return content, len(new_skills), is_initial

    def _sent(self, agent_id: str) -> set[str]:
        if agent_id not in self.sent_by_agent:
            self.sent_by_agent[agent_id] = set()
        return self.sent_by_agent[agent_id]


@dataclass(frozen=True)
class PromptSkill:
    name: str
    description: str
    body: str

    def full_prompt_text(self, args: str) -> str:
        """Stand-in for full materialization on slash / Skill tool / fork."""
        return self.body.replace("$ARGUMENTS", args.strip())


def catalog_vs_full(
    skill: PromptSkill, context_window_tokens: int | None
) -> tuple[str, str]:
    listing = format_commands_within_budget(
        [
            ListingCommand(
                name=skill.name,
                description=skill.description,
                source="skills",
                loaded_from="skills",
            )
        ],
        context_window_tokens,
    )
    return listing, skill.full_prompt_text("")


if __name__ == "__main__":
    assert get_char_budget(200_000) > 0

    sk = PromptSkill("lint-style", "When to use", "# Rules\nFix imports.\n")
    short, full = catalog_vs_full(sk, 200_000)
    assert "lint-style" in short
    assert "Fix imports" in full

    bundled = ListingCommand("core", "Bundled help", source="bundled")
    long_tail = ListingCommand(
        "plugin-x",
        "x" * 400,
        when_to_use="also long",
        source="plugin",
    )
    text = format_commands_within_budget([bundled, long_tail], 200_000)
    assert "core" in text and "plugin-x" in text

    tr = SkillListingTracker()
    c1 = tr.next_attachment_content(
        "", [ListingCommand("a", "da", source="skills")], 200_000
    )
    assert c1 is not None and c1[2] is True
    c2 = tr.next_attachment_content("", [ListingCommand("a", "da", source="skills")], 200_000)
    assert c2 is None

    tr2 = SkillListingTracker()
    tr2.suppress_next_for_resume()
    assert (
        tr2.next_attachment_content(
            "", [ListingCommand("a", "da", source="skills")], 200_000
        )
        is None
    )
    c_after = tr2.next_attachment_content(
        "", [ListingCommand("b", "db", source="skills")], 200_000
    )
    assert c_after is not None and "b" in c_after[0]

    fb = filter_to_bundled_and_mcp(
        [
            ListingCommand("b1", "d", source="bundled", loaded_from="bundled"),
            ListingCommand("m1", "d", source="skills", loaded_from="mcp"),
        ]
    )
    assert len(fb) == 2

    print("skill_context_pipeline ok")
