"""Tool: extract_methods — LLM-driven structured methods extraction."""

from __future__ import annotations

from loguru import logger

from ..llm import DEFAULT_MODEL, extract_to_schema
from ..schemas import FullText, MethodsStructured

SYSTEM_PROMPT = """You are a meticulous research-methods extractor.

Given the *Methods* (or equivalent) section of an academic paper, you will emit
a single structured object describing the procedure. Be faithful to the source:
do NOT invent reagents, equipment, or steps that aren't named in the text.
If something is vague in the source, leave the corresponding field empty rather
than guess. Set `confidence` low (e.g. 0.3) if the methods section is sparse,
high (>=0.8) only if the paper gives explicit reagents / volumes / equipment.

`steps` should be the procedural backbone, in order. Each step is one logical
operation (e.g. "Lyse cells in RIPA buffer", "Run qPCR with primers X/Y").
`reagents`, `equipment`, `analyses` should de-duplicate items mentioned across
steps — list each one once with its role/purpose.

Always emit valid JSON conforming exactly to the tool's input_schema."""


def _select_methods_text(full: FullText, max_chars: int = 30_000) -> str:
    """Pick the slice of full text most likely to contain methods."""
    methods = full.sections.get("methods", "").strip()
    experiments = full.sections.get("experiments", "").strip()
    materials = full.sections.get("materials_and_methods", "").strip()
    candidates = [s for s in (methods, materials, experiments) if s]
    if candidates:
        joined = "\n\n".join(candidates)
        return joined[:max_chars]
    # No section split — give the model the start of the document
    return full.text[:max_chars]


def extract_methods_from_text(
    *, paper_id: str, full: FullText, model: str | None = None
) -> MethodsStructured:
    """Run schema-constrained extraction over a FullText object.

    The Pydantic model `MethodsStructured` is used as the LLM tool schema, so
    the response is guaranteed to match the schema (or the call raises).
    """
    methods_text = _select_methods_text(full)
    if not methods_text:
        logger.warning("No methods text available for paper_id={}", paper_id)

    user_prompt = f"""Paper ID: {paper_id}

Below is the methods-relevant text extracted from the paper. Produce a single
structured methods object describing what the authors actually did.

--- BEGIN PAPER METHODS TEXT ---
{methods_text}
--- END PAPER METHODS TEXT ---

Required: set `paper_id` to "{paper_id}" exactly. Set `extraction_model` to the
model you are (best guess) — the caller will overwrite this if needed.
"""

    result = extract_to_schema(
        schema_cls=MethodsStructured,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
    )

    # Force authoritative paper_id + model
    if result.paper_id != paper_id:
        result = result.model_copy(update={"paper_id": paper_id})
    target_model = model or DEFAULT_MODEL
    if result.extraction_model != target_model:
        result = result.model_copy(update={"extraction_model": target_model})
    return result
