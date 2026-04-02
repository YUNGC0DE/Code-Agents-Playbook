"""Priority-based system prompt assembly (toy model of production layering)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptInputs:
    default_blocks: tuple[str, ...]
    custom_system_prompt: str | None
    agent_system_prompt: str | None
    override_system_prompt: str | None
    append_system_prompt: str | None
    # When True, agent instructions stack on top of defaults (proactive-style).
    proactive_mode: bool = False
    # Coordinator replaces default only when active and no main-thread agent.
    coordinator_mode: bool = False
    coordinator_prompt: str | None = None


def build_effective_system_prompt(p: PromptInputs) -> tuple[str, ...]:
    if p.override_system_prompt:
        return (p.override_system_prompt,)

    # Early exit: coordinator base does not compose with agent/custom/default.
    if p.coordinator_mode and not p.agent_system_prompt:
        blocks: tuple[str, ...] = (p.coordinator_prompt or "",)
        if p.append_system_prompt:
            blocks = (*blocks, p.append_system_prompt)
        return blocks

    if p.agent_system_prompt and p.proactive_mode:
        blocks = (
            *p.default_blocks,
            f"\n# Custom Agent Instructions\n{p.agent_system_prompt}",
        )
        if p.append_system_prompt:
            blocks = (*blocks, p.append_system_prompt)
        return blocks

    if p.agent_system_prompt:
        blocks = (p.agent_system_prompt,)
    elif p.custom_system_prompt:
        blocks = (p.custom_system_prompt,)
    else:
        blocks = p.default_blocks

    if p.append_system_prompt:
        blocks = (*blocks, p.append_system_prompt)
    return blocks


if __name__ == "__main__":
    base = PromptInputs(
        default_blocks=("You are a coding assistant.",),
        custom_system_prompt=None,
        agent_system_prompt="Agent: review only.",
        override_system_prompt=None,
        append_system_prompt="Always cite file paths.",
        proactive_mode=False,
        coordinator_mode=False,
    )
    assert build_effective_system_prompt(base)[0].startswith("Agent:")

    proactive = PromptInputs(
        default_blocks=("Autonomous default.",),
        custom_system_prompt="Would lose to agent",
        agent_system_prompt="Domain rules.",
        override_system_prompt=None,
        append_system_prompt="Tail note.",
        proactive_mode=True,
        coordinator_mode=False,
    )
    out = build_effective_system_prompt(proactive)
    assert out[0] == "Autonomous default."
    assert "Domain rules." in out[1]
    assert out[-1] == "Tail note."

    ov = PromptInputs(
        default_blocks=("x",),
        custom_system_prompt=None,
        agent_system_prompt=None,
        override_system_prompt="OVERRIDE",
        append_system_prompt="ignored",
    )
    assert build_effective_system_prompt(ov) == ("OVERRIDE",)

    coord = PromptInputs(
        default_blocks=("DEFAULT",),
        custom_system_prompt="CUSTOM",
        agent_system_prompt=None,
        override_system_prompt=None,
        append_system_prompt="APPEND",
        coordinator_mode=True,
        coordinator_prompt="COORD",
    )
    coord_out = build_effective_system_prompt(coord)
    assert coord_out == ("COORD", "APPEND")

    print("prompt_assembly ok")
