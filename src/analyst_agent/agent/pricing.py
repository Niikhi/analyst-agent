from dataclasses import dataclass, field

CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


@dataclass(frozen=True)
class Rates:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, prompt: int, output: int, cache_read: int, cache_write: int) -> float:
        rate = self.input_per_mtok / 1_000_000
        return (
            prompt * rate
            + cache_read * rate * CACHE_READ_MULTIPLIER
            + cache_write * rate * CACHE_WRITE_MULTIPLIER
            + output * self.output_per_mtok / 1_000_000
        )


BEDROCK_RATES: dict[str, Rates] = {
    "claude-sonnet-4-5": Rates(3.00, 15.00),
    "claude-haiku-4-5": Rates(1.00, 5.00),
}


def rates_for(model_id: str) -> Rates | None:
    lowered = model_id.lower()
    for key in sorted(BEDROCK_RATES, key=len, reverse=True):
        if key in lowered:
            return BEDROCK_RATES[key]
    return None


@dataclass
class TurnUsage:
    turn: int
    prompt_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int

    @property
    def billed_input_tokens(self) -> int:
        return self.prompt_tokens + self.cache_read_tokens + self.cache_write_tokens

    def cost(self, rates: Rates | None) -> float | None:
        if rates is None:
            return None
        return rates.cost(
            self.prompt_tokens, self.output_tokens, self.cache_read_tokens, self.cache_write_tokens
        )

    def uncached_cost(self, rates: Rates | None) -> float | None:
        if rates is None:
            return None
        return rates.cost(self.billed_input_tokens, self.output_tokens, 0, 0)


@dataclass
class RunCost:
    model_id: str
    turns: list[TurnUsage] = field(default_factory=list)

    @property
    def rates(self) -> Rates | None:
        return rates_for(self.model_id)

    def summary(self) -> dict:
        rates = self.rates
        cost = sum(filter(None, (t.cost(rates) for t in self.turns))) if rates else None
        uncached = sum(filter(None, (t.uncached_cost(rates) for t in self.turns))) if rates else None
        return {
            "model": self.model_id,
            "turns": len(self.turns),
            "prompt_tokens": sum(t.prompt_tokens for t in self.turns),
            "output_tokens": sum(t.output_tokens for t in self.turns),
            "cache_read_tokens": sum(t.cache_read_tokens for t in self.turns),
            "cache_write_tokens": sum(t.cache_write_tokens for t in self.turns),
            "cost_usd": round(cost, 6) if cost is not None else None,
            "cost_without_caching_usd": round(uncached, 6) if uncached is not None else None,
            "saved_by_caching_usd": (
                round(uncached - cost, 6) if cost is not None and uncached is not None else None
            ),
            "rates_known": rates is not None,
            "per_turn": [
                {
                    "turn": t.turn,
                    "prompt_tokens": t.prompt_tokens,
                    "output_tokens": t.output_tokens,
                    "cache_read_tokens": t.cache_read_tokens,
                    "cache_write_tokens": t.cache_write_tokens,
                    "cost_usd": round(c, 6) if (c := t.cost(rates)) is not None else None,
                }
                for t in self.turns
            ],
        }
