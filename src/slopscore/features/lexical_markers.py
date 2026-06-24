"""Lexical marker overuse.

Matches whole-word AI-vocabulary markers from ``data/lexicons/markers.yaml`` and scores by
frequency per 100 words, with a cluster bonus when several markers crowd one sentence. Profile
weights tolerate genre-legitimate words (e.g. "robust" in technical writing). The raw word is
never proof on its own — this is a density signal.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, Evidence, FeatureResult, Severity

Category = dict[str, Any]

# A marker rate of this many hits per 100 words saturates the dimension to ~1.0.
_FULL_SCALE_PER_100 = 4.0


@lru_cache(maxsize=1)
def _load_categories() -> list[Category]:
    with data_path("lexicons", "markers.yaml").open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    categories: list[Category] = []
    for key, cat in (raw["categories"] if raw else {}).items():
        cat["_key"] = key
        categories.append(cat)
    return categories


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[re.Pattern[str], Category]]:
    out: list[tuple[re.Pattern[str], Category]] = []
    for cat in _load_categories():
        terms = [re.escape(t) for t in cat["terms"]]
        pattern = re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.IGNORECASE)
        out.append((pattern, cat))
    return out


def _profile_weight(cat: Category, profile: str) -> float:
    base = float(cat.get("weight", 1.0))
    overrides = cat.get("profile_weights") or {}
    return base * float(overrides.get(profile, 1.0))


class LexicalMarkers:
    dimension = Dimension.lexical_markers

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        spans: list[Evidence] = []
        weighted_hits = 0.0
        per_sentence: dict[int, int] = {}

        sentence_index = _SentenceLocator(doc)
        for pattern, cat in _compiled():
            weight = _profile_weight(cat, profile)
            if weight <= 0:
                continue
            severity = Severity(cat.get("severity", "low"))
            explanation = str(cat.get("explanation", "AI-associated marker word."))
            for m in pattern.finditer(text):
                weighted_hits += weight
                spans.append(
                    doc.evidence(
                        rule_id=f"LEXICAL_{str(cat['_key']).upper()}",
                        severity=severity,
                        clean_start=m.start(),
                        clean_end=m.end(),
                        explanation=explanation,
                    )
                )
                si = sentence_index.index_of(m.start())
                per_sentence[si] = per_sentence.get(si, 0) + 1

        # Cluster bonus: sentences with 3+ markers count 1.5x.
        cluster_bonus = sum(0.5 for c in per_sentence.values() if c >= 3)
        rate = per_hundred_words(weighted_hits + cluster_bonus, doc.word_count)
        score = saturating(rate, _FULL_SCALE_PER_100)
        return FeatureResult(dimension=self.dimension, score=score, spans=spans)


class _SentenceLocator:
    """Maps a cleaned-text offset to the index of the sentence containing it."""

    def __init__(self, doc: Document) -> None:
        self._bounds = [(s.start, s.end) for s in doc.sentences]

    def index_of(self, pos: int) -> int:
        for i, (start, end) in enumerate(self._bounds):
            if start <= pos < end:
                return i
        return -1


register(LexicalMarkers())
