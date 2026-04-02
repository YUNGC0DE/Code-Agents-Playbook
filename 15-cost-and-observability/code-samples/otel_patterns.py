"""
Conceptual OpenTelemetry layout without importing the SDK.

Use this file as a checklist when wiring opentelemetry-api/sdk:
instrument names, safe attribute keys, and export gating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Instrument names (stable, low-cardinality namespace).
METRIC_TOKEN_INPUT_TOTAL = "agent.tokens.input"
METRIC_TOKEN_OUTPUT_TOTAL = "agent.tokens.output"
METRIC_COST_USD_TOTAL = "agent.cost.usd"
HISTO_TURN_LATENCY_S = "agent.turn.latency_seconds"

# Only these keys may appear on metrics (enforced in app code, not by OTel).
SAFE_METRIC_ATTRIBUTE_KEYS = frozenset({"model_family", "agent_kind", "deployment_environment"})


@dataclass
class ConceptualMetricRecord:
    """Stand-in for Counter.add / Histogram.record."""

    name: str
    value: float
    attributes: dict[str, str]


def validate_metric_attributes(attrs: dict[str, str]) -> dict[str, str]:
    keys = frozenset(attrs)
    bad = keys - SAFE_METRIC_ATTRIBUTE_KEYS
    if bad:
        raise ValueError(f"high-cardinality or unknown metric labels: {sorted(bad)}")
    return attrs


def record_conceptual_counter(name: str, delta: float, attributes: dict[str, str]) -> ConceptualMetricRecord:
    return ConceptualMetricRecord(name=name, value=delta, attributes=validate_metric_attributes(attributes))


def should_enable_otlp_export() -> bool:
    """Real code reads os.environ or config; default off for local runs."""
    return False


def build_resource_attributes(service_name: str, environment: str) -> dict[str, str]:
    """Resource describes the process, not the user's project."""
    return {"service.name": service_name, "deployment.environment": environment}


if __name__ == "__main__":
    r = record_conceptual_counter(
        METRIC_TOKEN_INPUT_TOTAL,
        100.0,
        {"model_family": "family-a", "agent_kind": "main", "deployment_environment": "dev"},
    )
    assert r.name == METRIC_TOKEN_INPUT_TOTAL
    try:
        validate_metric_attributes({"model_family": "x", "repo_path": "/tmp/secret"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected rejection of unsafe label")
    assert not should_enable_otlp_export()
    res = build_resource_attributes("my-agent", "staging")
    assert "service.name" in res
    _: dict[str, Any] = res
    print("otel_patterns ok")
