"""Cadence sameness: collapse of sentence-length variety (thin v0.1 implementation).

Pure-tokenization statistics, no POS tagging. Uniform sentence lengths (low coefficient of
variation) read as monotonous, machine-even prose -> high sameness.

A burstiness signal (penalize uniform mid-length clustering) was tried and reverted: it regressed
the non-native English fairness slice (FPR 0.00 -> 0.17). Sentence-length features are too entangled
with non-native writing style to use safely without richer, fairness-aware features. POS/syntactic
cadence is deferred to the ``[nlp]`` extra.
"""

from __future__ import annotations

import numpy as np

from slopscore.document import Document
from slopscore.features.base import register
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity

# Coefficient of variation in sentence length at/above which cadence is "varied" (sameness ~0).
_VARIED_CV = 0.6
# A sentence is "same length" as the document mean when within this fraction of it.
_RUN_TOLERANCE = 0.2
_RUN_MIN = 3
RULE_UNIFORM_RUN = "CADENCE_UNIFORM_RUN"
_NOT_PROSE = frozenset({"heading", "list_item"})


class Cadence:
    dimension = Dimension.cadence_sameness

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        # Headings and list items are not prose cadence: a bullet list is uniform by design.
        sentences = [
            s
            for s in doc.sentences
            if s.text.split() and not doc.in_block_kind(s.start, _NOT_PROSE)
        ]
        lengths = [len(s.text.split()) for s in sentences]
        if len(lengths) < 3:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])
        arr = np.array(lengths, dtype=float)
        mean = float(arr.mean())
        if mean == 0:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])
        cv = float(arr.std() / mean)
        # Low variation -> high sameness. Clamp to [0, 1].
        sameness = max(0.0, 1.0 - cv / _VARIED_CV)
        spans: list[Evidence] = []
        if sameness > 0:
            lo_i, hi_i = _longest_run(lengths, mean)
            if hi_i - lo_i >= _RUN_MIN:
                run = sentences[lo_i:hi_i]
                lo, hi = min(lengths[lo_i:hi_i]), max(lengths[lo_i:hi_i])
                spans.append(
                    doc.evidence(
                        rule_id=RULE_UNIFORM_RUN,
                        severity=Severity.low,
                        clean_start=run[0].start,
                        clean_end=run[-1].end,
                        explanation=(
                            f"{len(run)} consecutive sentences of {lo} to {hi} words around a "
                            f"{mean:.0f}-word mean (length CV {cv:.2f}, sameness {sameness:.2f})."
                        ),
                        kind=EvidenceKind.summary,
                    )
                )
        return FeatureResult(dimension=self.dimension, score=sameness, spans=spans)


def _longest_run(lengths: list[int], mean: float) -> tuple[int, int]:
    """[start, end) of the longest run of sentences within the tolerance band of the mean."""
    best = (0, 0)
    start = 0
    for i in range(len(lengths) + 1):
        inside = i < len(lengths) and abs(lengths[i] - mean) <= _RUN_TOLERANCE * mean
        if inside:
            continue
        if i - start > best[1] - best[0]:
            best = (start, i)
        start = i + 1
    return best


register(Cadence())
