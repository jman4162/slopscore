"""Combine feature results into a 0-100 SlopScore and assemble the Report.

Conservatism (v0.2): weak-alone dimensions are damped by a corroboration gate unless another
dimension co-fires; ``human_writing_signals`` enters with a negative weight; and the score
abstains from a confident label on very short or non-English input.
"""

from __future__ import annotations

import math

from slopscore.config import STRICTNESS_GAIN, Scorer, Settings
from slopscore.document import Document
from slopscore.features.base import registry
from slopscore.models import (
    STANDARD_WARNINGS,
    Dimension,
    Dimensions,
    Evidence,
    FeatureResult,
    InputMeta,
    Label,
    Report,
    Score,
    Severity,
    label_for_score,
)
from slopscore.scoring.confidence import abstain_reason, compute_confidence
from slopscore.scoring.profiles import profile_multipliers
from slopscore.scoring.weights import (
    BIAS,
    DEFAULT_WEIGHTS,
    ELEVATED,
    LONE_WEAK_DAMP,
    WEAK_DIMENSIONS,
)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _score_rules(
    by_dim: dict[Dimension, float], settings: Settings, elevated: set[Dimension]
) -> tuple[float, list[str]]:
    """Hand-set weighted sum with the corroboration gate. Returns (slop_score, gated_notes)."""
    multipliers = profile_multipliers(settings.profile)
    logit = BIAS
    gated_notes: list[str] = []
    for dim, weight in DEFAULT_WEIGHTS.items():
        value = by_dim.get(dim, 0.0)
        gate = 1.0
        if dim in WEAK_DIMENSIONS and dim in elevated and elevated == {dim}:
            gate = LONE_WEAK_DAMP
            gated_notes.append(dim.value)
        logit += weight * multipliers.get(dim, 1.0) * gate * value
    logit *= STRICTNESS_GAIN[settings.strictness]
    return round(100.0 * _sigmoid(logit), 1), gated_notes


def _score_ml(by_dim: dict[Dimension, float]) -> float:
    """Learned logistic-regression score over the raw dimension vector (no corroboration gate;
    the model's learned weights and calibration are the scoring rule)."""
    from slopscore.models import Dimensions
    from slopscore.scoring.model import feature_vector, load_model

    dims = Dimensions(**{d.value: v for d, v in by_dim.items()})
    return load_model().slop_score(feature_vector(dims))


def _assemble_evidence(
    results: list[FeatureResult],
    doc: Document,
    settings: Settings,
    warnings: list[str],
) -> list[Evidence]:
    """Collect spans, then apply per-rule disable, severity overrides, and inline suppression."""
    from slopscore.suppress import parse_suppressions

    known = frozenset(d.value for d in Dimension) | {
        e.rule_id for r in results for e in r.spans
    }
    suppressions = parse_suppressions(doc.original_text, known)
    if suppressions.unknown_names:
        warnings.insert(
            0,
            "Unknown name(s) in a slopscore suppression comment: "
            + ", ".join(sorted(suppressions.unknown_names)),
        )

    out: list[Evidence] = []
    for r in results:
        for e in r.spans:
            if e.rule_id in settings.disabled_rules:
                continue
            if suppressions.is_suppressed(e.start_char, e.rule_id, r.dimension.value):
                continue
            override = settings.rule_severity.get(e.rule_id)
            if override and override != e.severity.value:
                e = e.model_copy(update={"severity": Severity(override)})
            out.append(e)
    out.sort(key=lambda e: e.start_char)
    return out


def score_document(doc: Document, settings: Settings) -> Report:
    # Disabled dimensions skip their feature entirely (contribute 0 and emit no findings).
    results: list[FeatureResult] = [
        f.extract(doc, settings.profile)
        for f in registry()
        if f.dimension.value not in settings.disabled_dimensions
    ]
    by_dim: dict[Dimension, float] = {r.dimension: r.score for r in results}

    # Positive (slop-raising) dimensions that are elevated, ignoring the negative human signal.
    elevated: set[Dimension] = {
        d for d, v in by_dim.items() if v > ELEVATED and d is not Dimension.human_writing_signals
    }

    gated_notes: list[str] = []
    if settings.scorer is Scorer.ml:
        slop_score = _score_ml(by_dim)
    else:
        slop_score, gated_notes = _score_rules(by_dim, settings, elevated)

    confidence, conf_warnings = compute_confidence(doc, settings)
    abstained_reason = abstain_reason(doc, settings, elevated_count=len(elevated))

    label = label_for_score(slop_score)
    if abstained_reason is not None:
        # Cap the label at "mild" so an abstained scan never reads as a confident accusation.
        if label in (Label.elevated, Label.severe):
            label = Label.mild

    warnings = [*conf_warnings, *STANDARD_WARNINGS]
    if gated_notes:
        warnings.insert(
            0,
            "Damped (weak alone, no corroborating tell): "
            + ", ".join(sorted(gated_notes))
            + ". Use --strictness sensitive to include these.",
        )

    evidence = _assemble_evidence(results, doc, settings, warnings)

    return Report(
        input=InputMeta(
            source_type=doc.source_type,
            source=doc.source,
            profile=settings.profile,
            language=doc.language,
            word_count=doc.word_count,
        ),
        score=Score(
            slop_score=slop_score,
            label=label,
            confidence=confidence,
            strictness=settings.strictness.value,
            abstained=abstained_reason is not None,
            abstention_reason=abstained_reason,
        ),
        dimensions=Dimensions(**{d.value: v for d, v in by_dim.items()}),
        evidence=evidence,
        warnings=warnings,
        original_text=doc.original_text,
    )
