import json
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

from analyst_agent.agent.aws import bedrock_runtime, wrap_credential_error
from analyst_agent.config import get_settings

JSON_ONLY = (
    "\n\nReturn your final answer as a single JSON object matching this schema exactly. "
    "Emit only the JSON, with no prose before or after it and no markdown fence.\n\n{schema}"
)


def _text_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"text": content}] if content.strip() else []
    blocks: list[dict[str, Any]] = []
    for part in content or []:
        if isinstance(part, str):
            if part.strip():
                blocks.append({"text": part})
        elif isinstance(part, dict):
            text = part.get("text") or part.get("content")
            if isinstance(text, str) and text.strip():
                blocks.append({"text": text})
    return blocks


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def to_converse_messages(model_input: str | list[Any]) -> list[dict[str, Any]]:
    if isinstance(model_input, str):
        return [{"role": "user", "content": [{"text": model_input}]}]

    messages: list[dict[str, Any]] = []

    def push(role: str, blocks: list[dict[str, Any]]) -> None:
        if not blocks:
            return
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": blocks})

    for raw in model_input:
        item = _as_dict(raw)
        kind = item.get("type")

        if kind == "function_call":
            try:
                arguments = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            push(
                "assistant",
                [
                    {
                        "toolUse": {
                            "toolUseId": item["call_id"],
                            "name": item["name"],
                            "input": arguments,
                        }
                    }
                ],
            )
        elif kind == "function_call_output":
            output = item.get("output")
            payload = output if isinstance(output, str) else json.dumps(output)
            push(
                "user",
                [
                    {
                        "toolResult": {
                            "toolUseId": item["call_id"],
                            "content": [{"text": payload}],
                            "status": "error" if item.get("is_error") else "success",
                        }
                    }
                ],
            )
        else:
            role = item.get("role", "user")
            blocks = _text_blocks(item.get("content"))
            push("assistant" if role == "assistant" else "user", blocks)

    if not messages:
        messages = [{"role": "user", "content": [{"text": "Proceed."}]}]
    if messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": [{"text": "Proceed."}]})
    return messages


def to_tool_config(tools: list[Any]) -> dict[str, Any] | None:
    specs = []
    for tool in tools:
        schema = getattr(tool, "params_json_schema", None)
        if schema is None:
            continue
        specs.append(
            {
                "toolSpec": {
                    "name": tool.name,
                    "description": (getattr(tool, "description", "") or tool.name)[:1000],
                    "inputSchema": {"json": schema},
                }
            }
        )
    return {"tools": specs} if specs else None


def from_converse_response(payload: dict[str, Any], turn: int) -> list[Any]:
    content = payload.get("output", {}).get("message", {}).get("content", [])
    items: list[Any] = []
    texts: list[str] = []

    for index, block in enumerate(content):
        if "text" in block:
            texts.append(block["text"])
        elif "reasoningContent" in block:
            continue
        elif "toolUse" in block:
            use = block["toolUse"]
            items.append(
                ResponseFunctionToolCall(
                    id=f"fc_{turn}_{index}",
                    call_id=use["toolUseId"],
                    name=use["name"],
                    arguments=json.dumps(use.get("input", {})),
                    type="function_call",
                )
            )

    if texts:
        items.insert(
            0,
            ResponseOutputMessage(
                id=f"msg_{turn}",
                role="assistant",
                status="completed",
                type="message",
                content=[
                    ResponseOutputText(text="".join(texts), type="output_text", annotations=[])
                ],
            ),
        )
    return items


@dataclass
class BedrockConverseModel(Model):
    model_id: str
    max_tokens: int = 8192
    temperature: float | None = None
    thinking_budget: int | None = None
    _client: Any = field(default=None, repr=False)
    _turn: int = field(default=0, repr=False)

    @classmethod
    def from_settings(cls) -> "BedrockConverseModel":
        settings = get_settings()
        settings.require("bedrock_model_id")
        return cls(
            model_id=settings.bedrock_model_id,
            max_tokens=settings.bedrock_max_tokens,
            temperature=settings.bedrock_temperature,
            thinking_budget=settings.bedrock_thinking_budget,
        )

    def client(self) -> Any:
        if self._client is None:
            self._client = bedrock_runtime()
        return self._client

    def _system(self, instructions: str | None, output_schema: Any) -> list[dict[str, str]]:
        text = instructions or ""
        if output_schema is not None and not output_schema.is_plain_text():
            schema = json.dumps(output_schema.json_schema(), indent=2)
            text += JSON_ONLY.format(schema=schema)
        return [{"text": text}] if text.strip() else []

    def _inference_config(self, model_settings: Any) -> dict[str, Any]:
        config: dict[str, Any] = {"maxTokens": self.max_tokens}
        if self.thinking_budget is not None:
            return config
        temperature = getattr(model_settings, "temperature", None)
        if temperature is None:
            temperature = self.temperature
        if temperature is not None:
            config["temperature"] = temperature
        return config

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
        self._turn += 1

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": to_converse_messages(input),
            "inferenceConfig": self._inference_config(model_settings),
        }
        system = self._system(system_instructions, output_schema)
        if system:
            request["system"] = system

        tool_config = to_tool_config(tools)
        if tool_config:
            request["toolConfig"] = tool_config

        if self.thinking_budget is not None:
            request["additionalModelRequestFields"] = {
                "thinking": {"type": "enabled", "budget_tokens": self.thinking_budget}
            }

        try:
            payload = self.client().converse(**request)
        except Exception as exc:
            raise wrap_credential_error(exc) from exc

        raw_usage = payload.get("usage", {})
        usage = Usage(
            requests=1,
            input_tokens=raw_usage.get("inputTokens", 0),
            output_tokens=raw_usage.get("outputTokens", 0),
            total_tokens=raw_usage.get("totalTokens", 0),
        )
        return ModelResponse(
            output=from_converse_response(payload, self._turn),
            usage=usage,
            response_id=payload.get("ResponseMetadata", {}).get("RequestId"),
        )

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError(
            "Streaming is not implemented. Use Runner.run rather than Runner.run_streamed."
        )
