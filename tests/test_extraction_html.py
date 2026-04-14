"""Tests for ar5iv HTML section parsing."""

from __future__ import annotations

from methods_mcp.extraction.html import parse_ar5iv_sections


def test_parse_ar5iv_sections_minimal(ar5iv_minimal_html: str) -> None:
    text, sections = parse_ar5iv_sections(ar5iv_minimal_html)
    assert text  # we got *something*
    # Section names should normalise
    assert "introduction" in sections
    assert "methods" in sections
    assert "conclusion" in sections
    # Methods text contains the synthetic protocol details
    assert "serial dilution" in sections["methods"].lower()
    assert "spectramax" in sections["methods"].lower()
    # Abstract is captured even though it's a div, not a section
    assert "abstract" in sections


def test_parse_ar5iv_sections_empty_doc() -> None:
    text, sections = parse_ar5iv_sections("<html><body><p>nothing</p></body></html>")
    assert text == "nothing"
    assert sections == {}
