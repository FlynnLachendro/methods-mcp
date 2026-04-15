"""Unit tests for the plain-English narrative builder + hint classifier."""

from __future__ import annotations

from methods_mcp.narrative import (
    build_narrative,
    classify_error_hint,
    describe_confidence,
    split_signals,
)
from methods_mcp.schemas import (
    CodeRepo,
    CompositeError,
    MethodsStructured,
    PaperMetadata,
    PaperSource,
    ReproAssessment,
    ReproSignal,
)


def _meta() -> PaperMetadata:
    return PaperMetadata(
        paper_id="2509.06917",
        source=PaperSource.ARXIV,
        title="Paper2Agent",
        authors=["Miao", "Davis"],
        abstract="abs",
        publication_date="2025-09-08T17:28:42Z",
        primary_url="https://arxiv.org/abs/2509.06917",
        raw_input="2509.06917",
    )


def _methods(confidence: float = 0.72, notes: str | None = "sparse") -> MethodsStructured:
    return MethodsStructured(
        paper_id="2509.06917",
        summary="s",
        steps=[],
        confidence=confidence,
        notes=notes,
        extraction_model="claude-sonnet-4-6",
    )


def _repo() -> CodeRepo:
    return CodeRepo(
        paper_id="2509.06917",
        repo_url="https://github.com/jmiao24/Paper2Agent",
        detection_method="paper-text",
        confidence=0.9,
    )


def _repro() -> ReproAssessment:
    return ReproAssessment(
        paper_id="2509.06917",
        repo_url="https://github.com/jmiao24/Paper2Agent",
        overall_score=0.9,
        verdict="likely-reproducible",
        signals=[
            ReproSignal(name="has_readme", present=True, weight=0.10),
            ReproSignal(name="has_data_or_fixtures", present=False, weight=0.10),
        ],
        recommended_entrypoint="python make_figures.py",
        notes="Score 0.90/1.00",
    )


def test_describe_confidence_buckets() -> None:
    # Thresholds mirror the extraction prompt's rubric: low < 0.4, high >= 0.8.
    assert describe_confidence(0.1) == "low"
    assert describe_confidence(0.39) == "low"
    assert describe_confidence(0.4) == "moderate"
    assert describe_confidence(0.72) == "moderate"
    assert describe_confidence(0.79) == "moderate"
    assert describe_confidence(0.8) == "high"
    assert describe_confidence(1.0) == "high"


def test_split_signals_uses_plain_english_labels() -> None:
    signals = [
        ReproSignal(name="has_readme", present=True, weight=0.10),
        ReproSignal(name="has_data_or_fixtures", present=False, weight=0.10),
        ReproSignal(name="unknown_signal", present=True, weight=0.05),
    ]
    present, missing = split_signals(signals)
    assert "README" in present
    assert "unknown_signal" in present  # unknown names pass through unchanged
    assert "data/fixtures directory" in missing


def test_classify_error_hint_recognises_api_key() -> None:
    hint = classify_error_hint("extract_methods", "RuntimeError", "ANTHROPIC_API_KEY not set")
    assert hint is not None
    assert "ANTHROPIC_API_KEY" in hint


def test_classify_error_hint_recognises_rate_limit() -> None:
    assert classify_error_hint("fetch_paper_text", "HTTPError", "429 Too Many Requests") is not None
    assert classify_error_hint("fetch_paper_text", "HTTPError", "rate limit exceeded") is not None


def test_classify_error_hint_recognises_timeout() -> None:
    hint = classify_error_hint("fetch_paper_text", "ReadTimeout", "connection timed out")
    assert hint is not None
    assert "timed out" in hint.lower()


def test_classify_error_hint_returns_none_for_unknown_patterns() -> None:
    # No hint fabrication — unknown → None
    assert classify_error_hint("extract_methods", "ValueError", "something weird broke") is None


def test_classify_error_hint_auth_error_not_confused_with_schema_invalid() -> None:
    """Regression from live testing: 'invalid x-api-key' was wrongly matched by
    the schema-validation branch because it contains the substring 'invalid'.
    Auth errors should hit the auth hint, not the 'try a different model' one.
    """
    hint = classify_error_hint(
        "extract_methods",
        "AuthenticationError",
        (
            "Error code: 401 - {'type': 'error', 'error': "
            "{'type': 'authentication_error', 'message': 'invalid x-api-key'}}"
        ),
    )
    assert hint is not None
    assert "invalid or expired" in hint
    assert "different model" not in hint  # make sure the wrong branch didn't fire


def test_classify_error_hint_schema_validation_still_fires_on_validationerror() -> None:
    hint = classify_error_hint(
        "extract_methods", "ValidationError", "2 validation errors for MethodsStructured"
    )
    assert hint is not None
    assert "different model" in hint


def test_build_narrative_happy_path_echoes_every_number() -> None:
    narrative = build_narrative(_meta(), _methods(), _repo(), _repro(), errors=[])
    # Title + author echoed
    assert "Paper2Agent" in narrative
    assert "Miao et al." in narrative
    # Methods confidence echoed with a qualitative word
    assert "0.72" in narrative
    assert "moderate" in narrative
    # Repo echoed with detection blurb
    assert "jmiao24/Paper2Agent" in narrative
    assert "inline link" in narrative
    # Repro score + verdict + signals + entrypoint
    assert "0.90/1.00" in narrative
    assert "likely reproducible" in narrative
    assert "README" in narrative  # present signal
    assert "data/fixtures directory" in narrative  # missing signal
    assert "python make_figures.py" in narrative


def test_build_narrative_empty_when_metadata_missing() -> None:
    err = CompositeError(
        step="get_paper_metadata",
        error_type="RuntimeError",
        message="bad input",
    )
    narrative = build_narrative(None, None, None, None, errors=[err])
    assert "Couldn't resolve" in narrative
    assert "bad input" in narrative


def test_build_narrative_partial_mentions_failed_steps() -> None:
    err = CompositeError(
        step="extract_methods",
        error_type="RuntimeError",
        message="boom",
    )
    narrative = build_narrative(_meta(), None, _repo(), _repro(), errors=[err])
    assert "Methods extraction failed" in narrative
    assert "Partial result" in narrative
    assert "extract_methods" in narrative


def test_build_narrative_no_repo_explains_why_repro_is_unavailable() -> None:
    no_repo = CodeRepo(
        paper_id="2509.06917",
        repo_url=None,
        detection_method="none",
        confidence=0.0,
    )
    narrative = build_narrative(_meta(), _methods(), no_repo, None, errors=[])
    assert "No GitHub repository" in narrative
    assert "unavailable" in narrative


def test_build_narrative_recognises_degraded_repro_with_empty_signals() -> None:
    """Regression from live testing: when GitHub is unreachable, the repro
    assessor returns a ReproAssessment with signals=[] and notes="Repo not
    found or GitHub API unreachable." — the narrative should call that out,
    not echo 'Present: none. Missing: none.' which reads as real data.
    """
    degraded = ReproAssessment(
        paper_id="2509.06917",
        repo_url="https://github.com/jmiao24/Paper2Agent",
        overall_score=0.0,
        verdict="insufficient-info",
        signals=[],
        notes="Repo not found or GitHub API unreachable.",
    )
    narrative = build_narrative(_meta(), _methods(), _repo(), degraded, errors=[])
    assert "reproducibility assessment was unavailable" in narrative
    assert "GitHub API unreachable" in narrative
    assert "GITHUB_TOKEN" in narrative  # actionable suggestion included
    assert "Present signals: none" not in narrative  # old misleading phrasing gone
