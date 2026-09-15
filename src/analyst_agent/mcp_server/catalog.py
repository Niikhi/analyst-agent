RELATION_PURPOSE: dict[str, str] = {
    "sectors": "The three sectors covered. `slug` is the value used everywhere else.",
    "companies": (
        "The complete company universe. A company absent from this table is outside the "
        "dataset entirely and nothing can be said about it."
    ),
    "signals": (
        "Dated events that appear in no financial statement: headcount, management changes, "
        "guidance announcements, M&A, restructuring. Query this for any question about news, "
        "hiring, or recent developments."
    ),
    "market_data": (
        "What the stock market currently values each company at. One snapshot per company, "
        "not a time series."
    ),
    "v_company_coverage": (
        "How much data exists per company. Check this before making confident claims: a "
        "company with few periods or no signals supports a much weaker answer."
    ),
    "v_financials_enriched": (
        "Every reported period with EBITDA, free cash flow and net debt derived. Use for "
        "single-company history."
    ),
    "v_company_metrics": (
        "v_financials_enriched plus margins, growth rates, leverage and trailing-twelve-month "
        "aggregates, for every period. Use when the question needs history or trend."
    ),
    "v_latest_company_metrics": (
        "One row per company, its most recent quarter, with every metric. Use this for any "
        "cross-company comparison so all companies are measured at the same point."
    ),
    "v_sector_metrics": (
        "Sector medians and best-in-class values. Medians rather than averages because a "
        "single outlier would distort a six-company average."
    ),
    "v_mf_benchmark": (
        "Mutual fund lens. Every metric expressed as a difference from the sector median, "
        "because a long-only fund judges a company against the index it is measured on. "
        "Positive means better than the sector middle."
    ),
    "v_equity_margin_trend": (
        "Equity research lens. Margin deltas versus a year ago, not levels, because share "
        "prices move on change rather than on absolute quality. `margin_direction` classifies "
        "the move."
    ),
    "v_pe_lbo_screen": (
        "Private equity lens. Leverage headroom, cash conversion, entry multiple, and the "
        "size of the operational gap to the sector's best operator. A large margin gap is an "
        "opportunity here, not a warning."
    ),
}

COLUMN_DESCRIPTION: dict[str, str] = {
    "ebitda": "Operating income plus depreciation and amortisation. Never reported; derived here.",
    "ebitda_ttm": "EBITDA summed over the trailing four quarters.",
    "revenue_ttm": "Revenue summed over the trailing four quarters.",
    "free_cash_flow": "Cash from operations minus capital expenditure.",
    "free_cash_flow_ttm": "Free cash flow summed over the trailing four quarters.",
    "net_debt": (
        "Total debt minus cash. NULL when debt is not reported, which means unknown, not zero."
    ),
    "net_debt_to_ebitda": (
        "Net debt divided by trailing-twelve-month EBITDA. Under 3x is comfortable, 3-5x is "
        "stretched, above 5x is distressed. NULL when EBITDA is negative, where the ratio is "
        "meaningless, or when fewer than four quarters exist."
    ),
    "fcf_conversion": "Share of trailing-twelve-month EBITDA that became free cash flow.",
    "interest_coverage": "EBITDA divided by interest expense.",
    "operating_margin": "Operating income divided by revenue.",
    "ebitda_margin": "EBITDA divided by revenue.",
    "revenue_yoy_growth": "Revenue change versus the same period a year earlier, as a fraction.",
    "operating_margin_yoy_delta": (
        "Operating margin minus its value a year earlier, in fractional percentage points. "
        "Positive means expanding."
    ),
    "gross_margin_yoy_delta": "Gross margin minus its value a year earlier.",
    "margin_direction": "expanding, compressing, stable, or insufficient_history.",
    "operating_margin_vs_sector": "This company's operating margin minus the sector median.",
    "revenue_growth_vs_sector": "This company's revenue growth minus the sector median.",
    "roe_vs_sector": "This company's return on equity minus the sector median.",
    "quarters_of_growth_last_4": "How many of the last four quarters grew year on year.",
    "debt_capacity_at_5x": (
        "Additional debt the company could carry at a conventional 5x structure. Negative "
        "means it is already past that point."
    ),
    "leverage_verdict": (
        "material_headroom, limited_headroom, no_headroom, not_financeable, or "
        "unknown_no_debt_data."
    ),
    "margin_gap_to_sector_best": (
        "How far this company's EBITDA margin sits below the best operator in its sector. The "
        "core private equity opportunity measure."
    ),
    "ebitda_uplift_if_best_in_class": (
        "Annual EBITDA this company would add if it closed that margin gap. The operational "
        "thesis expressed in currency."
    ),
    "entry_multiple": (
        "Enterprise value divided by EBITDA, the price a buyer pays per unit of earnings. "
        "NULL when EBITDA is negative."
    ),
    "period_type": "Q for a quarter, FY for a full year, TTM for trailing twelve months.",
    "period_end": "Last day of the reporting period.",
    "signal_type": (
        "headcount, hiring, layoff, guidance, m_and_a, capex_plan, buyback, "
        "management_change, or restructuring."
    ),
    "value_num": "Numeric payload of a signal where one exists, such as an employee count.",
    "coverage_note": "What this sector's universe deliberately excludes.",
    "source_url": "Filing or page the row was sourced from. Cite this.",
}

EXPOSED = list(RELATION_PURPOSE)

NOTES = [
    "Only SELECT statements are permitted. The connection has no write privileges.",
    "Use v_latest_company_metrics for cross-company comparisons. Joining raw period tables "
    "multiplies each company by every period it holds and silently mixes different dates.",
    "Money is in reporting currency units, almost always USD. Margins, growth rates and "
    "deltas are fractions, so 0.041 means 4.1 percent.",
    "A NULL in a derived metric is deliberate. It means the inputs could not support the "
    "calculation, not that the value is zero.",
    "Resolve any company named by the user with resolve_company before querying it.",
    "Every fact row carries source_url. Include it when reporting a figure.",
]
