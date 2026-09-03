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


def per_hundred_words(count: float, word_count: int) -> float:
    """Normalize a raw (possibly weighted) count to a rate per 100 words."""
    if word_count <= 0:
        return 0.0
    return 100.0 * count / word_count


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


def severity_rate_score(doc: Document, spans: list[Evidence], full_scale: float) -> float:
    """The shared rule-pack scoring rule: severity-weighted hits per 100 words, saturating."""
    weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
    return saturating(per_hundred_words(weighted, doc.word_count), full_scale)
