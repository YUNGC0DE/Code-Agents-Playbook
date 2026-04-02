"""Session state for IDE bridge clients: id, high-water sequence, reconnect backoff.

Python 3.10+.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class SessionManager:
    """Tracks one remote session: monotonic seq for resume and reconnect backoff."""

    session_id: str
    last_seen_seq: int = 0
    reconnect_attempts: int = 0
    _rng: random.Random = field(default_factory=random.Random)

    def advance_seq(self, seq: int) -> None:
        """Update high-water mark after applying server events in order."""
        if seq > self.last_seen_seq:
            self.last_seen_seq = seq

    def resume_headers(self) -> dict[str, str]:
        """Example headers / query params for SSE Last-Event-ID style resume."""
        return {
            "X-Session-Id": self.session_id,
            "Last-Event-Id": str(self.last_seen_seq),
        }

    def next_backoff_seconds(self, cap: float = 30.0) -> float:
        self.reconnect_attempts += 1
        base = min(cap, 0.5 * (2 ** min(self.reconnect_attempts, 8)))
        jitter = self._rng.uniform(0, base * 0.2)
        return base + jitter

    def reset_backoff(self) -> None:
        self.reconnect_attempts = 0


if __name__ == "__main__":
    sm = SessionManager("s1")
    sm.advance_seq(1)
    sm.advance_seq(3)
    assert sm.last_seen_seq == 3
    assert sm.resume_headers()["Last-Event-Id"] == "3"
    assert sm.next_backoff_seconds() > 0
    sm.reset_backoff()
    assert sm.reconnect_attempts == 0
    print("session_manager ok")
