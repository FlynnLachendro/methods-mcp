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
from methods_mcp.tools.repo import (
    find_code_repo,
    find_repo_in_text,
    find_repos_in_text,
    quick_repo_assessment,
)


def _meta(source: PaperSource = PaperSource.URL, abstract: str | None = None) -> PaperMetadata:
    return PaperMetadata(
        paper_id="2410.01234",
        source=source,
        title="x",
        authors=[],
        abstract=abstract,
        primary_url="https://arxiv.org/abs/2410.01234",
        raw_input="2410.01234",
    )


# --- URL extraction / scoring ---


def test_find_repo_in_text_simple() -> None:
    text = "We release our code at https://github.com/example/agentic-bench. See README."
    assert find_repo_in_text(text) == "https://github.com/example/agentic-bench"


def test_find_repo_in_text_strips_dot_git_suffix() -> None:
    text = "clone https://github.com/example/agentic-bench.git for everything"
    assert find_repo_in_text(text) == "https://github.com/example/agentic-bench"


def test_find_repo_in_text_preserves_trailing_git_in_name() -> None:
    """Regression: `.rstrip('.git')` chewed any of '.gitT' off repo names.

    'Paper2Agent .' → must stay 'Paper2Agent', not 'Paper2Agen'.
    'distilbert' → must stay 'distilbert', not 'dis'.
    """
    text = "Code at https://github.com/jmiao24/Paper2Agent ."
    assert find_repo_in_text(text) == "https://github.com/jmiao24/Paper2Agent"

    text = "see https://github.com/huggingface/distilbert ."
    assert find_repo_in_text(text) == "https://github.com/huggingface/distilbert"


def test_find_repo_in_text_stops_at_sentence_punctuation() -> None:
    text = "Our repo is at https://github.com/acme/widget, and the data is elsewhere."
    assert find_repo_in_text(text) == "https://github.com/acme/widget"


def test_find_repo_in_text_none() -> None:
    assert find_repo_in_text("no urls here") is None


def test_find_repos_in_text_ranks_by_pre_url_phrase() -> None:
    """Multi-URL paper: the URL preceded by a STRONG phrase should win."""
    text = (
        "AlphaGenome Github repository: https://github.com/google-deepmind/alphagenome "
        "TISSUE Github repository: https://github.com/sunericd/TISSUE "
        "Scanpy Github repository: https://github.com/scverse/scanpy "
        "Code availability Paper2Agent is publicly available at "
        "https://github.com/jmiao24/Paper2Agent ."
    )
    ranking = find_repos_in_text(text)
    assert ranking[0].url == "https://github.com/jmiao24/Paper2Agent"
    assert ranking[0].score >= 10
    # The three case-study repos should rank lower (no STRONG phrase precedes them)
    loser_urls = {c.url for c in ranking[1:]}
    assert "https://github.com/google-deepmind/alphagenome" in loser_urls


def test_find_repos_in_text_dedupes_repeated_mentions() -> None:
    text = (
        "our code is at https://github.com/acme/widget. "
        "as discussed in https://github.com/acme/widget the library is..."
    )
    ranking = find_repos_in_text(text)
    assert len(ranking) == 1
    assert ranking[0].mentions == 2
    # mention-count bonus: 0.5 * (mentions - 1) added to the base score
    assert ranking[0].score >= 10 + 0.5


def test_find_repos_in_text_medium_phrase_over_weak() -> None:
    """MEDIUM phrase 'code:' beats no-signal mention on score."""
    text = (
        "see https://github.com/control/repo for context. "
        "Code: https://github.com/authors/paper for this work."
    )
    ranking = find_repos_in_text(text)
    assert ranking[0].url == "https://github.com/authors/paper"


# --- find_code_repo integration ---


@pytest.mark.asyncio
@respx.mock
async def test_find_code_repo_arxiv_tries_pwc_first_and_wins() -> None:
    """PWC is authoritative for arXiv and should beat paper-text scan."""
    respx.get("https://paperswithcode.com/api/v1/papers/?arxiv_id=2410.01234").mock(
        return_value=Response(
            200,
            json={
                "results": [{"repository_url": "https://github.com/pwc/real-repo"}],
            },
        )
    )
    result = await find_code_repo(
        metadata=_meta(source=PaperSource.ARXIV),
        full_text="Code at https://github.com/wrong/one for context.",
    )
    assert result.detection_method == "papers-with-code"
    assert result.repo_url == "https://github.com/pwc/real-repo"
    assert result.confidence == 0.95


@pytest.mark.asyncio
@respx.mock
async def test_find_code_repo_arxiv_falls_back_to_text_when_pwc_empty() -> None:
    respx.get("https://paperswithcode.com/api/v1/papers/?arxiv_id=2410.01234").mock(
        return_value=Response(200, json={"results": []})
    )
    result = await find_code_repo(
        metadata=_meta(source=PaperSource.ARXIV),
        full_text="Our code is available at https://github.com/authors/paper for this work.",
    )
    assert result.detection_method == "paper-text"
    assert result.repo_url == "https://github.com/authors/paper"
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_find_code_repo_non_arxiv_skips_pwc() -> None:
    """Non-arXiv papers should not hit PWC at all (would 404 anyway)."""
    result = await find_code_repo(
        metadata=_meta(source=PaperSource.URL),
        full_text="Code available at https://github.com/example/agentic-bench .",
    )
    assert result.detection_method == "paper-text"
    assert result.repo_url == "https://github.com/example/agentic-bench"


@pytest.mark.asyncio
async def test_find_code_repo_abstract_fallback() -> None:
    result = await find_code_repo(
        metadata=_meta(
            source=PaperSource.URL,
            abstract="We release our code at https://github.com/example/agentic-bench.",
        ),
        full_text=None,
    )
    assert result.detection_method == "abstract-link"
    assert result.repo_url == "https://github.com/example/agentic-bench"


@pytest.mark.asyncio
async def test_find_code_repo_none_found() -> None:
    result = await find_code_repo(
        metadata=_meta(source=PaperSource.URL),
        full_text="No repos in this text at all.",
    )
    assert result.detection_method == "none"
    assert result.repo_url is None
    assert result.confidence == 0.0


# --- Reproducibility assessment ---


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
    assert assessment.overall_score >= 0.7
    assert assessment.verdict == "likely-reproducible"
    assert assessment.recommended_entrypoint == "python make_figures.py"
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
