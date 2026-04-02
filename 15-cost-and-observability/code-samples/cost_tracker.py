"""Per-model usage accumulation with optional nested-session rollup (parent + child)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    web_search_requests: int = 0
    cost_usd: float = 0.0


@dataclass
class CostTracker:
    """Single session cost store: one place for invoice-style totals."""

    by_model: dict[str, ModelUsage] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    unknown_models: set[str] = field(default_factory=set)

    def add_usage(
        self,
        model: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        web_search_requests: int = 0,
        cost_usd: float | None,
    ) -> None:
        mu = self.by_model.setdefault(model, ModelUsage())
        mu.input_tokens += input_tokens
        mu.output_tokens += output_tokens
        mu.cache_read_input_tokens += cache_read_input_tokens
        mu.cache_creation_input_tokens += cache_creation_input_tokens
        mu.web_search_requests += web_search_requests
        if cost_usd is None:
            self.unknown_models.add(model)
        else:
            mu.cost_usd += cost_usd
            self.total_cost_usd += cost_usd

    def merge_child(self, child: CostTracker) -> None:
        """Fold a nested agent or fork run into this session (Chapter 10 pattern)."""
        self.unknown_models |= child.unknown_models
        for model, mu in child.by_model.items():
            self.add_usage(
                model,
                input_tokens=mu.input_tokens,
                output_tokens=mu.output_tokens,
                cache_read_input_tokens=mu.cache_read_input_tokens,
                cache_creation_input_tokens=mu.cache_creation_input_tokens,
                web_search_requests=mu.web_search_requests,
                cost_usd=mu.cost_usd if model not in child.unknown_models else None,
            )

    def total_tokens(self) -> int:
        t = 0
        for mu in self.by_model.values():
            t += (
                mu.input_tokens
                + mu.output_tokens
                + mu.cache_read_input_tokens
                + mu.cache_creation_input_tokens
            )
        return t


# Example per-million-token rates (USD); replace with your vendor table.
PRICE_PER_MTOK_USD: dict[str, tuple[float, float]] = {
    "example-model": (3.0, 15.0),  # input, output per 1M tokens
}


def price_usage_usd(model: str, input_t: int, output_t: int) -> float | None:
    rates = PRICE_PER_MTOK_USD.get(model)
    if rates is None:
        return None
    inp_r, out_r = rates
    return (input_t * inp_r + output_t * out_r) / 1_000_000.0


if __name__ == "__main__":
    main = CostTracker()
    main.add_usage(
        "example-model",
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=20,
        cache_creation_input_tokens=0,
        web_search_requests=0,
        cost_usd=price_usage_usd("example-model", 100, 50),
    )

    child = CostTracker()
    child.add_usage(
        "example-model",
        input_tokens=30,
        output_tokens=10,
        cost_usd=price_usage_usd("example-model", 30, 10),
    )
    main.merge_child(child)

    mystery = CostTracker()
    mystery.add_usage(
        "unknown-vendor-model",
        input_tokens=10,
        output_tokens=5,
        cost_usd=price_usage_usd("unknown-vendor-model", 10, 5),
    )
    assert "unknown-vendor-model" in mystery.unknown_models

    assert "example-model" in main.by_model
    assert main.total_cost_usd > 0
    assert main.total_tokens() == 100 + 50 + 20 + 30 + 10
    print("cost_tracker ok")
