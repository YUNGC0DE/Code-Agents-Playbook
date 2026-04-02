"""Network scope: domain allowlist tiers, pre-approved hosts, private IP / metadata blocking."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

TrustLevel = Literal["pre_approved", "task_allowlist", "unknown"]


# Domains a coding agent typically needs without per-task prompts (illustrative, not exhaustive).
PRE_APPROVED_DOMAINS: frozenset[str] = frozenset(
    {
        "registry.npmjs.org",
        "pypi.org",
        "files.pythonhosted.org",
        "crates.io",
        "static.crates.io",
        "github.com",
        "api.github.com",
        "raw.githubusercontent.com",
        "docs.python.org",
    }
)


@dataclass(frozen=True)
class NetworkScope:
    """Closed by default: only pre-approved + task list unless you extend policy."""

    task_domains: frozenset[str] = field(default_factory=frozenset)
    allow_localhost: bool = True


@dataclass(frozen=True)
class UrlCheckResult:
    allowed: bool
    trust: TrustLevel
    reason: str


_METADATA_IP = ipaddress.ip_address("169.254.169.254")


def _host_from_url(url: str) -> str | None:
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = parsed.hostname
    return host.lower() if host else None


def _is_private_or_loopback_host(host: str) -> bool:
    """Block SSRF-style targets unless explicitly allowed as hostname (not IP)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip == _METADATA_IP
    )


def check_url(
    url: str,
    scope: NetworkScope,
) -> UrlCheckResult:
    """Tiered allow: pre-approved registry/git/docs, then task list; else deny."""
    host = _host_from_url(url)
    if not host:
        return UrlCheckResult(False, "unknown", "unparseable URL")

    if _is_private_or_loopback_host(host):
        if scope.allow_localhost and ipaddress.ip_address(host).is_loopback:
            return UrlCheckResult(True, "task_allowlist", "localhost allowed by scope")
        return UrlCheckResult(False, "unknown", "private/link-local/metadata IP blocked")

    # Strip port for domain matching
    host_only = host.split("%")[0]

    if host_only in PRE_APPROVED_DOMAINS:
        return UrlCheckResult(True, "pre_approved", "pre-approved domain")

    if host_only in scope.task_domains:
        return UrlCheckResult(True, "task_allowlist", "task allowlist")

    return UrlCheckResult(False, "unknown", "domain not in network scope")


def host_matches_allowlist(host: str, allowed_suffixes: frozenset[str]) -> bool:
    """Suffix match so api.foo.com can match entry foo.com if listed (optional helper)."""
    h = host.lower().split("%")[0]
    if h in allowed_suffixes:
        return True
    return any(h.endswith("." + s) for s in allowed_suffixes if "." in s)


if __name__ == "__main__":
    ns = NetworkScope(task_domains=frozenset({"api.internal.example.com"}))
    assert check_url("https://pypi.org/simple/pip/", ns).allowed
    assert check_url("https://api.internal.example.com/v1", ns).allowed
    assert not check_url("https://evil.com/", ns).allowed
    assert not check_url("http://169.254.169.254/latest/meta-data/", ns).allowed
    assert check_url("http://127.0.0.1:8080/", ns).allowed  # loopback with allow_localhost
    print("network_scope ok")
