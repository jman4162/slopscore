"""Confidence in the score, driven by input length and language.

Per the spec, short text is unreliable (Turnitin suppresses <300 words). Confidence is a
product of penalty factors in [0, 1] and is reported separately from the score itself.
"""

from __future__ import annotations

from slopscore.config import Settings
from slopscore.document import Document


def compute_confidence(doc: Document, settings: Settings) -> tuple[float, list[str]]:
    warnings: list[str] = []
    factors: list[float] = []

    words = doc.word_count
    if words < 100:
        factors.append(0.25)
        warnings.append(
            f"Very short text ({words} words): score is low-confidence and easily skewed."
        )
    elif words < settings.min_reliable_words:
        factors.append(0.6)
        warnings.append(
            f"Short text ({words} words, under {settings.min_reliable_words}): "
            "treat the score as indicative only."
        )
    elif words < 1000:
        factors.append(0.85)
    else:
        factors.append(1.0)

    if doc.language != "en":
        factors.append(0.5)
        warnings.append(
            f"Detected language '{doc.language}': slopscore is tuned for English; "
            "confidence reduced."
        )
    elif doc.language_confidence < 0.7:
        factors.append(0.8)

    confidence = 1.0
    for f in factors:
        confidence *= f
    return round(confidence, 3), warnings
