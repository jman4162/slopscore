"""Phrase-pack dimensions: significance inflation and weasel/over-attribution.

Both are pure regex phrase packs loaded from ``data/patterns/<category>/``, scored by
severity-weighted density per 100 words (same shape as formulaic_patterns). New patterns are
added by dropping a YAML file in the category directory — no code change.
"""

from __future__ import annotations

from functools import lru_cache

from slopscore.document import Document
from slopscore.features._ruleset import (
    SEVERITY_WEIGHT,
    Rule,
    find_matches,
    load_rules_from_directory,
)
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, FeatureResult


class _PhrasePack:
    """A dimension backed by a directory of YAML phrase rules."""

    def __init__(self, dimension: Dimension, category: str, full_scale: float) -> None:
        self.dimension = dimension
        self._category = category
        self._full_scale = full_scale

    @lru_cache(maxsize=1)  # noqa: B019  (one instance per dimension; cache is fine)
    def _rules(self) -> list[Rule]:
        return load_rules_from_directory("patterns", self._category)

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, self._rules())
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        rate = per_hundred_words(weighted, doc.word_count)
        return FeatureResult(
            dimension=self.dimension,
            score=saturating(rate, self._full_scale),
            spans=spans,
        )


SignificanceInflation = _PhrasePack(
    Dimension.significance_inflation, "significance", full_scale=3.0
)
WeaselAttribution = _PhrasePack(Dimension.weasel_attribution, "attribution", full_scale=3.0)
UnsupportedClaims = _PhrasePack(Dimension.unsupported_claims, "claims", full_scale=3.0)

register(SignificanceInflation)
register(WeaselAttribution)
register(UnsupportedClaims)
