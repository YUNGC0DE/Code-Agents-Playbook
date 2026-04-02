"""Auto-compact: effective window, fixed buffers, optional percent override (educational)."""

from __future__ import annotations

# Mirrors production naming for teaching; tune from traces in your deployment.
AUTOCOMPACT_BUFFER_TOKENS = 13_000
# Cap reserved for summarizer output when computing "effective" usable window.
MAX_OUTPUT_RESERVED_FOR_SUMMARY = 20_000


def effective_context_window(model_window: int, max_output_reserved: int) -> int:
    """Usable window before autocompact buffer — model window minus summary headroom."""
    return max(0, model_window - max_output_reserved)


def autocompact_threshold(model_window: int, max_output_reserved: int) -> int:
    """Fire autocompact when estimated usage reaches this level."""
    return effective_context_window(model_window, max_output_reserved) - AUTOCOMPACT_BUFFER_TOKENS


def autocompact_threshold_with_pct_override(
    model_window: int,
    max_output_reserved: int,
    pct_override: float | None,
) -> int:
    """
    Optional lower threshold for testing: min(percent_of_effective, normal_autocompact).
    pct_override in (0, 100] — e.g. 50 means half of effective window.
    """
    base = autocompact_threshold(model_window, max_output_reserved)
    eff = effective_context_window(model_window, max_output_reserved)
    if pct_override is None or not (0 < pct_override <= 100):
        return base
    pct_floor = int(eff * (pct_override / 100))
    return min(pct_floor, base)


if __name__ == "__main__":
    t = autocompact_threshold(200_000, MAX_OUTPUT_RESERVED_FOR_SUMMARY)
    assert t == 200_000 - MAX_OUTPUT_RESERVED_FOR_SUMMARY - AUTOCOMPACT_BUFFER_TOKENS
    assert autocompact_threshold_with_pct_override(200_000, MAX_OUTPUT_RESERVED_FOR_SUMMARY, 50) < t
    print("auto_compaction ok", t)
