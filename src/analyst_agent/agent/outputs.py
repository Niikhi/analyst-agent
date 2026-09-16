from typing import Literal

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    company: str | None = Field(default=None, description="Ticker the figure belongs to")
    claim: str = Field(description="The specific figure or statement this source supports")
    period: str | None = Field(default=None, description="Period the figure covers")
    url: str = Field(description="source_url returned by the query that produced the figure")


class BaseAnswer(BaseModel):
    answer: str = Field(description="The analysis in prose, written in this persona's voice")
    companies_referenced: list[str] = Field(
        default_factory=list, description="Tickers actually discussed, resolved via resolve_company"
    )
    sources: list[SourceRef] = Field(
        default_factory=list,
        description="One entry per figure quoted. A figure with no source must not be stated.",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "high when every claim rests on queried rows with full coverage; medium when "
            "coverage is thin or the question is partly outside the data; low when the answer "
            "leans on little evidence."
        )
    )
    data_caveats: list[str] = Field(
        default_factory=list,
        description="Gaps that materially limit this answer, such as missing periods or NULLs",
    )
    out_of_scope: bool = Field(
        default=False,
        description="True when the question concerns a company or sector absent from the dataset",
    )


class MutualFundAnswer(BaseAnswer):
    stance: Literal["core_holding", "satellite", "underweight", "avoid", "no_call"] = Field(
        description="Position this name should take in a long-only portfolio"
    )
    benchmark_relative_view: str = Field(
        description="How this compares to the sector median, which is the index proxy here"
    )
    growth_durability: str = Field(
        description="Whether growth persisted across quarters or was a single period"
    )
    portfolio_fit: str = Field(description="Where this belongs in a long-only book, and why")
    risks: list[str] = Field(default_factory=list)


class EquityAnswer(BaseAnswer):
    rating: Literal["buy", "hold", "sell", "not_rated"]
    margin_trend: str = Field(
        description="Direction and size of the margin move, in percentage points"
    )
    earnings_quality: str = Field(
        description="Whether reported profit is backed by cash conversion"
    )
    valuation_vs_peers: str = Field(description="Multiple against sector peers")
    what_would_change_the_call: str = Field(
        description="The specific observation that would flip this rating"
    )
    risks: list[str] = Field(default_factory=list)


class PeAnswer(BaseAnswer):
    verdict: Literal["priority_target", "possible", "pass", "no_call"]
    thesis: str = Field(description="Why this is or is not worth owning outright")
    leverage_assessment: str = Field(
        description="Current leverage, headroom to a conventional structure, and cash cover"
    )
    entry_valuation_view: str = Field(description="What the entry multiple implies about price")
    operational_levers: list[str] = Field(
        default_factory=list, description="Specific, evidenced improvements a new owner could make"
    )
    value_creation_estimate: str = Field(
        description="Size of the prize if the margin gap to the best operator were closed"
    )
    exit_paths: list[str] = Field(default_factory=list)
    deal_risks: list[str] = Field(default_factory=list)


ANSWER_TYPES: dict[str, type[BaseAnswer]] = {
    "mutual_fund_analyst": MutualFundAnswer,
    "equity_analyst": EquityAnswer,
    "pe_analyst": PeAnswer,
}
