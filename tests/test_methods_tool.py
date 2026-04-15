"""Tests for tools/methods.py — structured methods extraction wrapper.

`extract_to_schema` is mocked so tests stay offline; what we're exercising
here is the text-selection logic (prefer `methods` > `materials_and_methods`
> `experiments` > truncated full text) and the post-hoc authoritative
`paper_id` / `extraction_model` overwrites.
"""

from __future__ import annotations

from unittest.mock import patch

from methods_mcp.schemas import FullText, MethodsStructured
from methods_mcp.tools.methods import _select_methods_text, extract_methods_from_text


def _full_text(**sections: str) -> FullText:
    joined = "\n\n".join(sections.values())
    return FullText(
        paper_id="2410.01234",
        text=joined or "fallback text body",
        source_url="https://ar5iv.labs.arxiv.org/html/2410.01234",
        extraction_method="arxiv-html",
        sections=sections,
        char_count=len(joined),
    )


def test_select_methods_text_prefers_methods_section() -> None:
    full = _full_text(introduction="intro", methods="methods body", results="results body")
    assert _select_methods_text(full) == "methods body"


def test_select_methods_text_falls_back_to_materials_and_methods() -> None:
    full = _full_text(introduction="intro", materials_and_methods="m+m body", results="res")
    assert "m+m body" in _select_methods_text(full)


def test_select_methods_text_falls_back_to_full_text() -> None:
    full = _full_text(introduction="intro", results="results only")
    # No methods/experiments/m+m → first `max_chars` of full text
    out = _select_methods_text(full)
    assert "intro" in out
    assert "results only" in out


def test_select_methods_text_truncates_at_max_chars() -> None:
    long_methods = "x" * 50_000
    full = _full_text(methods=long_methods)
    assert len(_select_methods_text(full, max_chars=5000)) == 5000


def _fake_methods_structured() -> MethodsStructured:
    return MethodsStructured(
        paper_id="overridden-by-extractor",
        summary="two-sentence summary",
        steps=[],
        reagents=[],
        equipment=[],
        analyses=[],
        notes=None,
        confidence=0.72,
        extraction_model="claude-placeholder",
    )


def test_extract_methods_from_text_overrides_paper_id_and_model() -> None:
    full = _full_text(methods="x")
    with patch(
        "methods_mcp.tools.methods.extract_to_schema",
        return_value=_fake_methods_structured(),
    ) as mock:
        result = extract_methods_from_text(
            paper_id="REAL-ID-42", full=full, model="claude-sonnet-4-6"
        )
    assert result.paper_id == "REAL-ID-42"
    assert result.extraction_model == "claude-sonnet-4-6"
    mock.assert_called_once()
    # verify the system prompt + schema were the expected ones
    kwargs = mock.call_args.kwargs
    assert kwargs["schema_cls"] is MethodsStructured
    assert "meticulous" in kwargs["system_prompt"].lower()
