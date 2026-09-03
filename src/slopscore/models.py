"""Pydantic data contracts for slopscore.

These models mirror the JSON output schema in the spec, so the report serializers in
``slopscore.report`` are thin and the JSON form is just ``Report.model_dump()``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.11.0"

# Disclaimers every report carries. The middle line encodes the core conservatism principle
# (corroborated by research: single tells are weak; ESL writers are over-flagged).
STANDARD_WARNINGS: tuple[str, ...] = (
    "This flags writing patterns, not authorship. It cannot prove text was written by AI.",
    "A single tell (one fancy word, one em dash) is weak alone; scores rise when tells co-occur.",
    "Scores are unreliable on short, translated, or non-native English text, "
    "which detectors over-flag (up to ~61% false positives in one study).",
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
    code = "code"


class Dimension(StrEnum):
    """The scored dimensions. Values match the JSON keys in ``Dimensions``."""

    # v0.1 dimensions
    lexical_markers = "lexical_markers"
    formulaic_structure = "formulaic_structure"
    genericity = "genericity"
    redundancy = "redundancy"
    cadence_sameness = "cadence_sameness"
    unsupported_claims = "unsupported_claims"
    prompt_residue = "prompt_residue"
    # v0.2 dimensions (mapped to WP:AISIGNS sections)
    significance_inflation = "significance_inflation"
    # v0.7: insight-signaling / pseudo-profundity ("load-bearing", "doing the real work").
    # Rules-only for now — deliberately excluded from the ML FEATURE_ORDER (no retrain needed).
    insight_signaling = "insight_signaling"
    # v0.9: performative candor / manufactured sincerity ("to be honest", "honest limits").
    # Fake vulnerability, as distinct from insight_signaling's fake insight and
    # weasel_attribution's fake evidence. Also rules-only (excluded from FEATURE_ORDER).
    performative_candor = "performative_candor"
    superficial_analysis = "superficial_analysis"
    weasel_attribution = "weasel_attribution"
    parallelism = "parallelism"
    copula_avoidance = "copula_avoidance"
    formatting_tells = "formatting_tells"
    # Negative signal: high score => more human-writing markers => LOWERS SlopScore.
    human_writing_signals = "human_writing_signals"


class Suggestion(BaseModel):
    """An opt-in, non-destructive rewrite suggestion for a finding (never auto-applied)."""

    text: str  # the proposed replacement for the span
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class EvidenceKind(StrEnum):
    """``finding``: a rule matched this span. ``summary``: a statistical dimension is pointing at
    the passage that drove its value; it explains the score but is not a rule hit, so it never
    trips ``--fail-on``, never enters SARIF, and never counts as a new baseline finding."""

    finding = "finding"
    summary = "summary"


class Evidence(BaseModel):
    """A single triggered finding. Offsets index the ORIGINAL source text."""

    rule_id: str
    severity: Severity
    span: str
    start_char: int
    end_char: int
    explanation: str
    suggestion: Suggestion | None = None
    kind: EvidenceKind = EvidenceKind.finding

    @property
    def is_summary(self) -> bool:
        return self.kind is EvidenceKind.summary


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
    significance_inflation: float = Field(default=0.0, ge=0.0, le=1.0)
    insight_signaling: float = Field(default=0.0, ge=0.0, le=1.0)
    performative_candor: float = Field(default=0.0, ge=0.0, le=1.0)
    superficial_analysis: float = Field(default=0.0, ge=0.0, le=1.0)
    weasel_attribution: float = Field(default=0.0, ge=0.0, le=1.0)
    parallelism: float = Field(default=0.0, ge=0.0, le=1.0)
    copula_avoidance: float = Field(default=0.0, ge=0.0, le=1.0)
    formatting_tells: float = Field(default=0.0, ge=0.0, le=1.0)
    human_writing_signals: float = Field(default=0.0, ge=0.0, le=1.0)
    optional_ai_detector: float | None = None


class BaselineComparison(BaseModel):
    """Per-dimension z-score deviation from a user's personal baseline profile."""

    profile_name: str
    deviations: dict[str, float] = Field(default_factory=dict)


# Mandatory caveat on every authorship signal — it is never folded into the SlopScore.
AUTHORSHIP_CAVEAT = (
    "Authorship signal — NOT evidence of authorship. Heuristic only; collapses on paraphrase, "
    "biased against non-native English, fails on newer models, unreliable on short text. "
    "Reported separately and never folded into the SlopScore. For curiosity, not accusation."
)


class DetectorResult(BaseModel):
    """A separated, optional authorship signal from an external detector (experimental)."""

    score: float = Field(ge=0.0, le=1.0)  # higher = more 'AI-like' per the detector
    method: str
    caveat: str = AUTHORSHIP_CAVEAT


class DimensionContribution(BaseModel):
    """One row of the score breakdown: how a dimension's value became logit."""

    dimension: str
    value: float
    weight: float
    multiplier: float = 1.0
    gate: float = 1.0
    logit: float
    # True for span-less dimensions (genericity, cadence, redundancy, human signals).
    statistical: bool = False
    findings: int = 0


class ScoreBreakdown(BaseModel):
    """Every point of the score, attributed. ``sigmoid(bias + gain * sum(positive logits) +
    human logit) * 100`` reproduces ``slop_score`` for the rules scorer."""

    bias: float
    gain: float
    corroboration: float  # multiplier applied to the weak dimensions, in [0.3, 1.0]
    contributions: list[DimensionContribution] = Field(default_factory=list)
    statistical_logit: float = 0.0  # sum of the logits of the span-less dimensions


class Score(BaseModel):
    slop_score: float = Field(ge=0.0, le=100.0)
    label: Label
    confidence: float = Field(ge=0.0, le=1.0)
    strictness: str
    # Set when the input is too short/uncertain to assign a confident label.
    abstained: bool = False
    abstention_reason: str | None = None


class Report(BaseModel):
    version: str = SCHEMA_VERSION
    input: InputMeta
    score: Score
    dimensions: Dimensions
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=lambda: list(STANDARD_WARNINGS))
    # Per-dimension attribution of the score (rules scorer; None under --scorer ml).
    breakdown: ScoreBreakdown | None = None
    baseline: BaselineComparison | None = None
    # Optional, separated authorship signal (never affects score/label). Caveat-bearing.
    authorship: DetectorResult | None = None
    # The text the evidence offsets index into (post-ingest; for Markdown, the extracted prose).
    # Needed to render HTML highlights and SARIF line/column regions.
    original_text: str = ""

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @property
    def findings(self) -> list[Evidence]:
        """Rule hits only: no statistical summaries, no advisory suggestions."""
        return [
            e for e in self.evidence if not e.is_summary and not e.rule_id.startswith("SUGGEST_")
        ]


def label_for_score(slop_score: float) -> Label:
    """Map a 0-100 SlopScore to its categorical label (spec thresholds)."""
    if slop_score < 25:
        return Label.low
    if slop_score < 50:
        return Label.mild
    if slop_score < 75:
        return Label.elevated
    return Label.severe
