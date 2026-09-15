import json
import re
from typing import Any

from sqlalchemy import Engine, create_engine, text

from analyst_agent.ingest.concepts import FINANCIAL_COLUMNS
from analyst_agent.ingest.config import admin_db_url
from analyst_agent.ingest.transform import PeriodRow
from analyst_agent.ingest.universe import SectorDefinition

SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings|"
    r"group|the|lp|llc|nv|sa)\b\.?",
    re.IGNORECASE,
)


def engine() -> Engine:
    return create_engine(admin_db_url(), future=True)


def filing_url(cik: str, accn: str) -> str:
    if not accn:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accn.replace('-', '')}/{accn}-index.htm"
    )


def aliases_for(name: str, ticker: str) -> set[str]:
    lowered = name.lower().replace(",", " ").replace(".", " ")
    trimmed = SUFFIXES.sub(" ", lowered)
    collapsed = " ".join(trimmed.split())
    return {a for a in {name.lower(), collapsed, ticker.lower()} if a}


def upsert_sector(conn: Any, definition: SectorDefinition) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO sectors (slug, display_name, coverage_note)
            VALUES (:slug, :display_name, :coverage_note)
            ON CONFLICT (slug) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    coverage_note = EXCLUDED.coverage_note
            RETURNING sector_id
            """
        ),
        definition.__dict__ | {"tickers": None},
    ).scalar_one()


def upsert_source(conn: Any, url: str, publisher: str, doc_type: str) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO sources (url, publisher, doc_type)
            VALUES (:url, :publisher, :doc_type)
            ON CONFLICT (url, doc_type) DO UPDATE SET retrieved_at = now()
            RETURNING source_id
            """
        ),
        {"url": url, "publisher": publisher, "doc_type": doc_type},
    ).scalar_one()


def store_raw(conn: Any, cik: str, endpoint: str, payload: dict[str, Any]) -> None:
    conn.execute(
        text(
            "INSERT INTO raw_filings (cik, endpoint, payload) "
            "VALUES (:cik, :endpoint, CAST(:payload AS jsonb))"
        ),
        {"cik": cik, "endpoint": endpoint, "payload": json.dumps(payload)},
    )


def upsert_company(
    conn: Any,
    sector_id: int,
    name: str,
    ticker: str,
    cik: str,
    fiscal_year_end_month: int | None,
    description: str | None,
    source_id: int,
) -> int:
    company_id = conn.execute(
        text(
            """
            INSERT INTO companies (sector_id, name, ticker, cik,
                                   fiscal_year_end_month, business_description, source_id)
            VALUES (:sector_id, :name, :ticker, :cik,
                    :fiscal_year_end_month, :description, :source_id)
            ON CONFLICT (cik) DO UPDATE
                SET sector_id = EXCLUDED.sector_id,
                    name = EXCLUDED.name,
                    ticker = EXCLUDED.ticker,
                    fiscal_year_end_month = EXCLUDED.fiscal_year_end_month,
                    business_description = EXCLUDED.business_description,
                    updated_at = now()
            RETURNING company_id
            """
        ),
        {
            "sector_id": sector_id,
            "name": name,
            "ticker": ticker,
            "cik": cik,
            "fiscal_year_end_month": fiscal_year_end_month,
            "description": description,
            "source_id": source_id,
        },
    ).scalar_one()

    for alias in aliases_for(name, ticker):
        conn.execute(
            text(
                "INSERT INTO company_aliases (company_id, alias) VALUES (:cid, :alias) "
                "ON CONFLICT (company_id, alias) DO NOTHING"
            ),
            {"cid": company_id, "alias": alias},
        )
    return company_id


def upsert_financials(conn: Any, company_id: int, cik: str, rows: list[PeriodRow]) -> int:
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in FINANCIAL_COLUMNS)
    columns = ", ".join(FINANCIAL_COLUMNS)
    placeholders = ", ".join(f":{c}" for c in FINANCIAL_COLUMNS)

    statement = text(
        f"""
        INSERT INTO financials (company_id, period_end, period_type, fiscal_year,
                                fiscal_period, form_type, filed_at, source_id, {columns})
        VALUES (:company_id, :period_end, :period_type, :fiscal_year,
                :fiscal_period, :form_type, :filed_at, :source_id, {placeholders})
        ON CONFLICT (company_id, period_end, period_type) DO UPDATE
            SET fiscal_year = EXCLUDED.fiscal_year,
                fiscal_period = EXCLUDED.fiscal_period,
                form_type = EXCLUDED.form_type,
                filed_at = EXCLUDED.filed_at,
                source_id = EXCLUDED.source_id,
                {assignments}
        """
    )

    written = 0
    for row in rows:
        source_id = upsert_source(
            conn, filing_url(cik, row.accn or ""), "SEC EDGAR", row.form_type or "10-Q"
        )
        params: dict[str, Any] = {
            "company_id": company_id,
            "period_end": row.period_end,
            "period_type": row.period_type,
            "fiscal_year": row.period_end.year,
            "fiscal_period": row.period_type if row.period_type == "FY" else None,
            "form_type": row.form_type,
            "filed_at": row.filed_at,
            "source_id": source_id,
        }
        for column in FINANCIAL_COLUMNS:
            params[column] = row.values.get(column)
        conn.execute(statement, params)
        written += 1
    return written
