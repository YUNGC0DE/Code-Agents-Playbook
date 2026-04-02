"""Deferred tool discovery: core tools in prompt; deferred tools via meta-tool.

Aligned with product Tool Search behavior:
- Default auto-enable when deferred tool defs exceed ~10% of context window
  (ENABLE_TOOL_SEARCH=auto or auto:N overrides the percentage).
- Approximate chars/token for MCP tool defs when token API is unavailable.
- Meta-tool name is fixed (ToolSearch) so the model can request schemas on demand;
  deferred tools use defer_loading on the wire when Tool Search mode is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tool Search threshold defaults (fraction of context window, percent)
DEFAULT_AUTO_TOOL_SEARCH_PERCENTAGE = 10  # percent of context window
CHARS_PER_TOKEN = 2.5  # fallback for MCP tool definition token estimates

# Meta-tool name for on-demand schema discovery (fixed product identifier)
TOOL_SEARCH_TOOL_NAME = "ToolSearch"


def get_auto_tool_search_char_threshold(context_window_tokens: int, percentage: int | None = None) -> int:
    """Mirror getAutoToolSearchCharThreshold(model): floor(window * pct/100 * CHARS_PER_TOKEN)."""
    pct = DEFAULT_AUTO_TOOL_SEARCH_PERCENTAGE if percentage is None else max(0, min(100, percentage))
    token_threshold = int(context_window_tokens * (pct / 100.0))
    return int(token_threshold * CHARS_PER_TOKEN)


@dataclass
class LazyToolRegistry:
    """Keeps full schemas in a side table; exposes minimal names to the model."""

    _schemas: dict[str, dict] = field(default_factory=dict)
    _in_prompt: set[str] = field(default_factory=set)
    _deferred: set[str] = field(default_factory=set)

    def register(self, name: str, schema: dict, in_prompt: bool = False, defer_loading: bool = False) -> None:
        self._schemas[name] = schema
        if defer_loading:
            self._deferred.add(name)
        elif in_prompt:
            self._in_prompt.add(name)

    def prompt_tool_list(self) -> list[str]:
        """Tools included in the initial API tool list (may include ToolSearch + minimal set)."""
        return sorted(self._in_prompt)

    def deferred_tool_names(self) -> list[str]:
        """Tools marked defer_loading — discovered via ToolSearch rather than upfront schemas."""
        return sorted(self._deferred)

    def fetch_schema(self, name: str) -> dict | None:
        return self._schemas.get(name)


if __name__ == "__main__":
    # Run: python3 deferred_tool_discovery.py
    reg = LazyToolRegistry()
    reg.register("core", {"type": "object"}, in_prompt=True)
    reg.register(TOOL_SEARCH_TOOL_NAME, {"type": "object"}, in_prompt=True)
    reg.register("heavy_plugin", {"type": "object"}, defer_loading=True)
    assert "heavy_plugin" not in reg.prompt_tool_list()
    assert "heavy_plugin" in reg.deferred_tool_names()
    assert reg.fetch_schema("heavy_plugin") is not None
    assert get_auto_tool_search_char_threshold(200_000) > 0
    print("deferred_tool_discovery ok")
