import json
from dataclasses import dataclass, field
from typing import Any

from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import ResponseOutputMessage, ResponseOutputText

NOTICE = (
    "STUB MODEL. No language model was called. This response exists only to verify that the "
    "API, the agent loop and the MCP connection are wired together correctly. It contains no "
    "analysis and no data was queried. Set ANALYST_MODEL=bedrock with valid credentials for a "
    "real answer."
)

PLACEHOLDER: dict[str, Any] = {
    "answer": NOTICE,
    "companies_referenced": [],
    "sources": [],
    "confidence": "low",
    "data_caveats": [NOTICE],
    "out_of_scope": False,
    "stance": "no_call",
    "benchmark_relative_view": NOTICE,
    "growth_durability": NOTICE,
    "portfolio_fit": NOTICE,
    "rating": "not_rated",
    "margin_trend": NOTICE,
    "earnings_quality": NOTICE,
    "valuation_vs_peers": NOTICE,
    "what_would_change_the_call": NOTICE,
    "verdict": "no_call",
    "thesis": NOTICE,
    "leverage_assessment": NOTICE,
    "entry_valuation_view": NOTICE,
    "value_creation_estimate": NOTICE,
    "operational_levers": [],
    "exit_paths": [],
    "deal_risks": [],
    "risks": [],
}


@dataclass
class StubModel(Model):
    seen_tools: list[str] = field(default_factory=list)

    async def get_response(
        self, system_instructions, input, model_settings, tools, output_schema,
        handoffs, tracing, **kwargs,
    ) -> ModelResponse:
        self.seen_tools = [t.name for t in tools]
        fields = set(output_schema.json_schema().get("properties", {})) if output_schema else set()
        payload = {k: v for k, v in PLACEHOLDER.items() if not fields or k in fields}
        message = ResponseOutputMessage(
            id="msg_stub",
            role="assistant",
            status="completed",
            type="message",
            content=[ResponseOutputText(text=json.dumps(payload), type="output_text", annotations=[])],
        )
        return ModelResponse(
            output=[message],
            usage=Usage(requests=1, input_tokens=0, output_tokens=0, total_tokens=0),
            response_id="resp_stub",
        )

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("StubModel does not stream")
