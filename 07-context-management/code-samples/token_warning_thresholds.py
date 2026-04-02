"""Token warning bands: warn / error / autocompact / blocking (educational)."""

from __future__ import annotations

from dataclasses import dataclass

WARNING_THRESHOLD_BUFFER_TOKENS = 20_000
ERROR_THRESHOLD_BUFFER_TOKENS = 20_000
AUTOCOMPACT_BUFFER_TOKENS = 13_000
MANUAL_COMPACT_BUFFER_TOKENS = 3_000
MAX_OUTPUT_RESERVED_FOR_SUMMARY = 20_000


def effective_context_window(model_window: int, max_output_reserved: int) -> int:
    return max(0, model_window - max_output_reserved)


def autocompact_threshold(model_window: int, max_output_reserved: int) -> int:
    return effective_context_window(model_window, max_output_reserved) - AUTOCOMPACT_BUFFER_TOKENS


@dataclass(frozen=True)
class TokenWarningState:
    percent_left: int
    is_above_warning: bool
    is_above_error: bool
    is_above_autocompact: bool
    is_at_blocking_limit: bool


def calculate_token_warning_state(
    token_usage: int,
    model_window: int,
    max_output_reserved: int,
    *,
    autocompact_enabled: bool,
    blocking_limit_override: int | None = None,
) -> TokenWarningState:
    """
    When autocompact is off, the comparison threshold for warn/error is the full
    effective window (no early autocompact trigger).
    """
    effective = effective_context_window(model_window, max_output_reserved)
    auto_thr = autocompact_threshold(model_window, max_output_reserved)
    threshold = auto_thr if autocompact_enabled else effective

    percent_left = max(0, round(((threshold - token_usage) / threshold) * 100)) if threshold else 0

    warning_threshold = threshold - WARNING_THRESHOLD_BUFFER_TOKENS
    error_threshold = threshold - ERROR_THRESHOLD_BUFFER_TOKENS

    default_blocking = effective - MANUAL_COMPACT_BUFFER_TOKENS
    blocking = (
        blocking_limit_override
        if blocking_limit_override is not None and blocking_limit_override > 0
        else default_blocking
    )

    return TokenWarningState(
        percent_left=percent_left,
        is_above_warning=token_usage >= warning_threshold,
        is_above_error=token_usage >= error_threshold,
        is_above_autocompact=autocompact_enabled and token_usage >= auto_thr,
        is_at_blocking_limit=token_usage >= blocking,
    )


if __name__ == "__main__":
    # 200k window, 20k reserved → autocompact at 167k; 170k crosses it.
    s = calculate_token_warning_state(
        170_000,
        model_window=200_000,
        max_output_reserved=MAX_OUTPUT_RESERVED_FOR_SUMMARY,
        autocompact_enabled=True,
    )
    assert s.is_above_autocompact
    print("token_warning_thresholds ok", s.percent_left)
