"""
Minimal skill file parsing aligned with typical skill-directory loaders.

- On-disk layout for /.claude/skills/: only skill-name/SKILL.md (directory per skill).
- Frontmatter: YAML-like key: value lines between --- fences (use a real YAML
  library in production; this stub is dependency-free for education).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillMeta:
    name: str
    description: str
    when_to_use: str | None = None
    argument_names: tuple[str, ...] = ()


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_simple_kv(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            out[key] = val
    return out


def _parse_arguments_field(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    parts = [p for p in raw.replace(",", " ").split() if p and not p.isdigit()]
    return tuple(parts)


def parse_skill_file(text: str) -> tuple[SkillMeta, str]:
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("missing_frontmatter")
    kv = _parse_simple_kv(m.group(1))
    body = text[m.end() :]
    args_raw = kv.get("arguments")
    return (
        SkillMeta(
            name=kv.get("name", "unnamed"),
            description=kv.get("description", ""),
            when_to_use=kv.get("when_to_use") or None,
            argument_names=_parse_arguments_field(args_raw),
        ),
        body.strip(),
    )


def expected_skill_md_path(skills_root: str, skill_dir_name: str) -> str:
    """Path pattern: {skills_root}/{skill_dir_name}/SKILL.md (see loadSkillsFromSkillsDir)."""
    return f"{skills_root.rstrip('/')}/{skill_dir_name}/SKILL.md"


if __name__ == "__main__":
    sample = """---
name: sql-review
description: Review SQL migrations.
when_to_use: When the user edits SQL or migrations.
arguments: scope path
---
# Instructions
Check for destructive DDL. Scope: $scope
"""
    meta, body = parse_skill_file(sample)
    assert meta.name == "sql-review"
    assert meta.argument_names == ("scope", "path")
    assert "destructive" in body
    assert "sql-review/SKILL.md" in expected_skill_md_path(".claude/skills", "sql-review")
    print("skill_loader ok")
