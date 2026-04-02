"""Discover project memory entrypoints by walking upward from cwd (simplified).

Real loaders also read `.agent/AGENT.md`, `.agent/rules/*.md`, managed and
user config paths, then merge with explicit precedence — this sample only
shows the parent-walk pattern for project instruction filenames.
"""

from __future__ import annotations

from pathlib import Path

# Typical project instruction filenames (not the memdir MEMORY.md entrypoint)
ENTRY_NAMES = ("AGENT.md", "AGENT.local.md")


def find_entrypoints(start: Path, stop_at: Path | None = None) -> list[Path]:
    """Collect existing entrypoint files from `start` up to `stop_at` (inclusive)."""
    found: list[Path] = []
    cur = start.resolve()
    stop = stop_at.resolve() if stop_at else Path(cur.anchor)
    while True:
        for name in ENTRY_NAMES:
            p = cur / name
            if p.is_file():
                found.append(p)
        if cur == stop or cur.parent == cur:
            break
        cur = cur.parent
    return found


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "AGENT.md").write_text("root rules")
        nested = root / "sub" / "nested"
        nested.mkdir(parents=True)
        (nested / "AGENT.md").write_text("nested wins for this folder")
        hits = find_entrypoints(nested, stop_at=root)
        assert len(hits) >= 1
    print("memory_index ok")
