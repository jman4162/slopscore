"""Learned scorer: JSON model inference, --scorer dispatch, and the promotion gate."""

from __future__ import annotations

from slopscore.config import Scorer, Settings
from slopscore.core import SlopScorer
from slopscore.eval.harness import should_promote
from slopscore.scoring.model import (
    FEATURE_ORDER,
    LogisticModel,
    load_model,
    model_available,
)

_SLOP = (
    "In today's fast-paced world this platform stands as a testament to innovation, reflecting "
    "its broader significance and fostering a vibrant, dynamic, and transformative ecosystem "
    "across the evolving landscape of the industry, marking a significant shift for everyone. "
    "Experts argue it plays a pivotal role and underscores an enduring legacy of progress."
)
_CLEAN = (
    "The bridge opened in 1937 after four years of construction. Crews poured 389,000 cubic "
    "yards of concrete and strung the cables by hand. Eleven workers died on the job that year. "
    "The lead engineer did most of the math but got no public credit until decades later."
)


def test_default_scorer_is_rules() -> None:
    # The replace-if-wins gate kept rules as default (ML did not beat it on TPR@1%FPR).
    assert Settings().scorer is Scorer.rules


def test_model_is_packaged_and_loads() -> None:
    assert model_available()
    model = load_model()
    assert isinstance(model, LogisticModel)
    assert len(model.weights) == len(FEATURE_ORDER)
    # Sign constraints: every slop dimension >= 0; the human-writing signal <= 0.
    *slop, human = model.weights
    assert all(w >= 0 for w in slop)
    assert human <= 0


def test_contributions_sum_to_logit() -> None:
    model = load_model()
    feats = [0.5] * len(FEATURE_ORDER)
    total = model.bias + sum(model.contributions(feats).values())
    assert abs(total - model.logit(feats)) < 1e-3


def test_ml_scorer_runs_and_separates() -> None:
    ml = SlopScorer(profile="blog", scorer="ml")
    slop = ml.scan_text(_SLOP).score.slop_score
    clean = ml.scan_text(_CLEAN).score.slop_score
    assert 0 <= clean <= 100 and 0 <= slop <= 100
    assert slop > clean


def _result(tpr: float, simple_fpr: float) -> dict:
    return {
        "metrics": {"tpr_at_1fpr": tpr},
        "fairness": {"simple_english": {"fpr": simple_fpr}},
    }


def test_promotion_gate_requires_tpr_and_fairness() -> None:
    rules = _result(0.80, 0.00)
    # Loses on TPR -> no promotion.
    assert should_promote(rules, _result(0.70, 0.00)) is False
    # Ties TPR but regresses the simple-English false-positive rate -> no promotion.
    assert should_promote(rules, _result(0.80, 0.40)) is False
    # Beats TPR and holds fairness -> promote.
    assert should_promote(rules, _result(0.88, 0.00)) is True
