from mcp.server.mcpserver import MCPServer

from analyst_agent.mcp_server.repository import Repository
from analyst_agent.mcp_server.schemas import (
    DescribeSchemaResult,
    ResolveCompanyResult,
    RunSqlResult,
    Sector,
)

mcp = MCPServer(
    "analyst-data",
    instructions=(
        "Read-only access to a curated financial dataset covering three sectors: tech, "
        "retail and logistics, with roughly six companies each. It is a deliberately narrow "
        "slice, not the whole market. Call describe_schema first to learn what is queryable. "
        "Resolve any company the user names with resolve_company before making claims about "
        "it; a not_found status means the dataset holds nothing on that company and no "
        "statement about it can be supported from here."
    ),
)

_repo: Repository | None = None

CONFIDENT = 0.9
SOLE_MATCH = 0.5
TIE_MARGIN = 0.1


def configure(repo: Repository) -> None:
    global _repo
    _repo = repo


def _require() -> Repository:
    if _repo is None:
        raise RuntimeError("Server started without a repository. Call configure(repo) first.")
    return _repo


@mcp.tool()
def describe_schema() -> DescribeSchemaResult:
    return _require().describe_schema()


@mcp.tool()
def run_sql(sql: str, limit: int = 50) -> RunSqlResult:
    return _require().run_sql(sql, limit)


@mcp.tool()
def resolve_company(name: str, sector: Sector | None = None) -> ResolveCompanyResult:
    repo = _require()
    query = name.strip()
    candidates = repo.find_companies(query, sector, limit=5)

    if not candidates:
        return ResolveCompanyResult(
            query=query,
            status="not_found",
            guidance=(
                f"No company matching '{query}' exists in this dataset. Do not describe, "
                "analyse or estimate anything about it. Say plainly that it is outside the "
                "data you have, and offer what is covered instead."
            ),
        )

    leader = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    contested = runner_up is not None and (leader.score - runner_up.score) < TIE_MARGIN

    sole = len(candidates) == 1 and leader.score >= SOLE_MATCH
    if sole or (leader.score >= CONFIDENT and not contested):
        return ResolveCompanyResult(
            query=query,
            status="found",
            match=leader,
            guidance=(
                f"Resolved to {leader.name} ({leader.ticker}) in the {leader.sector} sector. "
                f"Filter on company_id = {leader.company_id} in further queries. Every figure "
                "you state about it must come from a tool result."
            ),
        )

    return ResolveCompanyResult(
        query=query,
        status="ambiguous",
        candidates=candidates,
        guidance=(
            f"'{query}' did not resolve to exactly one company. Ask which of the candidates "
            "the user means, or narrow by sector. Do not pick one and proceed: analysing the "
            "wrong company is worse than asking."
        ),
    )
