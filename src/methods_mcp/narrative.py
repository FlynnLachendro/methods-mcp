"""Plain-English narrative builder for the `methods_repro_review` composite.

The goal: a reader (human or agent) can look at `narrative` + `status` alone
and understand the whole result without reading the README. Numbers from the
inner Pydantic objects are echoed with qualitative labels ("moderate
confidence (0.72)") so the scores are self-describing in context.

Pure function, no I/O, deterministic. Safe to call with any combination of
None sub-results — it adapts the sentences to what's available.
"""

from __future__ import annotations

from .schemas import (
    CodeRepo,
    CompositeError,
    MethodsStructured,
    PaperMetadata,
    ReproAssessment,
    ReproSignal,
)

_SIGNAL_LABELS: dict[str, str] = {
    "has_readme": "README",
    "readme_substantial": "substantive README",
    "has_dependencies_file": "dependencies file",
    "has_data_or_fixtures": "data/fixtures directory",
    "has_notebook": "notebooks",
    "has_figure_script": "figure-plotting script",
    "actively_maintained": "recent activity",
    "permissive_license": "permissive license",
}

_DETECTION_BLURB: dict[str, str] = {
    "paper-text": "from an inline link in the paper text",
    "abstract-link": "from a link in the abstract",
    "papers-with-code": "via the Papers With Code API (authoritative)",
    "metadata": "from paper metadata",
    "none": "",
}

_VERDICT_GLOSS: dict[str, str] = {
    "likely-reproducible": "likely reproducible",
    "partial": "partially reproducible (some infrastructure present, gaps likely)",
    "unlikely": "unlikely to be reproducible without extra work",
    "insufficient-info": "not enough information to assess",
}


def describe_confidence(c: float) -> str:
    """Map a 0-1 confidence to a human label.

    Thresholds mirror the extraction prompt's own rubric: `>=0.8` = "high"
    (explicit reagents/volumes/equipment), `~0.3` = "low" (sparse methods),
    everything in between = "moderate".
    """
    if c >= 0.8:
        return "high"
    if c >= 0.4:
        return "moderate"
    return "low"


def split_signals(signals: list[ReproSignal]) -> tuple[list[str], list[str]]:
    """Return (present_labels, missing_labels) for a list of ReproSignal."""
    present = [_SIGNAL_LABELS.get(s.name, s.name) for s in signals if s.present]
    missing = [_SIGNAL_LABELS.get(s.name, s.name) for s in signals if not s.present]
    return present, missing


def classify_error_hint(step: str, error_type: str, message: str) -> str | None:
    """Produce a plain-English, actionable hint for a sub-step failure.

    Returns None when no pattern matches — callers should leave `hint` unset
    rather than fabricate generic advice. Ordered most-specific first so a
    narrow match (auth failure) beats a broad one (schema validation).
    """
    m = message.lower()
    t = error_type.lower()

    # Auth failures: "AuthenticationError", "invalid x-api-key", "401".
    if (
        "authenticationerror" in t
        or "invalid x-api-key" in m
        or "invalid_api_key" in m
        or "401" in m
        or "authentication" in m
    ):
        return (
            "Your ANTHROPIC_API_KEY appears to be invalid or expired. "
            "Check the key in your environment and regenerate it at "
            "https://console.anthropic.com if needed."
        )
    if "anthropic_api_key" in m or "api key not set" in m:
        return "Set ANTHROPIC_API_KEY in your environment to enable LLM-powered tools."
    if "timeout" in m or "timed out" in m:
        return "The remote service timed out. Retry in a moment."
    if "rate limit" in m or "too many requests" in m or " 429" in m:
        return (
            "Rate-limited. Wait a minute and retry. For GitHub, setting "
            "GITHUB_TOKEN raises your limit from 60/hr to 5000/hr."
        )
    if step == "find_code_repo" and "404" in m:
        return "The declared repo URL returned 404 — it may have moved or been deleted."
    # Schema-validation failures only — narrow the check so it doesn't catch
    # "invalid x-api-key" or other non-schema errors that happen to contain "invalid".
    if step == "extract_methods" and "validationerror" in t:
        return (
            "The LLM returned a structurally-invalid response twice. "
            "Try a different model via the `model` argument or METHODS_MCP_MODEL."
        )
    if step == "fetch_paper_text" and ("pdf" in m or "encrypted" in m):
        return (
            "PDF parsing failed — the paper may be scanned, encrypted, or "
            "malformed. If this is an arXiv paper, try `prefer='html'` to "
            "force the ar5iv HTML path."
        )
    return None


def _author_blurb(authors: list[str]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return f" by {authors[0]}"
    return f" by {authors[0]} et al."


def build_narrative(
    metadata: PaperMetadata | None,
    methods: MethodsStructured | None,
    code_repo: CodeRepo | None,
    repro: ReproAssessment | None,
    errors: list[CompositeError],
) -> str:
    """Assemble the full plain-English summary from whatever sub-results exist."""
    if metadata is None:
        reason = errors[0].message if errors else "no reason reported"
        return f"Couldn't resolve the paper input. Reason: {reason}."

    sentences: list[str] = []

    date_blurb = f", {metadata.publication_date[:10]}" if metadata.publication_date else ""
    sentences.append(
        f"Resolved the paper: '{metadata.title}'{_author_blurb(metadata.authors)} "
        f"({metadata.source.value} {metadata.paper_id}{date_blurb})."
    )

    if methods is not None:
        n = len(methods.steps)
        qual = describe_confidence(methods.confidence)
        note = f" — {methods.notes.rstrip('.')}" if methods.notes else ""
        sentences.append(
            f"Extracted {n} methods step{'s' if n != 1 else ''} at {qual} "
            f"self-reported confidence ({methods.confidence:.2f}){note}."
        )
    elif any(e.step == "extract_methods" for e in errors):
        sentences.append("Methods extraction failed — see `errors` for details and a hint.")

    if code_repo is not None and code_repo.repo_url:
        how = _DETECTION_BLURB.get(code_repo.detection_method, "")
        how_part = f" {how}" if how else ""
        sentences.append(
            f"Detected the associated code repository {code_repo.repo_url}"
            f"{how_part} (detection confidence {code_repo.confidence:.2f})."
        )
    elif code_repo is not None:
        sentences.append(
            "No GitHub repository was detected via Papers With Code, paper text, "
            "or abstract — the reproducibility assessment is therefore unavailable."
        )

    if repro is not None:
        # Empty-signals shape = degraded "couldn't reach GitHub" response from
        # the no-clone assessor. Don't pretend we scored anything.
        if not repro.signals:
            sentences.append(
                "The reproducibility assessment was unavailable — "
                f"{repro.notes.rstrip('.')}. "
                "If you're hitting GitHub's unauthenticated rate limit (60/hr), "
                "set GITHUB_TOKEN to raise it to 5000/hr."
            )
        else:
            present, missing = split_signals(repro.signals)
            present_txt = ", ".join(present) if present else "none"
            missing_txt = ", ".join(missing) if missing else "none"
            entry = (
                f" Suggested entrypoint: `{repro.recommended_entrypoint}`."
                if repro.recommended_entrypoint
                else ""
            )
            sentences.append(
                f"The repo scored {repro.overall_score:.2f}/1.00 on the reproducibility "
                f"heuristic — verdict: {_VERDICT_GLOSS.get(repro.verdict, repro.verdict)}. "
                f"Present signals: {present_txt}. Missing: {missing_txt}.{entry}"
            )

    if errors:
        failed = sorted({e.step for e in errors})
        sentences.append(
            f"Partial result: {len(errors)} sub-step(s) failed "
            f"({', '.join(failed)}). See `errors` for details and hints."
        )

    return " ".join(sentences)
