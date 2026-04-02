"""MCP tool naming and template pattern (educational).

Production code builds a fully qualified tool name mcp__<server>__<tool> with
normalized segments, clones a shared MCPTool template per tools/list row, and
routes call() to tools/call on the right connection. mcpInfo keeps the
original server and tool names for routing and permissions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def normalize_name_for_mcp(name: str) -> str:
    """Simplified: API-safe token; real code also special-cases some hosted prefixes."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def build_mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Fully qualified name exposed to the model and permission rules."""
    s = normalize_name_for_mcp(server_name)
    t = normalize_name_for_mcp(tool_name)
    return f"mcp__{s}__{t}"


def mcp_info_from_string(fqn: str) -> tuple[str, str] | None:
    """Parse mcp__server__tool. Caveat: server names containing '__' are ambiguous."""
    parts = fqn.split("__")
    if len(parts) < 3 or parts[0] != "mcp":
        return None
    server = parts[1]
    tool = "__".join(parts[2:])
    return server, tool


# Shared template fields (illustrative); each MCP row spreads/overrides this.
MCP_TOOL_TEMPLATE: dict[str, Any] = {
    "kind": "mcp",
    "check_permissions_default": "passthrough_with_mcp_message",
}


@dataclass
class WrappedMcpTool:
    """One tools/list row mounted as an agent tool."""

    server_name: str
    original_tool_name: str
    input_schema: dict[str, Any]
    template: dict[str, Any] = field(default_factory=lambda: dict(MCP_TOOL_TEMPLATE))

    @property
    def name(self) -> str:
        return build_mcp_tool_name(self.server_name, self.original_tool_name)

    def to_agent_tool_dict(self) -> dict[str, Any]:
        return {
            **self.template,
            "name": self.name,
            "mcpInfo": {
                "serverName": self.server_name,
                "toolName": self.original_tool_name,
            },
            "inputJSONSchema": self.input_schema,
        }


if __name__ == "__main__":
    w = WrappedMcpTool("My Server", "search", {"type": "object"})
    d = w.to_agent_tool_dict()
    assert d["name"] == "mcp__My_Server__search"
    assert mcp_info_from_string(d["name"]) == ("My_Server", "search")
    print("mcp_tool_wrapper ok")
