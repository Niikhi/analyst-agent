from dataclasses import dataclass, field
from datetime import date
from typing import Any

from analyst_agent.ingest.concepts import (
    ANNUAL_DAYS,
    CUMULATIVE_CONCEPTS,
    DURATION_CONCEPTS,
    INSTANT_CONCEPTS,
    QUARTER_DAYS,
    UNSIGNED_CONCEPTS,
)


@dataclass
class Observation:
    value: float
    filed: date
    accn: str
    form: str


@dataclass
class PeriodRow:
    period_end: date
    period_type: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form_type: str | None = None
    filed_at: date | None = None
    accn: str | None = None
    values: dict[str, float] = field(default_factory=dict)


def _as_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _classify(fact: dict[str, Any]) -> tuple[str | None, date]:
    end = date.fromisoformat(fact["end"])
    start = _as_date(fact.get("start"))
    if start is None:
        return "instant", end
    days = (end - start).days
    if QUARTER_DAYS[0] <= days <= QUARTER_DAYS[1]:
        return "Q", end
    if ANNUAL_DAYS[0] <= days <= ANNUAL_DAYS[1]:
        return "FY", end
    return None, end


def _usd_facts(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return []
    units = node.get("units", {})
    for unit_key in ("USD", "USD/shares", "shares"):
        if unit_key in units:
            return units[unit_key]
    return []


def _collect(facts: dict[str, Any], tags: list[str], instant: bool) -> dict[Any, Observation]:
    collected: dict[Any, Observation] = {}
    for tag in tags:
        for fact in _usd_facts(facts, tag):
            period_type, end = _classify(fact)
            if period_type is None:
                continue
            if instant != (period_type == "instant"):
                continue
            if fact.get("val") is None:
                continue
            key = end if instant else (period_type, end)
            observation = Observation(
                value=float(fact["val"]),
                filed=date.fromisoformat(fact["filed"]),
                accn=fact.get("accn", ""),
                form=fact.get("form", ""),
            )
            existing = collected.get(key)
            if existing is None or observation.filed > existing.filed:
                collected[key] = observation
    return collected


def _collect_cumulative(facts: dict[str, Any], tags: list[str]) -> dict[Any, Observation]:
    by_start: dict[date, dict[date, Observation]] = {}
    for tag in tags:
        for fact in _usd_facts(facts, tag):
            start = _as_date(fact.get("start"))
            if start is None or fact.get("val") is None:
                continue
            end = date.fromisoformat(fact["end"])
            span = (end - start).days
            if span < 60 or span > ANNUAL_DAYS[1]:
                continue
            observation = Observation(
                value=float(fact["val"]),
                filed=date.fromisoformat(fact["filed"]),
                accn=fact.get("accn", ""),
                form=fact.get("form", ""),
            )
            bucket = by_start.setdefault(start, {})
            existing = bucket.get(end)
            if existing is None or observation.filed > existing.filed:
                bucket[end] = observation

    out: dict[Any, Observation] = {}
    for start, ends in by_start.items():
        previous_end: date | None = None
        previous_value = 0.0
        for end, observation in sorted(ends.items()):
            total_span = (end - start).days
            step_span = (end - previous_end).days if previous_end else total_span
            if QUARTER_DAYS[0] <= step_span <= QUARTER_DAYS[1]:
                out[("Q", end)] = Observation(
                    observation.value - previous_value,
                    observation.filed,
                    observation.accn,
                    observation.form,
                )
            if ANNUAL_DAYS[0] <= total_span <= ANNUAL_DAYS[1]:
                out[("FY", end)] = observation
            previous_end, previous_value = end, observation.value
    return out


def _resolve_total_debt(instants: dict[str, dict[date, Observation]], at: date) -> float | None:
    combined = instants.get("combined_debt", {}).get(at)
    if combined is not None:
        return combined.value
    parts = [
        instants.get(name, {}).get(at)
        for name in ("long_term_debt_noncurrent", "long_term_debt_current", "short_term_borrowings")
    ]
    present = [p.value for p in parts if p is not None]
    return sum(present) if present else None


def extract_periods(facts: dict[str, Any], limit: int = 12) -> list[PeriodRow]:
    durations = {
        concept: (
            _collect_cumulative(facts, tags)
            if concept in CUMULATIVE_CONCEPTS
            else _collect(facts, tags, instant=False)
        )
        for concept, tags in DURATION_CONCEPTS.items()
    }
    instants = {
        concept: _collect(facts, tags, instant=True)
        for concept, tags in INSTANT_CONCEPTS.items()
    }

    keys: set[tuple[str, date]] = set()
    for observations in durations.values():
        keys.update(observations.keys())

    rows: list[PeriodRow] = []
    for period_type, period_end in keys:
        row = PeriodRow(period_end=period_end, period_type=period_type)

        for concept, observations in durations.items():
            observation = observations.get((period_type, period_end))
            if observation is None:
                continue
            value = observation.value
            if concept in UNSIGNED_CONCEPTS:
                value = abs(value)
            row.values[concept] = value
            if row.filed_at is None or observation.filed > row.filed_at:
                row.filed_at = observation.filed
                row.form_type = observation.form
                row.accn = observation.accn

        for concept in ("cash_and_equivalents", "inventory", "total_assets", "total_equity"):
            observation = instants.get(concept, {}).get(period_end)
            if observation is not None:
                row.values[concept] = observation.value

        total_debt = _resolve_total_debt(instants, period_end)
        if total_debt is not None:
            row.values["total_debt"] = total_debt

        if "revenue" not in row.values and "net_income" not in row.values:
            continue
        rows.append(row)

    rows.sort(key=lambda r: (r.period_end, r.period_type), reverse=True)

    quarterly = [r for r in rows if r.period_type == "Q"][:limit]
    annual = [r for r in rows if r.period_type == "FY"][:4]
    return quarterly + annual


def coverage_report(rows: list[PeriodRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for concept in row.values:
            counts[concept] = counts.get(concept, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
