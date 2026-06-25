"""Evaluation harness: metrics, fairness, selective-prediction, and span scoring.

Used to measure both the rule-based and learned scorers honestly. The primary metric is
**TPR at a fixed low FPR** (not AUROC), because slopscore is a conservative linter where false
positives carry reputational cost. Imports scikit-learn (a core dependency); scan-time inference
stays pure-numpy and never imports this package.
"""

from slopscore.eval.metrics import EvalMetrics, compute_metrics, tpr_at_fpr

__all__ = ["EvalMetrics", "compute_metrics", "tpr_at_fpr"]
