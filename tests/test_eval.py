"""Eval harness: metrics, fairness, selective prediction, span scoring."""

from __future__ import annotations

import numpy as np

from slopscore.eval.fairness import subgroup_result
from slopscore.eval.metrics import compute_metrics, expected_calibration_error, tpr_at_fpr
from slopscore.eval.selective import risk_coverage
from slopscore.eval.span_metrics import iou, precision_recall


def test_tpr_at_fpr_perfect_separation() -> None:
    # Clean scores well below slop scores -> 100% TPR achievable at 0% FPR.
    y = np.array([0, 0, 0, 1, 1, 1])
    scores = np.array([5.0, 8.0, 12.0, 80.0, 85.0, 90.0])
    tpr, thr = tpr_at_fpr(y, scores, 0.01)
    assert tpr == 1.0
    assert 0.12 < thr <= 0.8


def test_metrics_record_shape() -> None:
    y = np.array([0, 0, 1, 1])
    scores = np.array([10.0, 30.0, 70.0, 95.0])
    m = compute_metrics(y, scores)
    assert m.n == 4 and m.n_positive == 2
    assert 0.0 <= m.pr_auc <= 1.0
    assert "tpr_at_1fpr" in m.as_dict()


def test_ece_zero_when_calibrated() -> None:
    # All-correct, confident predictions => low calibration error.
    y = np.array([0, 0, 1, 1])
    p = np.array([0.02, 0.05, 0.97, 0.99])
    assert expected_calibration_error(y, p) < 0.1


def test_subgroup_fpr() -> None:
    # A clean subgroup, two of three over the decision threshold => FPR 2/3.
    labels = np.array([0, 0, 0])
    scores = np.array([20.0, 60.0, 80.0])
    abstained = np.array([False, False, True])
    r = subgroup_result("plain", labels, scores, abstained)
    assert r.fpr == 2 / 3
    assert r.abstention_rate == 1 / 3


def test_risk_coverage_abstention_helps() -> None:
    labels = np.array([0, 1, 0, 1])
    scores = np.array([90.0, 80.0, 95.0, 85.0])  # the two clean ones are wrongly high
    abstained = np.array([True, False, True, False])  # we abstain on the wrong ones
    rc = risk_coverage(labels, scores, abstained)
    assert rc.accuracy_covered > rc.accuracy_all


def test_span_metrics() -> None:
    assert iou((0, 10), (0, 10)) == 1.0
    assert iou((0, 10), (5, 15)) == 5 / 15
    p, r = precision_recall([(0, 5), (10, 15)], [(0, 5)], mode="exact")
    assert r == 1.0 and p == 0.5
    _p2, r2 = precision_recall([(0, 6)], [(0, 5)], mode="iou", threshold=0.5)
    assert r2 == 1.0  # IoU 5/6 >= 0.5
