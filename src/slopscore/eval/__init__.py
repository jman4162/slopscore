"""Evaluation harness: metrics, fairness, selective-prediction, and span scoring.

Used to measure both the rule-based and learned scorers honestly. The primary metric is
**TPR at a fixed low FPR** (not AUROC), because slopscore is a conservative linter where false
positives carry reputational cost.

``metrics`` needs scikit-learn, which is the ``[eval]`` extra (the scan path is numpy-only and
never imports this package). The metric names are resolved lazily so that ``eval.datasets``
(used by ``slopscore-lint fairness``) imports without it.
"""

from __future__ import annotations

from typing import Any

__all__ = ["EvalMetrics", "compute_metrics", "tpr_at_fpr"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from slopscore.eval import metrics

        return getattr(metrics, name)
    raise AttributeError(name)
