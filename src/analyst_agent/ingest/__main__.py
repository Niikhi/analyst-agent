import argparse
import sys

from sqlalchemy import text

from analyst_agent.ingest import load
from analyst_agent.ingest.edgar import EdgarClient
from analyst_agent.ingest.transform import coverage_report, extract_periods
from analyst_agent.ingest.universe import SECTORS


def fiscal_month(facts: dict) -> int | None:
    end = facts.get("facts", {}).get("dei", {})
    for node in end.values():
        for unit_facts in node.get("units", {}).values():
            for fact in unit_facts:
                if fact.get("fp") == "FY" and fact.get("end"):
                    return int(fact["end"][5:7])
    return None


def ingest_sector(slug: str, limit: int, dry_run: bool) -> None:
    definition = SECTORS[slug]
    tickers = definition.tickers[:limit] if limit else definition.tickers

    with EdgarClient() as client, load.engine().begin() as conn:
        sector_id = load.upsert_sector(conn, definition)
        print(f"\nsector {slug}: {len(tickers)} companies")

        for ticker in tickers:
            try:
                entry = client.resolve_ticker(ticker)
            except LookupError as exc:
                print(f"  {ticker:6} SKIP  {exc}")
                continue

            cik = entry["cik"]
            facts = client.company_facts(cik)
            rows = extract_periods(facts)
            quarterly = sum(1 for r in rows if r.period_type == "Q")
            annual = sum(1 for r in rows if r.period_type == "FY")

            if dry_run:
                print(f"  {ticker:6} {entry['title'][:38]:40} Q={quarterly:2} FY={annual}")
                print(f"         {coverage_report(rows)}")
                continue

            load.store_raw(conn, cik, "companyfacts", facts)
            source_id = load.upsert_source(
                conn,
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                "SEC EDGAR",
                "companyfacts",
            )
            company_id = load.upsert_company(
                conn,
                sector_id=sector_id,
                name=entry["title"],
                ticker=ticker,
                cik=cik,
                fiscal_year_end_month=fiscal_month(facts),
                description=None,
                source_id=source_id,
            )
            written = load.upsert_financials(conn, company_id, cik, rows)
            print(f"  {ticker:6} {entry['title'][:38]:40} Q={quarterly:2} FY={annual}  rows={written}")

        if dry_run:
            conn.rollback()


def summarise() -> None:
    with load.engine().connect() as conn:
        print("\ncoverage")
        for row in conn.execute(
            text(
                "SELECT sector, count(*) AS companies, "
                "       sum(financial_period_count) AS periods, "
                "       max(latest_period_end) AS latest "
                "FROM v_company_coverage GROUP BY sector ORDER BY sector"
            )
        ):
            print(f"  {row.sector:10} companies={row.companies} periods={row.periods} latest={row.latest}")

        print("\nnull rate by column on quarterly rows")
        columns = [
            "revenue", "gross_profit", "operating_income", "depreciation_amortization",
            "net_income", "cash_from_operations", "capital_expenditure",
            "cash_and_equivalents", "total_debt", "total_equity",
        ]
        parts = ", ".join(
            f"round(100.0 * count({c}) / nullif(count(*),0)) AS {c}" for c in columns
        )
        row = conn.execute(text(f"SELECT count(*) AS n, {parts} FROM financials WHERE period_type='Q'")).one()
        print(f"  rows={row.n}")
        for c in columns:
            filled = getattr(row, c)
            print(f"    {c:28} {filled if filled is not None else 0:>3}% populated")


def main() -> int:
    parser = argparse.ArgumentParser(prog="analyst-ingest")
    parser.add_argument("--sector", choices=sorted(SECTORS) + ["all"], default="logistics")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if args.summary:
        summarise()
        return 0

    slugs = sorted(SECTORS) if args.sector == "all" else [args.sector]
    for slug in slugs:
        ingest_sector(slug, args.limit, args.dry_run)

    if not args.dry_run:
        summarise()
    return 0


if __name__ == "__main__":
    sys.exit(main())
