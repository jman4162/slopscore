"""Score a labeled set with a chosen scorer and compute the full metrics bundle."""

from __future__ import annotations

from typing import Any

import numpy as np

from slopscore.core import SlopScorer
from slopscore.eval.datasets import LabeledRow
from slopscore.eval.fairness import subgroup_result
from slopscore.eval.metrics import compute_metrics
from slopscore.eval.selective import risk_coverage


def _score_rows(
    rows: list[LabeledRow], profile: str, scorer_kind: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    scorer = SlopScorer(profile=profile, scorer=scorer_kind)
    scores, abstained, labels, subgroups = [], [], [], []
    for r in rows:
        report = scorer.scan_text(r.text)
        scores.append(report.score.slop_score)
        abstained.append(report.score.abstained)
        labels.append(r.label)
        subgroups.append(r.subgroup)
    return (
        np.array(scores, dtype=float),
        np.array(abstained, dtype=bool),
        np.array(labels, dtype=int),
        np.array(subgroups, dtype=object),
    )


def evaluate(
    rows: list[LabeledRow], *, profile: str = "blog", scorer: str = "rules"
) -> dict[str, Any]:
    """Run metrics + per-subgroup fairness + selective prediction for one scorer."""
    scores, abstained, labels, subgroups = _score_rows(rows, profile, scorer)

    metrics = compute_metrics(labels, scores).as_dict()
    rc = risk_coverage(labels, scores, abstained)

    fairness = {}
    for group in sorted(set(subgroups.tolist())):
        mask = subgroups == group
        fairness[group] = vars(subgroup_result(group, labels[mask], scores[mask], abstained[mask]))

    return {
        "scorer": scorer,
        "profile": profile,
        "metrics": metrics,
        "selective": vars(rc),
        "fairness": fairness,
    }


def should_promote(
    rules_result: dict[str, Any], ml_result: dict[str, Any], *, tol: float = 0.02
) -> bool:
    """Replace-if-wins gate. The learned scorer becomes default ONLY if it both:

    1. does not lose on the primary metric (TPR at 1% FPR), and
    2. does not regress any subgroup false-positive rate (fairness guardrail).

    Otherwise the rule scorer stays the default. ``tol`` is the allowed slack.
    """
    if ml_result["metrics"]["tpr_at_1fpr"] + tol < rules_result["metrics"]["tpr_at_1fpr"]:
        return False
    for group, ml_fair in ml_result["fairness"].items():
        rules_fair = rules_result["fairness"].get(group)
        if rules_fair is not None and ml_fair["fpr"] > rules_fair["fpr"] + tol:
            return False
    return True
