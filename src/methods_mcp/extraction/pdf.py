"""PDF fallback extractor — pypdf-based, intentionally minimal.

Use only when ar5iv HTML is unavailable. Heavier extractors (Nougat, marker)
are deliberately out of scope for the lightweight wedge.
"""

from __future__ import annotations

import io
import re

import httpx
from pypdf import PdfReader

USER_AGENT = "methods-mcp/0.1 (https://github.com/FlynnLachendro/methods-mcp)"

WHITESPACE_RE = re.compile(r"\s+")


async def fetch_pdf_text(
    pdf_url: str, *, timeout: float = 60.0, max_bytes: int = 50_000_000
) -> str:
    """Download a PDF and extract plain text via pypdf.

    Raises httpx.HTTPError on network failure. Returns whitespace-normalised text.
    """
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        resp = await client.get(pdf_url)
        resp.raise_for_status()
        if len(resp.content) > max_bytes:
            raise ValueError(f"PDF exceeds max_bytes={max_bytes}")
        data = resp.content

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    return WHITESPACE_RE.sub(" ", text).strip()


SECTION_HEADING_RE = re.compile(
    r"\b(abstract|introduction|background|related\s+work|methods?|methodology|materials\s+and\s+methods|experiments?|evaluation|results?|discussion|conclusions?|limitations)\b",
    re.I,
)


def heuristic_split_sections(full_text: str) -> dict[str, str]:
    """Very loose section split using regex on common section headings.

    PDFs lose all structural info, so this is best-effort. Anything that doesn't
    match cleanly stays in `full_text` and we skip section segmentation.
    """
    # Find heading positions
    matches = list(SECTION_HEADING_RE.finditer(full_text))
    if len(matches) < 2:
        return {}

    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).lower().strip()
        # Normalise
        if name.startswith("method"):
            name = "methods"
        elif name.startswith("conclusion"):
            name = "conclusion"
        elif name.startswith("result"):
            name = "results"
        elif name.startswith("experiment"):
            name = "experiments"
        elif name == "materials and methods":
            name = "methods"

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        # If we already saw this section, keep the longer text
        if name in sections and len(sections[name]) > len(body):
            continue
        sections[name] = body
    return sections
