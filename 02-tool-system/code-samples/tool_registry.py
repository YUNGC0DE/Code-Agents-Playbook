"""Tool registry: register built-ins and resolve by name for API listing and execution."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel


type AsyncToolFn = Callable[[BaseModel, dict[str, Any]], Coroutine[Any, Any, str]]


class RegisteredTool:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        run: AsyncToolFn,
        *,
        aliases: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.run = run
        self.aliases = aliases


def tool_matches_name(tool: RegisteredTool, name: str) -> bool:
    """True if `name` equals the tool's primary name or any alias."""
    return tool.name == name or name in tool.aliases


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def find_by_name(self, name: str) -> RegisteredTool | None:
        """Resolve by primary name or alias (linear scan; large pools may use a secondary alias index)."""
        for t in self._tools.values():
            if tool_matches_name(t, name):
                return t
        return None

    def list_openai_style(self) -> list[dict[str, Any]]:
        out = []
        for t in self._tools.values():
            out.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_model.model_json_schema(),
                }
            )
        return out


if __name__ == "__main__":
    from pydantic import Field

    class NopInput(BaseModel):
        x: int = Field(default=0)

    async def nop_run(_: BaseModel, __: dict[str, Any]) -> str:
        return "ok"

    reg = ToolRegistry()
    reg.register(
        RegisteredTool(
            "nop",
            "no-op",
            NopInput,
            nop_run,
            aliases=("legacy_nop",),
        )
    )
    assert reg.get("nop") is not None
    assert reg.find_by_name("legacy_nop") is not None
    assert reg.find_by_name("missing") is None
    print(reg.list_openai_style())
