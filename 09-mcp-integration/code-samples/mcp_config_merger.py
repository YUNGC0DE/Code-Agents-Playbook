"""Merge MCP server maps: last layer wins per server id (same as shallow assign per key).

The product combines scopes in a fixed order; for the same server name, a later
layer replaces the entire entry for that id (not a deep merge of nested dicts).
Enterprise-only and connector-vs-manual deduplication are omitted here.
"""

from __future__ import annotations

from typing import Any


def merge_ordered_layers(layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Later dicts override earlier ones for each top-level server id."""
    out: dict[str, Any] = {}
    for layer in layers:
        for server_id, cfg in layer.items():
            out[server_id] = cfg
    return out


def merge_mcp_configs(user: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible helper: project overrides user for the same server id."""
    return merge_ordered_layers([user, project])


if __name__ == "__main__":
    user = {"s1": {"url": "https://a.example", "timeout": 5}}
    project = {"s1": {"url": "https://b.example", "timeout": 10}}
    m = merge_mcp_configs(user, project)
    assert m["s1"]["url"] == "https://b.example" and m["s1"]["timeout"] == 10

    # Full product order (conceptual): plugin < user < project < local — local wins last
    plugin = {"p": {"cmd": "plugin"}}
    loc = {"p": {"cmd": "local"}}
    full = merge_ordered_layers([plugin, {"u": {}}, {"p": {"cmd": "user"}}, loc])
    assert full["p"]["cmd"] == "local"
    print("mcp_config_merger ok")
