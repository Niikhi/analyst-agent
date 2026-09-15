import time
from datetime import date
from typing import Any

from sqlalchemy import text

from analyst_agent.ingest.load import upsert_source

REQUEST_INTERVAL = 0.4
YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{ticker}"

_FIELDS = {
    "price": ("currentPrice", "regularMarketPrice"),
    "market_cap": ("marketCap",),
    "enterprise_value": ("enterpriseValue",),
    "shares_outstanding": ("sharesOutstanding",),
    "pe_ratio": ("trailingPE",),
    "ev_to_ebitda": ("enterpriseToEbitda",),
    "ev_to_sales": ("enterpriseToRevenue",),
    "beta": ("beta",),
}


def _first(info: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = info.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def fetch_quote(ticker: str) -> dict[str, Any] | None:
    import yfinance as yf

    time.sleep(REQUEST_INTERVAL)
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None
    if not info or info.get("marketCap") is None:
        return None

    quote = {name: _first(info, keys) for name, keys in _FIELDS.items()}

    raw_yield = _first(info, ("dividendYield",))
    if raw_yield is not None:
        quote["dividend_yield"] = raw_yield / 100 if raw_yield > 1 else raw_yield
    else:
        quote["dividend_yield"] = None

    employees = info.get("fullTimeEmployees")
    quote["employees"] = int(employees) if employees else None
    return quote


def upsert_market_data(conn: Any, company_id: int, ticker: str, quote: dict[str, Any]) -> None:
    source_id = upsert_source(
        conn, YAHOO_QUOTE_URL.format(ticker=ticker), "Yahoo Finance", "market_data"
    )
    conn.execute(
        text(
            """
            INSERT INTO market_data (company_id, as_of, price, market_cap, enterprise_value,
                                     shares_outstanding, pe_ratio, ev_to_ebitda, ev_to_sales,
                                     dividend_yield, beta, source_id)
            VALUES (:company_id, :as_of, :price, :market_cap, :enterprise_value,
                    :shares_outstanding, :pe_ratio, :ev_to_ebitda, :ev_to_sales,
                    :dividend_yield, :beta, :source_id)
            ON CONFLICT (company_id, as_of) DO UPDATE
                SET price = EXCLUDED.price,
                    market_cap = EXCLUDED.market_cap,
                    enterprise_value = EXCLUDED.enterprise_value,
                    shares_outstanding = EXCLUDED.shares_outstanding,
                    pe_ratio = EXCLUDED.pe_ratio,
                    ev_to_ebitda = EXCLUDED.ev_to_ebitda,
                    ev_to_sales = EXCLUDED.ev_to_sales,
                    dividend_yield = EXCLUDED.dividend_yield,
                    beta = EXCLUDED.beta,
                    source_id = EXCLUDED.source_id
            """
        ),
        {
            "company_id": company_id,
            "as_of": date.today(),
            "source_id": source_id,
            **{k: quote.get(k) for k in (*_FIELDS, "dividend_yield")},
        },
    )


def upsert_headcount_signal(conn: Any, company_id: int, ticker: str, employees: int) -> None:
    source_id = upsert_source(
        conn, YAHOO_QUOTE_URL.format(ticker=ticker), "Yahoo Finance", "company_profile"
    )
    conn.execute(
        text(
            """
            INSERT INTO signals (company_id, event_date, signal_type, headline,
                                 body, value_num, value_unit, direction, source_id)
            VALUES (:company_id, :event_date, 'headcount', :headline,
                    :body, :value_num, 'employees', 'neutral', :source_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "company_id": company_id,
            "event_date": date.today(),
            "headline": f"Reports approximately {employees:,} full-time employees",
            "body": (
                "Current headcount as reported on the company profile. This is a "
                "point-in-time snapshot, not a historical series, so period-over-period "
                "headcount change cannot be derived from it."
            ),
            "value_num": employees,
            "source_id": source_id,
        },
    )
