"""Formulaic structure: templated scaffolding phrases.

Runs the regex ruleset in ``data/patterns/formulaic.yaml`` and scores by severity-weighted
density per 100 words, with a repetition bonus when the same template recurs.
"""

from __future__ import annotations

from functools import lru_cache

from slopscore.document import Document
from slopscore.features._ruleset import SEVERITY_WEIGHT, Rule, find_matches, load_rules
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, FeatureResult

_FULL_SCALE_PER_100 = 3.0


@lru_cache(maxsize=1)
def _rules() -> list[Rule]:
    return load_rules("patterns", "formulaic.yaml")


class FormulaicPatterns:
    dimension = Dimension.formulaic_structure

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, _rules())
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        # Repetition bonus: a template firing more than once is more suspicious.
        seen: dict[str, int] = {}
        for s in spans:
            seen[s.rule_id] = seen.get(s.rule_id, 0) + 1
        repetition = sum(0.5 * (n - 1) for n in seen.values() if n > 1)
        rate = per_hundred_words(weighted + repetition, doc.word_count)
        return FeatureResult(
            dimension=self.dimension,
            score=saturating(rate, _FULL_SCALE_PER_100),
            spans=spans,
        )


register(FormulaicPatterns())
