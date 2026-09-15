DROP VIEW IF EXISTS
    v_pe_lbo_screen,
    v_equity_margin_trend,
    v_mf_benchmark,
    v_company_coverage,
    v_sector_metrics,
    v_latest_company_metrics,
    v_company_metrics,
    v_financials_enriched
CASCADE;

CREATE OR REPLACE VIEW v_financials_enriched AS
SELECT
    f.financial_id,
    f.company_id,
    c.name            AS company_name,
    c.ticker,
    s.slug            AS sector,
    f.period_end,
    f.period_type,
    f.fiscal_year,
    f.fiscal_period,
    f.currency,

    f.revenue,
    f.cost_of_revenue,
    f.gross_profit,
    f.operating_expenses,
    f.operating_income,
    f.depreciation_amortization,
    f.interest_expense,
    f.net_income,
    f.eps_diluted,
    f.shares_diluted,
    f.cash_from_operations,
    f.capital_expenditure,
    f.cash_and_equivalents,
    f.inventory,
    f.total_assets,
    f.total_debt,
    f.total_equity,

    f.operating_income + COALESCE(f.depreciation_amortization, 0)  AS ebitda,

    f.cash_from_operations - COALESCE(f.capital_expenditure, 0)    AS free_cash_flow,

    CASE WHEN f.total_debt IS NOT NULL
         THEN f.total_debt - COALESCE(f.cash_and_equivalents, 0) END AS net_debt,

    f.form_type,
    f.filed_at,
    f.source_id,
    src.url        AS source_url,
    src.publisher  AS source_publisher,
    src.doc_type   AS source_doc_type,
    src.retrieved_at
FROM financials f
JOIN companies c ON c.company_id = f.company_id
JOIN sectors   s ON s.sector_id  = c.sector_id
LEFT JOIN sources src ON src.source_id = f.source_id;

CREATE OR REPLACE VIEW v_company_metrics AS
WITH ratios AS (
    SELECT
        e.*,
        e.gross_profit        / NULLIF(e.revenue, 0)       AS gross_margin,
        e.operating_income    / NULLIF(e.revenue, 0)       AS operating_margin,
        e.ebitda              / NULLIF(e.revenue, 0)       AS ebitda_margin,
        e.net_income          / NULLIF(e.revenue, 0)       AS net_margin,
        e.free_cash_flow      / NULLIF(e.revenue, 0)       AS fcf_margin,
        e.capital_expenditure / NULLIF(e.revenue, 0)       AS capex_intensity,
        e.net_income          / NULLIF(e.total_equity, 0)  AS return_on_equity,
        e.inventory           / NULLIF(e.revenue, 0)       AS inventory_intensity,

        CASE WHEN e.interest_expense > 0 AND e.ebitda > 0
             THEN e.ebitda / e.interest_expense END              AS interest_coverage
    FROM v_financials_enriched e
),
windowed AS (
    SELECT
        r.*,
        SUM(r.ebitda)          OVER w4 AS ebitda_ttm,
        SUM(r.revenue)         OVER w4 AS revenue_ttm,
        SUM(r.free_cash_flow)  OVER w4 AS free_cash_flow_ttm,
        COUNT(r.ebitda)        OVER w4 AS ttm_quarter_count,
        CASE r.period_type
            WHEN 'Q'  THEN r.revenue / NULLIF(LAG(r.revenue, 4) OVER w, 0) - 1
            WHEN 'FY' THEN r.revenue / NULLIF(LAG(r.revenue, 1) OVER w, 0) - 1
        END AS revenue_yoy_growth,
        CASE r.period_type
            WHEN 'Q'  THEN r.ebitda / NULLIF(LAG(r.ebitda, 4) OVER w, 0) - 1
            WHEN 'FY' THEN r.ebitda / NULLIF(LAG(r.ebitda, 1) OVER w, 0) - 1
        END AS ebitda_yoy_growth,
        CASE r.period_type
            WHEN 'Q'  THEN r.operating_margin - LAG(r.operating_margin, 4) OVER w
            WHEN 'FY' THEN r.operating_margin - LAG(r.operating_margin, 1) OVER w
        END AS operating_margin_yoy_delta,
        CASE r.period_type
            WHEN 'Q'  THEN r.gross_margin - LAG(r.gross_margin, 4) OVER w
            WHEN 'FY' THEN r.gross_margin - LAG(r.gross_margin, 1) OVER w
        END AS gross_margin_yoy_delta
    FROM ratios r
    WINDOW
        w  AS (PARTITION BY r.company_id, r.period_type ORDER BY r.period_end),
        w4 AS (PARTITION BY r.company_id, r.period_type ORDER BY r.period_end
               ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)
)
SELECT
    w.*,
    CASE WHEN w.ttm_quarter_count = 4 AND w.ebitda_ttm > 0
         THEN w.net_debt / w.ebitda_ttm END          AS net_debt_to_ebitda,
    CASE WHEN w.ttm_quarter_count = 4 AND w.ebitda_ttm > 0
         THEN w.total_debt / w.ebitda_ttm END        AS gross_debt_to_ebitda,
    CASE WHEN w.ttm_quarter_count = 4 AND w.ebitda_ttm > 0
         THEN w.free_cash_flow_ttm / w.ebitda_ttm END AS fcf_conversion
FROM windowed w;

CREATE OR REPLACE VIEW v_latest_company_metrics AS
SELECT DISTINCT ON (company_id) *
FROM v_company_metrics
WHERE period_type = 'Q'
ORDER BY company_id, period_end DESC;

CREATE OR REPLACE VIEW v_sector_metrics AS
SELECT
    sector,
    COUNT(*)                                                                  AS company_count,
    MAX(period_end)                                                           AS latest_period_end,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY gross_margin)::numeric                 AS median_gross_margin,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY operating_margin)::numeric             AS median_operating_margin,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY ebitda_margin)::numeric                AS median_ebitda_margin,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY net_margin)::numeric                   AS median_net_margin,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY revenue_yoy_growth)::numeric           AS median_revenue_yoy_growth,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY net_debt_to_ebitda)::numeric           AS median_net_debt_to_ebitda,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY fcf_conversion)::numeric               AS median_fcf_conversion,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY return_on_equity)::numeric             AS median_return_on_equity,
    MAX(ebitda_margin)                                                        AS best_ebitda_margin,
    MAX(operating_margin)                                                     AS best_operating_margin
FROM v_latest_company_metrics
GROUP BY sector;

CREATE OR REPLACE VIEW v_company_coverage AS
SELECT
    c.company_id,
    c.name,
    c.ticker,
    s.slug AS sector,
    COUNT(DISTINCT f.financial_id)                                    AS financial_period_count,
    MIN(f.period_end)                                                 AS earliest_period_end,
    MAX(f.period_end)                                                 AS latest_period_end,
    COUNT(DISTINCT sg.signal_id)                                      AS signal_count,
    MAX(sg.event_date)                                                AS latest_signal_date,
    EXISTS (SELECT 1 FROM market_data m WHERE m.company_id = c.company_id) AS has_market_data
FROM companies c
JOIN sectors s        ON s.sector_id = c.sector_id
LEFT JOIN financials f ON f.company_id = c.company_id AND f.period_type = 'Q'
LEFT JOIN signals sg   ON sg.company_id = c.company_id
GROUP BY c.company_id, c.name, c.ticker, s.slug;

CREATE OR REPLACE VIEW v_mf_benchmark AS
SELECT
    l.company_id,
    l.company_name,
    l.ticker,
    l.sector,
    l.period_end,

    l.operating_margin,
    sm.median_operating_margin,
    l.operating_margin      - sm.median_operating_margin      AS operating_margin_vs_sector,

    l.revenue_yoy_growth,
    sm.median_revenue_yoy_growth,
    l.revenue_yoy_growth    - sm.median_revenue_yoy_growth    AS revenue_growth_vs_sector,

    l.return_on_equity,
    sm.median_return_on_equity,
    l.return_on_equity      - sm.median_return_on_equity      AS roe_vs_sector,

    (SELECT COUNT(*) FROM v_company_metrics h
      WHERE h.company_id = l.company_id
        AND h.period_type = 'Q'
        AND h.revenue_yoy_growth > 0
        AND h.period_end > l.period_end - INTERVAL '1 year')  AS quarters_of_growth_last_4,

    md.pe_ratio,
    md.dividend_yield,
    md.beta,
    md.market_cap,
    l.source_url
FROM v_latest_company_metrics l
JOIN v_sector_metrics sm ON sm.sector = l.sector
LEFT JOIN LATERAL (
    SELECT * FROM market_data m
    WHERE m.company_id = l.company_id
    ORDER BY m.as_of DESC
    LIMIT 1
) md ON TRUE;

CREATE OR REPLACE VIEW v_equity_margin_trend AS
SELECT
    l.company_id,
    l.company_name,
    l.ticker,
    l.sector,
    l.period_end,

    l.revenue,
    l.revenue_yoy_growth,

    l.gross_margin,
    l.gross_margin_yoy_delta,
    l.operating_margin,
    l.operating_margin_yoy_delta,
    l.ebitda_margin,
    l.net_margin,

    CASE
        WHEN l.operating_margin_yoy_delta >  0.005 THEN 'expanding'
        WHEN l.operating_margin_yoy_delta < -0.005 THEN 'compressing'
        WHEN l.operating_margin_yoy_delta IS NULL  THEN 'insufficient_history'
        ELSE 'stable'
    END                                                        AS margin_direction,

    l.eps_diluted,
    l.operating_margin - sm.median_operating_margin            AS operating_margin_vs_peers,

    md.pe_ratio,
    md.ev_to_ebitda,
    md.ev_to_sales,
    l.source_url
FROM v_latest_company_metrics l
JOIN v_sector_metrics sm ON sm.sector = l.sector
LEFT JOIN LATERAL (
    SELECT * FROM market_data m
    WHERE m.company_id = l.company_id
    ORDER BY m.as_of DESC
    LIMIT 1
) md ON TRUE;

CREATE OR REPLACE VIEW v_pe_lbo_screen AS
SELECT
    l.company_id,
    l.company_name,
    l.ticker,
    l.sector,
    l.period_end,

    l.ebitda,
    l.ebitda_ttm,
    l.ebitda_margin,
    l.free_cash_flow,
    l.free_cash_flow_ttm,
    l.fcf_conversion,
    l.net_debt,
    l.net_debt_to_ebitda,
    l.interest_coverage,
    l.capex_intensity,

    CASE WHEN l.ebitda_ttm > 0 AND l.net_debt IS NOT NULL
         THEN (5.0 * l.ebitda_ttm) - l.net_debt END                AS debt_capacity_at_5x,
    CASE
        WHEN l.net_debt IS NULL                    THEN 'unknown_no_debt_data'
        WHEN l.ebitda_ttm IS NULL                  THEN 'insufficient_history'
        WHEN l.ebitda_ttm <= 0                     THEN 'not_financeable'
        WHEN l.net_debt_to_ebitda >= 5.0           THEN 'no_headroom'
        WHEN l.net_debt_to_ebitda >= 3.0           THEN 'limited_headroom'
        ELSE 'material_headroom'
    END                                                            AS leverage_verdict,

    sm.best_ebitda_margin,
    sm.best_ebitda_margin - l.ebitda_margin                        AS margin_gap_to_sector_best,
    CASE WHEN l.revenue > 0
         THEN (sm.best_ebitda_margin - l.ebitda_margin) * COALESCE(l.revenue_ttm, l.revenue)
    END                                                            AS ebitda_uplift_if_best_in_class,

    md.enterprise_value,
    md.ev_to_ebitda                                                AS entry_multiple,
    sm.median_ebitda_margin,
    md.market_cap,
    l.source_url
FROM v_latest_company_metrics l
JOIN v_sector_metrics sm ON sm.sector = l.sector
LEFT JOIN LATERAL (
    SELECT * FROM market_data m
    WHERE m.company_id = l.company_id
    ORDER BY m.as_of DESC
    LIMIT 1
) md ON TRUE;
