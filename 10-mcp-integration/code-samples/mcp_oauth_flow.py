"""Conceptual OAuth steps for remote MCP servers (educational, no network I/O).

Production clients discover OAuth metadata over HTTPS, use bounded timeouts per
HTTP call, run browser-based authorization with a localhost redirect, and store
refreshed tokens securely — see MCP authorization and protected-resource discovery
in the protocol ecosystem.
"""

from __future__ import annotations

from dataclasses import dataclass

# Per-request budget in seconds (illustrative; real clients set fetch timeouts)
OAUTH_REQUEST_TIMEOUT_SEC = 30


@dataclass(frozen=True)
class OAuthDiscoveryPlan:
    """Ordered probes used before starting an interactive auth code flow."""

    mcp_base_url: str

    def well_known_candidates(self) -> list[str]:
        base = self.mcp_base_url.rstrip("/")
        return [
            f"{base}/.well-known/oauth-protected-resource",
            # Some servers co-host AS metadata under alternate paths — product code probes both.
        ]


def estimate_oauth_handshake_budget(num_http_round_trips: int) -> float:
    """Rough upper bound for planning UX (not a hard deadline for the OS)."""
    return num_http_round_trips * OAUTH_REQUEST_TIMEOUT_SEC


if __name__ == "__main__":
    plan = OAuthDiscoveryPlan("https://mcp.example/v1")
    assert "oauth-protected-resource" in plan.well_known_candidates()[0]
    assert estimate_oauth_handshake_budget(3) == 90.0
    print("mcp_oauth_flow ok")
