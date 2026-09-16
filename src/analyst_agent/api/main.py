import time
from typing import Any, Literal

from agents.exceptions import MaxTurnsExceeded, UserError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from analyst_agent.agent.personas import PERSONA_KEYS, load_personas
from analyst_agent.agent.aws import AwsCredentialsUnavailable
from analyst_agent.agent.runner import SECTORS, AnalystRequest, mcp_url, run_analysis
from analyst_agent.config import MissingSetting, get_settings

PersonaKey = Literal["mutual_fund_analyst", "equity_analyst", "pe_analyst"]
SectorKey = Literal["tech", "retail", "logistics"]

app = FastAPI(
    title="Analyst Agent",
    version="0.1.0",
    description=(
        "One persona-configurable agent over a curated financial dataset. Any persona may be "
        "paired with any sector. The same agent serves this API and the Streamlit UI."
    ),
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, examples=["Which names look like buyout targets?"])
    persona: PersonaKey = Field(examples=["pe_analyst"])
    sector: SectorKey = Field(examples=["logistics"])


class AskResponse(BaseModel):
    persona: str
    persona_name: str
    sector: str
    question: str
    answer_schema: str = Field(description="Which output type this persona returns")
    answer: dict[str, Any] = Field(description="Persona-specific structured analysis")
    tool_calls: list[str] = Field(description="MCP tools the agent invoked, in order")
    elapsed_ms: int
    model: str


class PersonaInfo(BaseModel):
    key: str
    display_name: str
    answer_schema: str
    answer_fields: list[str]
    priority_metrics: list[str]
    preferred_relations: list[str]
    playbook: list[str]


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.bedrock_model_id,
        "aws_profile": settings.aws_profile or "<default chain>",
        "aws_region": settings.aws_region,
        "thinking_budget": settings.bedrock_thinking_budget,
        "prompt_caching": settings.bedrock_prompt_caching,
        "max_turns": settings.agent_max_turns,
        "mcp_url": mcp_url(),
        "personas": list(PERSONA_KEYS),
        "sectors": list(SECTORS),
    }


@app.get("/personas", response_model=list[PersonaInfo])
def personas() -> list[PersonaInfo]:
    return [
        PersonaInfo(
            key=p.key,
            display_name=p.display_name,
            answer_schema=p.answer_type.__name__,
            answer_fields=list(p.answer_type.model_fields),
            priority_metrics=list(p.priority_metrics),
            preferred_relations=list(p.preferred_relations),
            playbook=list(p.playbook),
        )
        for p in load_personas().values()
    ]


@app.get("/sectors")
def sectors() -> list[str]:
    return list(SECTORS)


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    persona = load_personas()[request.persona]
    started = time.perf_counter()

    try:
        result = await run_analysis(
            AnalystRequest(
                question=request.question, persona=request.persona, sector=request.sector
            )
        )
    except MissingSetting as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AwsCredentialsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MaxTurnsExceeded as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"The agent did not finish within {get_settings().agent_max_turns} tool-call "
                "turns. Raise AGENT_MAX_TURNS, or narrow the question."
            ),
        ) from exc
    except UserError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach the MCP server at {mcp_url()}. Start it with "
            f"'python -m analyst_agent.mcp_server'. ({exc})",
        ) from exc

    return AskResponse(
        persona=result.persona,
        persona_name=persona.display_name,
        sector=result.sector,
        question=result.question,
        answer_schema=type(result.answer).__name__,
        answer=result.answer.model_dump(),
        tool_calls=result.tool_calls,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        model=get_settings().bedrock_model_id,
    )
