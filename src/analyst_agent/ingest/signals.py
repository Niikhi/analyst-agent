from datetime import date
from typing import Any

from sqlalchemy import text

from analyst_agent.ingest.load import filing_url, upsert_source

ITEM_MAP: dict[str, tuple[str, str, str]] = {
    "1.01": ("m_and_a", "neutral", "Entry into a material definitive agreement"),
    "1.02": ("m_and_a", "neutral", "Termination of a material definitive agreement"),
    "2.01": ("m_and_a", "neutral", "Completion of an acquisition or disposition of assets"),
    "2.02": ("guidance", "neutral", "Announced results of operations and financial condition"),
    "2.03": ("capex_plan", "neutral", "Created a direct financial obligation"),
    "2.05": ("restructuring", "negative", "Costs associated with exit or disposal activities"),
    "2.06": ("restructuring", "negative", "Recorded a material impairment"),
    "5.02": ("management_change", "neutral", "Departure or election of directors or officers"),
    "7.01": ("guidance", "neutral", "Regulation FD disclosure to investors"),
}

SKIP_ITEMS = {"9.01", "5.03", "5.07", "8.01", "3.01", "4.01", "5.05"}


def extract_events(submissions: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    if not forms:
        return []

    events: list[dict[str, Any]] = []
    seen: set[tuple[date, str]] = set()

    for i, form in enumerate(forms):
        if form != "8-K":
            continue
        raw_items = (recent.get("items") or [""] * len(forms))[i]
        if not raw_items:
            continue
        filed = date.fromisoformat(recent["filingDate"][i])
        accn = recent["accessionNumber"][i]

        for code in (c.strip() for c in raw_items.split(",")):
            if code in SKIP_ITEMS or code not in ITEM_MAP:
                continue
            signal_type, direction, description = ITEM_MAP[code]
            key = (filed, code)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "event_date": filed,
                    "signal_type": signal_type,
                    "direction": direction,
                    "headline": description,
                    "body": f"SEC Form 8-K, Item {code}, filed {filed.isoformat()}.",
                    "accn": accn,
                }
            )

    events.sort(key=lambda e: e["event_date"], reverse=True)
    return events[:limit]


def upsert_events(conn: Any, company_id: int, cik: str, events: list[dict[str, Any]]) -> int:
    statement = text(
        """
        INSERT INTO signals (company_id, event_date, signal_type, headline,
                             body, direction, source_id)
        VALUES (:company_id, :event_date, :signal_type, :headline,
                :body, :direction, :source_id)
        ON CONFLICT DO NOTHING
        """
    )
    written = 0
    for event in events:
        source_id = upsert_source(conn, filing_url(cik, event["accn"]), "SEC EDGAR", "8-K")
        conn.execute(
            statement,
            {
                "company_id": company_id,
                "event_date": event["event_date"],
                "signal_type": event["signal_type"],
                "headline": event["headline"],
                "body": event["body"],
                "direction": event["direction"],
                "source_id": source_id,
            },
        )
        written += 1
    return written
