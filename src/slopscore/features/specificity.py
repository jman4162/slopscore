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

import bisect

import regex as re

from slopscore.document import Document
from slopscore.features._nlp import is_nlp_available, parse
from slopscore.features.base import register, saturating
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity
from slopscore.spans import TextSpan

RULE_GENERIC_SENTENCE = "GENERIC_SENTENCE"
_SUMMARY_LIMIT = 3

# Digit runs cover years, so years are not matched separately (they used to be counted twice).
_NUMBER = re.compile(r"\b\d[\d,.]*\b")
_URL = re.compile(r"https?://\S+")
# Proper-noun heuristic: a capitalized word not at the start of a sentence.
_PROPER = re.compile(r"(?<=[a-z,;:]\s)\p{Lu}\p{Ll}+")
# Acronyms (API, CI, HTTP2) and code-like identifiers (snake_case, camelCase, dotted.paths,
# `backticked`): concrete references that technical and README prose is built from.
_ACRONYM = re.compile(r"\b\p{Lu}[\p{Lu}\d]{1,}\b")
_IDENTIFIER = re.compile(r"`[^`\n]+`|\b\w+_\w+\b|\b[a-z]+[A-Z]\w+\b|\b\w+\.\w+\(\)")
# Spelled-out cardinals. Off by default: genericity is calibrated against the digit-only count,
# and widening it there would shift every document's score. metadiscourse opts in, because it
# asks a narrower question — does this sentence carry a fact at all? — and "roughly three in
# five households returned the form" plainly does. "one" and "half" are excluded: they are far
# more often pronouns and idioms ("one of the", "half the time") than quantities.
_SPELLED_NUMBER = re.compile(
    r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty"
    r"|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|trillion|dozen)\b",
    re.IGNORECASE,
)

# Evidence items per sentence at or above which the text is "specific enough" (genericity ~0).
_TARGET_PER_SENTENCE = 0.75


def concrete_evidence_count(text: str, *, spelled_numbers: bool = False) -> int:
    """Count the concrete references in a span: numbers, URLs, proper nouns, acronyms, ids.

    Shared with ``features/metadiscourse.py``, which uses it as a predicate (is this sentence
    carrying any fact at all?) rather than as a score. Kept here because this is where the
    regexes and the "no name, number, date, URL, or identifier" wording already live.
    """
    return (
        len(_NUMBER.findall(text))
        + len(_URL.findall(text))
        + len(_PROPER.findall(text))
        + len(_ACRONYM.findall(text))
        + len(_IDENTIFIER.findall(text))
        + (len(_SPELLED_NUMBER.findall(text)) if spelled_numbers else 0)
    )


def _per_sentence_regex(sentences: list[TextSpan]) -> list[int]:
    return [concrete_evidence_count(s.text) for s in sentences]


def _per_sentence_nlp(text: str, sentences: list[TextSpan]) -> list[int]:
    """Named entities bucketed by sentence (plus URLs and identifiers), when spaCy is available."""
    try:
        ents = parse(text).ents  # PERSON/ORG/GPE/DATE/CARDINAL/QUANTITY/...
    except Exception:
        return _per_sentence_regex(sentences)
    counts = [len(_URL.findall(s.text)) + len(_IDENTIFIER.findall(s.text)) for s in sentences]
    starts = [s.start for s in sentences]
    for ent in ents:
        i = bisect.bisect_right(starts, ent.start_char) - 1
        if 0 <= i < len(counts):
            counts[i] += 1
    return counts


class Specificity:
    dimension = Dimension.genericity

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        sentences = [s for s in doc.sentences if s.text.strip()]
        if not sentences:
            items = float(concrete_evidence_count(doc.cleaned_text))
            genericity = 1.0 - saturating(items, _TARGET_PER_SENTENCE)
            return FeatureResult(dimension=self.dimension, score=genericity, spans=[])
        per_sentence = (
            _per_sentence_nlp(doc.cleaned_text, sentences)
            if is_nlp_available()
            else _per_sentence_regex(sentences)
        )
        density = sum(per_sentence) / len(sentences)
        # Invert: full specificity -> 0 genericity; no specificity -> 1.
        genericity = 1.0 - saturating(density, _TARGET_PER_SENTENCE)
        spans: list[Evidence] = []
        if genericity > 0:
            empty = [s for s, n in zip(sentences, per_sentence, strict=True) if n == 0]
            k = len(empty)
            for s in sorted(empty, key=lambda s: -len(s.text))[:_SUMMARY_LIMIT]:
                spans.append(
                    doc.evidence(
                        rule_id=RULE_GENERIC_SENTENCE,
                        severity=Severity.low,
                        clean_start=s.start,
                        clean_end=s.end,
                        explanation=(
                            f"{k} of {len(sentences)} sentences carry no name, number, date, "
                            f"URL, or identifier (genericity {genericity:.2f}); this is one."
                        ),
                        kind=EvidenceKind.summary,
                    )
                )
            spans.sort(key=lambda e: e.start_char)
        return FeatureResult(dimension=self.dimension, score=genericity, spans=spans)


register(Specificity())
