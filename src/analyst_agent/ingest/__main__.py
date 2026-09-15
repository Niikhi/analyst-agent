import argparse
import sys

from sqlalchemy import text

from analyst_agent.ingest import load, market, signals
from analyst_agent.ingest.edgar import EdgarClient
from analyst_agent.ingest.transform import coverage_report, extract_periods
from analyst_agent.ingest.universe import SECTORS


def fiscal_month(facts: dict) -> int | None:
    for node in facts.get("facts", {}).get("dei", {}).values():
        for unit_facts in node.get("units", {}).values():
            for fact in unit_facts:
                if fact.get("fp") == "FY" and fact.get("end"):
                    return int(fact["end"][5:7])
    return None


def company_ids(conn, slug: str) -> list[tuple[int, str, str]]:
    rows = conn.execute(
        text(
            "SELECT c.company_id, c.ticker, c.cik FROM companies c "
            "JOIN sectors s ON s.sector_id = c.sector_id "
            "WHERE s.slug = :slug ORDER BY c.company_id"
        ),
        {"slug": slug},
    ).all()
    return [(r.company_id, r.ticker, r.cik) for r in rows]


def ingest_financials(slug: str, limit: int, dry_run: bool) -> None:
    definition = SECTORS[slug]
    tickers = definition.tickers[:limit] if limit else definition.tickers

    with EdgarClient() as client, load.engine().begin() as conn:
        sector_id = load.upsert_sector(conn, definition)
        print(f"\nfinancials :: {slug} :: {len(tickers)} companies")

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
                print(f"  {ticker:6} {entry['title'][:36]:38} Q={quarterly:2} FY={annual}")
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
            print(f"  {ticker:6} {entry['title'][:36]:38} Q={quarterly:2} FY={annual}  rows={written}")

        if dry_run:
            conn.rollback()


def ingest_market(slug: str, dry_run: bool) -> None:
    with load.engine().begin() as conn:
        targets = company_ids(conn, slug)
        print(f"\nmarket :: {slug} :: {len(targets)} companies")

        for company_id, ticker, _cik in targets:
            quote = market.fetch_quote(ticker)
            if quote is None:
                print(f"  {ticker:6} SKIP  no quote returned")
                continue

            employees = quote.get("employees")
            price = quote.get("price")
            ev_ebitda = quote.get("ev_to_ebitda")
            print(
                f"  {ticker:6} price={price} ev/ebitda={ev_ebitda} "
                f"pe={quote.get('pe_ratio')} employees={employees}"
            )
            if dry_run:
                continue

            market.upsert_market_data(conn, company_id, ticker, quote)
            if employees:
                market.upsert_headcount_signal(conn, company_id, ticker, employees)

        if dry_run:
            conn.rollback()


def ingest_signals(slug: str, dry_run: bool) -> None:
    with EdgarClient() as client, load.engine().begin() as conn:
        targets = company_ids(conn, slug)
        print(f"\nsignals :: {slug} :: {len(targets)} companies")

        for company_id, ticker, cik in targets:
            events = signals.extract_events(client.submissions(cik))
            kinds = sorted({e["signal_type"] for e in events})
            print(f"  {ticker:6} events={len(events):2}  {kinds}")
            if dry_run:
                continue
            signals.upsert_events(conn, company_id, cik, events)

        if dry_run:
            conn.rollback()


def summarise() -> None:
    with load.engine().connect() as conn:
        print("\ncoverage")
        for row in conn.execute(
            text(
                "SELECT sector, count(*) AS companies, "
                "       sum(financial_period_count) AS periods, "
                "       sum(signal_count) AS signals, "
                "       count(*) FILTER (WHERE has_market_data) AS with_market, "
                "       max(latest_period_end) AS latest "
                "FROM v_company_coverage GROUP BY sector ORDER BY sector"
            )
        ):
            print(
                f"  {row.sector:10} companies={row.companies} periods={row.periods} "
                f"signals={row.signals} market={row.with_market} latest={row.latest}"
            )

        print("\nsignals by type")
        for row in conn.execute(
            text("SELECT signal_type, count(*) AS n FROM signals GROUP BY 1 ORDER BY n DESC")
        ):
            print(f"  {row.signal_type:20} {row.n}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="analyst-ingest")
    parser.add_argument("--sector", choices=sorted(SECTORS) + ["all"], default="all")
    parser.add_argument("--what", choices=["financials", "market", "signals", "all"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if args.summary:
        summarise()
        return 0

    slugs = sorted(SECTORS) if args.sector == "all" else [args.sector]
    for slug in slugs:
        if args.what in ("financials", "all"):
            ingest_financials(slug, args.limit, args.dry_run)
        if args.what in ("market", "all"):
            ingest_market(slug, args.dry_run)
        if args.what in ("signals", "all"):
            ingest_signals(slug, args.dry_run)

    if not args.dry_run:
        summarise()
    return 0


if __name__ == "__main__":
    sys.exit(main())
