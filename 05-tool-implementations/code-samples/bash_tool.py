#!/usr/bin/env python3
"""
Simplified bash pre-flight security analysis (pattern-based, educational).

Production agents usually combine a shell-aware parser or AST with a broader
denylist (redirections, heredocs, obfuscation, read-only allowlists). This file
shows a small subset so tests stay obvious.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Stable machine-oriented codes for logging / policy (not for end-user prose).
REASON_EMPTY = "empty_command"
REASON_NULL_BYTE = "null_byte"
REASON_PROCESS_SUB = "process_substitution"
REASON_CMD_SUB = "command_substitution"
REASON_BACKTICK = "backtick_substitution"
REASON_ZSH_EQUALS = "zsh_equals_expansion"


@dataclass(frozen=True)
class SecurityResult:
    allowed: bool
    reason: str | None = None


_COMMAND_SUB_PATTERNS = (
    (re.compile(r"\$\("), REASON_CMD_SUB),
    (re.compile(r"<\("), REASON_PROCESS_SUB),
    (re.compile(r"`"), REASON_BACKTICK),
)


def analyze_command(cmd: str) -> SecurityResult:
    stripped = cmd.strip()
    if not stripped:
        return SecurityResult(False, REASON_EMPTY)
    if "\x00" in cmd:
        return SecurityResult(False, REASON_NULL_BYTE)
    for rx, code in _COMMAND_SUB_PATTERNS:
        if rx.search(cmd):
            return SecurityResult(False, code)
    # zsh: word-initial "=cmd" expands like $(which cmd) — can bypass naive prefix rules
    if re.search(r"(?:^|[\s;&|])=[a-zA-Z_]", cmd):
        return SecurityResult(False, REASON_ZSH_EQUALS)
    return SecurityResult(True, None)


if __name__ == "__main__":
    assert analyze_command("echo hi").allowed
    assert not analyze_command("echo $(rm -rf /)").allowed
    assert analyze_command("echo $(rm -rf /)").reason == REASON_CMD_SUB
    # Assignment "VAR=value" must not trip the zsh "=cmd" heuristic
    assert analyze_command("VAR=value echo ok").allowed
    assert not analyze_command("=curl example.test").allowed
    print("bash_tool ok")
