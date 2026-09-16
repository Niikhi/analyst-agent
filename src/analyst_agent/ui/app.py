import requests
import streamlit as st

from analyst_agent.config import get_settings

API_URL = get_settings().api_url
TIMEOUT = 180

SAMPLES = {
    ("pe_analyst", "logistics"): "Which companies look like attractive buyout targets?",
    ("pe_analyst", "tech"): "If I had to take one company private, which and what is the thesis?",
    ("mutual_fund_analyst", "retail"): "Which would fit a long-term core holding versus one to avoid?",
    ("mutual_fund_analyst", "tech"): "Is this sector a good place to be putting money to work?",
    ("equity_analyst", "logistics"): "Walk me through the margin profile. Who is improving and who is under pressure?",
    ("equity_analyst", "tech"): "Is this sector a good place to be putting money to work?",
}

st.set_page_config(page_title="Analyst Agent", page_icon="analyst", layout="wide")


@st.cache_data(ttl=30)
def fetch(path: str):
    return requests.get(f"{API_URL}{path}", timeout=10).json()


def render_common(answer: dict) -> None:
    left, right = st.columns([3, 2])
    with left:
        st.markdown("### Answer")
        st.write(answer.get("answer", ""))
    with right:
        st.metric("Confidence", answer.get("confidence", "?"))
        if answer.get("out_of_scope"):
            st.warning("Flagged out of scope: not covered by the dataset.")
        companies = answer.get("companies_referenced") or []
        if companies:
            st.markdown("**Companies referenced**")
            st.write(", ".join(companies))


def render_persona_fields(persona: str, answer: dict) -> None:
    layouts = {
        "mutual_fund_analyst": [
            ("Stance", "stance"),
            ("Versus the sector median", "benchmark_relative_view"),
            ("Growth durability", "growth_durability"),
            ("Portfolio fit", "portfolio_fit"),
        ],
        "equity_analyst": [
            ("Rating", "rating"),
            ("Margin trend", "margin_trend"),
            ("Earnings quality", "earnings_quality"),
            ("Valuation versus peers", "valuation_vs_peers"),
            ("What would change the call", "what_would_change_the_call"),
        ],
        "pe_analyst": [
            ("Verdict", "verdict"),
            ("Thesis", "thesis"),
            ("Leverage", "leverage_assessment"),
            ("Entry valuation", "entry_valuation_view"),
            ("Value creation", "value_creation_estimate"),
        ],
    }
    headline_keys = {"stance", "rating", "verdict"}
    st.markdown("### Analysis")
    for label, key in layouts[persona]:
        value = answer.get(key)
        if not value:
            continue
        if key in headline_keys:
            st.markdown(f"**{label}:** `{value}`")
        else:
            st.markdown(f"**{label}**")
            st.write(value)

    for label, key in (
        ("Operational levers", "operational_levers"),
        ("Exit paths", "exit_paths"),
        ("Deal risks", "deal_risks"),
        ("Risks", "risks"),
    ):
        items = answer.get(key) or []
        if items:
            st.markdown(f"**{label}**")
            for item in items:
                st.markdown(f"- {item}")


def render_evidence(answer: dict, tool_calls: list[str], elapsed_ms: int) -> None:
    st.markdown("### Evidence")
    sources = answer.get("sources") or []
    if sources:
        st.dataframe(
            [
                {
                    "Company": s.get("company") or "",
                    "Claim": s.get("claim", ""),
                    "Period": s.get("period") or "",
                    "Source": s.get("url", ""),
                }
                for s in sources
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No sources returned. Treat any figure above with caution.")

    caveats = answer.get("data_caveats") or []
    if caveats:
        st.markdown("**Data caveats**")
        for c in caveats:
            st.markdown(f"- {c}")

    st.caption(f"MCP tools called: {' -> '.join(tool_calls) or 'none'}  |  {elapsed_ms} ms")


def render_cost(usage: dict | None) -> None:
    if not usage:
        return
    st.markdown("### Cost")
    cols = st.columns(4)
    cost = usage.get("cost_usd")
    cols[0].metric("This question", f"${cost:.4f}" if cost is not None else "rates unknown")
    cols[1].metric("Turns", usage["turns"])
    cols[2].metric(
        "Input tokens",
        f"{usage['prompt_tokens'] + usage['cache_read_tokens'] + usage['cache_write_tokens']:,}",
    )
    cols[3].metric("Output tokens", f"{usage['output_tokens']:,}")

    saved = usage.get("saved_by_caching_usd")
    if saved:
        without = usage.get("cost_without_caching_usd")
        st.caption(
            f"Prompt caching saved ${saved:.4f} "
            f"({saved / without * 100:.0f}% of ${without:.4f} uncached). "
            f"{usage['cache_read_tokens']:,} tokens served from cache."
        )
    elif not usage.get("rates_known"):
        st.caption(
            f"No published rate for {usage['model']} in the pricing table, so only token "
            "counts are shown."
        )

    with st.expander("Per-turn breakdown"):
        st.dataframe(
            [
                {
                    "Turn": t["turn"],
                    "Prompt": f"{t['prompt_tokens']:,}",
                    "Cache read": f"{t['cache_read_tokens']:,}",
                    "Cache write": f"{t['cache_write_tokens']:,}",
                    "Output": f"{t['output_tokens']:,}",
                    "Cost": f"${t['cost_usd']:.5f}" if t["cost_usd"] is not None else "-",
                }
                for t in usage["per_turn"]
            ],
            width="stretch",
            hide_index=True,
        )


st.title("Analyst Agent")

try:
    health = fetch("/health")
    personas = {p["key"]: p for p in fetch("/personas")}
except Exception as exc:
    st.error(
        f"Cannot reach the API at {API_URL}.\n\n"
        "Start it with:\n\n"
        "`uvicorn analyst_agent.api.main:app --port 8000`\n\n"
        f"({exc})"
    )
    st.stop()

with st.sidebar:
    st.header("Configuration")
    persona_key = st.selectbox(
        "Persona",
        options=list(personas),
        format_func=lambda k: personas[k]["display_name"],
    )
    sector = st.selectbox("Sector", options=health["sectors"])

    st.divider()
    chosen = personas[persona_key]
    st.caption("This persona returns")
    st.code(chosen["answer_schema"], language=None)
    st.caption("Starts from")
    st.code("\n".join(chosen["preferred_relations"]), language=None)
    st.caption("Judged on")
    st.code("\n".join(chosen["priority_metrics"][:5]), language=None)

    st.divider()
    st.caption(f"API: {API_URL}")
    st.caption(f"MCP: {health['mcp_url']}")
    st.caption(f"Model: {health['model']}")
    st.caption(f"AWS: {health['aws_profile']} / {health['aws_region']}")
    extras = []
    if health.get("prompt_caching"):
        extras.append("prompt caching")
    if health.get("thinking_budget"):
        extras.append(f"thinking {health['thinking_budget']}")
    if extras:
        st.caption(" | ".join(extras))

with st.expander("What this persona does differently", expanded=False):
    st.markdown(f"**{chosen['display_name']} works through:**")
    steps = [f"{i}. {step}" for i, step in enumerate(chosen["playbook"], 1)]
    st.markdown("\n".join(steps))

default_q = SAMPLES.get((persona_key, sector), "")
question = st.text_area("Question", value=default_q, height=90, key=f"q_{persona_key}_{sector}")
submitted = st.button("Ask", type="primary", disabled=not question.strip())

if submitted:
    with st.spinner(f"{chosen['display_name']} is querying the dataset..."):
        try:
            response = requests.post(
                f"{API_URL}/ask",
                json={"question": question, "persona": persona_key, "sector": sector},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
            st.stop()

    if response.status_code != 200:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text[:1500] or "(empty response body)"
        st.error(f"{response.status_code}")
        st.code(detail, language=None)
        st.stop()

    payload = response.json()
    answer = payload["answer"]

    st.caption(
        f"{payload['persona_name']} - {payload['sector']} - returned as "
        f"`{payload['answer_schema']}`"
    )
    render_common(answer)
    st.divider()
    render_persona_fields(persona_key, answer)
    st.divider()
    render_evidence(answer, payload["tool_calls"], payload["elapsed_ms"])
    st.divider()
    render_cost(payload.get("usage"))

    with st.expander("Raw JSON (what the API returns to another system)"):
        st.json(payload)
