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
from typing import Literal

from fastmcp import FastMCP
from loguru import logger

from . import __version__
from .llm import is_anthropic_configured
from .narrative import build_narrative, classify_error_hint
from .schemas import (
    CodeRepo,
    CompositeError,
    CompositeStatus,
    CompositeStep,
    FullText,
    HealthReport,
    MethodsReproReview,
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
    version=__version__,
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


def _record_error(
    errors: list[CompositeError],
    step: CompositeStep,
    exc: Exception,
) -> None:
    """Append a structured, hint-enriched entry to the errors list."""
    error_type = type(exc).__name__
    message = str(exc)
    errors.append(
        CompositeError(
            step=step,
            error_type=error_type,
            message=message,
            hint=classify_error_hint(step, error_type, message),
        )
    )


@mcp.tool
async def methods_repro_review(input_str: str, model: str | None = None) -> MethodsReproReview:
    """Resolve a paper + extract methods + find its code repo + assess reproducibility — in one call.

    Returns a `MethodsReproReview` object. **Read `narrative` first** — it's a
    plain-English summary of everything retrieved, with every numeric score
    echoed in context (e.g. "moderate confidence (0.72)"). Then:

    - `status`: `"ok"` (all sub-steps succeeded), `"partial"` (some failed — see
      `errors`), or `"empty"` (couldn't even resolve the input paper).
    - `metadata`, `methods`, `code_repo`, `repro_assessment`: the structured
      sub-results. Any step that failed contributes `null` for its key;
      `null` means **unavailable**, not zero.
    - `errors`: list of `{step, error_type, message, hint}` — one entry per
      failed sub-step, with an actionable hint where the failure pattern is
      recognised (e.g. missing ANTHROPIC_API_KEY, rate-limit, 404, timeout).

    For the meaning of numeric scores and verdict buckets, see the
    "Scores & verdicts explained" section of the README.
    """
    errors: list[CompositeError] = []

    # 1. Metadata — hard requirement for every other step.
    try:
        metadata = await _get_paper_metadata(input_str)
    except Exception as e:
        _record_error(errors, "get_paper_metadata", e)
        return MethodsReproReview(
            status=CompositeStatus.EMPTY,
            narrative=build_narrative(None, None, None, None, errors),
            metadata=None,
            methods=None,
            code_repo=None,
            repro_assessment=None,
            errors=errors,
        )

    # 2. Full text (feeds methods + find_code_repo).
    full: FullText | None = None
    try:
        full = await _fetch_paper_text(input_str)
    except Exception as e:
        _record_error(errors, "fetch_paper_text", e)

    # 3. Methods (needs full text + Anthropic).
    methods: MethodsStructured | None = None
    if full is not None:
        try:
            methods = extract_methods_from_text(paper_id=metadata.paper_id, full=full, model=model)
        except Exception as e:
            _record_error(errors, "extract_methods", e)

    # 4. Repo lookup.
    code_repo: CodeRepo
    try:
        code_repo = await _find_code_repo(metadata=metadata, full_text=full.text if full else None)
    except Exception as e:
        _record_error(errors, "find_code_repo", e)
        code_repo = CodeRepo(
            paper_id=metadata.paper_id,
            repo_url=None,
            detection_method="none",
            confidence=0.0,
            notes=str(e),
        )

    # 5. Reproducibility heuristic (needs a repo URL).
    repro: ReproAssessment | None = None
    if code_repo.repo_url:
        try:
            repro = await _quick_repo_assessment(code_repo.repo_url, paper_id=metadata.paper_id)
        except Exception as e:
            _record_error(errors, "assess_repo_reproducibility", e)

    status = CompositeStatus.OK if not errors else CompositeStatus.PARTIAL

    return MethodsReproReview(
        status=status,
        narrative=build_narrative(metadata, methods, code_repo, repro, errors),
        metadata=metadata,
        methods=methods,
        code_repo=code_repo,
        repro_assessment=repro,
        errors=errors,
    )


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
