"""Defer expensive work until first use.

Patterns in TS bundles: dynamic import() inside init branches; lazy Zod factories;
lazy require() behind feature() gates or to break circular imports.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def heavy_sqrt(x: float) -> Any:
    math: ModuleType = importlib.import_module("math")
    return math.sqrt(x)


def lazy_factory(loader: Callable[[], T]) -> Callable[[], T]:
    """Return a callable that invokes loader() once and caches the result."""

    cache: list[T] = []

    def _get() -> T:
        if not cache:
            cache.append(loader())
        return cache[0]

    return _get


if __name__ == "__main__":
    assert heavy_sqrt(4.0) == 2.0

    builds = {"n": 0}

    def build_expensive() -> str:
        builds["n"] += 1
        return "singleton"

    get_x = lazy_factory(build_expensive)
    assert get_x() == "singleton" and get_x() == "singleton" and builds["n"] == 1
    print("lazy_loading ok")
