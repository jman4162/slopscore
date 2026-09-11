"""Feature protocol and registry.

Every dimension is a ``Feature``: given a :class:`Document` and a profile, it returns a
:class:`FeatureResult` (a [0, 1] score plus evidence spans). The scorer iterates the
registry, so adding a dimension later means writing one class and registering it.

Span-backed features also implement :class:`SpanScored`: their score is a pure function of the
spans they emitted, so the scorer can drop disabled or suppressed spans FIRST and recompute the
dimension from what survives. ``extract`` must route through the same ``score_spans`` so that
``score_spans(doc, profile, result.spans) == result.score`` holds by construction. Statistical
features (genericity, cadence, redundancy, human signals) have nothing to filter and do not
implement it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from slopscore.document import Document
from slopscore.models import Dimension, Evidence, FeatureResult, Severity


@runtime_checkable
class Feature(Protocol):
    dimension: Dimension

    def extract(self, doc: Document, profile: str) -> FeatureResult: ...


@runtime_checkable
class SpanScored(Protocol):
    """A feature whose score is a pure function of its surviving spans."""

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float: ...


@runtime_checkable
class Cataloged(Protocol):
    """A feature that can list every rule id it may emit (for suppression-name validation)."""

    def rule_ids(self) -> frozenset[str]: ...


_REGISTRY: list[Feature] = []


def register(feature: Feature) -> Feature:
    """Add a feature to the global registry (idempotent by dimension)."""
    if any(f.dimension is feature.dimension for f in _REGISTRY):
        return feature
    _REGISTRY.append(feature)
    return feature


def registry() -> list[Feature]:
    return list(_REGISTRY)


# Optional floor on the density denominator, opt in per call site via ``min_words``.
#
# It is NOT applied by default, and that is a measured decision rather than caution. Floored
# globally it did two things its own rationale did not predict. It raised scores on short text
# carrying human signal, because a saturated slop dimension cannot be lowered any further while
# ``human_writing_signals`` -- a negative weight -- is shrunk, removing the counterweight: a
# 36-word slop paragraph with a date and a price went 75.4 up to 80.0. And it inverted
# ``--by-paragraph``: under a floor a paragraph's score tracks its absolute hit COUNT rather than
# its density, so a 57-word mild paragraph outranked a 16-word dense one (12.6 against 10.1,
# where unfloored the order is the right way round at 16.4 against 20.6). Ranking paragraphs is
# the entire purpose of that flag.
#
# ``metadiscourse`` opts in because it is the one dimension that is neither weak-damped nor
# corroborating, so a single low-severity marker saturating it in a 17-word document had nothing
# else holding it back: a clean benchmark row scored 50.2, and 20.2 with the floor.
#
# The trade-off is real and is not papered over: below 100 words that dimension scores on hit
# COUNT rather than density, so it does not rank short paragraphs the way ``--by-paragraph``
# wants. Removing the floor does not restore density there -- the rate saturates at 1.0 instead,
# for one hit in eleven words as much as four in forty-four -- so the choice is between
# count-based and pinned-at-maximum, and count-based is the one that does not convict clean
# short text. ``tests/test_conservatism.py`` pins both halves of that comparison.
MIN_RATE_WORDS = 100


def per_hundred_words(count: float, word_count: int, min_words: int = 0) -> float:
    """Normalize a raw (possibly weighted) count to a rate per 100 words.

    ``min_words`` floors the denominator; see the note above for why it is off by default.
    """
    if word_count <= 0:
        return 0.0
    return 100.0 * count / max(word_count, min_words)


def saturating(rate: float, full_scale: float) -> float:
    """Map a non-negative rate to [0, 1], reaching ~1.0 near ``full_scale``."""
    if full_scale <= 0:
        return 0.0
    return min(1.0, rate / full_scale)


# Severity weights used when turning a set of hits into a [0, 1] score.
SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.low: 1.0,
    Severity.medium: 2.0,
    Severity.high: 4.0,
}


def severity_rate_score(
    doc: Document, spans: list[Evidence], full_scale: float, min_words: int = 0
) -> float:
    """The shared rule-pack scoring rule: severity-weighted hits per 100 words, saturating."""
    weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
    return saturating(per_hundred_words(weighted, doc.word_count, min_words), full_scale)
