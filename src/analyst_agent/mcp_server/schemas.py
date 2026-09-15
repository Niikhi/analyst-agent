from typing import Any, Literal

from pydantic import BaseModel, Field

Sector = Literal["tech", "retail", "logistics"]


class ColumnInfo(BaseModel):
    name: str
    type: str
    description: str | None = None


class RelationInfo(BaseModel):
    name: str
    kind: Literal["table", "view"]
    purpose: str
    columns: list[ColumnInfo]


class DescribeSchemaResult(BaseModel):
    relations: list[RelationInfo]
    notes: list[str] = Field(
        description="Rules and caveats that apply to any query against this schema"
    )


class RunSqlResult(BaseModel):
    sql: str = Field(description="The statement executed, after the row cap was applied")
    error: str | None = Field(
        default=None,
        description=(
            "Why the query did not run. A rejected or invalid query is a normal outcome, "
            "not a failure: read this, correct the SQL and try again."
        ),
    )
    row_count: int = 0
    truncated: bool = Field(default=False, description="True when the row cap cut the result short")
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class CompanyCandidate(BaseModel):
    company_id: int
    name: str
    ticker: str | None = None
    sector: Sector
    match_type: Literal["exact", "alias", "fuzzy"]
    score: float = Field(ge=0.0, le=1.0)


class ResolveCompanyResult(BaseModel):
    query: str
    status: Literal["found", "ambiguous", "not_found"]
    match: CompanyCandidate | None = None
    candidates: list[CompanyCandidate] = Field(default_factory=list)
    guidance: str = Field(
        description="What this status means and what the caller may legitimately assert"
    )
