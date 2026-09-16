import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ScriptedModel(Model):
    turns: list[ToolCall | dict[str, Any] | Callable[[list[Any]], dict[str, Any]]]
    seen_tools: list[str] = field(default_factory=list)
    seen_instructions: list[str] = field(default_factory=list)
    calls_made: list[str] = field(default_factory=list)
    _turn: int = 0

    async def get_response(
        self,
        system_instructions,
        input,
        model_settings,
        tools,
        output_schema,
        handoffs,
        tracing,
        **kwargs,
    ) -> ModelResponse:
        if not self.seen_tools:
            self.seen_tools = [t.name for t in tools]
        if system_instructions:
            self.seen_instructions.append(system_instructions)

        step = self.turns[min(self._turn, len(self.turns) - 1)]
        self._turn += 1
        usage = Usage(requests=1, input_tokens=0, output_tokens=0, total_tokens=0)

        if isinstance(step, ToolCall):
            self.calls_made.append(step.name)
            call = ResponseFunctionToolCall(
                id=f"fc_{self._turn}",
                call_id=f"call_{self._turn}",
                name=step.name,
                arguments=json.dumps(step.arguments),
                type="function_call",
            )
            return ModelResponse(output=[call], usage=usage, response_id=f"resp_{self._turn}")

        payload = step(input) if callable(step) else step
        message = ResponseOutputMessage(
            id=f"msg_{self._turn}",
            role="assistant",
            status="completed",
            type="message",
            content=[ResponseOutputText(text=json.dumps(payload), type="output_text", annotations=[])],
        )
        return ModelResponse(output=[message], usage=usage, response_id=f"resp_{self._turn}")

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("ScriptedModel does not stream")
