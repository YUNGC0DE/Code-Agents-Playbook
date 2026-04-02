"""
Argument substitution for skill bodies (simplified host-style behavior).

Supports:
- $ARGUMENTS — full raw string
- $ARGUMENTS[0], $ARGUMENTS[1] — positional
- $0, $1 — shorthand indices
- $name — only for names listed in argument_names (named slots by position)

Does not implement full shell-quote parsing; uses whitespace split as fallback.
"""

from __future__ import annotations

import re


def parse_arguments(args: str) -> list[str]:
    if not args or not args.strip():
        return []
    # Product uses shell-quote; educational fallback:
    return args.split()


def substitute_arguments(
    content: str,
    args: str | None,
    append_if_no_placeholder: bool = True,
    argument_names: list[str] | None = None,
) -> str:
    if args is None:
        return content

    argument_names = argument_names or []
    parsed = parse_arguments(args)
    original = content

    for i, name in enumerate(argument_names):
        if not name or name.isdigit():
            continue
        content = re.sub(rf"\${re.escape(name)}(?![\[\w])", parsed[i] if i < len(parsed) else "", content)

    def repl_bracket(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        return parsed[idx] if idx < len(parsed) else ""

    content = re.sub(r"\$ARGUMENTS\[(\d+)\]", repl_bracket, content)

    def repl_digit(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        return parsed[idx] if idx < len(parsed) else ""

    content = re.sub(r"\$(\d+)(?!\w)", repl_digit, content)
    content = content.replace("$ARGUMENTS", args)

    if content == original and append_if_no_placeholder and args.strip():
        content = content + f"\n\nARGUMENTS: {args}"
    return content


def substitute_session_vars(content: str, skill_dir: str | None, session_id: str) -> str:
    """Mirrors ${CLAUDE_SKILL_DIR} and ${CLAUDE_SESSION_ID} in createSkillCommand."""
    out = content.replace("${CLAUDE_SESSION_ID}", session_id)
    if skill_dir:
        out = out.replace("${CLAUDE_SKILL_DIR}", skill_dir)
    return out


if __name__ == "__main__":
    assert "hello" in substitute_arguments("Say $ARGUMENTS", "hello")
    assert substitute_arguments("a $0 $1", "x y") == "a x y"
    assert substitute_arguments("n=$n", "first second", argument_names=["n"]) == "n=first"
    body = substitute_session_vars("dir=${CLAUDE_SKILL_DIR}", "/app/skills/foo", "sid")
    assert "/app/skills/foo" in body
    print("argument_substitution ok")
