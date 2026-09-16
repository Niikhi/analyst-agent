import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
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
            use_container_width=True,
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

if health["model"] == "stub":
    st.warning(
        "Running with ANALYST_MODEL=stub. No language model is called and answers are "
        "placeholders that verify wiring only. Set ANALYST_MODEL=bedrock with credentials "
        "for real analysis."
    )

with st.expander("What this persona does differently", expanded=False):
    st.markdown(f"**{chosen['display_name']} works through:**")
    for i, step in enumerate(chosen["playbook"], 1):
        st.markdown(f"{i}. {step}")

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
        st.error(f"{response.status_code}: {response.json().get('detail', response.text)}")
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

    with st.expander("Raw JSON (what the API returns to another system)"):
        st.json(payload)
