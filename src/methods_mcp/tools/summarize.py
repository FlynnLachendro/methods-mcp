"""Tool: summarize_paper — short structured summaries in three modes."""

from __future__ import annotations

from ..llm import DEFAULT_MODEL, extract_to_schema
from ..schemas import FullText, PaperSummary

SYSTEM_PROMPT_TEMPLATE = """You are an expert research summarizer.

Mode = {mode}.
- "abstract": tight, 2-3 sentence summary close to the authors' own framing.
- "tldr": a one-line takeaway suitable for a daily-paper feed.
- "exec": an executive summary — what they did, what they found, why it matters.

`key_findings` is 2-5 short bullet points (one sentence each). The
`methodology_oneliner` is exactly one sentence describing the technical approach.
Do not invent results; if uncertain, hedge."""


def summarize_paper_from_text(
    *,
    paper_id: str,
    full: FullText,
    mode: str,
    model: str | None = None,
) -> PaperSummary:
    if mode not in {"abstract", "tldr", "exec"}:
        raise ValueError(f"mode must be one of abstract|tldr|exec, got: {mode}")

    # Use abstract + intro + conclusion if available; else first ~12k chars
    abstract = full.sections.get("abstract", "")
    intro = full.sections.get("introduction", "")
    conclusion = full.sections.get("conclusion", "")
    if abstract or intro or conclusion:
        text_block = "\n\n".join(s for s in (abstract, intro, conclusion) if s)[:15_000]
    else:
        text_block = full.text[:15_000]

    user_prompt = f"""Paper ID: {paper_id}

--- PAPER TEXT (excerpts) ---
{text_block}
--- END PAPER TEXT ---

Required: set `paper_id` to "{paper_id}" exactly, `mode` to "{mode}".
"""
    result = extract_to_schema(
        schema_cls=PaperSummary,
        system_prompt=SYSTEM_PROMPT_TEMPLATE.format(mode=mode),
        user_prompt=user_prompt,
        model=model,
    )
    target_model = model or DEFAULT_MODEL
    return result.model_copy(
        update={
            "paper_id": paper_id,
            "mode": mode,
            "extraction_model": target_model,
        }
    )
