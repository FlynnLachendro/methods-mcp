"""Tests for llm.extract_to_schema — the schema-forced Anthropic tool-use wrapper.

We mock `anthropic.Anthropic` so tests stay offline and deterministic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from methods_mcp import llm


class _Toy(BaseModel):
    """A tiny schema used to exercise the extraction loop."""

    name: str
    count: int = Field(ge=0)


def _fake_tool_use_response(payload: dict[str, Any]) -> MagicMock:
    """Build a mock Anthropic message whose single content block is a ToolUseBlock-like object."""
    from anthropic.types import ToolUseBlock

    block = ToolUseBlock.model_construct(
        id="toolu_fake_1",
        name="_toy",
        input=payload,
        type="tool_use",
    )
    resp = MagicMock()
    resp.content = [block]
    return resp


def _fake_text_only_response() -> MagicMock:
    """A response that doesn't contain a tool_use block — should make extract_to_schema raise."""
    from anthropic.types import TextBlock

    block = TextBlock(type="text", text="I can't help with that.", citations=None)
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_is_anthropic_configured_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert llm.is_anthropic_configured() is True
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.is_anthropic_configured() is False


def test_extract_to_schema_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.extract_to_schema(
            schema_cls=_Toy,
            system_prompt="test",
            user_prompt="test",
        )


def test_extract_to_schema_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_tool_use_response({"name": "x", "count": 3})
    with patch.object(llm, "_client", return_value=fake_client):
        out = llm.extract_to_schema(
            schema_cls=_Toy,
            system_prompt="sys",
            user_prompt="usr",
        )
    assert out == _Toy(name="x", count=3)
    # exactly one Anthropic call on the happy path
    assert fake_client.messages.create.call_count == 1


def test_extract_to_schema_repairs_invalid_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """First attempt returns invalid payload (count<0); extractor retries once and succeeds."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _fake_tool_use_response({"name": "x", "count": -1}),  # fails ge=0 validation
        _fake_tool_use_response({"name": "x", "count": 0}),  # valid
    ]
    with patch.object(llm, "_client", return_value=fake_client):
        out = llm.extract_to_schema(
            schema_cls=_Toy,
            system_prompt="sys",
            user_prompt="usr",
        )
    assert out == _Toy(name="x", count=0)
    assert fake_client.messages.create.call_count == 2


def test_extract_to_schema_gives_up_after_one_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive invalid payloads => validation error bubbles up."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _fake_tool_use_response({"name": "x", "count": -1}),
        _fake_tool_use_response({"name": "x", "count": -5}),
    ]
    from pydantic import ValidationError

    with (
        patch.object(llm, "_client", return_value=fake_client),
        pytest.raises(ValidationError),
    ):
        llm.extract_to_schema(
            schema_cls=_Toy,
            system_prompt="sys",
            user_prompt="usr",
        )


def test_extract_to_schema_errors_on_no_tool_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """If Claude refuses the tool call and returns text only, we raise a clear error."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_text_only_response()
    with (
        patch.object(llm, "_client", return_value=fake_client),
        pytest.raises(RuntimeError, match="tool_use"),
    ):
        llm.extract_to_schema(
            schema_cls=_Toy,
            system_prompt="sys",
            user_prompt="usr",
        )
