"""Scoped memory: merge layers so later (more specific) files override earlier ones.

Educational ordering (simplified): user-wide < project files < local overrides.
Production systems also insert managed policy, walk-from-cwd project memory files,
memdir (MEMORY.md), and team entrypoints with a strict precedence ladder.
"""

from __future__ import annotations

from pathlib import Path


def collect_memory_layers(
    project_root: Path,
    user_memory: str | None,
    project_files: list[Path],
    local_files: list[Path],
) -> list[tuple[str, str]]:
    """
    Returns ordered (label, text) with increasing precedence.
    """
    layers: list[tuple[str, str]] = []
    if user_memory:
        layers.append(("user", user_memory))
    for p in sorted(project_files):
        layers.append((f"project:{p.name}", p.read_text(errors="replace")))
    for p in sorted(local_files):
        layers.append((f"local:{p.name}", p.read_text(errors="replace")))
    return layers


def merged_markdown(layers: list[tuple[str, str]]) -> str:
    parts = [f"<!-- {label} -->\n{text}" for label, text in layers]
    return "\n\n".join(parts)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        proj = root / "MEM.md"
        proj.write_text("Use ruff.")
        layers = collect_memory_layers(root, "Global hint.", [proj], [])
        text = merged_markdown(layers)
        assert "Global" in text and "ruff" in text
    print("scoped_memory ok")
