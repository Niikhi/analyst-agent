# Analyst Agent

One configurable agent that answers financial questions as a Mutual Fund, Equity, or PE
analyst, grounded in a Postgres dataset it queries live through MCP, reachable from a REST
API and a Streamlit UI.

Any of the three personas can be paired with any of the three sectors, giving the nine
combinations the brief asks for.

```
  Streamlit :8501 ──HTTP──▶ FastAPI :8000 ──▶ AgentRunner ──MCP/HTTP──▶ MCP server :8765 ──▶ Postgres
  curl / other system ────────────┘              │                        (3 tools)
                                                 └─ persona = lens + views + playbook + output schema
```

The UI calls the REST API rather than importing the agent, so the two interfaces cannot
drift apart.

---

## Quickstart

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and a running Postgres 16 with the
`pg_trgm` extension available (ships with a standard install).

```bash
git clone <repo> && cd analyst-agent
uv sync
cp .env.example .env          # then edit it, see Configuration below
```

**1. Create the database and apply the schema**

```bash
createdb -U postgres "analyst-agent"

psql -U postgres -d "analyst-agent" -f db/schema/001_core.sql
psql -U postgres -d "analyst-agent" -f db/schema/002_views.sql
psql -U postgres -d "analyst-agent" -v ro_password="pick-a-password" -f db/schema/003_roles.sql
```

All three are idempotent, so they can be re-run. `002_views.sql` drops and rebuilds the views,
which takes their grants with them — always run `003_roles.sql` after it.

`003_roles.sql` creates `analyst_ro`, the read-only role the MCP server connects as. Put the
same password into `ANALYST_DB_URL` in `.env`.

**2. Load the data — either way works**

```bash
# Fast: restore the committed snapshot (18 companies, 288 financial rows, 378 signals)
psql -U postgres -d "analyst-agent" -f db/seed/analyst-agent-data.sql

# Or rebuild from source: pulls live from SEC EDGAR and Yahoo Finance, takes a few minutes
uv run python -m analyst_agent.ingest --sector all
```

**3. Point at a Bedrock model**

Credentials come from a named AWS profile, so an SSO login is enough — no keys in `.env`:

```bash
aws sso login --profile default
uv run python -m analyst_agent.agent.models     # lists Claude models your account has
```

Set the chosen identifier as `BEDROCK_MODEL_ID`. Prefer an inference profile (`us.anthropic.…`)
when the base model is not available on-demand in your region.

**4. Run the three processes** (separate terminals)

```bash
uv run python -m analyst_agent.mcp_server                      # MCP server  :8765
uv run uvicorn analyst_agent.api.main:app --port 8000          # REST API    :8000
uv run streamlit run src/analyst_agent/ui/app.py               # UI          :8501
```

Open http://localhost:8501, or http://localhost:8000/docs for the API.

### Configuration

All settings are read once through `src/analyst_agent/config.py`, a `pydantic-settings` model.
Nothing else in the codebase calls `os.getenv` or `load_dotenv`, so every setting has one
declared type, one default, and one place to change it.

| Variable | Purpose |
|---|---|
| `ANALYST_DB_ADMIN_URL` | Owner connection, used by the ingest pipeline only |
| `ANALYST_DB_URL` | Read-only `analyst_ro` connection, used by the MCP server |
| `SEC_USER_AGENT` | `app-name your@email.com`. EDGAR returns 403 without a contact address |
| `AWS_PROFILE` | Named profile from `~/.aws/config`. Blank uses the default chain. |
| `AWS_REGION` | Defaults to `us-east-1` |
| `BEDROCK_MODEL_ID` | Model or inference-profile id. See step 3. |
| `BEDROCK_MAX_TOKENS` | Defaults to 8192 |
| `BEDROCK_TEMPERATURE` | Blank leaves it to the model |
| `BEDROCK_THINKING_BUDGET` | Blank disables extended thinking. Minimum 1024 when set. |
| `AGENT_MAX_TURNS` | Tool-call turns before a run is abandoned. Defaults to 16. |
| `MCP_HOST` / `MCP_PORT` | MCP server bind address |
| `API_URL` | Where the UI looks for the API |

**No AWS keys are stored anywhere.** boto3 builds a session from `AWS_PROFILE`, so SSO works
directly. An expired token surfaces as a 503 telling you to run `aws sso login --profile <name>`
rather than a stack trace.

### Choosing a model

Sonnet-class or better is the right default. The agent writes SQL against a twelve-relation
schema, has to respect NULL semantics it is told about in prose, and has to produce genuinely
different analysis per persona. A small model writes plausible but wrong SQL and flattens the
persona differences, which is exactly what the brief grades.

`BEDROCK_THINKING_BUDGET` enables extended thinking where the model supports it. The tool loop
already imposes structure, so it helps most at the final synthesis step rather than during
retrieval. Note that Bedrock rejects `temperature` when thinking is enabled, so the adapter
drops it automatically.

`AGENT_MAX_TURNS` defaults to 16. A complete pass is roughly `describe_schema`,
`resolve_company`, three to five queries, then the answer; the remainder is headroom for
correcting a failed query. Exhausting it returns a 504 naming the limit rather than a partial
answer.

---

## Using it

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Which companies look like attractive buyout targets?",
       "persona":"pe_analyst","sector":"logistics"}'
```

```jsonc
{
  "persona": "pe_analyst",
  "sector": "logistics",
  "answer_schema": "PeAnswer",
  "answer": {
    "answer": "...",
    "verdict": "priority_target",
    "thesis": "...",
    "leverage_assessment": "...",
    "operational_levers": ["..."],
    "value_creation_estimate": "...",
    "exit_paths": ["..."],
    "deal_risks": ["..."],
    "companies_referenced": ["UPS"],
    "sources": [{"company":"UPS","claim":"net debt/EBITDA 2.10x","period":"2026-06-30","url":"https://www.sec.gov/..."}],
    "confidence": "high",
    "data_caveats": ["..."],
    "out_of_scope": false
  },
  "tool_calls": ["describe_schema", "resolve_company", "run_sql"],
  "elapsed_ms": 8421
}
```

| Endpoint | |
|---|---|
| `POST /ask` | question + persona + sector → structured analysis |
| `GET /personas` | each persona's output schema, metrics, views and playbook |
| `GET /health` | model in use, MCP url, available personas and sectors |
| `GET /sectors` | |

Unknown personas and sectors are `Literal` types, so an invalid value returns a 422 naming
the valid options rather than an empty result.

---

## Write-up

### Schema decisions

**Base tables hold as-filed facts only. Everything derived lives in a view.** No `ebitda`,
`net_debt`, margin, or growth column exists in `financials`. A stored derived value can drift
from its inputs: some loader path eventually writes it inconsistently and nothing catches it.
As a view expression it is correct by construction and testable. `db/schema/002_views.sql` is
where the analytical logic lives, which is also what makes the `run_sql` tool safe — the model
writes ad-hoc SQL, but EBITDA derivation, period alignment, divide-by-zero and the
meaninglessness of leverage on negative EBITDA are already handled underneath it.

**Provenance is a table, not a convention.** Every financial row carries a `source_id` into
`sources`. The `sources[]` array in the API response is populated by a join, not by the
model's memory, which is what makes "grounded" checkable rather than claimed.

**A raw landing zone sits in front of the typed tables.** `raw_filings` stores the EDGAR
payload verbatim in JSONB. When a tag mapping turns out wrong — which happened four times —
the transform is re-run rather than the data re-scraped. The agent is deliberately denied
access to this table; the payloads are megabytes and would destroy the context window.

**Periods are modelled as `period_end` + `period_type`** so quarterly, annual and TTM figures
coexist without colliding across companies with different fiscal calendars. `companies` carries
`fiscal_year_end_month` because Costco's Q1 and Target's Q1 cover different months, and any
naive "compare the latest quarter" query is wrong without that offset.

**NULL means unknown, never zero.** This is enforced rather than hoped for: `net_debt` is NULL
when debt is unreported, leverage ratios are NULL when EBITDA is negative or fewer than four
quarters exist, and `leverage_verdict` has an explicit `unknown_no_debt_data` value.

### MCP design

**Three tools, not twelve.** The first design had a semantic tool per query shape —
`get_company_financials`, `screen_companies`, `compare_to_sector` and so on. That amounts to
pre-guessing every question a reviewer might ask, and it fails the moment they ask something
else, with no fallback. The final surface is:

| Tool | |
|---|---|
| `describe_schema` | 12 relations with column types and meanings |
| `run_sql` | guarded SELECT over the views |
| `resolve_company` | name → entry, or an explicit `not_found` |

`resolve_company` stays a dedicated tool for one specific reason. Under `run_sql` alone, asking
about a company outside the dataset returns zero rows — and zero rows is *ambiguous* to a
model, which retries, then hedges, and hedging is where hallucination leaks in. A dedicated
tool returns `status: not_found` with instructions not to characterise the company. That is the
mechanism behind the brief's out-of-scope test, and it is deterministic.

**`run_sql` is guarded by Postgres privileges, not string filtering.** The connection is
`analyst_ro`: `SELECT` only, `default_transaction_read_only`, a 10s `statement_timeout`, and no
access to `raw_filings`. Regex-scanning generated SQL for "DELETE" is a filter that gets slipped
past; a missing privilege is not. Application-level checks (single statement, `SELECT`/`WITH`
only, row cap) sit on top as a fast, legible first line.

**Errors are returned as data, not raised.** mcp 2.x masks a raised exception as
`"Error executing tool run_sql"`, which tells the model nothing it can act on. `run_sql` instead
returns an `error` field carrying either the refusal reason or the Postgres message
(`column "x" does not exist  Call describe_schema to check the available columns`). A rejected
query becomes a correctable outcome, the same way `not_found` is a valid answer rather than a
failure.

**`catalog.py` is prompt engineering in a data file.** Column names and types come live from
`information_schema` so they cannot drift from the database; only the *meanings* are written by
hand. It is where `margin_gap_to_sector_best` is explained as "the core private equity
opportunity measure".

### Persona design

The brief asks that the persona change how the agent *reasons*, not how it writes. A persona
here is four things, and voice is only the first:

| Layer | |
|---|---|
| **Lens** | the analytical worldview, as prose in `agent/personas/*.yaml` |
| **Data** | which views and metrics it starts from |
| **Playbook** | ordered steps it must work through before answering |
| **Output schema** | a Pydantic type that differs per persona |

The output schema does the most work, because the model must populate the fields and the
reasoning follows:

```
MutualFundAnswer   stance, benchmark_relative_view, growth_durability, portfolio_fit
EquityAnswer       rating, margin_trend, earnings_quality, valuation_vs_peers,
                   what_would_change_the_call
PeAnswer           verdict, thesis, leverage_assessment, entry_valuation_view,
                   operational_levers, value_creation_estimate, exit_paths, deal_risks
```

Three different JSON shapes from the same question, which makes the differentiation checkable
rather than asserted. `GET /personas` exposes the field lists without running a query.

It is also structural in the database. `v_mf_benchmark` expresses every metric as a difference
from the sector median, because a long-only fund is judged against an index. `v_equity_margin_trend`
carries margin *deltas*, because share prices move on change rather than level.
`v_pe_lbo_screen` carries leverage headroom, cash conversion and `ebitda_uplift_if_best_in_class`
— a question the other two views never ask, because a large margin gap is an opportunity to a
buyout firm and a warning to a stock picker.

`docs/finance-primer.md` explains the domain behind these choices.

---

## Data sourcing and quality caveats

18 companies across three sectors, 288 financial rows (216 quarterly, 72 annual), 378 signals,
18 market snapshots.

| Data | Source |
|---|---|
| Financials | SEC EDGAR `companyfacts` XBRL API — free, no key |
| Market data & headcount | Yahoo Finance via `yfinance` |
| Signals | SEC 8-K filings via the EDGAR submissions API |

**Known caveats:**

- **`gross_profit` is only 33% populated.** Transport filers do not report it — they report one
  lump of operating expenses. Not a bug; an artifact of the industry.
- **`total_debt` is 84% populated.** Snowflake genuinely carries almost none; others tag
  borrowings in ways not yet covered.
- **Headcount is a point-in-time snapshot with no history**, so period-over-period change cannot
  be derived from it.
- **8-K signals carry the standard SEC item description**, not the filing's own headline — the
  submissions index does not expose one. Item codes are mapped to signal types; routine items
  (9.01 exhibits, 5.07 shareholder votes) are skipped.
- **Market data is one snapshot per company**, not a time series.
- **Restatements are not modelled.** A period often appears twice (original 10-Q, restated in the
  10-K); the latest filing wins and the as-filed figure is kept.
- **Fiscal calendars differ across filers**, so "the latest quarter" covers different months for
  different companies.

### Bugs the real data exposed

Worth recording, because each is a case of a formula silently producing a plausible number from
data that could not support it:

1. **Tag priority broke on the first tag returning anything.** J.B. Hunt's `Revenues` holds only
   pre-2015 periods, so it won and current revenue vanished entirely. Tags now merge per-period.
2. **Cash flow in 10-Qs is year-to-date, not quarterly.** Duration filtering caught only Q1 and
   FY. Quarterly values are now derived by differencing consecutive YTD figures. Coverage went
   from 50% to 100%.
3. **`net_debt` coalesced missing debt to zero**, turning "no debt data" into "net cash". GXO got
   a `material_headroom` buyout verdict built on an absent column.
4. **Leverage used quarterly EBITDA.** UPS read 10.38x and looked unfinanceable; against TTM it
   is 2.10x.
5. **Snowflake's entry multiple was −113x** — negative EBITDA producing a meaningless negative
   multiple, the same trap as leverage.

---

## What is verified, and what is not

**Verified end to end:** the MCP server over a real client session (three tools discovered, six
absent companies return `not_found`, eleven real names resolve including aliases, writes and
stacked statements refused with a reason); the agent loop against live Postgres through MCP;
all nine persona × sector combinations returning their own schema; the seed restoring into a
fresh database with the views computing correctly; the UI re-rendering its fields when the
persona changes.

**Not verified: the Bedrock call itself.** No AWS credentials were used at any point in
development. `agent/bedrock.py` adapts the Agents SDK `Model` interface to the Converse API via
boto3 with no LiteLLM layer, and its conversion functions *are* tested directly — tool-call
round trips produce valid user/assistant alternation, consecutive same-role messages merge as
Converse requires, Agents SDK tools become `toolConfig` entries, `reasoningContent` blocks are
skipped, and Converse content blocks become `ResponseOutputMessage` /
`ResponseFunctionToolCall` items. The untested surface is the single
`client.converse(**request)` call.

`agent/scripted.py` is a `Model` that replays a fixed sequence of tool calls and a final
payload. It is how the loop is tested without a cloud call, and it is a test fixture rather
than a runtime mode: there is no way to serve a fake answer through the API.

Converse has no native structured-output mode, so the JSON schema is appended to the system
prompt. If that proves unreliable in practice, the fallback is a `submit_analysis` tool whose
input schema *is* the answer schema — a pattern that works through any provider.

---

## What I would improve with more time

**A citation validator between the model and the response.** Every figure in the answer should
be checked against the tool results that produced it, and any unmatched number should drop
`confidence` automatically and be flagged. Right now `confidence` is the model's own judgement,
which is exactly the kind of self-report this architecture otherwise avoids. The Agents SDK's
`output_guardrail` is the natural hook, and it would turn grounding from a strong convention
into an enforced property — the same move the schema already makes for NULL handling.

Beyond that: an eval harness running all nine combinations plus the two trap questions on every
commit, with answers diffed across personas so differentiation becomes a regression test;
derived quarterly cash-flow reconciled against the annual figure to catch differencing errors;
and sector coverage widened enough that the medians are defensible — six companies is thin for a
benchmark.

---

## Layout

```
db/schema/          001_core.sql, 002_views.sql, 003_roles.sql
db/seed/            committed data snapshot
src/analyst_agent/
  ingest/           EDGAR + Yahoo pipeline
  mcp_server/       MCPServer, repository, catalog
  agent/            personas, output schemas, Bedrock adapter, runner
  api/              FastAPI
  ui/               Streamlit
docs/               finance-primer.md
```
