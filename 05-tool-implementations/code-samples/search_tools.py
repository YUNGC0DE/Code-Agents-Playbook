#!/usr/bin/env python3
"""
Glob + grep-style search with deterministic limits (educational stand-ins).

A real stack calls ripgrep (or similar) with timeouts, gitignore-style rules,
and VCS directory exclusions. Here we use pathlib + re to show head_limit,
offset, and match caps only.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path


def glob_files(root: Path, pattern: str, *, max_files: int = 500) -> list[str]:
    out: list[str] = []
    for p in root.rglob("*"):
        if len(out) >= max_files:
            break
        if p.is_file() and fnmatch.fnmatch(p.name, pattern):
            out.append(str(p.relative_to(root)))
    return out


def grep_content(
    root: Path,
    regex: str,
    *,
    glob_filter: str = "*.py",
    max_matches: int = 200,
    max_file_bytes: int = 512 * 1024,
    head_limit: int = 250,
    offset: int = 0,
) -> list[tuple[str, int, str]]:
    """
    Return up to max_matches (path, line_no, line_preview) tuples, then apply
    offset/head_limit for pagination over that capped list (rg-style UX).
    """
    rx = re.compile(regex)
    matches: list[tuple[str, int, str]] = []
    for path in root.rglob(glob_filter):
        if len(matches) >= max_matches:
            break
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
        except OSError:
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if len(matches) >= max_matches:
                break
            if rx.search(line):
                matches.append((str(path.relative_to(root)), i, line[:500]))
    start = offset
    end = start + head_limit if head_limit > 0 else len(matches)
    return matches[start:end]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "a.py").write_text("def foo(): pass\n")
        (root / "b.py").write_text("def bar(): pass\n")
        assert glob_files(root, "*.py")
        all_hits = grep_content(root, r"def \w+", max_matches=50, head_limit=0)
        assert len(all_hits) >= 1
        page = grep_content(root, r"def ", head_limit=1, offset=0)
        assert len(page) == 1
    print("search_tools ok")
