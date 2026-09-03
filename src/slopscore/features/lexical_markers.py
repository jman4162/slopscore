"""Lexical marker overuse.

Matches whole-word AI-vocabulary markers from ``data/lexicons/markers.yaml`` and scores by
frequency per 100 words, with a cluster bonus when several markers crowd one sentence. Profile
weights tolerate genre-legitimate words (e.g. "robust" in technical writing). The raw word is
never proof on its own: this is a density signal.

The score is a pure function of the surviving spans (``score_spans``), so the scorer can drop
disabled or suppressed markers and recompute. Each span's weight comes from its lexicon category
(recovered from the ``LEXICAL_<CATEGORY>`` rule id), and the cluster bonus is recomputed from
span positions in original-text coordinates.
"""

from __future__ import annotations

import bisect
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
# Sentences with at least this many markers earn the cluster bonus.
_CLUSTER_MIN = 3
_CLUSTER_BONUS = 0.5


def _rule_id(cat: Category) -> str:
    return f"LEXICAL_{str(cat['_key']).upper()}"


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


@lru_cache(maxsize=1)
def _category_by_rule_id() -> dict[str, Category]:
    return {_rule_id(cat): cat for cat in _load_categories()}


def _profile_weight(cat: Category, profile: str) -> float:
    base = float(cat.get("weight", 1.0))
    overrides = cat.get("profile_weights") or {}
    return base * float(overrides.get(profile, 1.0))


class LexicalMarkers:
    dimension = Dimension.lexical_markers

    def rule_ids(self) -> frozenset[str]:
        return frozenset(_category_by_rule_id())

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        categories = _category_by_rule_id()
        weighted_hits = 0.0
        per_sentence: dict[int, int] = {}
        locator = _SentenceLocator(doc)
        for e in spans:
            cat = categories.get(e.rule_id)
            if cat is None:
                continue
            weighted_hits += _profile_weight(cat, profile)
            si = locator.index_of(e.start_char)
            per_sentence[si] = per_sentence.get(si, 0) + 1
        # Cluster bonus: sentences with several markers count extra.
        cluster_bonus = sum(_CLUSTER_BONUS for c in per_sentence.values() if c >= _CLUSTER_MIN)
        rate = per_hundred_words(weighted_hits + cluster_bonus, doc.word_count)
        return saturating(rate, _FULL_SCALE_PER_100)

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        spans: list[Evidence] = []
        for pattern, cat in _compiled():
            if _profile_weight(cat, profile) <= 0:
                continue
            severity = Severity(cat.get("severity", "low"))
            explanation = str(cat.get("explanation", "AI-associated marker word."))
            for m in pattern.finditer(text):
                spans.append(
                    doc.evidence(
                        rule_id=_rule_id(cat),
                        severity=severity,
                        clean_start=m.start(),
                        clean_end=m.end(),
                        explanation=explanation,
                    )
                )
        return FeatureResult(
            dimension=self.dimension, score=self.score_spans(doc, profile, spans), spans=spans
        )


class _SentenceLocator:
    """Maps an ORIGINAL-text offset to the index of the sentence containing it."""

    def __init__(self, doc: Document) -> None:
        bounds = [doc.mapper.to_original(s.start, s.end) for s in doc.sentences]
        self._starts = [b[0] for b in bounds]
        self._ends = [b[1] for b in bounds]

    def index_of(self, pos: int) -> int:
        i = bisect.bisect_right(self._starts, pos) - 1
        if i >= 0 and self._starts[i] <= pos < self._ends[i]:
            return i
        return -1


register(LexicalMarkers())
