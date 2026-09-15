SELECT format(
    CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_ro')
         THEN 'ALTER ROLE analyst_ro LOGIN PASSWORD %L'
         ELSE 'CREATE ROLE analyst_ro LOGIN PASSWORD %L'
    END, :'ro_password')
\gexec

GRANT CONNECT ON DATABASE "analyst-agent" TO analyst_ro;
GRANT USAGE   ON SCHEMA public    TO analyst_ro;

GRANT SELECT ON
    sectors, companies, company_aliases,
    financials, market_data, signals, sources
TO analyst_ro;

GRANT SELECT ON
    v_financials_enriched,
    v_company_metrics,
    v_latest_company_metrics,
    v_sector_metrics,
    v_company_coverage,
    v_mf_benchmark,
    v_equity_margin_trend,
    v_pe_lbo_screen
TO analyst_ro;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM analyst_ro;

ALTER ROLE analyst_ro SET default_transaction_read_only = on;

ALTER ROLE analyst_ro SET statement_timeout = '10s';
