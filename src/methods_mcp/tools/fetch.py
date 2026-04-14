"""Helper tools: fetch_paper_text, get_paper_metadata.

These are intentionally minimal — methods-mcp's wedge is the *methods + repro*
layer. We supply just enough fetch capability to stand alone; users wanting a
broader paper toolkit should also load `paper-mcp` (Bhvaik) alongside.
"""

from __future__ import annotations

import httpx
from loguru import logger

from ..extraction.html import fetch_ar5iv_html, parse_ar5iv_sections
from ..extraction.pdf import fetch_pdf_text, heuristic_split_sections
from ..identifiers import resolve
from ..schemas import FullText, PaperMetadata, PaperSource
from ..sources.arxiv import fetch_arxiv_metadata


async def get_paper_metadata(input_str: str) -> PaperMetadata:
    """Resolve an input (URL / arXiv ID / DOI) to a canonical PaperMetadata record.

    For arXiv IDs we hit the arXiv export API. For other sources we return the
    minimum we can resolve from the URL alone (title/authors empty); this keeps
    the helper cheap and avoids brittle scraping.
    """
    resolved = resolve(input_str)

    if resolved.source is PaperSource.ARXIV:
        try:
            arxiv_meta = await fetch_arxiv_metadata(resolved.canonical_id)
        except httpx.HTTPError as e:
            logger.warning("arXiv metadata fetch failed for {}: {}", resolved.canonical_id, e)
            arxiv_meta = {"title": "", "authors": [], "abstract": None, "publication_date": None}
        return PaperMetadata(
            paper_id=resolved.canonical_id,
            source=resolved.source,
            title=arxiv_meta["title"],
            authors=arxiv_meta["authors"],
            abstract=arxiv_meta["abstract"],
            publication_date=arxiv_meta["publication_date"],
            primary_url=resolved.primary_url,
            pdf_url=resolved.pdf_url,
            html_url=resolved.html_url,
            venue="arXiv",
            raw_input=input_str,
        )

    return PaperMetadata(
        paper_id=resolved.canonical_id,
        source=resolved.source,
        title="",
        authors=[],
        abstract=None,
        publication_date=None,
        primary_url=resolved.primary_url,
        pdf_url=resolved.pdf_url,
        html_url=resolved.html_url,
        venue=None,
        raw_input=input_str,
    )


async def fetch_paper_text(input_str: str, *, prefer: str = "auto") -> FullText:
    """Return the best-effort full text + section split for a paper.

    `prefer` ∈ {"auto", "html", "pdf"}. Default tries ar5iv HTML first for
    arXiv papers (cheap, structured), falls back to PDF + heuristic section
    split. Non-arXiv inputs go straight to PDF if a PDF URL is known.
    """
    resolved = resolve(input_str)

    if resolved.source is PaperSource.ARXIV and prefer in ("auto", "html") and resolved.html_url:
        try:
            html = await fetch_ar5iv_html(resolved.html_url)
            text, sections = parse_ar5iv_sections(html)
            if text:
                return FullText(
                    paper_id=resolved.canonical_id,
                    text=text,
                    source_url=resolved.html_url,
                    extraction_method="arxiv-html",
                    sections=sections,
                    char_count=len(text),
                )
            logger.warning(
                "ar5iv returned empty text for {}; falling back to PDF", resolved.html_url
            )
        except httpx.HTTPError as e:
            logger.warning(
                "ar5iv fetch failed for {}: {}; falling back to PDF", resolved.html_url, e
            )

    if resolved.pdf_url:
        text = await fetch_pdf_text(resolved.pdf_url)
        sections = heuristic_split_sections(text) if text else {}
        return FullText(
            paper_id=resolved.canonical_id,
            text=text,
            source_url=resolved.pdf_url,
            extraction_method="pdf",
            sections=sections,
            char_count=len(text),
        )

    raise ValueError(
        f"No usable URL found for input '{input_str}'. "
        "Provide an arXiv ID/URL, bioRxiv URL, or a direct PDF URL."
    )
