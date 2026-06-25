"""Selective-prediction (abstention) metrics.

slopscore abstains (caps the label at "mild") on short / non-English text. These functions show
that abstaining trades coverage for accuracy in the right direction: accuracy on the texts we DO
confidently judge should exceed accuracy if we had judged everything.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from slopscore.eval.fairness import DEFAULT_DECISION


@dataclass(frozen=True)
class RiskCoverage:
    coverage: float  # fraction of items we do NOT abstain on
    accuracy_covered: float  # accuracy on the covered (confident) items
    accuracy_all: float  # accuracy if we judged everything (no abstention)


def risk_coverage(
    labels: np.ndarray,
    scores: np.ndarray,
    abstained: np.ndarray,
    decision: float = DEFAULT_DECISION,
) -> RiskCoverage:
    labels = np.asarray(labels)
    pred = np.asarray(scores, dtype=float) >= decision
    abstained = np.asarray(abstained, dtype=bool)
    correct = pred == labels.astype(bool)

    covered = ~abstained
    cov = float(covered.mean()) if len(labels) else 0.0
    acc_cov = float(correct[covered].mean()) if covered.any() else 0.0
    acc_all = float(correct.mean()) if len(labels) else 0.0
    return RiskCoverage(coverage=cov, accuracy_covered=acc_cov, accuracy_all=acc_all)
