"""
Mutable loop state carried between iterations — mirrors the production pattern:
one `State` object updated at "continue" sites (spread/replace), not ad-hoc globals.

Fields align with what a production query loop keeps outside the message list:
recovery counters, compaction flags, optional pending work, and chain depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class QueryChainTracking:
    """Monotonic depth inside a logical agent chain (nested / sub-queries)."""

    chain_id: str
    depth: int


@dataclass
class AutoCompactTracking:
    """Tracks autocompact attempts and circuit-breaker style failure streak."""

    compacted: bool = False
    turn_counter: int = 0
    turn_id: str = ""
    consecutive_failures: int = 0


@dataclass
class LoopState:
    """
    Session-scoped state for the generator loop (not serialized into API messages).

    Production loops keep similar data to:
    - bound expensive retries (max output recovery),
    - avoid repeating reactive compact,
    - carry pending async work across iterations,
    - record why the last iteration continued (for tests and telemetry).
    """

    turn_count: int = 0
    usage: Usage = field(default_factory=Usage)
    max_output_tokens_recovery_count: int = 0
    has_attempted_reactive_compact: bool = False
    auto_compact_tracking: AutoCompactTracking | None = None
    stop_hook_active: bool | None = None
    pending_tool_use_summary: Any | None = None
    max_output_tokens_override: int | None = None
    query_chain: QueryChainTracking | None = None
    # Why the previous iteration continued — tests, logging, and gating
    # (e.g. skip a collapse-drain step if the last pass already did it).
    last_transition: str | None = None

    def on_turn_start(self) -> None:
        self.turn_count += 1

    def add_usage(self, input_tok: int, output_tok: int) -> None:
        self.usage.input_tokens += input_tok
        self.usage.output_tokens += output_tok

    def bump_query_depth(self, chain_id: str) -> None:
        """Each loop iteration deepens the chain (0 on first entry, then +1)."""
        if self.query_chain is None:
            self.query_chain = QueryChainTracking(chain_id=chain_id, depth=0)
        else:
            self.query_chain = QueryChainTracking(
                chain_id=self.query_chain.chain_id,
                depth=self.query_chain.depth + 1,
            )


def simulate_three_turns() -> LoopState:
    st = LoopState()
    for _ in range(3):
        st.on_turn_start()
        st.add_usage(100, 50)
    return st


if __name__ == "__main__":
    s = simulate_three_turns()
    print("turns", s.turn_count)
    print("usage", s.usage)
    st2 = LoopState()
    st2.bump_query_depth("abc")
    st2.bump_query_depth("abc")
    assert st2.query_chain and st2.query_chain.depth == 1
    print("state_machine ok")
