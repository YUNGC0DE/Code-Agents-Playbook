"""Heuristic extraction stub + skip logic mirroring 'main already wrote memdir'.

Real extraction uses a model-backed agent; this file demonstrates:
1) naive line-based candidates (stand-in for an extractMemories-style job),
2) skipping a background pass when the transcript already records a write
   into memdir (same dedupe idea as production).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def extract_candidates(assistant_reply: str) -> list[str]:
    """
    Looks for explicit 'Remember:' lines — production uses structured extraction.
    """
    out: list[str] = []
    for line in assistant_reply.splitlines():
        m = re.match(r"^\s*Remember:\s*(.+)$", line, re.I)
        if m:
            out.append(m.group(1).strip())
    return out


def extract_memories(assistant_reply: str) -> list[str]:
    """
    Minimal stand-in for an end-of-turn extractMemories pass: returns candidate
    lines to persist into memdir (here, only Remember: heuristics).
    """
    return extract_candidates(assistant_reply)


@dataclass
class FakeToolUse:
    """Minimal stand-in for a write tool targeting a path."""

    path: str


def should_skip_background_extraction(
    memory_dir_prefix: str,
    tool_uses_since_marker: list[FakeToolUse],
) -> bool:
    """
    Return True if any write targets a path under memdir.
    Background extraction can skip that range to avoid duplicate writes.
    """
    prefix = memory_dir_prefix.rstrip("/") + "/"
    for tu in tool_uses_since_marker:
        p = tu.path.replace("\\", "/")
        if p.startswith(prefix) or p.rstrip("/") == memory_dir_prefix.rstrip("/"):
            return True
    return False


if __name__ == "__main__":
    text = "Some analysis.\nRemember: always run tests before commit.\nDone."
    assert "always run tests" in extract_candidates(text)[0]
    assert extract_memories(text) == extract_candidates(text)

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        mem_root = str(Path(d) / "workspace" / "memory")
        notes = f"{mem_root}/notes.md"
        assert should_skip_background_extraction(mem_root, [FakeToolUse(path=notes)])
        assert not should_skip_background_extraction(mem_root, [])
    print("memory_extraction ok")
