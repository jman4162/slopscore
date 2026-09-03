"""Specificity / evidence density -> genericity dimension.

Counts concrete-evidence signals per sentence; low density -> high genericity. The default path
uses regex (numbers, URLs, acronyms, code-like identifiers, a capitalization proper-noun
heuristic). When the ``[nlp]`` extra is installed, named-entity density (people, places,
organizations, dates, quantities) replaces the brittle proper-noun regex; the regex remains the
fallback.

This is a STATISTICAL dimension: it emits no spans and it cannot tell abstract human prose from
abstract machine prose (both have zero evidence items). It is weighted low in the scorer and it
never corroborates a weak tell. Measured densities that set ``_TARGET_PER_SENTENCE``: concrete
narrative 2.2 items/sentence, technical documentation 0.3 (0.9 with identifiers), a project README
0.4 (0.8 with acronyms), plain non-native English 0.1, first-person reflective prose 0.0.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features._nlp import is_nlp_available, parse
from slopscore.features.base import register, saturating
from slopscore.models import Dimension, FeatureResult

# Digit runs cover years, so years are not matched separately (they used to be counted twice).
_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_URL = re.compile(r"https?://\S+")
# Proper-noun heuristic: a capitalized word not at the start of a sentence.
_PROPER = re.compile(r"(?<=[a-z,;:]\s)\p{Lu}\p{Ll}+")
# Acronyms (API, CI, HTTP2) and code-like identifiers (snake_case, camelCase, dotted.paths,
# `backticked`): concrete references that technical and README prose is built from.
_ACRONYM = re.compile(r"\b\p{Lu}[\p{Lu}\d]{1,}\b")
_IDENTIFIER = re.compile(r"`[^`\n]+`|\b\w+_\w+\b|\b[a-z]+[A-Z]\w+\b|\b\w+\.\w+\(\)")

# Evidence items per sentence at or above which the text is "specific enough" (genericity ~0).
_TARGET_PER_SENTENCE = 0.75


def _regex_evidence(text: str) -> int:
    return (
        len(_NUMBER.findall(text))
        + len(_URL.findall(text))
        + len(_PROPER.findall(text))
        + len(_ACRONYM.findall(text))
        + len(_IDENTIFIER.findall(text))
    )


def _nlp_evidence(text: str) -> int:
    """Named-entity density (concrete references) plus URLs and identifiers, when spaCy is
    available."""
    try:
        ents = len(parse(text).ents)  # PERSON/ORG/GPE/DATE/CARDINAL/QUANTITY/...
    except Exception:
        return _regex_evidence(text)
    return ents + len(_URL.findall(text)) + len(_IDENTIFIER.findall(text))


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
