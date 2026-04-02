"""Minimal analytics boundary: allowlisted keys per event before emit (PII-safe by contract)."""

from __future__ import annotations

from typing import Any


# Central contract: extend only after privacy review.
ALLOWED_KEYS_BY_EVENT: dict[str, frozenset[str]] = {
    "session_start": frozenset({"session_id", "environment", "client_kind"}),
    "model_turn_complete": frozenset(
        {"session_id", "model", "input_tokens", "output_tokens", "stop_reason"}
    ),
    "permission_decision": frozenset({"session_id", "tool_name", "decision"}),
}


class AnalyticsService:
    """Drop-in gate: invalid events never reach the sink."""

    def __init__(self, allowed: dict[str, frozenset[str]] | None = None) -> None:
        self._allowed = allowed or ALLOWED_KEYS_BY_EVENT

    def validate(self, name: str, fields: dict[str, Any]) -> dict[str, Any]:
        allowed = self._allowed.get(name)
        if allowed is None:
            raise ValueError(f"unknown analytics event: {name!r}")
        keys = frozenset(fields)
        extra = keys - allowed
        if extra:
            raise ValueError(f"disallowed keys for {name!r}: {sorted(extra)}")
        missing_required = allowed - keys  # optional: require non-empty subset
        _ = missing_required
        return {k: fields[k] for k in sorted(fields)}

    def emit(self, name: str, fields: dict[str, Any], sink: list[tuple[str, dict[str, Any]]]) -> None:
        sink.append((name, self.validate(name, fields)))


if __name__ == "__main__":
    svc = AnalyticsService()
    out: list[tuple[str, dict[str, Any]]] = []
    svc.emit(
        "model_turn_complete",
        {
            "session_id": "abc",
            "model": "example-model",
            "input_tokens": 120,
            "output_tokens": 40,
            "stop_reason": "end_turn",
        },
        out,
    )
    try:
        svc.validate("model_turn_complete", {"session_id": "x", "user_home_path": "/secret"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected rejection of non-allowlisted key")
    assert len(out) == 1
    print("analytics_service ok")
