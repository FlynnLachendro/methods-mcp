"""methods-mcp FastMCP server entrypoint.

Exposes a small, sharply-scoped tool surface for AI agents that need to:
- canonicalise a paper reference,
- pull its full text,
- extract a structured methods object via Claude,
- find the associated code repo,
- assess that repo's reproducibility heuristically,
- summarise the paper at three depths.

Run via stdio (default for Claude Code / Claude Desktop):
    methods-mcp
or HTTP transport:
    methods-mcp --transport http --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

import argparse
from typing import Any, Literal

from fastmcp import FastMCP
from loguru import logger

from . import __version__
from .llm import is_anthropic_configured
from .schemas import (
    CodeRepo,
    FullText,
    HealthReport,
    MethodsStructured,
    PaperMetadata,
    PaperSummary,
    ReproAssessment,
)
from .tools.fetch import fetch_paper_text as _fetch_paper_text
from .tools.fetch import get_paper_metadata as _get_paper_metadata
from .tools.methods import extract_methods_from_text
from .tools.repo import find_code_repo as _find_code_repo
from .tools.repo import quick_repo_assessment as _quick_repo_assessment
from .tools.summarize import summarize_paper_from_text

mcp: FastMCP = FastMCP(
    name="methods-mcp",
    instructions=(
        "Lightweight on-demand MCP for academic-paper methods extraction and code-repo "
        "reproducibility heuristics. Pair with paper-mcp (Bhvaik) for broader paper "
        "search/citation tooling — methods-mcp focuses on the structured-methods + repro layer."
    ),
)


@mcp.tool
async def health() -> HealthReport:
    """Return a small health report — confirms the server is alive and configured."""
    return HealthReport(
        version=__version__,
        anthropic_configured=is_anthropic_configured(),
        transports=["stdio", "http"],
    )


@mcp.tool
async def get_paper_metadata(input_str: str) -> PaperMetadata:
    """Resolve an arXiv ID/URL, bioRxiv URL, DOI, or generic URL to canonical metadata.

    For arXiv inputs this hits the arXiv export API to fetch title/authors/abstract.
    Other sources return the resolved URL with empty bibliographic fields (cheap by design).
    """
    return await _get_paper_metadata(input_str)


@mcp.tool
async def fetch_paper_text(input_str: str, prefer: str = "auto") -> FullText:
    """Return best-effort full text + section split for a paper.

    prefer: one of "auto" (default), "html" (force ar5iv HTML — arXiv only), or "pdf".
    Sections are normalised to lowercase canonical names: abstract, introduction,
    methods, experiments, results, discussion, conclusion, limitations, related_work.
    """
    return await _fetch_paper_text(input_str, prefer=prefer)


@mcp.tool
async def extract_methods(input_str: str, model: str | None = None) -> MethodsStructured:
    """Extract a structured methods object from a paper.

    Pulls full text, isolates the methods-relevant section(s), then asks Claude
    (default: claude-sonnet-4-6) to fill out a Pydantic schema with steps,
    reagents, equipment, and analyses. Validation-enforced — invalid responses
    trigger one repair attempt before raising.

    Requires ANTHROPIC_API_KEY in the server's environment.
    """
    metadata = await _get_paper_metadata(input_str)
    full = await _fetch_paper_text(input_str)
    return extract_methods_from_text(paper_id=metadata.paper_id, full=full, model=model)


@mcp.tool
async def find_code_repo(input_str: str) -> CodeRepo:
    """Discover the code repo (if any) associated with a paper.

    Strategy: scan the paper's full text and abstract for github.com URLs;
    fall back to Papers With Code lookup for arXiv papers.
    """
    metadata = await _get_paper_metadata(input_str)
    try:
        full = await _fetch_paper_text(input_str)
        return await _find_code_repo(metadata=metadata, full_text=full.text)
    except Exception as e:
        logger.warning("Couldn't fetch full text for repo discovery: {}", e)
        return await _find_code_repo(metadata=metadata, full_text=None)


@mcp.tool
async def assess_repo_reproducibility(
    repo_url: str, paper_id: str | None = None
) -> ReproAssessment:
    """Heuristic, no-clone reproducibility assessment of a GitHub repo.

    Returns a verdict (likely-reproducible / partial / unlikely / insufficient-info)
    plus weighted signals: README quality, dependency files, fixture data,
    notebooks, figure-generating scripts, recent maintenance, license. No code
    is downloaded or executed. Set GITHUB_TOKEN to raise the API rate limit.
    """
    return await _quick_repo_assessment(repo_url, paper_id=paper_id)


@mcp.tool
async def summarize_paper(
    input_str: str, mode: Literal["abstract", "tldr", "exec"] = "tldr", model: str | None = None
) -> PaperSummary:
    """Generate an LLM summary of a paper in one of three modes.

    abstract = 2-3 sentences close to the authors' framing.
    tldr     = one-line takeaway.
    exec     = executive summary (what / found / why-it-matters).
    """
    metadata = await _get_paper_metadata(input_str)
    full = await _fetch_paper_text(input_str)
    return summarize_paper_from_text(paper_id=metadata.paper_id, full=full, mode=mode, model=model)


@mcp.tool
async def methods_repro_review(input_str: str, model: str | None = None) -> dict[str, Any]:
    """Composite tool: extract methods + find repo + assess reproducibility, in one call.

    Convenience wrapper that an agent can call once and get the full picture.
    Returns a dict with keys: metadata, methods, code_repo, repro_assessment.
    Any sub-step that fails contributes a null and a `_errors` list entry.
    """
    errors: list[str] = []
    metadata = await _get_paper_metadata(input_str)

    full: FullText | None = None
    try:
        full = await _fetch_paper_text(input_str)
    except Exception as e:
        errors.append(f"fetch_paper_text failed: {e}")

    methods: MethodsStructured | None = None
    if full is not None:
        try:
            methods = extract_methods_from_text(paper_id=metadata.paper_id, full=full, model=model)
        except Exception as e:
            errors.append(f"extract_methods failed: {e}")

    code_repo: CodeRepo
    try:
        code_repo = await _find_code_repo(metadata=metadata, full_text=full.text if full else None)
    except Exception as e:
        errors.append(f"find_code_repo failed: {e}")
        code_repo = CodeRepo(
            paper_id=metadata.paper_id,
            repo_url=None,
            detection_method="none",
            confidence=0.0,
            notes=str(e),
        )

    repro: ReproAssessment | None = None
    if code_repo.repo_url:
        try:
            repro = await _quick_repo_assessment(code_repo.repo_url, paper_id=metadata.paper_id)
        except Exception as e:
            errors.append(f"assess_repo_reproducibility failed: {e}")

    return {
        "metadata": metadata.model_dump(mode="json"),
        "methods": methods.model_dump(mode="json") if methods else None,
        "code_repo": code_repo.model_dump(mode="json"),
        "repro_assessment": repro.model_dump(mode="json") if repro else None,
        "_errors": errors,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="methods-mcp", description="methods-mcp FastMCP server")
    p.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport for the MCP server. Default stdio (Claude Code / Desktop).",
    )
    p.add_argument("--host", default="127.0.0.1", help="Host (http/sse only).")
    p.add_argument("--port", type=int, default=8765, help="Port (http/sse only).")
    p.add_argument("--version", action="version", version=f"methods-mcp {__version__}")
    return p


def main() -> None:
    """Console-script entry point. Parses argv and starts the FastMCP server."""
    args = _build_arg_parser().parse_args()
    logger.info("methods-mcp {} starting on {}", __version__, args.transport)
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
