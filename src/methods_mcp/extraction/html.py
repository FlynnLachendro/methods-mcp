"""Extract paper full text from arXiv ar5iv HTML.

ar5iv (https://ar5iv.labs.arxiv.org/) renders LaTeX papers as HTML, which is far
cheaper to parse than PDFs. We treat ar5iv as the primary path for arXiv papers
and fall back to PDF only when ar5iv 404s or the paper isn't on arXiv.
"""

from __future__ import annotations

import re

import httpx
from selectolax.parser import HTMLParser

USER_AGENT = "methods-mcp/0.1 (https://github.com/FlynnLachendro/methods-mcp)"

# Heuristic section-name normalization. Headings vary wildly across papers.
SECTION_ALIASES: dict[str, str] = {
    "introduction": "introduction",
    "background": "background",
    "related work": "related_work",
    "methods": "methods",
    "method": "methods",
    "methodology": "methods",
    "extended methods": "methods",
    "online methods": "methods",
    "supplementary methods": "methods",
    "materials and methods": "methods",
    "experimental setup": "methods",
    "experiments": "experiments",
    "evaluation": "experiments",
    "results": "results",
    "results and discussion": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "abstract": "abstract",
    "limitations": "limitations",
}

WHITESPACE_RE = re.compile(r"\s+")
# Strip leading numbering: "1." / "1)" / "1Introduction" / "I." / "Section 1:" / "Chapter 2 -"
LEADING_NUMBER_RE = re.compile(r"^(?:section|chapter|appendix)?\s*[\divxlc]+[\.\)\-:]?\s*")
SECTION_PREFIX_RE = re.compile(r"^section\s+\d+[:.\s]+")


def _norm_heading(text: str) -> str | None:
    cleaned = WHITESPACE_RE.sub(" ", text.strip().lower())
    cleaned = SECTION_PREFIX_RE.sub("", cleaned)
    cleaned = LEADING_NUMBER_RE.sub("", cleaned)
    cleaned = cleaned.strip().rstrip(":").strip()
    if not cleaned:
        return None
    for alias, canonical in SECTION_ALIASES.items():
        if cleaned == alias or cleaned.startswith(alias + " ") or cleaned.startswith(alias + ":"):
            return canonical
    return None


async def fetch_ar5iv_html(html_url: str, *, timeout: float = 30.0) -> str:
    """GET the ar5iv HTML for an arXiv paper. Raises httpx.HTTPError on failure."""
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        resp = await client.get(html_url)
        resp.raise_for_status()
        return resp.text


def parse_ar5iv_sections(html: str) -> tuple[str, dict[str, str]]:
    """Parse ar5iv HTML into (full_text, {section_name: section_text}).

    Sections are detected by H1/H2 headings whose text matches SECTION_ALIASES.
    """
    tree = HTMLParser(html)

    # Drop bibliography / footnotes / nav / scripts / styles
    for selector in ("nav", "script", "style", ".ltx_bibliography", ".ltx_acknowledgements"):
        for node in tree.css(selector):
            node.decompose()

    body_text_parts: list[str] = []
    sections: dict[str, str] = {}

    # ar5iv uses div.ltx_section / div.ltx_subsection with a heading
    for section_node in tree.css(".ltx_section, .ltx_subsection, section, article > div"):
        heading_node = section_node.css_first(
            "h1.ltx_title, h2.ltx_title, h3.ltx_title, h1, h2, h3"
        )
        if heading_node is None:
            continue
        canonical = _norm_heading(heading_node.text())
        if canonical is None:
            continue
        # collect body text of the section (skip nested headings duplicating)
        body = " ".join(t.strip() for t in section_node.text().split())
        # strip the heading text itself from the start
        heading_text = heading_node.text().strip()
        if body.lower().startswith(heading_text.lower()):
            body = body[len(heading_text) :].strip()
        sections.setdefault(canonical, "")
        sections[canonical] = (sections[canonical] + " " + body).strip()
        body_text_parts.append(body)

    # Fallback full text: just the body
    body_node = tree.css_first("article") or tree.css_first("body")
    full_text = body_node.text(separator=" ") if body_node else " ".join(body_text_parts)
    full_text = WHITESPACE_RE.sub(" ", full_text).strip()

    # Also harvest abstract block if not already captured
    if "abstract" not in sections:
        abstract_node = tree.css_first(".ltx_abstract, .abstract")
        if abstract_node:
            sections["abstract"] = WHITESPACE_RE.sub(" ", abstract_node.text()).strip()

    return full_text, sections
