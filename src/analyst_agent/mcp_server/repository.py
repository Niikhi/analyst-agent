import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from analyst_agent.config import get_settings
from analyst_agent.mcp_server import catalog
from analyst_agent.mcp_server.schemas import (
    ColumnInfo,
    CompanyCandidate,
    DescribeSchemaResult,
    RelationInfo,
    RunSqlResult,
)


MAX_ROWS = 200
FUZZY_FLOOR = 0.3
LEADING = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def build_engine() -> Engine:
    settings = get_settings()
    settings.require("analyst_db_url")
    return create_engine(settings.analyst_db_url, future=True, pool_pre_ping=True)


class Repository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def describe_schema(self) -> DescribeSchemaResult:
        query = text(
            """
            SELECT c.table_name, c.column_name, c.data_type, t.table_type
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = 'public' AND c.table_name = ANY(:names)
            ORDER BY c.table_name, c.ordinal_position
            """
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"names": catalog.EXPOSED}).all()

        grouped: dict[str, list[ColumnInfo]] = {}
        kinds: dict[str, str] = {}
        for row in rows:
            grouped.setdefault(row.table_name, []).append(
                ColumnInfo(
                    name=row.column_name,
                    type=row.data_type,
                    description=catalog.COLUMN_DESCRIPTION.get(row.column_name),
                )
            )
            kinds[row.table_name] = "view" if row.table_type == "VIEW" else "table"

        relations = [
            RelationInfo(
                name=name,
                kind=kinds[name],
                purpose=catalog.RELATION_PURPOSE[name],
                columns=grouped[name],
            )
            for name in catalog.EXPOSED
            if name in grouped
        ]
        return DescribeSchemaResult(relations=relations, notes=catalog.NOTES)

    def run_sql(self, sql: str, limit: int) -> RunSqlResult:
        statement = sql.strip().rstrip(";").strip()
        capped = max(1, min(limit, MAX_ROWS))
        wrapped = f"SELECT * FROM ({statement}) AS _q LIMIT {capped + 1}"

        refusal = None
        if not statement:
            refusal = "Empty statement."
        elif ";" in statement:
            refusal = "Only one statement may be sent at a time."
        elif not LEADING.match(statement):
            refusal = (
                "Only SELECT and WITH queries are permitted. This connection has no write "
                "privileges."
            )
        if refusal:
            return RunSqlResult(sql=statement, error=refusal)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(wrapped))
                columns = list(result.keys())
                fetched = result.fetchall()
        except SQLAlchemyError as exc:
            detail = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
            return RunSqlResult(
                sql=wrapped,
                error=f"{detail} Call describe_schema to check the available columns.",
            )

        truncated = len(fetched) > capped
        rows = [
            {col: _jsonable(value) for col, value in zip(columns, row)}
            for row in fetched[:capped]
        ]
        return RunSqlResult(
            sql=wrapped,
            row_count=len(rows),
            truncated=truncated,
            columns=columns,
            rows=rows,
        )

    def find_companies(
        self, query: str, sector: str | None, limit: int
    ) -> list[CompanyCandidate]:
        statement = text(
            """
            WITH scored AS (
                SELECT c.company_id, c.name, c.ticker, s.slug AS sector,
                       GREATEST(
                           CASE WHEN lower(c.ticker) = :q OR lower(c.name) = :q THEN 1.0 ELSE 0 END,
                           CASE WHEN EXISTS (
                                    SELECT 1 FROM company_aliases a
                                    WHERE a.company_id = c.company_id AND lower(a.alias) = :q
                                ) THEN 0.95 ELSE 0 END,
                           similarity(lower(c.name), :q),
                           word_similarity(:q, lower(c.name)),
                           COALESCE((
                               SELECT MAX(word_similarity(:q, lower(a.alias)))
                               FROM company_aliases a WHERE a.company_id = c.company_id
                           ), 0)
                       ) AS score
                FROM companies c
                JOIN sectors s ON s.sector_id = c.sector_id
                WHERE CAST(:sector AS text) IS NULL OR s.slug = CAST(:sector AS text)
            )
            SELECT * FROM scored WHERE score >= :floor ORDER BY score DESC, name LIMIT :limit
            """
        )
        with self._engine.connect() as conn:
            rows = conn.execute(
                statement,
                {
                    "q": query.strip().lower(),
                    "sector": sector,
                    "floor": FUZZY_FLOOR,
                    "limit": limit,
                },
            ).all()

        candidates = []
        for row in rows:
            score = float(row.score)
            if score >= 1.0:
                match_type = "exact"
            elif score >= 0.95:
                match_type = "alias"
            else:
                match_type = "fuzzy"
            candidates.append(
                CompanyCandidate(
                    company_id=row.company_id,
                    name=row.name,
                    ticker=row.ticker,
                    sector=row.sector,
                    match_type=match_type,
                    score=min(score, 1.0),
                )
            )
        return candidates
