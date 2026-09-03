"""Combine feature results into a 0-100 SlopScore and assemble the Report.

Conservatism: weak-alone dimensions are damped by a corroboration gate unless a strong,
span-backed dimension co-fires; ``human_writing_signals`` enters with a negative weight; and the
score abstains from a confident label on very short or non-English input.

Ordering matters: disabled rules, inline suppressions, and severity overrides are applied to each
feature's spans BEFORE its score is computed (``SpanScored.score_spans``), so silencing a rule
removes its points as well as its evidence.
"""

from __future__ import annotations

import math

from slopscore.config import STRICTNESS_GAIN, Scorer, Settings
from slopscore.document import Document
from slopscore.features.base import Feature, SpanScored, registry
from slopscore.models import (
    STANDARD_WARNINGS,
    Dimension,
    DimensionContribution,
    Dimensions,
    Evidence,
    FeatureResult,
    InputMeta,
    Label,
    Report,
    Score,
    ScoreBreakdown,
    Severity,
    label_for_score,
)
from slopscore.scoring.confidence import abstain_reason, compute_confidence
from slopscore.scoring.profiles import profile_multipliers
from slopscore.scoring.weights import (
    BIAS,
    CORROBORATING_DIMENSIONS,
    DEFAULT_WEIGHTS,
    ELEVATED,
    STATISTICAL_DIMENSIONS,
    WEAK_DIMENSIONS,
    weak_gate,
)
from slopscore.suppress import Suppressions


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _score_rules(
    by_dim: dict[Dimension, float],
    settings: Settings,
    findings: dict[Dimension, int] | None = None,
) -> tuple[float, list[str], ScoreBreakdown]:
    """Hand-set weighted sum with the corroboration gate.

    Returns ``(slop_score, gated_notes, breakdown)``. ``logit = BIAS + gain * S_pos + w_human *
    human`` where ``S_pos`` is the gated, profile-weighted sum over the slop-raising dimensions.
    The strictness gain scales only the evidence sum: scaling the bias as well made
    "conservative" score HIGHER than "sensitive" on clean text.
    """
    multipliers = profile_multipliers(settings.profile)
    strongest = max((by_dim.get(d, 0.0) for d in CORROBORATING_DIMENSIONS), default=0.0)
    gate = weak_gate(strongest)
    gain = STRICTNESS_GAIN[settings.strictness]
    gated_notes = [d.value for d in WEAK_DIMENSIONS if gate < 1.0 and by_dim.get(d, 0.0) > ELEVATED]
    counts = findings or {}

    positive = 0.0
    human = 0.0
    rows: list[DimensionContribution] = []
    for dim, weight in DEFAULT_WEIGHTS.items():
        value = by_dim.get(dim, 0.0)
        if dim is Dimension.human_writing_signals:
            human = weight * value
            rows.append(
                DimensionContribution(
                    dimension=dim.value,
                    value=value,
                    weight=weight,
                    logit=round(human, 4),
                    statistical=True,
                )
            )
            continue
        dim_gate = gate if dim in WEAK_DIMENSIONS else 1.0
        multiplier = multipliers.get(dim, 1.0)
        contribution = weight * multiplier * dim_gate * value
        positive += contribution
        rows.append(
            DimensionContribution(
                dimension=dim.value,
                value=value,
                weight=weight,
                multiplier=multiplier,
                gate=dim_gate,
                logit=round(gain * contribution, 4),
                statistical=dim in STATISTICAL_DIMENSIONS,
                findings=counts.get(dim, 0),
            )
        )
    logit = BIAS + gain * positive + human
    breakdown = ScoreBreakdown(
        bias=BIAS,
        gain=gain,
        corroboration=round(gate, 4),
        contributions=rows,
        statistical_logit=round(sum(r.logit for r in rows if r.statistical), 4),
    )
    return round(100.0 * _sigmoid(logit), 1), sorted(gated_notes), breakdown


def _score_ml(by_dim: dict[Dimension, float]) -> float:
    """Learned logistic-regression score over the raw dimension vector (no corroboration gate;
    the model's learned weights and calibration are the scoring rule)."""
    from slopscore.scoring.model import feature_vector, load_model

    dims = Dimensions(**{d.value: v for d, v in by_dim.items()})
    return load_model().slop_score(feature_vector(dims))


def _filter_spans(
    result: FeatureResult, settings: Settings, suppressions: Suppressions
) -> tuple[list[Evidence], bool]:
    """Apply per-rule disable, inline suppression, and severity overrides to one feature's spans.

    Returns the surviving spans and whether anything changed (so an unchanged feature keeps its
    already-computed score without a second pass).
    """
    kept: list[Evidence] = []
    changed = False
    for e in result.spans:
        if e.rule_id in settings.disabled_rules or suppressions.is_suppressed(
            e.start_char, e.rule_id, result.dimension.value
        ):
            changed = True
            continue
        override = settings.rule_severity.get(e.rule_id)
        if override and override != e.severity.value:
            e = e.model_copy(update={"severity": Severity(override)})
            changed = True
        kept.append(e)
    return kept, changed


def _extract_filtered(
    feature: Feature,
    doc: Document,
    settings: Settings,
    suppressions: Suppressions,
    *,
    broad: bool = False,
) -> FeatureResult:
    """Run one feature, drop its silenced spans, and rescore it from what survives."""
    if broad:
        result = feature.extract(doc, settings.profile, broad=True)  # type: ignore[call-arg]
    else:
        result = feature.extract(doc, settings.profile)
    kept, changed = _filter_spans(result, settings, suppressions)
    if not changed:
        return result
    if isinstance(feature, SpanScored):
        score = feature.score_spans(doc, settings.profile, kept)
        return FeatureResult(dimension=result.dimension, score=score, spans=kept)
    return result.model_copy(update={"spans": kept})


def score_document(doc: Document, settings: Settings) -> Report:
    from slopscore.features.catalog import known_suppression_names
    from slopscore.suppress import parse_suppressions

    warnings: list[str] = []
    suppressions = parse_suppressions(doc.original_text, known_suppression_names())
    if suppressions.unknown_names:
        warnings.append(
            "Unknown name(s) in a slopscore suppression comment: "
            + ", ".join(sorted(suppressions.unknown_names))
        )

    # Disabled dimensions skip their feature entirely (contribute 0 and emit no findings).
    results: list[FeatureResult] = [
        _extract_filtered(f, doc, settings, suppressions)
        for f in registry()
        if f.dimension.value not in settings.disabled_dimensions
    ]

    # Opt-in broad tier: re-score each broad-capable phrase pack over core + broad rules (mirrors
    # the settings.suggest special-case). Off by default so dimensions stay conservative.
    if settings.broad_rules:
        from slopscore.features.phrase_packs import broad_packs

        for pack in broad_packs():
            if pack.dimension.value in settings.disabled_dimensions:
                continue
            broad_result = _extract_filtered(pack, doc, settings, suppressions, broad=True)
            results = [broad_result if r.dimension is pack.dimension else r for r in results]

    by_dim: dict[Dimension, float] = {r.dimension: r.score for r in results}

    gated_notes: list[str] = []
    breakdown: ScoreBreakdown | None = None
    if settings.scorer is Scorer.ml:
        slop_score = _score_ml(by_dim)
    else:
        counts = {r.dimension: sum(1 for e in r.spans if not e.is_summary) for r in results}
        slop_score, gated_notes, breakdown = _score_rules(by_dim, settings, counts)

    confidence, conf_warnings = compute_confidence(doc, settings)
    abstained_reason = abstain_reason(doc, settings)

    label = label_for_score(slop_score)
    if abstained_reason is not None:
        # Cap the label at "mild" so an abstained scan never reads as a confident accusation.
        if label in (Label.elevated, Label.severe):
            label = Label.mild

    if gated_notes:
        warnings.append(
            "Damped (weak alone, no corroborating tell): "
            + ", ".join(gated_notes)
            + ". These dimensions count in full only when a strong tell co-fires."
        )
    warnings.extend(conf_warnings)
    warnings.extend(STANDARD_WARNINGS)

    evidence: list[Evidence] = [e for r in results for e in r.spans]
    if settings.suggest:
        from slopscore.features.suggestions import find_suggestions

        evidence.extend(
            e for e in find_suggestions(doc) if e.rule_id not in settings.disabled_rules
        )
    evidence.sort(key=lambda e: e.start_char)

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
        breakdown=breakdown,
        original_text=doc.original_text,
    )
