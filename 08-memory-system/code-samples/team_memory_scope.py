"""
Team memory lives under `<memdir>/team/` — a namespace separate from
checked-in project instruction files. Product code validates writes
(symlink-safe containment); this sample only checks path prefix membership.
"""

from __future__ import annotations

from pathlib import Path


def team_memory_dir(auto_mem_dir: Path) -> Path:
    """Shared team files live under memdir/team/ (sibling to MEMORY.md)."""
    return (auto_mem_dir / "team").resolve()


def is_team_memory_path(candidate: Path, auto_mem_dir: Path) -> bool:
    """True if `candidate` is inside the team subtree of auto-memory."""
    try:
        candidate.resolve().relative_to(team_memory_dir(auto_mem_dir))
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "project" / "memory"
        team = base / "team"
        team.mkdir(parents=True)
        f = team / "goals.md"
        f.write_text("ship")
        assert is_team_memory_path(f, base) is True
        assert is_team_memory_path(base / "MEMORY.md", base) is False
    print("team_memory_scope ok")
