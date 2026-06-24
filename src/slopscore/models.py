"""Pydantic data contracts for slopscore.

These models mirror the JSON output schema in the spec, so the report serializers in
``slopscore.report`` are thin and the JSON form is just ``Report.model_dump()``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"

# The two disclaimers that every report carries, per the spec.
STANDARD_WARNINGS: tuple[str, ...] = (
    "This is not proof of AI authorship.",
    "Scores are less reliable on short, translated, or non-native English text.",
)


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Label(StrEnum):
    low = "low"
    mild = "mild"
    elevated = "elevated"
    severe = "severe"


class SourceType(StrEnum):
    text = "text"
    markdown = "markdown"
    json = "json"
    website = "website"


class Dimension(StrEnum):
    """The scored dimensions. Values match the JSON keys in ``Dimensions``."""

    lexical_markers = "lexical_markers"
    formulaic_structure = "formulaic_structure"
    genericity = "genericity"
    redundancy = "redundancy"
    cadence_sameness = "cadence_sameness"
    unsupported_claims = "unsupported_claims"
    prompt_residue = "prompt_residue"


class Evidence(BaseModel):
    """A single triggered finding. Offsets index the ORIGINAL source text."""

    rule_id: str
    severity: Severity
    span: str
    start_char: int
    end_char: int
    explanation: str


class FeatureResult(BaseModel):
    """What every feature extractor returns: a [0, 1] score plus its evidence."""

    dimension: Dimension
    score: float = Field(ge=0.0, le=1.0)
    spans: list[Evidence] = Field(default_factory=list)


class InputMeta(BaseModel):
    source_type: SourceType
    source: str
    profile: str
    language: str
    word_count: int


class Dimensions(BaseModel):
    lexical_markers: float = Field(default=0.0, ge=0.0, le=1.0)
    formulaic_structure: float = Field(default=0.0, ge=0.0, le=1.0)
    genericity: float = Field(default=0.0, ge=0.0, le=1.0)
    redundancy: float = Field(default=0.0, ge=0.0, le=1.0)
    cadence_sameness: float = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_claims: float = Field(default=0.0, ge=0.0, le=1.0)
    prompt_residue: float = Field(default=0.0, ge=0.0, le=1.0)
    optional_ai_detector: float | None = None


class Score(BaseModel):
    slop_score: float = Field(ge=0.0, le=100.0)
    label: Label
    confidence: float = Field(ge=0.0, le=1.0)
    strictness: str


class Report(BaseModel):
    version: str = SCHEMA_VERSION
    input: InputMeta
    score: Score
    dimensions: Dimensions
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=lambda: list(STANDARD_WARNINGS))

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)


def label_for_score(slop_score: float) -> Label:
    """Map a 0-100 SlopScore to its categorical label (spec thresholds)."""
    if slop_score < 25:
        return Label.low
    if slop_score < 50:
        return Label.mild
    if slop_score < 75:
        return Label.elevated
    return Label.severe
