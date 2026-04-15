"""Tools: find_code_repo + reproducibility heuristics (no execution required).

The lightweight wedge: assess a paper's reproducibility from public GitHub
metadata + tree contents, without cloning or running anything.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal

import httpx
from loguru import logger

from ..schemas import CodeRepo, PaperMetadata, ReproAssessment, ReproSignal

GITHUB_URL_RE = re.compile(
    # Trailing char class rules out common sentence punctuation eating real repo
    # characters (e.g. "Paper2Agent ." → we want "Paper2Agent", not "Paper2Agen").
    r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?=/|\.git\b|[\s,.;:!?\])}>]|$)",
    re.I,
)
PWC_API = "https://paperswithcode.com/api/v1/papers"
USER_AGENT = "methods-mcp/0.1 (https://github.com/FlynnLachendro/methods-mcp)"

# Phrases that strongly suggest the GitHub URL following/preceding them is
# *the paper's own* repo, not a case-study reference.
STRONG_PHRASES: tuple[str, ...] = (
    "code availability",
    "code is available at",
    "publicly available at",
    "is available at",
    "we release our code",
    "we release the code",
    "we make our code",
    "implementation is available",
    "source code available",
    "our implementation",
    "our code",
    "this paper",
    "this work",
)
MEDIUM_PHRASES: tuple[str, ...] = (
    "code:",
    "github:",
    "available at",
    "code repository",
    "released at",
    "we provide",
)


def _normalise_repo_url(owner: str, repo: str) -> str:
    # `.rstrip(".git")` is a set-of-chars strip and chews trailing "." / "g" / "i"
    # / "t" characters off real repo names. Use `removesuffix` instead.
    return f"https://github.com/{owner}/{repo.removesuffix('.git')}"


@dataclass
class _RepoCandidate:
    url: str
    score: float = 0.0
    mentions: int = 0
    contexts: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _score_context(window: str) -> tuple[float, str | None]:
    """Return (score, matched-phrase) for the ±chars window around a URL."""
    w = window.lower()
    for p in STRONG_PHRASES:
        if p in w:
            return 10.0, p
    for p in MEDIUM_PHRASES:
        if p in w:
            return 5.0, p
    return 1.0, None


def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _gh_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def find_repos_in_text(text: str, *, pre_window: int = 100) -> list[_RepoCandidate]:
    """Find every GitHub URL in `text`, scored by the text that *precedes* it.

    We only look at ``pre_window`` chars *before* each URL (not after), because
    the text preceding a URL is what introduces it — post-URL text is usually
    the next sentence. This stops the "code availability" section header from
    bleeding backwards and scoring earlier case-study URLs.

    Score per mention: 10 if a STRONG phrase precedes the URL, 5 for MEDIUM,
    1 otherwise. Per repo (deduped): sum + 0.5 * (mentions - 1). Sorted best-first.
    """
    if not text:
        return []
    candidates: dict[str, _RepoCandidate] = {}
    for m in GITHUB_URL_RE.finditer(text):
        owner, repo = m.group(1), m.group(2)
        url = _normalise_repo_url(owner, repo)
        pre = text[max(0, m.start() - pre_window) : m.start()]
        s, matched = _score_context(pre)
        c = candidates.setdefault(url, _RepoCandidate(url=url))
        c.score += s
        c.mentions += 1
        c.contexts.append(pre.strip())
        if matched:
            c.reasons.append(f"phrase '{matched}'")
    for c in candidates.values():
        if c.mentions > 1:
            c.score += 0.5 * (c.mentions - 1)
            c.reasons.append(f"{c.mentions} mentions")
    return sorted(candidates.values(), key=lambda x: x.score, reverse=True)


def find_repo_in_text(text: str) -> str | None:
    """Best-scored GitHub URL in `text`, or None.

    Thin wrapper over :func:`find_repos_in_text` kept for stability / testing.
    """
    repos = find_repos_in_text(text)
    return repos[0].url if repos else None


async def find_code_repo(*, metadata: PaperMetadata, full_text: str | None = None) -> CodeRepo:
    """Discover a code repo for a paper.

    Strategy, in order:
      1. Papers With Code (arXiv-only, authoritative paper→repo mapping).
      2. Scored full-text scan — collect every GitHub URL, rank by surrounding
         phrases ("code availability", "our code", etc.) + mention count.
      3. Scored abstract scan (same approach, smaller corpus).
    """
    # 1. Papers With Code is the most authoritative signal — try it first.
    if metadata.source.value == "arxiv":
        try:
            async with httpx.AsyncClient(
                timeout=15.0, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.get(f"{PWC_API}/?arxiv_id={metadata.paper_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("results", []):
                        repo_url = r.get("repository_url")
                        if repo_url:
                            return CodeRepo(
                                paper_id=metadata.paper_id,
                                repo_url=repo_url,
                                detection_method="papers-with-code",
                                confidence=0.95,
                                notes="Resolved via Papers With Code API (authoritative).",
                            )
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Papers With Code lookup failed: {}", e)

    # 2. Full-text scored scan.
    if full_text:
        candidates = find_repos_in_text(full_text)
        if candidates:
            top = candidates[0]
            # Confidence scales with how decisive the top candidate was:
            # a lone URL gets ~0.7; a URL with a strong phrase + beating runners-up gets ~0.95.
            has_strong = top.score >= 10
            margin = top.score - (candidates[1].score if len(candidates) > 1 else 0.0)
            confidence = min(0.95, 0.6 + (0.2 if has_strong else 0.0) + min(margin, 10.0) * 0.015)
            notes = (
                f"Scored {len(candidates)} GitHub URL(s) in paper text; top={top.url} "
                f"(score {top.score:.1f}, {', '.join(top.reasons) or 'first match'})."
            )
            return CodeRepo(
                paper_id=metadata.paper_id,
                repo_url=top.url,
                detection_method="paper-text",
                confidence=round(confidence, 2),
                notes=notes,
            )

    # 3. Abstract fallback.
    if metadata.abstract:
        candidates = find_repos_in_text(metadata.abstract)
        if candidates:
            return CodeRepo(
                paper_id=metadata.paper_id,
                repo_url=candidates[0].url,
                detection_method="abstract-link",
                confidence=0.85,
                notes="Found GitHub URL in the abstract.",
            )

    return CodeRepo(
        paper_id=metadata.paper_id,
        repo_url=None,
        detection_method="none",
        confidence=0.0,
        notes="No GitHub URL found via Papers With Code, paper text, or abstract.",
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
    # Same footgun as 0.1.5: `.rstrip(".git")` strips any of ".gitT"; use
    # `removesuffix` so repo names ending in t/g/i/. survive intact.
    owner, repo = m.group(1), m.group(2).removesuffix(".git")

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
