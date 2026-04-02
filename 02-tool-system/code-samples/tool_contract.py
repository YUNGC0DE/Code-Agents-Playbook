"""Tool contract: Protocol + Pydantic v2 models for structured, validated inputs."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class EchoInput(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str

    async def run(self, inp: BaseModel, ctx: dict[str, Any]) -> str: ...


class EchoTool:
    name = "echo"
    description = "Echo input text."

    async def run(self, inp: BaseModel, ctx: dict[str, Any]) -> str:
        data = EchoInput.model_validate(inp.model_dump())
        return data.text.upper()


async def main() -> None:
    t: Tool = EchoTool()
    out = await t.run(EchoInput(text="hello"), {})
    assert out == "HELLO"
    print("tool_contract ok:", out)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
