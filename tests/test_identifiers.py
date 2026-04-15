"""Tests for the URL/ID resolver."""

from __future__ import annotations

import pytest

from methods_mcp.identifiers import resolve
from methods_mcp.schemas import PaperSource


@pytest.mark.parametrize(
    ("input_str", "expected_id"),
    [
        ("2410.01234", "2410.01234"),
        ("2410.01234v3", "2410.01234"),
        ("https://arxiv.org/abs/2410.01234", "2410.01234"),
        ("https://arxiv.org/abs/2410.01234v2", "2410.01234"),
        ("https://arxiv.org/pdf/2410.01234", "2410.01234"),
        ("https://arxiv.org/html/2410.01234", "2410.01234"),
        ("http://arxiv.org/abs/2410.01234", "2410.01234"),
    ],
)
def test_resolve_arxiv_variants(input_str: str, expected_id: str) -> None:
    r = resolve(input_str)
    assert r.source is PaperSource.ARXIV
    assert r.canonical_id == expected_id
    assert r.html_url == f"https://ar5iv.labs.arxiv.org/html/{expected_id}"
    assert r.pdf_url == f"https://arxiv.org/pdf/{expected_id}"


def test_resolve_doi() -> None:
    r = resolve("10.1234/abcd.5678")
    assert r.source is PaperSource.DOI
    assert r.canonical_id == "10.1234/abcd.5678"
    assert r.primary_url == "https://doi.org/10.1234/abcd.5678"


def test_resolve_biorxiv() -> None:
    r = resolve("https://www.biorxiv.org/content/10.1101/2024.05.01.123456v1")
    assert r.source is PaperSource.BIORXIV
    assert "biorxiv.org" in r.primary_url


def test_resolve_generic_url() -> None:
    r = resolve("https://example.com/paper.pdf")
    assert r.source is PaperSource.URL
    assert r.primary_url == "https://example.com/paper.pdf"


def test_resolve_unknown() -> None:
    r = resolve("just some text")
    assert r.source is PaperSource.UNKNOWN
