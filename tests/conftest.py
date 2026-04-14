"""Shared pytest fixtures for methods-mcp tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def arxiv_atom_response() -> str:
    return (FIXTURES / "arxiv_2410_01234.xml").read_text(encoding="utf-8")


@pytest.fixture
def ar5iv_minimal_html() -> str:
    return (FIXTURES / "ar5iv_minimal.html").read_text(encoding="utf-8")


@pytest.fixture
def github_repo_meta() -> str:
    return (FIXTURES / "github_repo_meta.json").read_text(encoding="utf-8")


@pytest.fixture
def github_readme() -> str:
    return (FIXTURES / "github_readme.json").read_text(encoding="utf-8")


@pytest.fixture
def github_tree() -> str:
    return (FIXTURES / "github_tree.json").read_text(encoding="utf-8")
