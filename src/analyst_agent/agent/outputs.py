from typing import Literal

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    company: str | None = Field(
        default=None,
        description=(
            "Ticker the figure belongs to. Leave null only for a figure computed across the "
            "whole sector, such as a median, and in that case do not attach one company's "
            "filing url to it."
        ),
    )
    claim: str = Field(description="The specific figure or statement this source supports")
    period: str | None = Field(default=None, description="Period the figure covers")
    url: str = Field(
        description=(
            "The source_url returned by the query that produced this figure. It must be the "
            "row's own source. A sector aggregate has no single filing behind it, so cite the "
            "view it came from rather than one company's filing."
        )
    )


class BaseAnswer(BaseModel):
    answer: str = Field(description="The analysis in prose, written in this persona's voice")
    companies_referenced: list[str] = Field(
        default_factory=list,
        description=(
            "Every ticker you name anywhere in this response. Required whenever you discuss a "
            "company, including when the question was about something outside the dataset and "
            "you offered these as alternatives. An empty list means you discussed no company."
        ),
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
        description=(
            "Your actual position call, and it must agree with your prose. If the analysis "
            "argues a name is worth owning, say core_holding or satellite; if it argues "
            "against, say underweight or avoid. Where the question covers several companies, "
            "give the call for the one your answer leads with. Use no_call only when the "
            "dataset genuinely cannot support any position, such as an out-of-scope company."
        )
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
    rating: Literal["buy", "hold", "sell", "not_rated"] = Field(
        description=(
            "Your actual call, and it must agree with your prose. If the analysis says a name "
            "is deteriorating or is a value trap, that is a sell; if it says the market has "
            "not yet priced an improvement, that is a buy. Where the question covers several "
            "companies, rate the one your answer leads with. Use not_rated only when the "
            "dataset cannot support a view at all."
        )
    )
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
    verdict: Literal["priority_target", "possible", "pass", "no_call"] = Field(
        description=(
            "Your actual call, and it must agree with your prose. If the analysis makes a case "
            "for owning a company outright, say priority_target or possible; if it argues the "
            "financing or the operations rule it out, say pass. Where the question covers "
            "several companies, give the verdict for the one your answer leads with. Use "
            "no_call only when the dataset cannot support a view, such as an out-of-scope "
            "company."
        )
    )
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
