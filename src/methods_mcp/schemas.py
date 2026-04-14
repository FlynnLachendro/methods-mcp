"""Pydantic schemas for tool inputs / outputs."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperSource(StrEnum):
    ARXIV = "arxiv"
    BIORXIV = "biorxiv"
    DOI = "doi"
    URL = "url"
    UNKNOWN = "unknown"


class PaperMetadata(BaseModel):
    """Canonical identifier + minimal bibliographic record for a paper."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(description="Canonical identifier (e.g. arXiv ID, DOI).")
    source: PaperSource
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_date: str | None = Field(default=None, description="ISO 8601 date when known.")
    primary_url: str
    pdf_url: str | None = None
    html_url: str | None = Field(default=None, description="ar5iv HTML URL for arXiv papers.")
    venue: str | None = None
    raw_input: str = Field(description="The original URL/ID the caller supplied.")


class FullText(BaseModel):
    """Best-effort full text of a paper, optionally segmented by section."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    text: str
    source_url: str
    extraction_method: Literal["arxiv-html", "pdf", "raw-text"]
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Section name (lowercased) -> text. Empty if extraction couldn't segment.",
    )
    char_count: int


class MethodStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    description: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)


class Reagent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: str | None = None
    role: str | None = None
    vendor: str | None = None


class Equipment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str | None = None
    settings: str | None = None


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    purpose: str | None = None
    software: str | None = None
    statistical_test: str | None = None


class MethodsStructured(BaseModel):
    """LLM-extracted, schema-validated methods section."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    summary: str = Field(description="2-3 sentence overview of the methods.")
    steps: list[MethodStep] = Field(default_factory=list)
    reagents: list[Reagent] = Field(default_factory=list)
    equipment: list[Equipment] = Field(default_factory=list)
    analyses: list[Analysis] = Field(default_factory=list)
    notes: str | None = Field(
        default=None,
        description="Free-form caveats from the extractor (e.g. 'methods section is sparse').",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="LLM self-reported confidence in the structured extraction."
    )
    extraction_model: str = Field(description="Model identifier used for extraction.")


class CodeRepo(BaseModel):
    """Detected code repository associated with a paper, if any."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str | None = None
    repo_url: str | None = None
    detection_method: Literal["paper-text", "abstract-link", "papers-with-code", "metadata", "none"]
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class ReproSignal(BaseModel):
    """One heuristic signal contributing to the reproducibility verdict."""

    model_config = ConfigDict(extra="forbid")

    name: str
    present: bool
    details: str | None = None
    weight: float = Field(ge=0.0, le=1.0)


class ReproAssessment(BaseModel):
    """Heuristic, no-execution-required reproducibility assessment of a code repo."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str | None = None
    repo_url: str
    overall_score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["likely-reproducible", "partial", "unlikely", "insufficient-info"]
    signals: list[ReproSignal] = Field(default_factory=list)
    recommended_entrypoint: str | None = Field(
        default=None,
        description="E.g. 'python make_figures.py' if a likely figure-generating script was found.",
    )
    notes: str


class PaperSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    mode: Literal["abstract", "tldr", "exec"]
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    methodology_oneliner: str
    extraction_model: str


class HealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: str = "methods-mcp"
    version: str
    anthropic_configured: bool
    transports: list[str]
