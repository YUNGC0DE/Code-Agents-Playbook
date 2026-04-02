"""MCP-style client: connection lifecycle and transport kinds (educational).

Real implementations run a JSON-RPC session (initialize, tools/list, etc.)
with per-request timeouts; remote transports may reconnect after disconnect.
Connection *outcomes* can include needs-auth or failed before any tools exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TransportKind(str, Enum):
    """Aligned with common MCP deployment patterns: local process vs URL-based."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class SessionOutcome(str, Enum):
    """High-level state of one server from the agent's perspective (simplified)."""

    DISCONNECTED = "disconnected"
    PENDING = "pending"  # connect in flight
    CONNECTED = "connected"  # handshake done; tools/list may run
    DISABLED = "disabled"  # configured off; no I/O
    NEEDS_AUTH = "needs_auth"  # remote OAuth / token missing; placeholder tools possible
    FAILED = "failed"  # error or unreachable


@dataclass
class McpClient:
    """Educational stand-in — no real JSON-RPC or subprocess I/O."""

    outcome: SessionOutcome = SessionOutcome.DISCONNECTED
    server_name: str = ""
    transport: TransportKind = TransportKind.STDIO

    def start_connect(self, name: str, transport: TransportKind = TransportKind.STDIO) -> None:
        self.server_name = name
        self.transport = transport
        self.outcome = SessionOutcome.PENDING

    def mark_connected(self) -> None:
        self.outcome = SessionOutcome.CONNECTED

    def mark_failed(self) -> None:
        self.outcome = SessionOutcome.FAILED

    def close(self) -> None:
        self.outcome = SessionOutcome.DISCONNECTED


if __name__ == "__main__":
    c = McpClient()
    c.start_connect("demo", TransportKind.STDIO)
    assert c.outcome == SessionOutcome.PENDING
    c.mark_connected()
    assert c.outcome == SessionOutcome.CONNECTED
    c.close()
    print("mcp_client ok")
