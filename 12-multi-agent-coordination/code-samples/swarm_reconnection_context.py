"""Conceptual team context: fresh spawn (CLI) vs resumed session (transcript).

Fresh spawn: environment / argv establishes team and agent name early.
Resume: session metadata names the team and agent; roster lookup supplies
the member's stable id (missing roster row => treat as removed / unknown).

Leader vs member: no agent_id means lead; members carry a roster id.
Matches the usual swarm reconnection split (dynamic CLI context vs session replay).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TeamContext:
    team_name: str
    agent_name: str
    """Stable id for this member; None when this process is the team lead."""
    agent_id: Optional[str]

    @property
    def is_leader(self) -> bool:
        return self.agent_id is None


def context_from_fresh_spawn(
    team_name: str,
    agent_name: str,
    agent_id: Optional[str],
) -> TeamContext:
    """New process started with explicit team / teammate env or CLI."""
    return TeamContext(
        team_name=team_name,
        agent_name=agent_name,
        agent_id=agent_id,
    )


def context_from_resumed_session(
    team_name: str,
    agent_name: str,
    member_agent_id: Optional[str],
) -> TeamContext:
    """Session replay: names from transcript; id from current team roster if present."""
    return TeamContext(
        team_name=team_name,
        agent_name=agent_name,
        agent_id=member_agent_id,
    )


if __name__ == "__main__":
    lead = context_from_fresh_spawn("proj", "TeamLead", None)
    assert lead.is_leader

    mate = context_from_resumed_session("proj", "worker-1", "agent-uuid-7")
    assert not mate.is_leader and mate.agent_id == "agent-uuid-7"

    print("swarm_reconnection_context ok")
