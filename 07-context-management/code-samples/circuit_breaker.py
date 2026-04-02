"""Circuit breaker for consecutive autocompact failures (educational)."""

from __future__ import annotations

from dataclasses import dataclass

# Aligns with production default: stop hammering the API after a few doomed attempts.
MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class CompactCircuitBreaker:
    consecutive_failures: int = 0

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self, *, user_aborted: bool = False) -> None:
        """User abort of the summarize pass should not trip the breaker."""
        if user_aborted:
            return
        self.consecutive_failures += 1

    def should_stop_retrying(self) -> bool:
        return self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES


if __name__ == "__main__":
    cb = CompactCircuitBreaker()
    cb.record_failure(user_aborted=True)
    assert cb.consecutive_failures == 0
    for _ in range(MAX_CONSECUTIVE_FAILURES):
        cb.record_failure()
    assert cb.should_stop_retrying()
    cb.record_success()
    assert not cb.should_stop_retrying()
    print("circuit_breaker ok")
