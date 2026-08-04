"""Phrase-pack dimensions: significance inflation, weasel/over-attribution, unsupported claims,
insight signaling, and performative candor.

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

# Phrase packs that carry an opt-in broad tier (populated in __init__). The scorer re-scores each
# of these over core+broad rules when --broad is set.
_BROAD_PACKS: list[_PhrasePack] = []


def broad_packs() -> list[_PhrasePack]:
    """Phrase packs that have a ``--broad`` tier, in registration order."""
    return list(_BROAD_PACKS)


class _PhrasePack:
    """A dimension backed by a directory of YAML phrase rules.

    An optional ``broad_category`` holds an extra, opt-in tier of higher-false-positive rules that
    only score when ``extract(..., broad=True)`` is requested (the scorer sets this from the
    ``--broad`` flag). The core tier stays the default so the dimension is conservative by default.
    """

    def __init__(
        self,
        dimension: Dimension,
        category: str,
        full_scale: float,
        broad_category: str | None = None,
    ) -> None:
        self.dimension = dimension
        self._category = category
        self._full_scale = full_scale
        self._broad_category = broad_category
        if broad_category is not None:
            _BROAD_PACKS.append(self)

    @lru_cache(maxsize=1)  # noqa: B019  (one instance per dimension; cache is fine)
    def _rules(self) -> list[Rule]:
        return load_rules_from_directory("patterns", self._category)

    @lru_cache(maxsize=1)  # noqa: B019  (one instance per dimension; cache is fine)
    def _broad_rules(self) -> list[Rule]:
        if self._broad_category is None:
            return []
        return load_rules_from_directory("patterns", self._broad_category)

    def extract(self, doc: Document, profile: str, broad: bool = False) -> FeatureResult:
        rules = self._rules() + (self._broad_rules() if broad else [])
        spans = find_matches(doc, rules)
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
WeaselAttribution = _PhrasePack(
    Dimension.weasel_attribution,
    "attribution",
    full_scale=3.0,
    broad_category="attribution_broad",
)
UnsupportedClaims = _PhrasePack(Dimension.unsupported_claims, "claims", full_scale=3.0)
# Insight-signaling / pseudo-profundity (v0.7). The broad tier is opt-in via ``--broad``.
InsightSignaling = _PhrasePack(
    Dimension.insight_signaling,
    "insight_signaling",
    full_scale=3.0,
    broad_category="insight_signaling_broad",
)

# Performative candor / manufactured sincerity (v0.9). The broad tier is opt-in via ``--broad``.
# full_scale is 4.0 rather than the 3.0 the other packs use: candor markers have the highest
# legitimate-human overlap of any dimension here, and at 3.0 a single low-severity hit in a
# 60-word doc scores 0.56 — over the corroboration gate's ELEVATED threshold. At 4.0 it is 0.42,
# under it, with no practical difference at realistic document lengths.
PerformativeCandor = _PhrasePack(
    Dimension.performative_candor,
    "performative_candor",
    full_scale=4.0,
    broad_category="performative_candor_broad",
)

register(SignificanceInflation)
register(WeaselAttribution)
register(UnsupportedClaims)
register(InsightSignaling)
register(PerformativeCandor)
