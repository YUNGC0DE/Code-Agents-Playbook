"""
Speculative classifier: start risk analysis before the user answers the dialog;
consume result when resolving the same tool_use id. Optional race vs timeout
mirrors “wait briefly for classifier before showing the dialog” behavior.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal, TypedDict


class _RaceResult(TypedDict):
    kind: Literal["classifier", "timeout"]
    label: str | None


@dataclass
class SpeculativeClassifier:
    """Maps tool_use_id -> Task of classification result."""

    _tasks: dict[str, asyncio.Task[str]] = field(default_factory=dict)

    def start(self, tool_use_id: str, command: str) -> None:
        if tool_use_id in self._tasks:
            return

        async def classify() -> str:
            await asyncio.sleep(0.05)
            return "high_risk" if "rm -rf" in command else "low_risk"

        task = asyncio.create_task(classify())
        # Swallow exception on abandoned tasks (mirrors production defensive handling)
        task.add_done_callback(lambda t: t.exception())
        self._tasks[tool_use_id] = task

    def peek(self, tool_use_id: str) -> asyncio.Task[str] | None:
        """Non-destructive view; production often keys shell checks by normalized command."""
        return self._tasks.get(tool_use_id)

    async def consume(self, tool_use_id: str) -> str | None:
        t = self._tasks.pop(tool_use_id, None)
        if t is None:
            return None
        return await t


async def race_classifier_or_timeout(
    classify_task: asyncio.Task[str],
    timeout_s: float,
) -> _RaceResult:
    """Return classifier label if it finishes first, else timeout (dialog may follow)."""

    done, _ = await asyncio.wait(
        {classify_task},
        timeout=timeout_s,
        return_when=asyncio.FIRST_COMPLETED,
    )
    if classify_task in done:
        return {"kind": "classifier", "label": classify_task.result()}
    return {"kind": "timeout", "label": None}


async def main() -> None:
    sc = SpeculativeClassifier()
    sc.start("tu1", "echo hello")
    r = await sc.consume("tu1")
    assert r == "low_risk"
    sc.start("tu2", "rm -rf /")
    assert await sc.consume("tu2") == "high_risk"

    sc.start("tu3", "echo race")
    t = sc.peek("tu3")
    assert t is not None
    raced = await race_classifier_or_timeout(t, timeout_s=1.0)
    assert raced["kind"] == "classifier"
    assert raced["label"] == "low_risk"
    assert await sc.consume("tu3") == "low_risk"

    print("speculative_classifier ok")


if __name__ == "__main__":
    asyncio.run(main())
