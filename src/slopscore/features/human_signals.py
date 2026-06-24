"""Signs of HUMAN writing — a negative signal that LOWERS the SlopScore.

WP:AISIGNS "Signs of human writing": plain copulas (is/has), plain verbs (wrote/used/tried vs
authored/utilized/attempted), superlatives/definitive statements ("the first", "one of the"),
hedges ("perhaps", "tends to"), and concrete numbers/dates. Empirically these are MORE common
in human Wikipedia prose than in LLM output (Geng & Trotta; PNAS Reinhart et al.).

Returns a [0,1] score (1 = dense human markers) and NO spans — it is a counterweight, not a
finding. The scorer gives this dimension a negative weight.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, FeatureResult

# Plain past-tense verbs LLMs tend to dress up (wrote->authored, used->utilized, tried->attempted).
_PLAIN_VERBS = re.compile(
    r"\b(?:wrote|used|made|found|showed|told|said|gave|took|went|began|built|tried|"
    r"died|moved|bought|sold|won|lost|ran|led|kept|held)\b",
    re.IGNORECASE,
)
# Definitive/superlative statements of fact (LLMs hedge away from these).
_SUPERLATIVE = re.compile(
    r"\b(?:the first|the only|the last|the oldest|the largest|the smallest|"
    r"one of the|the (?:first|second|third)\b)",
    re.IGNORECASE,
)
# Genuine hedges/intensifiers common in human prose (distinct from AI 'it is worth noting').
_HEDGES = re.compile(
    r"\b(?:perhaps|maybe|roughly|about|around|nearly|arguably|likely|seems? to|tends? to|"
    r"a (?:bit|little)|sort of|kind of)\b",
    re.IGNORECASE,
)
# Concrete numbers, years, measurements, money.
_CONCRETE = re.compile(r"\b\d[\d,.]*\b|\$\d|\b(?:19|20)\d{2}\b")

# Rate (per 100 words) of combined human markers at which the signal saturates.
_FULL_SCALE_PER_100 = 6.0


class HumanWritingSignals:
    dimension = Dimension.human_writing_signals

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        count = (
            len(_PLAIN_VERBS.findall(text))
            + 1.5 * len(_SUPERLATIVE.findall(text))
            + len(_HEDGES.findall(text))
            + len(_CONCRETE.findall(text))
        )
        rate = per_hundred_words(count, doc.word_count)
        return FeatureResult(
            dimension=self.dimension,
            score=saturating(rate, _FULL_SCALE_PER_100),
            spans=[],
        )


register(HumanWritingSignals())
