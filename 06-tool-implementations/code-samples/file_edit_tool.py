#!/usr/bin/env python3
"""
File edit tool: resolve path inside allowed roots and validate replacement.

Join relative paths to a workspace root before resolving so "../" cannot escape
the jail via cwd. Symlink targets outside the root are rejected after resolve().
"""

from __future__ import annotations

from pathlib import Path


class FileEditError(Exception):
    pass


def resolve_allowed_path(user_path: str, roots: tuple[Path, ...]) -> Path:
    raw = Path(user_path).expanduser()
    for root in roots:
        root_res = root.resolve()
        if raw.is_absolute():
            candidate = raw.resolve()
        else:
            candidate = (root_res / raw).resolve()
        try:
            candidate.relative_to(root_res)
        except ValueError:
            continue
        return candidate
    raise FileEditError("path_outside_allowed_roots")


def apply_replacement(
    text: str,
    old: str,
    new: str,
    *,
    replace_all: bool = False,
    must_occur_once: bool = True,
) -> str:
    if old == new:
        raise FileEditError("no_op_edit")
    count = text.count(old)
    if count == 0:
        raise FileEditError("old_string_not_found")
    if replace_all:
        return text.replace(old, new)
    if must_occur_once and count != 1:
        raise FileEditError("old_string_ambiguous")
    return text.replace(old, new, 1)


def assert_file_size_ok(path: Path, max_bytes: int) -> None:
    try:
        size = path.stat().st_size
    except OSError as e:
        raise FileEditError("stat_failed") from e
    if size > max_bytes:
        raise FileEditError("file_too_large")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        base = Path(d).resolve()
        f = base / "a.txt"
        f.write_text("hello world")
        p = resolve_allowed_path(str(f), (base,))
        assert_file_size_ok(p, max_bytes=1024 * 1024)
        t = p.read_text()
        out = apply_replacement(t, "world", "there")
        assert "hello there" in out
        out2 = apply_replacement("a a a", "a", "b", replace_all=True)
        assert out2 == "b b b"
    print("file_edit_tool ok")
