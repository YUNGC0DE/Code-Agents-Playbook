"""Resolve feature gates once per session; load optional modules only when on.

Bundled code may use compile-time feature('FLAG') so dead branches are removed.
Python equivalent: a single resolve step returns plain booleans / small structs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionGates:
    enterprise_ui: bool
    experimental_retriever: bool


def resolve_gates(environ: dict[str, str] | None = None) -> SessionGates:
    env = environ if environ is not None else os.environ
    return SessionGates(
        enterprise_ui=env.get("APP_ENTERPRISE", "") == "1",
        experimental_retriever=env.get("APP_EXPERIMENTAL_RAG", "") == "1",
    )


def get_enterprise_module(gates: SessionGates) -> object | None:
    if not gates.enterprise_ui:
        return None

    class _Enterprise:
        name = "enterprise"

    return _Enterprise()


if __name__ == "__main__":
    default = resolve_gates({})
    assert default.enterprise_ui is False
    assert get_enterprise_module(default) is None

    on = resolve_gates({"APP_ENTERPRISE": "1"})
    assert get_enterprise_module(on) is not None
    print("feature_gates ok")
