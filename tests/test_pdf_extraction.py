"""Tests for the PDF section heuristic split."""

from __future__ import annotations

from methods_mcp.extraction.pdf import heuristic_split_sections


def test_heuristic_split_sections_basic() -> None:
    text = (
        "Abstract We tested everything. "
        "Introduction This paper does X. "
        "Methods We dissolved compound X in PBS buffer. "
        "Results The dose curves were monotonic. "
        "Conclusion We are happy."
    )
    sections = heuristic_split_sections(text)
    assert "abstract" in sections
    assert "introduction" in sections
    assert "methods" in sections
    assert "results" in sections
    assert "conclusion" in sections
    assert "dissolved compound X" in sections["methods"]


def test_heuristic_split_sections_returns_empty_when_no_headings() -> None:
    text = "this is just one big block of text with no obvious sections"
    sections = heuristic_split_sections(text)
    assert sections == {}
