"""Feature protocol and registry.

Every dimension is a ``Feature``: given a :class:`Document` and a profile, it returns a
:class:`FeatureResult` (a [0, 1] score plus evidence spans). The scorer iterates the
registry, so adding a dimension later means writing one class and registering it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from slopscore.document import Document
from slopscore.models import Dimension, FeatureResult


@runtime_checkable
class Feature(Protocol):
    dimension: Dimension

    def extract(self, doc: Document, profile: str) -> FeatureResult: ...


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
