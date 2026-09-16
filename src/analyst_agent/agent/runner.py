from dataclasses import dataclass

from agents import Agent, ModelSettings, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from agents.models.interface import Model

from analyst_agent.agent.outputs import BaseAnswer
from analyst_agent.agent.personas import Persona, get_persona
from analyst_agent.config import get_settings

set_tracing_disabled(True)

SECTORS = ("tech", "retail", "logistics")


@dataclass
class AnalystRequest:
    question: str
    persona: str
    sector: str

    def validated(self) -> "AnalystRequest":
        if self.sector not in SECTORS:
            raise ValueError(f"Unknown sector {self.sector!r}. Available: {list(SECTORS)}")
        get_persona(self.persona)
        if not self.question.strip():
            raise ValueError("question must not be empty")
        return self


@dataclass
class AnalystResult:
    persona: str
    sector: str
    question: str
    answer: BaseAnswer
    tool_calls: list[str]
    usage: dict | None = None


def mcp_url() -> str:
    return get_settings().resolved_mcp_url


def build_agent(persona: Persona, sector: str, model: Model | str, server: MCPServerStreamableHttp) -> Agent:
    return Agent(
        name=persona.display_name,
        instructions=persona.instructions(sector),
        model=model,
        model_settings=ModelSettings(tool_choice="auto"),
        mcp_servers=[server],
        output_type=persona.answer_type,
    )


async def run_analysis(
    request: AnalystRequest,
    model: Model | str | None = None,
    max_turns: int | None = None,
) -> AnalystResult:
    request = request.validated()
    persona = get_persona(request.persona)
    resolved_model = model if model is not None else default_model()
    turns = max_turns if max_turns is not None else get_settings().agent_max_turns

    params = MCPServerStreamableHttpParams(url=mcp_url())
    async with MCPServerStreamableHttp(params=params, cache_tools_list=True) as server:
        agent = build_agent(persona, request.sector, resolved_model, server)
        result = await Runner.run(
            agent,
            f"Sector: {request.sector}\nQuestion: {request.question}",
            max_turns=turns,
        )

    tool_calls = [
        item.raw_item.name
        for item in result.new_items
        if getattr(item, "type", None) == "tool_call_item" and hasattr(item.raw_item, "name")
    ]
    cost = getattr(resolved_model, "cost", None)
    return AnalystResult(
        persona=request.persona,
        sector=request.sector,
        question=request.question,
        answer=result.final_output,
        tool_calls=tool_calls,
        usage=cost.summary() if cost is not None else None,
    )


def default_model() -> Model:
    from analyst_agent.agent.bedrock import BedrockConverseModel

    return BedrockConverseModel.from_settings()
