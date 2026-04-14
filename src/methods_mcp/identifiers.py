"""Resolve user-supplied paper IDs / URLs to a canonical (source, id) pair."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import PaperSource

ARXIV_ABS_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?", re.I)
ARXIV_BARE_RE = re.compile(r"^([0-9]{4}\.[0-9]{4,5})(?:v\d+)?$")
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
BIORXIV_RE = re.compile(r"biorxiv\.org/content/(?:10\.\d+/)?([0-9.]+v?\d*)", re.I)
URL_RE = re.compile(r"^https?://", re.I)


@dataclass
class ResolvedPaper:
    source: PaperSource
    canonical_id: str
    primary_url: str
    pdf_url: str | None = None
    html_url: str | None = None


def resolve(input_str: str) -> ResolvedPaper:
    """Best-effort resolution of a user-supplied URL / ID to a canonical paper handle.

    Recognises arXiv (URLs and bare IDs), bioRxiv URLs, raw DOIs, and falls back to a
    generic URL handle. The returned object always carries a usable primary_url.
    """
    s = input_str.strip()

    # arXiv URL forms
    m = ARXIV_ABS_RE.search(s)
    if m:
        arxiv_id = m.group(1)
        return ResolvedPaper(
            source=PaperSource.ARXIV,
            canonical_id=arxiv_id,
            primary_url=f"https://arxiv.org/abs/{arxiv_id}",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            html_url=f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}",
        )

    # Bare arXiv ID (e.g. 2410.12345)
    m = ARXIV_BARE_RE.match(s)
    if m:
        arxiv_id = m.group(1)
        return ResolvedPaper(
            source=PaperSource.ARXIV,
            canonical_id=arxiv_id,
            primary_url=f"https://arxiv.org/abs/{arxiv_id}",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            html_url=f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}",
        )

    # bioRxiv
    m = BIORXIV_RE.search(s)
    if m:
        biorxiv_id = m.group(1)
        return ResolvedPaper(
            source=PaperSource.BIORXIV,
            canonical_id=biorxiv_id,
            primary_url=s if URL_RE.match(s) else f"https://www.biorxiv.org/content/{biorxiv_id}",
            pdf_url=(s.rstrip("/") + ".full.pdf") if URL_RE.match(s) else None,
        )

    # Bare DOI
    m = DOI_RE.search(s)
    if m and not URL_RE.match(s):
        doi = m.group(1)
        return ResolvedPaper(
            source=PaperSource.DOI,
            canonical_id=doi,
            primary_url=f"https://doi.org/{doi}",
        )

    # Generic URL
    if URL_RE.match(s):
        return ResolvedPaper(
            source=PaperSource.URL,
            canonical_id=s,
            primary_url=s,
        )

    return ResolvedPaper(
        source=PaperSource.UNKNOWN,
        canonical_id=s,
        primary_url=s,
    )
