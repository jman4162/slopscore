"""Subgroup false-positive-rate evaluation.

The fairness risk for an AI-pattern detector is over-flagging plain or non-native-English prose
(Liang et al. 2023: ~61% FP on TOEFL essays). These helpers measure FPR / abstention per subgroup
so the model card can report them and CI can fail on regressions. Array-based and decoupled from
any particular scorer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# A positive (flagged) prediction is a 0-100 score at/above this (i.e. elevated or severe).
DEFAULT_DECISION = 50.0


@dataclass(frozen=True)
class SubgroupResult:
    group: str
    n: int
    fpr: float  # over the clean (label==0) members of the subgroup
    fnr: float  # over the slop (label==1) members, if any
    abstention_rate: float


def subgroup_result(
    group: str,
    labels: np.ndarray,
    scores: np.ndarray,
    abstained: np.ndarray,
    decision: float = DEFAULT_DECISION,
) -> SubgroupResult:
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=float)
    abstained = np.asarray(abstained, dtype=bool)
    flagged = scores >= decision

    clean = labels == 0
    slop = labels == 1
    fpr = float(flagged[clean].mean()) if clean.any() else 0.0
    fnr = float((~flagged[slop]).mean()) if slop.any() else 0.0
    return SubgroupResult(
        group=group,
        n=len(labels),
        fpr=fpr,
        fnr=fnr,
        abstention_rate=float(abstained.mean()) if len(abstained) else 0.0,
    )
