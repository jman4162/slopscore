"""Combine feature results into a 0-100 SlopScore and assemble the Report.

Conservatism (v0.2): weak-alone dimensions are damped by a corroboration gate unless another
dimension co-fires; ``human_writing_signals`` enters with a negative weight; and the score
abstains from a confident label on very short or non-English input.
"""

from __future__ import annotations

import math

from slopscore.config import STRICTNESS_GAIN, Settings
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


def score_document(doc: Document, settings: Settings) -> Report:
    results: list[FeatureResult] = [f.extract(doc, settings.profile) for f in registry()]
    by_dim: dict[Dimension, float] = {r.dimension: r.score for r in results}

    # Positive (slop-raising) dimensions that are elevated, ignoring the negative human signal.
    elevated = {
        d
        for d, v in by_dim.items()
        if v > ELEVATED and d is not Dimension.human_writing_signals
    }

    multipliers = profile_multipliers(settings.profile)
    logit = BIAS
    gated_notes: list[str] = []
    for dim, weight in DEFAULT_WEIGHTS.items():
        value = by_dim.get(dim, 0.0)
        gate = 1.0
        if dim in WEAK_DIMENSIONS and dim in elevated and elevated == {dim}:
            # This weak dimension is the ONLY elevated signal -> damp it.
            gate = LONE_WEAK_DAMP
            gated_notes.append(dim.value)
        logit += weight * multipliers.get(dim, 1.0) * gate * value

    logit *= STRICTNESS_GAIN[settings.strictness]
    slop_score = round(100.0 * _sigmoid(logit), 1)

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

    evidence: list[Evidence] = [span for r in results for span in r.spans]
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
    )
