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


# Below this word count a confident slop label is unreliable, so we abstain.
_ABSTAIN_WORDS = 100


def abstain_reason(doc: Document, settings: Settings, *, elevated_count: int) -> str | None:
    """Return a reason to abstain from a confident label, or None to score normally.

    Abstaining caps the reported label at "mild" — slopscore refuses to call a text severe when
    the evidence base is too thin to be fair (short text, non-English, or no corroborating tell).
    """
    if doc.word_count < _ABSTAIN_WORDS:
        return (
            f"Only {doc.word_count} words: too short to assign a confident label "
            f"(reliable above ~{settings.min_reliable_words})."
        )
    if doc.language != "en":
        return (
            f"Detected language '{doc.language}': slopscore is tuned for English and "
            "over-flags other languages; label withheld."
        )
    return None
