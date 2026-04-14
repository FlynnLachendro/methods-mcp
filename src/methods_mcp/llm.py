"""Thin Anthropic client wrapper for schema-validated LLM extraction.

Uses Anthropic tool-use to coerce the model into emitting a JSON object that
matches a target Pydantic schema. Falls back to one repair attempt if the
first response fails validation.
"""

from __future__ import annotations

import os
from typing import Any, TypeVar, cast

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam, ToolUseBlock
from loguru import logger
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = os.environ.get("METHODS_MCP_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = int(os.environ.get("METHODS_MCP_MAX_TOKENS", "4096"))


def is_anthropic_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _client() -> Anthropic:
    return Anthropic()


def _strip_optional_keys(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool-use input_schema requires a JSON Schema object — pass through.

    Pydantic v2 model_json_schema gives us a fine JSON Schema already; we only
    drop the top-level `title` to avoid noise in the Anthropic Console.
    """
    out = dict(schema)
    out.pop("title", None)
    return out


def extract_to_schema(
    *,
    schema_cls: type[T],
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_tokens: int | None = None,
) -> T:
    """Ask Claude to fill out `schema_cls`. Returns a validated instance.

    Strategy: define a single tool whose input_schema is the Pydantic JSON Schema,
    and force the model to call it. Validate the call's input via Pydantic. On
    validation error, send a single repair message including the validation error.
    """
    if not is_anthropic_configured():
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. methods-mcp needs it for LLM-driven extraction."
        )

    target_model = model or DEFAULT_MODEL
    target_max_tokens = max_tokens or DEFAULT_MAX_TOKENS
    client = _client()

    json_schema = _strip_optional_keys(schema_cls.model_json_schema())
    tool_name = schema_cls.__name__.lower()

    tools: list[ToolParam] = [
        cast(
            ToolParam,
            {
                "name": tool_name,
                "description": f"Emit a single, complete instance of {schema_cls.__name__}.",
                "input_schema": json_schema,
            },
        )
    ]
    tool_choice: ToolChoiceToolParam = {"type": "tool", "name": tool_name}

    messages: list[MessageParam] = [{"role": "user", "content": user_prompt}]

    for attempt in range(2):
        resp = client.messages.create(
            model=target_model,
            max_tokens=target_max_tokens,
            system=system_prompt,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )
        # Find the tool_use block (narrows the union to ToolUseBlock for type-checking)
        tool_block = next((b for b in resp.content if isinstance(b, ToolUseBlock)), None)
        if tool_block is None:
            raise RuntimeError(
                f"Anthropic response had no tool_use block; got types: "
                f"{[getattr(b, 'type', None) for b in resp.content]}"
            )

        try:
            return schema_cls.model_validate(tool_block.input)
        except ValidationError as ve:
            if attempt == 0:
                logger.warning("Schema validation failed on attempt 1; requesting repair: {}", ve)
                messages.extend(
                    [
                        cast(
                            MessageParam,
                            {"role": "assistant", "content": resp.content},
                        ),
                        cast(
                            MessageParam,
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_block.id,
                                        "content": (
                                            "Your previous output failed Pydantic validation with: "
                                            f"{ve}. Please call the tool again with a corrected payload."
                                        ),
                                        "is_error": True,
                                    }
                                ],
                            },
                        ),
                    ]
                )
                continue
            raise

    raise RuntimeError("Schema extraction failed after repair attempt.")
