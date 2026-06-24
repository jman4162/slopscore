"""Prompt residue: high-confidence assistant artifacts.

Presence-based (not density-based): a single high-severity hit, like "as an AI language
model", drives the dimension near 1.0 regardless of document length.
"""

from __future__ import annotations

from functools import lru_cache

from slopscore.document import Document
from slopscore.features._ruleset import SEVERITY_WEIGHT, Rule, find_matches, load_rules
from slopscore.features.base import register, saturating
from slopscore.models import Dimension, FeatureResult

# One high-severity hit (weight 4) saturates the dimension.
_FULL_SCALE = 4.0


@lru_cache(maxsize=1)
def _rules() -> list[Rule]:
    return load_rules("patterns", "prompt_residue.yaml")


class PromptResidue:
    dimension = Dimension.prompt_residue

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, _rules())
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        return FeatureResult(
            dimension=self.dimension,
            score=saturating(weighted, _FULL_SCALE),
            spans=spans,
        )


register(PromptResidue())
