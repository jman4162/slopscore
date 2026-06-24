"""Specificity / evidence density -> genericity dimension (thin v0.1 implementation).

Counts concrete-evidence signals (numbers, dates, URLs, and a capitalization-based
proper-noun heuristic) per sentence. Low evidence density -> high genericity score. NER-backed
proper-noun detection is deferred to the ``[nlp]`` extra in v0.2.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features.base import register, saturating
from slopscore.models import Dimension, FeatureResult

_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_URL = re.compile(r"https?://\S+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
# Proper-noun heuristic: a capitalized word not at the start of a sentence.
_PROPER = re.compile(r"(?<=[a-z,;:]\s)\p{Lu}\p{Ll}+")

# Evidence items per sentence at or above which the text is "specific enough" (genericity ~0).
_TARGET_PER_SENTENCE = 1.5


class Specificity:
    dimension = Dimension.genericity

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        n_sentences = max(len(doc.sentences), 1)
        evidence_items = (
            len(_NUMBER.findall(text))
            + len(_URL.findall(text))
            + len(_YEAR.findall(text))
            + len(_PROPER.findall(text))
        )
        density = evidence_items / n_sentences
        # Invert: full specificity -> 0 genericity; no specificity -> 1.
        genericity = 1.0 - saturating(density, _TARGET_PER_SENTENCE)
        return FeatureResult(dimension=self.dimension, score=genericity, spans=[])


register(Specificity())
