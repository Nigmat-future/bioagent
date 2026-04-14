"""Token usage tracking across agent calls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    """Accumulates token usage across all agent invocations."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    def add(self, *, input_tokens: int = 0, output_tokens: int = 0,
            cache_creation: int | None = None, cache_read: int | None = None) -> None:
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0
        self.cache_creation += cache_creation or 0
        self.cache_read += cache_read or 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def summary(self) -> str:
        return (
            f"Tokens — input: {self.input_tokens:,}, "
            f"output: {self.output_tokens:,}, "
            f"total: {self.total:,}"
        )


# Global tracker singleton
global_token_usage = TokenUsage()
