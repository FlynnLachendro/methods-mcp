"""Tests for tools/summarize.py — mode handling + authoritative overwrites."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from methods_mcp.schemas import FullText, PaperSummary
from methods_mcp.tools.summarize import summarize_paper_from_text


def _full_text(**sections: str) -> FullText:
    joined = "\n\n".join(sections.values())
    return FullText(
        paper_id="2410.01234",
        text=joined or "fallback body",
        source_url="https://ar5iv.labs.arxiv.org/html/2410.01234",
        extraction_method="arxiv-html",
        sections=sections,
        char_count=len(joined),
    )


def _fake_summary() -> PaperSummary:
    return PaperSummary(
        paper_id="placeholder",
        mode="tldr",
        summary="one-line takeaway",
        key_findings=["finding 1", "finding 2"],
        methodology_oneliner="methodology in one line",
        extraction_model="placeholder",
    )


@pytest.mark.parametrize("mode", ["abstract", "tldr", "exec"])
def test_summarize_accepts_each_mode(mode: str) -> None:
    full = _full_text(abstract="a", introduction="i", conclusion="c")
    with patch(
        "methods_mcp.tools.summarize.extract_to_schema", return_value=_fake_summary()
    ) as mock:
        result = summarize_paper_from_text(
            paper_id="2410.01234", full=full, mode=mode, model="claude-sonnet-4-6"
        )
    assert result.mode == mode
    assert result.paper_id == "2410.01234"
    assert result.extraction_model == "claude-sonnet-4-6"
    # confirm the system prompt was mode-aware
    system = mock.call_args.kwargs["system_prompt"]
    assert f"Mode = {mode}" in system


def test_summarize_rejects_bad_mode() -> None:
    full = _full_text(abstract="a")
    with pytest.raises(ValueError, match="mode must be one of"):
        summarize_paper_from_text(paper_id="2410.01234", full=full, mode="invalid")


def test_summarize_uses_abstract_intro_conclusion_when_present() -> None:
    full = _full_text(
        abstract="ABSTRACT_TEXT",
        introduction="INTRO_TEXT",
        conclusion="CONCL_TEXT",
        results="SHOULD_NOT_APPEAR",
    )
    with patch(
        "methods_mcp.tools.summarize.extract_to_schema", return_value=_fake_summary()
    ) as mock:
        summarize_paper_from_text(paper_id="x", full=full, mode="tldr")
    user_prompt = mock.call_args.kwargs["user_prompt"]
    assert "ABSTRACT_TEXT" in user_prompt
    assert "INTRO_TEXT" in user_prompt
    assert "CONCL_TEXT" in user_prompt
    assert "SHOULD_NOT_APPEAR" not in user_prompt


def test_summarize_falls_back_to_raw_text_when_no_sections() -> None:
    full = _full_text()  # no sections at all
    with patch(
        "methods_mcp.tools.summarize.extract_to_schema", return_value=_fake_summary()
    ) as mock:
        summarize_paper_from_text(paper_id="x", full=full, mode="tldr")
    user_prompt = mock.call_args.kwargs["user_prompt"]
    assert "fallback body" in user_prompt
