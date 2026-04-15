"""Tests for the fetch / metadata helper tools (offline via respx)."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from methods_mcp.schemas import PaperSource
from methods_mcp.tools.fetch import fetch_paper_text, get_paper_metadata


@pytest.mark.asyncio
@respx.mock
async def test_get_paper_metadata_arxiv(arxiv_atom_response: str) -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=Response(200, text=arxiv_atom_response)
    )
    meta = await get_paper_metadata("2410.01234")
    assert meta.source is PaperSource.ARXIV
    assert meta.paper_id == "2410.01234"
    assert "Agentic Approach" in meta.title
    assert "Ada Lovelace" in meta.authors
    assert "Alan Turing" in meta.authors
    assert meta.abstract is not None
    assert "synthetic abstract" in meta.abstract


@pytest.mark.asyncio
async def test_get_paper_metadata_unknown_input() -> None:
    meta = await get_paper_metadata("https://example.com/random.pdf")
    assert meta.source is PaperSource.URL
    assert meta.title == ""
    assert meta.authors == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_paper_text_arxiv_html(ar5iv_minimal_html: str) -> None:
    respx.get("https://ar5iv.labs.arxiv.org/html/2410.01234").mock(
        return_value=Response(200, text=ar5iv_minimal_html)
    )
    full = await fetch_paper_text("2410.01234")
    assert full.paper_id == "2410.01234"
    assert full.extraction_method == "arxiv-html"
    assert "methods" in full.sections
    assert full.char_count > 100


@pytest.mark.asyncio
async def test_fetch_paper_text_no_url_raises() -> None:
    with pytest.raises(ValueError):
        await fetch_paper_text("just some random text")
