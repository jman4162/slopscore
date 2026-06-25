"""Detector metrics for a conservative linter.

Primary metric is TPR at a fixed low FPR (1% and 5%), with PR-AUC and calibration error (ECE,
Brier) alongside. AUROC is reported for reference only — it averages over all thresholds and
hides behavior at the low-FPR operating point we actually care about (Mitchell et al. 2024; RAID).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import TypeAlias

import numpy as np
from sklearn.metrics import (
    auc,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

FloatArray: TypeAlias = np.ndarray


def _as_unit(scores: FloatArray) -> FloatArray:
    scores = np.asarray(scores, dtype=float)
    return scores / 100.0 if scores.max(initial=0.0) > 1.0 else scores


def tpr_at_fpr(y_true: FloatArray, scores: FloatArray, target_fpr: float) -> tuple[float, float]:
    """Return ``(tpr, threshold)`` at the operating point closest to ``target_fpr`` (FPR<=target).

    Picks the highest-TPR threshold whose FPR does not exceed the target, so the reported number
    is achievable without breaching the false-positive budget.
    """
    y_true = np.asarray(y_true)
    scores = _as_unit(scores)
    fpr, tpr, thr = roc_curve(y_true, scores)
    ok = fpr <= target_fpr
    if not ok.any():
        return 0.0, 1.0
    idx = int(np.argmax(tpr * ok))  # highest TPR among allowed points
    return float(tpr[idx]), float(thr[idx])


def pr_auc(y_true: FloatArray, scores: FloatArray) -> float:
    precision, recall, _ = precision_recall_curve(np.asarray(y_true), _as_unit(scores))
    return float(auc(recall, precision))


def expected_calibration_error(y_true: FloatArray, scores: FloatArray, bins: int = 10) -> float:
    """Binned |confidence - accuracy|, weighted by bin population."""
    y_true = np.asarray(y_true, dtype=float)
    p = _as_unit(scores)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = len(p)
    for lo, hi in pairwise(edges):
        mask = (p >= lo) & (p < hi) if hi < 1.0 else (p >= lo) & (p <= hi)
        if mask.any():
            ece += abs(p[mask].mean() - y_true[mask].mean()) * mask.sum() / n
    return float(ece)


@dataclass(frozen=True)
class EvalMetrics:
    n: int
    n_positive: int
    auroc: float
    pr_auc: float
    tpr_at_1fpr: float
    tpr_at_5fpr: float
    ece: float
    brier: float

    def as_dict(self) -> dict[str, float]:
        return {
            "n": self.n,
            "n_positive": self.n_positive,
            "auroc": round(self.auroc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "tpr_at_1fpr": round(self.tpr_at_1fpr, 4),
            "tpr_at_5fpr": round(self.tpr_at_5fpr, 4),
            "ece": round(self.ece, 4),
            "brier": round(self.brier, 4),
        }


def compute_metrics(y_true: FloatArray, scores: FloatArray) -> EvalMetrics:
    y = np.asarray(y_true)
    p = _as_unit(scores)
    return EvalMetrics(
        n=len(y),
        n_positive=int(y.sum()),
        auroc=float(roc_auc_score(y, p)) if len(set(y.tolist())) > 1 else float("nan"),
        pr_auc=pr_auc(y, p),
        tpr_at_1fpr=tpr_at_fpr(y, p, 0.01)[0],
        tpr_at_5fpr=tpr_at_fpr(y, p, 0.05)[0],
        ece=expected_calibration_error(y, p),
        brier=float(brier_score_loss(y, p)),
    )
