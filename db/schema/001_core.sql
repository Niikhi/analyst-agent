CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE sources (
    source_id     BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url           TEXT        NOT NULL,
    publisher     TEXT,
    doc_type      TEXT        NOT NULL,
    published_at  DATE,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes         TEXT,
    UNIQUE (url, doc_type)
);

CREATE TABLE raw_filings (
    raw_id      BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cik         TEXT        NOT NULL,
    endpoint    TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sectors (
    sector_id      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug           TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL,
    coverage_note  TEXT NOT NULL
);

CREATE TABLE companies (
    company_id             BIGINT   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sector_id              SMALLINT NOT NULL REFERENCES sectors(sector_id),
    name                   TEXT     NOT NULL,
    ticker                 TEXT     UNIQUE,
    cik                    TEXT     UNIQUE,
    exchange               TEXT,
    country                TEXT     NOT NULL DEFAULT 'US',
    reporting_currency     CHAR(3)  NOT NULL DEFAULT 'USD',
    fiscal_year_end_month  SMALLINT CHECK (fiscal_year_end_month BETWEEN 1 AND 12),
    business_description   TEXT,
    source_id              BIGINT   REFERENCES sources(source_id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE company_aliases (
    alias_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id  BIGINT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    alias       TEXT   NOT NULL,
    UNIQUE (company_id, alias)
);

CREATE TABLE financials (
    financial_id              BIGINT   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id                BIGINT   NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    period_end                DATE     NOT NULL,
    period_type               TEXT     NOT NULL CHECK (period_type IN ('Q','FY','TTM')),
    fiscal_year               SMALLINT,
    fiscal_period             TEXT,
    currency                  CHAR(3)  NOT NULL DEFAULT 'USD',

    revenue                   NUMERIC(20,2),
    cost_of_revenue           NUMERIC(20,2),
    gross_profit              NUMERIC(20,2),
    operating_expenses        NUMERIC(20,2),
    operating_income          NUMERIC(20,2),
    depreciation_amortization NUMERIC(20,2),
    interest_expense          NUMERIC(20,2),
    net_income                NUMERIC(20,2),
    eps_diluted               NUMERIC(12,4),
    shares_diluted            NUMERIC(20,2),

    cash_from_operations      NUMERIC(20,2),
    capital_expenditure       NUMERIC(20,2),

    cash_and_equivalents      NUMERIC(20,2),
    inventory                 NUMERIC(20,2),
    total_assets              NUMERIC(20,2),
    total_debt                NUMERIC(20,2),
    total_equity              NUMERIC(20,2),

    form_type                 TEXT,
    filed_at                  DATE,
    source_id                 BIGINT REFERENCES sources(source_id),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (company_id, period_end, period_type)
);

CREATE TABLE market_data (
    market_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id          BIGINT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    as_of               DATE   NOT NULL,
    price               NUMERIC(16,4),
    market_cap          NUMERIC(20,2),
    enterprise_value    NUMERIC(20,2),
    shares_outstanding  NUMERIC(20,2),
    pe_ratio            NUMERIC(12,4),
    ev_to_ebitda        NUMERIC(12,4),
    ev_to_sales         NUMERIC(12,4),
    dividend_yield      NUMERIC(10,6),
    beta                NUMERIC(10,4),
    source_id           BIGINT REFERENCES sources(source_id),
    UNIQUE (company_id, as_of)
);

CREATE TABLE signals (
    signal_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    event_date   DATE   NOT NULL,
    signal_type  TEXT   NOT NULL CHECK (signal_type IN (
                     'headcount','hiring','layoff','guidance','m_and_a',
                     'capex_plan','buyback','management_change','restructuring')),
    headline     TEXT   NOT NULL,
    body         TEXT,
    value_num    NUMERIC(20,2),
    value_unit   TEXT,
    direction    TEXT CHECK (direction IN ('positive','negative','neutral')),
    source_id    BIGINT NOT NULL REFERENCES sources(source_id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_companies_sector    ON companies (sector_id);
CREATE INDEX idx_companies_name_trgm ON companies USING gin (name gin_trgm_ops);
CREATE INDEX idx_aliases_trgm        ON company_aliases USING gin (alias gin_trgm_ops);

CREATE INDEX idx_financials_company_period ON financials (company_id, period_end DESC);
CREATE INDEX idx_financials_period_type    ON financials (period_type, period_end DESC);

CREATE INDEX idx_market_company_asof ON market_data (company_id, as_of DESC);

CREATE INDEX idx_signals_company_date ON signals (company_id, event_date DESC);
CREATE INDEX idx_signals_type         ON signals (signal_type, event_date DESC);

CREATE INDEX idx_raw_filings_cik      ON raw_filings (cik, fetched_at DESC);
