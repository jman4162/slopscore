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
from slopscore.models import Dimension, FeatureResult

# Coefficient of variation in sentence length at/above which cadence is "varied" (sameness ~0).
_VARIED_CV = 0.6


class Cadence:
    dimension = Dimension.cadence_sameness

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        lengths = [len(s.text.split()) for s in doc.sentences if s.text.split()]
        if len(lengths) < 3:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])
        arr = np.array(lengths, dtype=float)
        mean = float(arr.mean())
        if mean == 0:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])
        cv = float(arr.std() / mean)
        # Low variation -> high sameness. Clamp to [0, 1].
        sameness = max(0.0, 1.0 - cv / _VARIED_CV)
        return FeatureResult(dimension=self.dimension, score=sameness, spans=[])


register(Cadence())
