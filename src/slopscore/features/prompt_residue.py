"""Prompt residue: high-confidence assistant artifacts.

Presence-based up to 300 words: a single high-severity hit, like "as an AI language model",
saturates the dimension in a pasted chatbot reply. Above 300 words it becomes a rate, so one
quoted phrase in a long article about chatbots (a real false positive: 1,400 clean words scored
96.6 "severe") decays instead of convicting the whole document. The dimension stays a strong
corroborator, not a weak one: genuine residue in a short paste must still unlock the weak tells.
"""

from __future__ import annotations

from functools import lru_cache

from slopscore.document import Document
from slopscore.features._ruleset import SEVERITY_WEIGHT, Rule, find_matches, load_rules
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, Evidence, FeatureResult

# Documents at or under this length are scored by presence: the word count is floored here.
_PRESENCE_WORDS = 300
# One high-severity hit (weight 4) per _PRESENCE_WORDS saturates the dimension.
_FULL_SCALE_PER_100 = 4.0 * 100.0 / _PRESENCE_WORDS


@lru_cache(maxsize=1)
def _rules() -> list[Rule]:
    return load_rules("patterns", "prompt_residue.yaml")


class PromptResidue:
    dimension = Dimension.prompt_residue

    def rule_ids(self) -> frozenset[str]:
        return frozenset(r.rule_id for r in _rules())

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        rate = per_hundred_words(weighted, max(doc.word_count, _PRESENCE_WORDS))
        return saturating(rate, _FULL_SCALE_PER_100)

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, _rules())
        return FeatureResult(
            dimension=self.dimension, score=self.score_spans(doc, profile, spans), spans=spans
        )


register(PromptResidue())
