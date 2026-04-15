"""Token usage tracking across agent calls."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Model-aware pricing table (USD per 1M tokens).
# Pricing as of 2025 for Anthropic Claude models.
# Falls back to DEFAULT for unknown models.
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-opus-4-5": {"input": 15.0, "output": 75.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    # Default fallback (conservative estimate)
    "default": {"input": 3.0, "output": 15.0},
}


def get_model_pricing(model: str) -> tuple[float, float]:
    """Return (input_cost_per_m, output_cost_per_m) for the given model name.

    Matches by prefix so versioned model IDs (e.g. "claude-sonnet-4-5-20250929")
    are covered by both the exact key and the prefix fallback.
    """
    if model in _MODEL_PRICING:
        p = _MODEL_PRICING[model]
        return p["input"], p["output"]
    # Prefix match (e.g. "claude-sonnet-4-5-20250929" → "claude-sonnet-4-5")
    for key, p in _MODEL_PRICING.items():
        if key != "default" and model.startswith(key):
            return p["input"], p["output"]
    default = _MODEL_PRICING["default"]
    return default["input"], default["output"]


class BudgetExceeded(Exception):
    """Raised when token or cost budget is exceeded."""


@dataclass
class TokenUsage:
    """Accumulates token usage across all agent invocations.

    Supports budget enforcement: call check_budget() after each API call
    to raise BudgetExceeded when limits are hit.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    # Budget limits (0 = unlimited)
    token_budget: int = 0
    cost_budget_usd: float = 0.0

    # Per-1M token costs — set from model pricing at construction time
    INPUT_COST_PER_M: float = field(default=3.0)
    OUTPUT_COST_PER_M: float = field(default=15.0)

    def add(self, *, input_tokens: int = 0, output_tokens: int = 0,
            cache_creation: int | None = None, cache_read: int | None = None) -> None:
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0
        self.cache_creation += cache_creation or 0
        self.cache_read += cache_read or 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimated cost in USD based on token counts."""
        return (
            self.input_tokens * self.INPUT_COST_PER_M / 1_000_000
            + self.output_tokens * self.OUTPUT_COST_PER_M / 1_000_000
        )

    @property
    def is_over_token_budget(self) -> bool:
        return self.token_budget > 0 and self.total > self.token_budget

    @property
    def is_over_cost_budget(self) -> bool:
        return self.cost_budget_usd > 0 and self.estimated_cost_usd > self.cost_budget_usd

    def check_budget(self) -> None:
        """Raise BudgetExceeded if any budget is exceeded."""
        if self.is_over_token_budget:
            raise BudgetExceeded(
                f"Token budget exceeded: {self.total:,} > {self.token_budget:,}"
            )
        if self.is_over_cost_budget:
            raise BudgetExceeded(
                f"Cost budget exceeded: ${self.estimated_cost_usd:.2f} > ${self.cost_budget_usd:.2f}"
            )

    def summary(self) -> str:
        parts = [
            f"Tokens — input: {self.input_tokens:,}, "
            f"output: {self.output_tokens:,}, "
            f"total: {self.total:,}"
        ]
        if self.token_budget > 0:
            parts.append(f"budget: {self.token_budget:,} ({'OVER' if self.is_over_token_budget else 'OK'})")
        if self.cost_budget_usd > 0:
            parts.append(f"cost: ${self.estimated_cost_usd:.2f}/${self.cost_budget_usd:.2f}")
        return " | ".join(parts)


# Global tracker — initialized with budget and model-aware pricing from settings
def _init_global_usage() -> TokenUsage:
    try:
        from bioagent.config.settings import settings
        model = settings.get_primary_model()
        input_cost, output_cost = get_model_pricing(model)
        return TokenUsage(
            token_budget=settings.token_budget,
            cost_budget_usd=settings.cost_budget_usd,
            INPUT_COST_PER_M=input_cost,
            OUTPUT_COST_PER_M=output_cost,
        )
    except Exception:
        return TokenUsage()


global_token_usage = _init_global_usage()
