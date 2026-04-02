"""Sandbox configuration: deny-within-allow for FS writes, layered enforcement hook."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ViolationMode = Literal["deny", "ask", "log"]


@dataclass(frozen=True)
class SandboxConfig:
    """OS-level or runtime-sandbox mirror of app-level scope (defense in depth)."""

    fs_read_allow: tuple[str, ...]
    fs_write_allow: tuple[str, ...]
    fs_write_deny: tuple[str, ...] = ()
    network_domains: tuple[str, ...] = ()
    on_violation: ViolationMode = "deny"


def _under_any(roots: tuple[str, ...], path: str) -> bool:
    p = os.path.realpath(path)
    for r in roots:
        base = os.path.realpath(r)
        if p == base or p.startswith(base + os.sep):
            return True
    return False


def can_read_path(cfg: SandboxConfig, path: str) -> bool:
    return _under_any(cfg.fs_read_allow, path)


def can_write_path(cfg: SandboxConfig, path: str) -> bool:
    """Coarse write allow, then deny-within-allow for secrets and VCS internals."""
    if not _under_any(cfg.fs_write_allow, path):
        return False
    p = os.path.realpath(path)
    for denied in cfg.fs_write_deny:
        d = os.path.realpath(denied)
        if p == d or p.startswith(d + os.sep):
            return False
    return True


@dataclass
class LayeredEnforcementResult:
    app_allowed: bool
    sandbox_allowed: bool
    executed: bool


def layered_tool_execution(
    *,
    app_scope_allows: bool,
    sandbox_cfg: SandboxConfig,
    path: str,
    is_write: bool,
) -> LayeredEnforcementResult:
    """Both application-level scope and sandbox must pass (chapter diagram)."""
    if not app_scope_allows:
        return LayeredEnforcementResult(False, False, False)
    sandbox_ok = (
        can_write_path(sandbox_cfg, path)
        if is_write
        else can_read_path(sandbox_cfg, path)
    )
    return LayeredEnforcementResult(True, sandbox_ok, sandbox_ok)


if __name__ == "__main__":
    import tempfile

    proj = tempfile.mkdtemp()
    try:
        deny_env = os.path.join(proj, ".env")
        Path(deny_env).write_text("SECRET=1", encoding="utf-8")

        cfg = SandboxConfig(
            fs_read_allow=(proj,),
            fs_write_allow=(proj,),
            fs_write_deny=(deny_env, os.path.join(proj, ".git")),
            network_domains=("pypi.org",),
            on_violation="deny",
        )
        safe_file = os.path.join(proj, "src", "app.py")
        os.makedirs(os.path.dirname(safe_file), exist_ok=True)
        Path(safe_file).write_text("print(1)", encoding="utf-8")

        assert can_write_path(cfg, safe_file)
        assert not can_write_path(cfg, deny_env)

        r = layered_tool_execution(
            app_scope_allows=True,
            sandbox_cfg=cfg,
            path=deny_env,
            is_write=True,
        )
        assert r.app_allowed and not r.sandbox_allowed and not r.executed

        r2 = layered_tool_execution(
            app_scope_allows=False,
            sandbox_cfg=cfg,
            path=safe_file,
            is_write=True,
        )
        assert not r2.executed
    finally:
        shutil.rmtree(proj, ignore_errors=True)
    print("sandbox_config ok")
