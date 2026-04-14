"""Tests for repo discovery and reproducibility heuristics.

Network calls to the GitHub REST API are intercepted with respx so the tests
are deterministic and offline-safe.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from methods_mcp.schemas import PaperMetadata, PaperSource
from methods_mcp.tools.repo import find_code_repo, find_repo_in_text, quick_repo_assessment


def test_find_repo_in_text_simple() -> None:
    text = "We release our code at https://github.com/example/agentic-bench. See README."
    assert find_repo_in_text(text) == "https://github.com/example/agentic-bench"


def test_find_repo_in_text_strips_dot_git() -> None:
    text = "clone https://github.com/example/agentic-bench.git for everything"
    assert find_repo_in_text(text) == "https://github.com/example/agentic-bench"


def test_find_repo_in_text_none() -> None:
    assert find_repo_in_text("no urls here") is None


@pytest.mark.asyncio
async def test_find_code_repo_from_full_text() -> None:
    metadata = PaperMetadata(
        paper_id="2410.01234",
        source=PaperSource.ARXIV,
        title="x",
        authors=[],
        abstract=None,
        primary_url="https://arxiv.org/abs/2410.01234",
        raw_input="2410.01234",
    )
    result = await find_code_repo(
        metadata=metadata,
        full_text="Code at https://github.com/example/agentic-bench for everything.",
    )
    assert result.repo_url == "https://github.com/example/agentic-bench"
    assert result.detection_method == "paper-text"
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_find_code_repo_from_abstract() -> None:
    metadata = PaperMetadata(
        paper_id="2410.01234",
        source=PaperSource.URL,
        title="x",
        authors=[],
        abstract="We release our code at https://github.com/example/agentic-bench.",
        primary_url="https://example.com/paper",
        raw_input="https://example.com/paper",
    )
    result = await find_code_repo(metadata=metadata, full_text=None)
    assert result.repo_url == "https://github.com/example/agentic-bench"
    assert result.detection_method == "abstract-link"


@pytest.mark.asyncio
@respx.mock
async def test_quick_repo_assessment_high_score(
    github_repo_meta: str, github_readme: str, github_tree: str
) -> None:
    respx.get("https://api.github.com/repos/example/agentic-bench").mock(
        return_value=Response(200, json=json.loads(github_repo_meta))
    )
    respx.get("https://api.github.com/repos/example/agentic-bench/readme").mock(
        return_value=Response(200, json=json.loads(github_readme))
    )
    respx.get("https://api.github.com/repos/example/agentic-bench/git/trees/main").mock(
        return_value=Response(200, json=json.loads(github_tree))
    )

    assessment = await quick_repo_assessment(
        "https://github.com/example/agentic-bench", paper_id="2410.01234"
    )
    assert assessment.repo_url == "https://github.com/example/agentic-bench"
    # README + deps + data + notebook + figure script + recent + permissive license
    # Should land in likely-reproducible territory
    assert assessment.overall_score >= 0.7
    assert assessment.verdict == "likely-reproducible"
    assert assessment.recommended_entrypoint == "python make_figures.py"
    # Each signal is present
    assert {s.name for s in assessment.signals} == {
        "has_readme",
        "readme_substantial",
        "has_dependencies_file",
        "has_data_or_fixtures",
        "has_notebook",
        "has_figure_script",
        "actively_maintained",
        "permissive_license",
    }


@pytest.mark.asyncio
@respx.mock
async def test_quick_repo_assessment_repo_not_found() -> None:
    respx.get("https://api.github.com/repos/missing/repo").mock(return_value=Response(404))
    assessment = await quick_repo_assessment("https://github.com/missing/repo")
    assert assessment.verdict == "insufficient-info"
    assert assessment.overall_score == 0.0


@pytest.mark.asyncio
async def test_quick_repo_assessment_invalid_url() -> None:
    assessment = await quick_repo_assessment("not-a-github-url")
    assert assessment.verdict == "insufficient-info"
    assert assessment.signals == []
