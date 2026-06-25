"""Specificity / evidence density -> genericity dimension.

Counts concrete-evidence signals per sentence; low density -> high genericity. The default path
uses regex (numbers, dates, URLs, a capitalization proper-noun heuristic). When the ``[nlp]`` extra
is installed, named-entity density (people, places, organizations, dates, quantities) replaces the
brittle proper-noun regex for a more accurate specificity estimate; the regex remains the fallback.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features._nlp import is_nlp_available, parse
from slopscore.features.base import register, saturating
from slopscore.models import Dimension, FeatureResult

_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_URL = re.compile(r"https?://\S+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
# Proper-noun heuristic: a capitalized word not at the start of a sentence.
_PROPER = re.compile(r"(?<=[a-z,;:]\s)\p{Lu}\p{Ll}+")

# Evidence items per sentence at or above which the text is "specific enough" (genericity ~0).
_TARGET_PER_SENTENCE = 1.5


def _regex_evidence(text: str) -> int:
    return (
        len(_NUMBER.findall(text))
        + len(_URL.findall(text))
        + len(_YEAR.findall(text))
        + len(_PROPER.findall(text))
    )


def _nlp_evidence(text: str) -> int:
    """Named-entity density (concrete references) plus URLs, when spaCy is available."""
    try:
        ents = len(parse(text).ents)  # PERSON/ORG/GPE/DATE/CARDINAL/QUANTITY/...
    except Exception:
        return _regex_evidence(text)
    return ents + len(_URL.findall(text))


class Specificity:
    dimension = Dimension.genericity

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        n_sentences = max(len(doc.sentences), 1)
        evidence_items = _nlp_evidence(text) if is_nlp_available() else _regex_evidence(text)
        density = evidence_items / n_sentences
        # Invert: full specificity -> 0 genericity; no specificity -> 1.
        genericity = 1.0 - saturating(density, _TARGET_PER_SENTENCE)
        return FeatureResult(dimension=self.dimension, score=genericity, spans=[])


register(Specificity())
