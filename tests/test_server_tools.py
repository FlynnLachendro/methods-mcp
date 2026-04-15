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


async def _run_composite(**kwargs: object) -> dict[str, object]:
    """Invoke the composite tool and unwrap the FastMCP ToolResult to a plain dict."""
    tool = await mcp.get_tool("methods_repro_review")
    result = await tool.run(arguments=kwargs)
    payload = getattr(result, "structured_content", None) or result
    if hasattr(payload, "data"):
        payload = payload.data
    assert isinstance(payload, dict)
    return payload


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
        payload = await _run_composite(input_str="2509.06917")

    # New response shape: status + narrative + 4 sub-objects + errors
    assert set(payload.keys()) >= {
        "status",
        "narrative",
        "metadata",
        "methods",
        "code_repo",
        "repro_assessment",
        "errors",
    }
    assert payload["status"] == "ok"
    assert payload["errors"] == []
    assert isinstance(payload["narrative"], str)
    assert len(payload["narrative"]) > 50  # actually populated, not empty
    assert "Paper2Agent" in payload["narrative"]  # title echoed
    assert payload["code_repo"]["repo_url"] == "https://github.com/google-deepmind/alphagenome"
    assert payload["repro_assessment"]["verdict"] == "likely-reproducible"


@pytest.mark.asyncio
async def test_methods_repro_review_collects_subtool_errors() -> None:
    """If a sub-step blows up, composite returns partial results with structured errors."""
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
        payload = await _run_composite(input_str="2509.06917")

    assert payload["status"] == "partial"
    assert payload["methods"] is None
    # code_repo + repro should still be populated
    assert payload["code_repo"]["repo_url"] == "https://github.com/google-deepmind/alphagenome"
    assert payload["repro_assessment"] is not None
    # One structured error recorded, with step + error_type + message
    errors = payload["errors"]
    assert len(errors) == 1
    assert errors[0]["step"] == "extract_methods"
    assert errors[0]["error_type"] == "RuntimeError"
    assert "Anthropic down" in errors[0]["message"]
    # Narrative mentions the partial state
    assert "Partial result" in payload["narrative"]


@pytest.mark.asyncio
async def test_methods_repro_review_empty_when_metadata_fails() -> None:
    """If paper resolution itself fails, status is 'empty' and no sub-steps ran."""
    with patch(
        "methods_mcp.server._get_paper_metadata",
        AsyncMock(side_effect=RuntimeError("bad input")),
    ):
        payload = await _run_composite(input_str="not-a-paper")

    assert payload["status"] == "empty"
    assert payload["metadata"] is None
    assert payload["methods"] is None
    assert payload["code_repo"] is None
    assert payload["repro_assessment"] is None
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["step"] == "get_paper_metadata"
    assert "Couldn't resolve the paper input" in payload["narrative"]


@pytest.mark.asyncio
async def test_methods_repro_review_attaches_hint_for_missing_api_key() -> None:
    """An ANTHROPIC_API_KEY-shaped error should produce an actionable hint."""
    with (
        patch("methods_mcp.server._get_paper_metadata", AsyncMock(return_value=_meta())),
        patch("methods_mcp.server._fetch_paper_text", AsyncMock(return_value=_full())),
        patch(
            "methods_mcp.server.extract_methods_from_text",
            side_effect=RuntimeError("ANTHROPIC_API_KEY not set"),
        ),
        patch("methods_mcp.server._find_code_repo", AsyncMock(return_value=_repo())),
        patch("methods_mcp.server._quick_repo_assessment", AsyncMock(return_value=_repro())),
    ):
        payload = await _run_composite(input_str="2509.06917")

    assert payload["status"] == "partial"
    hint = payload["errors"][0]["hint"]
    assert hint is not None
    assert "ANTHROPIC_API_KEY" in hint


@pytest.mark.asyncio
async def test_methods_repro_review_no_repo_detected() -> None:
    """When no repo is found, repro_assessment is null and narrative explains why."""
    no_repo = CodeRepo(
        paper_id="2509.06917",
        repo_url=None,
        detection_method="none",
        confidence=0.0,
        notes="no URL found",
    )
    with (
        patch("methods_mcp.server._get_paper_metadata", AsyncMock(return_value=_meta())),
        patch("methods_mcp.server._fetch_paper_text", AsyncMock(return_value=_full())),
        patch("methods_mcp.server.extract_methods_from_text", return_value=_methods()),
        patch("methods_mcp.server._find_code_repo", AsyncMock(return_value=no_repo)),
    ):
        payload = await _run_composite(input_str="2509.06917")

    assert payload["status"] == "ok"  # "no repo" isn't a failure
    assert payload["repro_assessment"] is None
    assert "No GitHub repository was detected" in payload["narrative"]
