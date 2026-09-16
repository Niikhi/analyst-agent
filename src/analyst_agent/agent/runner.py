import os
from dataclasses import dataclass

from agents import Agent, ModelSettings, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from agents.models.interface import Model
from dotenv import load_dotenv

from analyst_agent.agent.outputs import BaseAnswer
from analyst_agent.agent.personas import Persona, get_persona

load_dotenv()
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


def mcp_url() -> str:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = os.getenv("MCP_PORT", "8765")
    return os.getenv("MCP_URL", f"http://{host}:{port}/mcp")


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
    max_turns: int = 12,
) -> AnalystResult:
    request = request.validated()
    persona = get_persona(request.persona)
    resolved_model = model if model is not None else default_model()

    params = MCPServerStreamableHttpParams(url=mcp_url())
    async with MCPServerStreamableHttp(params=params, cache_tools_list=True) as server:
        agent = build_agent(persona, request.sector, resolved_model, server)
        result = await Runner.run(
            agent,
            f"Sector: {request.sector}\nQuestion: {request.question}",
            max_turns=max_turns,
        )

    tool_calls = [
        item.raw_item.name
        for item in result.new_items
        if getattr(item, "type", None) == "tool_call_item" and hasattr(item.raw_item, "name")
    ]
    return AnalystResult(
        persona=request.persona,
        sector=request.sector,
        question=request.question,
        answer=result.final_output,
        tool_calls=tool_calls,
    )


class ModelNotConfigured(RuntimeError):
    pass


def default_model() -> Model:
    backend = os.getenv("ANALYST_MODEL", "bedrock").lower()

    if backend == "stub":
        from analyst_agent.agent.stub import StubModel

        return StubModel()

    if backend != "bedrock":
        raise ModelNotConfigured(f"Unknown ANALYST_MODEL={backend!r}. Use 'bedrock' or 'stub'.")

    from analyst_agent.agent.bedrock import BedrockConverseModel

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ModelNotConfigured(
            "BEDROCK_MODEL_ID is not set. Set it in .env alongside valid AWS credentials, "
            "or set ANALYST_MODEL=stub to exercise the transport without a model."
        )
    return BedrockConverseModel(model_id=model_id, region=os.getenv("AWS_REGION", "us-east-1"))
