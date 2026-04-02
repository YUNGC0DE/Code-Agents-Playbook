"""Minimal staging for context-collapse style history (educational stub)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CollapseCommit:
    """Represents a committed slice of archived context (opaque id + size)."""

    commit_id: str
    token_estimate: int


@dataclass
class ContextCollapseStaging:
    """
    In-memory analogue: ordered commits + optional snapshot for resume.
    Full compaction clears this staging in production stacks.
    """

    commits: list[CollapseCommit] = field(default_factory=list)
    snapshot_token_estimate: int | None = None

    def record_commit(self, entry: CollapseCommit) -> None:
        self.commits.append(entry)

    def stage_snapshot(self, token_estimate: int) -> None:
        self.snapshot_token_estimate = token_estimate

    def clear_after_full_compact(self) -> None:
        self.commits.clear()
        self.snapshot_token_estimate = None


if __name__ == "__main__":
    st = ContextCollapseStaging()
    st.record_commit(CollapseCommit("a1", 10_000))
    st.stage_snapshot(5_000)
    st.clear_after_full_compact()
    assert st.commits == [] and st.snapshot_token_estimate is None
    print("context_collapse_stub ok")
