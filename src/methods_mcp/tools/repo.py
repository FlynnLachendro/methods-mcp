"""Tools: find_code_repo + reproducibility heuristics (no execution required).

The lightweight wedge: assess a paper's reproducibility from public GitHub
metadata + tree contents, without cloning or running anything.
"""

from __future__ import annotations

import os
import re
from pathlib import PurePosixPath
from typing import Any, Literal

import httpx
from loguru import logger

from ..schemas import CodeRepo, PaperMetadata, ReproAssessment, ReproSignal

GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:/|\.git|\s|$)", re.I
)
PWC_API = "https://paperswithcode.com/api/v1/papers"
USER_AGENT = "methods-mcp/0.1 (https://github.com/FlynnLachendro/methods-mcp)"


def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _gh_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def find_repo_in_text(text: str) -> str | None:
    """First GitHub URL found in `text`, normalised."""
    m = GITHUB_URL_RE.search(text)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2).rstrip(".git")
    return f"https://github.com/{owner}/{repo}"


async def find_code_repo(*, metadata: PaperMetadata, full_text: str | None = None) -> CodeRepo:
    """Discover a code repo for a paper.

    Strategy:
      1. Scan paper full_text for github.com URLs.
      2. Scan abstract.
      3. (arXiv-only) try Papers With Code lookup.
    """
    if full_text:
        url = find_repo_in_text(full_text)
        if url:
            return CodeRepo(
                paper_id=metadata.paper_id,
                repo_url=url,
                detection_method="paper-text",
                confidence=0.9,
                notes="Found GitHub URL inline in the paper text.",
            )

    if metadata.abstract:
        url = find_repo_in_text(metadata.abstract)
        if url:
            return CodeRepo(
                paper_id=metadata.paper_id,
                repo_url=url,
                detection_method="abstract-link",
                confidence=0.85,
                notes="Found GitHub URL in the abstract.",
            )

    # Papers With Code lookup (arXiv-only — PWC keys on arxiv ID)
    if metadata.source.value == "arxiv":
        try:
            async with httpx.AsyncClient(
                timeout=15.0, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.get(
                    f"{PWC_API}/?arxiv_id={metadata.paper_id}",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        # PWC sometimes carries a repository_url; otherwise we'd need /repositories endpoint
                        for r in results:
                            repo_url = r.get("repository_url")
                            if repo_url:
                                return CodeRepo(
                                    paper_id=metadata.paper_id,
                                    repo_url=repo_url,
                                    detection_method="papers-with-code",
                                    confidence=0.75,
                                    notes="Resolved via Papers With Code API.",
                                )
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Papers With Code lookup failed: {}", e)

    return CodeRepo(
        paper_id=metadata.paper_id,
        repo_url=None,
        detection_method="none",
        confidence=0.0,
        notes="No GitHub URL found in paper text, abstract, or Papers With Code.",
    )


# --- Reproducibility heuristics ---

LIKELY_FIG_FILES = (
    r"make_figures?\.py",
    r"plot.*\.py",
    r"figures?\.py",
    r"reproduce.*\.py",
    r"figure_\d+\.py",
    r"run_all\.sh",
    r"reproduce.*\.sh",
)
LIKELY_FIG_RE = re.compile("|".join(LIKELY_FIG_FILES), re.I)
DEPS_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "environment.yml",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "setup.py",
    "setup.cfg",
    "package.json",
    "renv.lock",
    "DESCRIPTION",
    "Dockerfile",
}
DATA_DIRS = {"data", "datasets", "fixtures", "examples"}
NOTEBOOK_DIRS = {"notebooks", "nbs"}


async def _gh_get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any] | list[Any] | None:
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            data: dict[str, Any] | list[Any] = resp.json()
            return data
        if resp.status_code == 404:
            return None
        logger.warning("GitHub API {} returned {}", url, resp.status_code)
    except httpx.HTTPError as e:
        logger.warning("GitHub API call failed: {}", e)
    return None


async def quick_repo_assessment(repo_url: str, *, paper_id: str | None = None) -> ReproAssessment:
    """Heuristic, no-clone reproducibility assessment via the GitHub REST API.

    Signals (each contributes weighted score):
      - has_readme (0.10)
      - readme_substantial (0.15) — > 1500 chars, mentions install/run/figure
      - has_dependencies_file (0.20)
      - has_data_or_fixtures (0.10)
      - has_notebook (0.10)
      - has_figure_script (0.20) — file matching make_figures.py / reproduce.* / etc.
      - actively_maintained (0.10) — pushed within last 2 years
      - permissive_license (0.05) — MIT/BSD/Apache/etc.
    """
    m = GITHUB_URL_RE.search(repo_url)
    if not m:
        return ReproAssessment(
            paper_id=paper_id,
            repo_url=repo_url,
            overall_score=0.0,
            verdict="insufficient-info",
            signals=[],
            notes="Not a recognisable GitHub URL.",
        )
    owner, repo = m.group(1), m.group(2).rstrip(".git")

    signals: list[ReproSignal] = []
    recommended_entrypoint: str | None = None

    async with httpx.AsyncClient(timeout=20.0, headers=_gh_headers()) as client:
        repo_meta = await _gh_get_json(client, f"https://api.github.com/repos/{owner}/{repo}")
        if not repo_meta or not isinstance(repo_meta, dict):
            return ReproAssessment(
                paper_id=paper_id,
                repo_url=repo_url,
                overall_score=0.0,
                verdict="insufficient-info",
                signals=[],
                notes="Repo not found or GitHub API unreachable.",
            )

        default_branch = repo_meta.get("default_branch", "main")
        pushed_at = repo_meta.get("pushed_at", "")
        license_info = repo_meta.get("license") or {}
        spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None

        # README
        readme_data = await _gh_get_json(
            client, f"https://api.github.com/repos/{owner}/{repo}/readme"
        )
        readme_text = ""
        if isinstance(readme_data, dict) and readme_data.get("content"):
            import base64

            try:
                readme_text = base64.b64decode(readme_data["content"]).decode(
                    "utf-8", errors="replace"
                )
            except Exception as e:
                logger.warning("README decode failed: {}", e)

        signals.append(
            ReproSignal(
                name="has_readme",
                present=bool(readme_text),
                details=f"{len(readme_text)} chars" if readme_text else "no README detected",
                weight=0.10,
            )
        )
        readme_substantial = len(readme_text) > 1500 and any(
            k in readme_text.lower() for k in ("install", "run", "reproduce", "figure", "usage")
        )
        signals.append(
            ReproSignal(
                name="readme_substantial",
                present=readme_substantial,
                details=(
                    "README mentions install/run/reproduce/figure/usage"
                    if readme_substantial
                    else "thin or generic README"
                ),
                weight=0.15,
            )
        )

        # Tree (recursive)
        tree_data = await _gh_get_json(
            client,
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
        )
        paths: list[str] = []
        if isinstance(tree_data, dict):
            for node in tree_data.get("tree", []):
                if isinstance(node, dict) and node.get("type") == "blob":
                    paths.append(node.get("path", ""))

        path_lc = [p.lower() for p in paths]
        deps_present = any(PurePosixPath(p).name in DEPS_FILES for p in paths)
        signals.append(
            ReproSignal(
                name="has_dependencies_file",
                present=deps_present,
                details=", ".join(p for p in paths if PurePosixPath(p).name in DEPS_FILES)[:200]
                or None,
                weight=0.20,
            )
        )

        data_present = any(p.split("/", 1)[0].lower() in DATA_DIRS for p in paths)
        signals.append(
            ReproSignal(
                name="has_data_or_fixtures",
                present=data_present,
                details=("data/ or fixtures/ directory present" if data_present else None),
                weight=0.10,
            )
        )

        notebook_present = any(p.endswith(".ipynb") for p in paths) or any(
            p.split("/", 1)[0].lower() in NOTEBOOK_DIRS for p in paths
        )
        signals.append(
            ReproSignal(
                name="has_notebook",
                present=notebook_present,
                details=("notebook(s) present" if notebook_present else None),
                weight=0.10,
            )
        )

        fig_script = next((p for p in paths if LIKELY_FIG_RE.search(PurePosixPath(p).name)), None)
        if fig_script:
            recommended_entrypoint = (
                f"python {fig_script}" if fig_script.endswith(".py") else f"bash {fig_script}"
            )
        signals.append(
            ReproSignal(
                name="has_figure_script",
                present=bool(fig_script),
                details=fig_script,
                weight=0.20,
            )
        )

        recently = bool(pushed_at and pushed_at >= "2024-01-01")
        signals.append(
            ReproSignal(
                name="actively_maintained",
                present=recently,
                details=f"last push: {pushed_at or 'unknown'}",
                weight=0.10,
            )
        )

        permissive = spdx in {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"}
        signals.append(
            ReproSignal(
                name="permissive_license",
                present=permissive,
                details=spdx,
                weight=0.05,
            )
        )

        # Ignore unused locals lint
        _ = path_lc

    score = sum(s.weight for s in signals if s.present)
    score = round(min(1.0, score), 3)

    verdict: Literal["likely-reproducible", "partial", "unlikely", "insufficient-info"]
    if score >= 0.7:
        verdict = "likely-reproducible"
    elif score >= 0.45:
        verdict = "partial"
    elif score >= 0.2:
        verdict = "unlikely"
    else:
        verdict = "insufficient-info"

    notes_parts = [f"Score {score:.2f}/1.00 over {len(signals)} signals."]
    if recommended_entrypoint:
        notes_parts.append(f"Recommended entrypoint: `{recommended_entrypoint}`.")
    else:
        notes_parts.append("No obvious figure-generating script detected.")

    return ReproAssessment(
        paper_id=paper_id,
        repo_url=f"https://github.com/{owner}/{repo}",
        overall_score=score,
        verdict=verdict,
        signals=signals,
        recommended_entrypoint=recommended_entrypoint,
        notes=" ".join(notes_parts),
    )
