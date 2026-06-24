"""Combine feature results into a 0-100 SlopScore and assemble the Report."""

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
    Report,
    Score,
    label_for_score,
)
from slopscore.scoring.confidence import compute_confidence
from slopscore.scoring.profiles import profile_multipliers
from slopscore.scoring.weights import BIAS, DEFAULT_WEIGHTS


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_document(doc: Document, settings: Settings) -> Report:
    results: list[FeatureResult] = [f.extract(doc, settings.profile) for f in registry()]
    by_dim: dict[Dimension, float] = {r.dimension: r.score for r in results}

    multipliers = profile_multipliers(settings.profile)
    logit = BIAS
    for dim, weight in DEFAULT_WEIGHTS.items():
        value = by_dim.get(dim, 0.0)
        logit += weight * multipliers.get(dim, 1.0) * value

    logit *= STRICTNESS_GAIN[settings.strictness]
    slop_score = round(100.0 * _sigmoid(logit), 1)

    confidence, conf_warnings = compute_confidence(doc, settings)

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
            label=label_for_score(slop_score),
            confidence=confidence,
            strictness=settings.strictness.value,
        ),
        dimensions=Dimensions(**{d.value: v for d, v in by_dim.items()}),
        evidence=evidence,
        warnings=[*conf_warnings, *STANDARD_WARNINGS],
    )
