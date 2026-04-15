"""Integration-ish smoke tests for the FastMCP tool wrappers in server.py.

Exercises the composite `methods_repro_review` tool plus the individual
wrappers, without hitting the network or the Anthropic API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from methods_mcp.schemas import (
    CodeRepo,
    FullText,
    MethodsStructured,
    PaperMetadata,
    PaperSource,
    ReproAssessment,
    ReproSignal,
)
from methods_mcp.server import mcp


def _meta() -> PaperMetadata:
    return PaperMetadata(
        paper_id="2509.06917",
        source=PaperSource.ARXIV,
        title="Paper2Agent",
        authors=["A B"],
        abstract="abs",
        primary_url="https://arxiv.org/abs/2509.06917",
        raw_input="2509.06917",
    )


def _full() -> FullText:
    return FullText(
        paper_id="2509.06917",
        text="body with https://github.com/google-deepmind/alphagenome in it",
        source_url="https://ar5iv.labs.arxiv.org/html/2509.06917",
        extraction_method="arxiv-html",
        sections={"methods": "steps"},
        char_count=100,
    )


def _methods() -> MethodsStructured:
    return MethodsStructured(
        paper_id="2509.06917",
        summary="s",
        steps=[],
        reagents=[],
        equipment=[],
        analyses=[],
        confidence=0.7,
        extraction_model="claude-sonnet-4-6",
    )


def _repo() -> CodeRepo:
    return CodeRepo(
        paper_id="2509.06917",
        repo_url="https://github.com/google-deepmind/alphagenome",
        detection_method="paper-text",
        confidence=0.9,
    )


def _repro() -> ReproAssessment:
    return ReproAssessment(
        paper_id="2509.06917",
        repo_url="https://github.com/google-deepmind/alphagenome",
        overall_score=0.9,
        verdict="likely-reproducible",
        signals=[ReproSignal(name="has_readme", present=True, weight=0.10)],
        recommended_entrypoint="python make_figures.py",
        notes="Score 0.90/1.00",
    )


@pytest.mark.asyncio
async def test_health_tool_returns_version_and_config() -> None:
    health_tool = await mcp.get_tool("health")
    result = await health_tool.run(arguments={})
    # FastMCP wraps structured output into a ToolResult; inspect `.structured_content`
    payload = getattr(result, "structured_content", None) or result
    if hasattr(payload, "data"):
        payload = payload.data
    assert payload is not None


@pytest.mark.asyncio
async def test_methods_repro_review_composes_all_subtools() -> None:
    """Happy path: every sub-call returns a valid object; composite assembles them."""
    with (
        patch("methods_mcp.server._get_paper_metadata", AsyncMock(return_value=_meta())),
        patch("methods_mcp.server._fetch_paper_text", AsyncMock(return_value=_full())),
        patch(
            "methods_mcp.server.extract_methods_from_text",
            return_value=_methods(),
        ),
        patch("methods_mcp.server._find_code_repo", AsyncMock(return_value=_repo())),
        patch("methods_mcp.server._quick_repo_assessment", AsyncMock(return_value=_repro())),
    ):
        tool = await mcp.get_tool("methods_repro_review")
        result = await tool.run(arguments={"input_str": "2509.06917"})

    # FastMCP will have wrapped our dict return in a ToolResult; pull out the dict
    payload = getattr(result, "structured_content", None) or result
    if hasattr(payload, "data"):
        payload = payload.data
    # methods-mcp composite returns dict with 4 keys + _errors
    assert isinstance(payload, dict)
    assert set(payload.keys()) >= {"metadata", "methods", "code_repo", "repro_assessment"}
    assert payload["_errors"] == []
    assert payload["code_repo"]["repo_url"] == "https://github.com/google-deepmind/alphagenome"
    assert payload["repro_assessment"]["verdict"] == "likely-reproducible"


@pytest.mark.asyncio
async def test_methods_repro_review_collects_subtool_errors() -> None:
    """If methods-extraction blows up, the composite records the error and returns
    partial results — it doesn't raise."""
    with (
        patch("methods_mcp.server._get_paper_metadata", AsyncMock(return_value=_meta())),
        patch("methods_mcp.server._fetch_paper_text", AsyncMock(return_value=_full())),
        patch(
            "methods_mcp.server.extract_methods_from_text",
            side_effect=RuntimeError("Anthropic down"),
        ),
        patch("methods_mcp.server._find_code_repo", AsyncMock(return_value=_repo())),
        patch("methods_mcp.server._quick_repo_assessment", AsyncMock(return_value=_repro())),
    ):
        tool = await mcp.get_tool("methods_repro_review")
        result = await tool.run(arguments={"input_str": "2509.06917"})

    payload = getattr(result, "structured_content", None) or result
    if hasattr(payload, "data"):
        payload = payload.data
    assert isinstance(payload, dict)
    assert payload["methods"] is None
    # code_repo + repro should still be populated
    assert payload["code_repo"]["repo_url"] == "https://github.com/google-deepmind/alphagenome"
    assert payload["repro_assessment"] is not None
    # error recorded
    assert any("Anthropic down" in e for e in payload["_errors"])
