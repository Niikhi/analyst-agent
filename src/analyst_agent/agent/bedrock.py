import asyncio
import json
import logging
import threading
import time
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function as ToolCallFunction
from openai.types.completion_usage import CompletionUsage

from analyst_agent.agent.aws import as_credential_error
from analyst_agent.agent.pricing import RunCost, TurnUsage
from analyst_agent.config import get_settings

logger = logging.getLogger(__name__)

CACHE_POINT = {"cachePoint": {"type": "default"}}

FINISH_REASON = {
    "tool_use": "tool_calls",
    "max_tokens": "length",
    "stop_sequence": "stop",
    "end_turn": "stop",
    "content_filtered": "content_filter",
}

RETRYABLE = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
}

SCHEMA_INSTRUCTION = """

## Final answer format

Every message you send is either a tool call or your final answer.

When you have gathered enough data, your final message must be exactly one JSON object
matching this schema and nothing else. Populate every field.

{schema}
"""


class BedrockTruncated(RuntimeError):
    pass


def extract_json(text: str) -> str:
    if not text:
        return text
    body = text.strip()
    if "```" in body:
        for chunk in body.split("```")[1::2]:
            candidate = chunk.lstrip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    start = body.find("{")
    if start == -1:
        return body
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(body)):
        char = body[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return body[start : index + 1]
    return body


def system_blocks(messages: list[dict[str, Any]], cache: bool) -> list[dict[str, Any]] | None:
    parts: list[str] = []
    for message in messages:
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str) and content:
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
    if not any(parts):
        return None
    blocks: list[dict[str, Any]] = [{"text": "\n\n".join(p for p in parts if p)}]
    if cache:
        blocks.append(CACHE_POINT)
    return blocks


def to_converse_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content")

        if role == "system":
            continue

        if role == "tool":
            block = {
                "toolResult": {
                    "toolUseId": message.get("tool_call_id"),
                    "content": [
                        {"text": content if isinstance(content, str) else json.dumps(content)}
                    ],
                }
            }
            if (
                converted
                and converted[-1]["role"] == "user"
                and all("toolResult" in b for b in converted[-1]["content"])
            ):
                converted[-1]["content"].append(block)
            else:
                converted.append({"role": "user", "content": [block]})
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"text": str(content)})
            for call in message.get("tool_calls") or []:
                function = call.get("function", {})
                raw_args = function.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}
                blocks.append(
                    {
                        "toolUse": {
                            "toolUseId": call.get("id"),
                            "name": function.get("name"),
                            "input": arguments,
                        }
                    }
                )
            if blocks:
                converted.append({"role": "assistant", "content": blocks})
            continue

        if isinstance(content, str):
            blocks = [{"text": content}] if content else []
        elif isinstance(content, list):
            blocks = [
                {"text": b.get("text", "")}
                for b in content
                if isinstance(b, dict) and b.get("text")
            ]
        else:
            blocks = [{"text": str(content)}] if content else []

        if blocks:
            converted.append({"role": "user", "content": blocks})

    if not converted:
        converted = [{"role": "user", "content": [{"text": "Proceed."}]}]
    if converted[0]["role"] != "user":
        converted.insert(0, {"role": "user", "content": [{"text": "Proceed."}]})
    return converted


def flatten_tool_blocks(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    changed = False
    for message in messages:
        rebuilt: list[dict[str, Any]] = []
        for block in message.get("content") or []:
            use = block.get("toolUse")
            result = block.get("toolResult")
            if isinstance(use, dict):
                changed = True
                rebuilt.append({"text": f"[called {use.get('name')} with "
                                        f"{json.dumps(use.get('input'), default=str)}]"})
            elif isinstance(result, dict):
                changed = True
                texts = [
                    c.get("text", "") for c in result.get("content") or [] if isinstance(c, dict)
                ]
                rebuilt.append({"text": "[tool result]\n" + "\n".join(texts)})
            else:
                rebuilt.append(block)
        if rebuilt:
            out.append({**message, "content": rebuilt})
    return out if changed else messages


def to_tool_config(tools: list[dict[str, Any]] | None, cache: bool) -> dict[str, Any] | None:
    if not tools:
        return None
    specs: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function", tool)
        name = function.get("name")
        if not name:
            continue
        specs.append(
            {
                "toolSpec": {
                    "name": name,
                    "description": (function.get("description") or name)[:1000],
                    "inputSchema": {"json": function.get("parameters") or {"type": "object"}},
                }
            }
        )
    if not specs:
        return None
    if cache:
        specs.append(CACHE_POINT)
    return {"tools": specs}


def schema_from_response_format(response_format: Any) -> dict[str, Any] | None:
    if not isinstance(response_format, dict):
        return None
    if response_format.get("type") != "json_schema":
        return None
    return (response_format.get("json_schema") or {}).get("schema")


class _Completions:
    def __init__(self, adapter: "BedrockChatAdapter") -> None:
        self.adapter = adapter

    async def create(self, **kwargs: Any) -> ChatCompletion:
        from openai._types import NotGiven, Omit

        clean = {
            key: value
            for key, value in kwargs.items()
            if value is not None and not isinstance(value, (NotGiven, Omit))
        }
        return await self.adapter.complete(clean)


class _Chat:
    def __init__(self, adapter: "BedrockChatAdapter") -> None:
        self.completions = _Completions(adapter)


class BedrockChatAdapter:
    _clients: dict[str, Any] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        model_id: str,
        region: str,
        profile: str | None = None,
        max_tokens: int = 8192,
        temperature: float | None = None,
        thinking_budget: int | None = None,
        prompt_caching: bool = True,
        max_attempts: int = 5,
    ) -> None:
        self.model_id = model_id
        self.region = region
        self.profile = profile
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.thinking_budget = thinking_budget
        self.prompt_caching = prompt_caching
        self.max_attempts = max_attempts

        self.cost = RunCost(model_id=model_id)
        self.last_text: str | None = None
        self.last_stop_reason: str | None = None
        self._turn = 0

        self.base_url = f"https://bedrock-runtime.{region}.amazonaws.com"
        self.api_key = "bedrock-adapter"
        self.chat = _Chat(self)

    @classmethod
    def from_settings(cls) -> "BedrockChatAdapter":
        settings = get_settings()
        settings.require("bedrock_model_id")
        return cls(
            model_id=settings.bedrock_model_id,
            region=settings.aws_region,
            profile=settings.aws_profile,
            max_tokens=settings.bedrock_max_tokens,
            temperature=settings.bedrock_temperature,
            thinking_budget=settings.bedrock_thinking_budget,
            prompt_caching=settings.bedrock_prompt_caching,
        )

    def client(self) -> Any:
        key = f"{self.profile or 'default'}:{self.region}"
        existing = self._clients.get(key)
        if existing is not None:
            return existing
        with self._lock:
            existing = self._clients.get(key)
            if existing is None:
                session = boto3.Session(profile_name=self.profile, region_name=self.region)
                existing = session.client(
                    "bedrock-runtime",
                    config=BotoConfig(
                        max_pool_connections=50, retries={"max_attempts": 1, "mode": "standard"}
                    ),
                )
                self._clients[key] = existing
        return existing

    def build_request(self, params: dict[str, Any]) -> dict[str, Any]:
        messages = params.get("messages") or []
        schema = schema_from_response_format(params.get("response_format"))

        system = system_blocks(messages, self.prompt_caching) or []
        if schema is not None:
            instruction = SCHEMA_INSTRUCTION.format(schema=json.dumps(schema, indent=2))
            if system and "text" in system[0]:
                system[0]["text"] += instruction
            else:
                system = [{"text": instruction}]
                if self.prompt_caching:
                    system.append(CACHE_POINT)

        converse_messages = to_converse_messages(messages)
        tool_config = to_tool_config(params.get("tools"), self.prompt_caching)
        if tool_config is None:
            converse_messages = flatten_tool_blocks(converse_messages)
        if self.prompt_caching and converse_messages:
            converse_messages[-1]["content"].append(CACHE_POINT)

        inference: dict[str, Any] = {"maxTokens": self.max_tokens}
        if self.thinking_budget is None:
            temperature = params.get("temperature", self.temperature)
            if temperature is not None:
                inference["temperature"] = float(temperature)

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": converse_messages,
            "inferenceConfig": inference,
        }
        if system:
            request["system"] = system
        if tool_config:
            request["toolConfig"] = tool_config
        if self.thinking_budget is not None:
            request["additionalModelRequestFields"] = {
                "thinking": {"type": "enabled", "budget_tokens": self.thinking_budget}
            }
        return request

    async def _converse(self, request: dict[str, Any]) -> dict[str, Any]:
        delay = 1.0
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await asyncio.to_thread(self.client().converse, **request)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in RETRYABLE and attempt < self.max_attempts:
                    logger.warning(
                        "Bedrock %s on attempt %d/%d, retrying in %.1fs",
                        code, attempt, self.max_attempts, delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 20.0)
                    continue
                raise as_credential_error(exc) from exc
            except Exception as exc:
                raise as_credential_error(exc) from exc
        raise RuntimeError("unreachable")

    def record_usage(self, payload: dict[str, Any]) -> CompletionUsage:
        raw = payload.get("usage") or {}
        turn = TurnUsage(
            turn=self._turn,
            prompt_tokens=raw.get("inputTokens", 0),
            output_tokens=raw.get("outputTokens", 0),
            cache_read_tokens=raw.get("cacheReadInputTokens", 0),
            cache_write_tokens=(
                raw.get("cacheWriteInputTokens", 0) or raw.get("cacheCreationInputTokens", 0)
            ),
        )
        self.cost.turns.append(turn)
        return CompletionUsage(
            prompt_tokens=turn.billed_input_tokens,
            completion_tokens=turn.output_tokens,
            total_tokens=turn.billed_input_tokens + turn.output_tokens,
        )

    async def complete(self, params: dict[str, Any]) -> ChatCompletion:
        self._turn += 1
        payload = await self._converse(self.build_request(params))

        stop_reason = payload.get("stopReason", "end_turn")
        self.last_stop_reason = stop_reason
        finish_reason = FINISH_REASON.get(stop_reason, "stop")
        usage = self.record_usage(payload)

        texts: list[str] = []
        tool_calls: list[ChatCompletionMessageToolCall] = []
        for block in payload.get("output", {}).get("message", {}).get("content", []):
            if "text" in block:
                texts.append(block["text"])
            elif "toolUse" in block:
                use = block["toolUse"]
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=use["toolUseId"],
                        type="function",
                        function=ToolCallFunction(
                            name=use["name"], arguments=json.dumps(use.get("input", {}))
                        ),
                    )
                )

        content = "".join(texts) or None
        self.last_text = content

        wants_json = schema_from_response_format(params.get("response_format")) is not None
        if wants_json and content and not tool_calls:
            if finish_reason == "length":
                raise BedrockTruncated(
                    f"The model hit the {self.max_tokens} token limit before completing its "
                    f"JSON answer, so the response is cut off. Raise BEDROCK_MAX_TOKENS."
                )
            content = extract_json(content)

        message = ChatCompletionMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls or None,
        )
        return ChatCompletion(
            id=f"chatcmpl-bedrock-{self._turn}",
            model=self.model_id,
            object="chat.completion",
            created=int(time.time()),
            choices=[Choice(index=0, finish_reason=finish_reason, message=message)],
            usage=usage,
        )
