"""arXiv API helpers — minimal canonical-metadata fetcher."""

from __future__ import annotations

from typing import Any

import httpx
from selectolax.parser import HTMLParser

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "methods-mcp/0.1 (https://github.com/FlynnLachendro/methods-mcp)"


async def fetch_arxiv_metadata(arxiv_id: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch arXiv metadata for the given ID via the export API.

    Returns a dict with title, authors (list), abstract, publication_date (ISO).
    Raises httpx.HTTPError on network / API failure.
    """
    params = {"id_list": arxiv_id, "max_results": "1"}
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()
        xml = resp.text

    # arXiv returns Atom XML — parse via selectolax (XML mode by treating as HTML works for our needs)
    tree = HTMLParser(xml)
    entry = tree.css_first("entry")
    if entry is None:
        return {
            "title": "",
            "authors": [],
            "abstract": None,
            "publication_date": None,
        }

    title_node = entry.css_first("title")
    title = (title_node.text(strip=True) if title_node else "").replace("\n", " ").strip()

    summary_node = entry.css_first("summary")
    abstract = summary_node.text(strip=True) if summary_node else None

    published_node = entry.css_first("published")
    publication_date = published_node.text(strip=True) if published_node else None

    authors: list[str] = []
    for author_node in entry.css("author"):
        name_node = author_node.css_first("name")
        if name_node:
            authors.append(name_node.text(strip=True))

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "publication_date": publication_date,
    }
