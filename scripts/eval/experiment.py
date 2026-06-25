"""Real-corpus experiment: compare the rule scorer, the sign-constrained LR, and a monotone
LightGBM on a held-out test split of the committed seed + fetched MAGE corpus.

Reports honest held-out metrics (TPR@FPR, PR-AUC, ECE) and runs the LightGBM experiment. It does
NOT retrain the shipped model: MAGE labels by authorship, not slop, so the shipped slop scorer
stays seed-trained (see the note in main). LightGBM is an experiment only — it needs trees at scan
time, so it is never shipped (the scan path stays pure-numpy LR).

Run: ``python scripts/eval/fetch.py mage`` then ``python scripts/eval/experiment.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from _common import MONOTONE, fit_constrained_lr, platt
from sklearn.model_selection import train_test_split

from slopscore.core import SlopScorer
from slopscore.eval.datasets import load_jsonl, load_seed
from slopscore.eval.metrics import compute_metrics
from slopscore.scoring.model import feature_vector

SEED = 13
CACHE = Path.home() / ".cache" / "slopscore"
REPO = Path(__file__).resolve().parents[2]


def _load_rows() -> list:
    rows = list(load_seed())
    mage = CACHE / "mage.jsonl"
    if mage.exists():
        rows += load_jsonl(mage)
    return rows


def _scan_all(texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """One pass: per text, the feature vector AND the rule scorer's 0-1 score."""
    scorer = SlopScorer(profile="blog")
    feats, rule = [], []
    for i, t in enumerate(texts):
        rep = scorer.scan_text(t)
        feats.append(feature_vector(rep.dimensions))
        rule.append(rep.score.slop_score / 100.0)
        if (i + 1) % 200 == 0:
            print(f"  scanned {i + 1}/{len(texts)}")
    return np.array(feats, dtype=float), np.array(rule, dtype=float)


def main() -> None:
    rows = _load_rows()
    texts = [r.text for r in rows]
    y = np.array([r.label for r in rows])
    print(f"corpus: {len(rows)} rows ({int(y.sum())} slop / {int((1 - y).sum())} clean)")
    x, rule_scores = _scan_all(texts)

    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.3, random_state=SEED, stratify=y)

    # --- sign-constrained LR ---
    bias, w = fit_constrained_lr(x[tr], y[tr])
    a, b = platt(bias + x[tr] @ w, y[tr])
    lr_prob_te = 1.0 / (1.0 + np.exp(-(a * (bias + x[te] @ w) + b)))

    # --- monotone LightGBM (experiment only; not shipped) ---
    lgbm_metrics = None
    try:
        from lightgbm import LGBMClassifier

        gbm = LGBMClassifier(
            n_estimators=200,
            num_leaves=7,
            learning_rate=0.05,
            monotone_constraints=MONOTONE,
            min_child_samples=20,
            verbose=-1,
            random_state=SEED,
        )
        gbm.fit(x[tr], y[tr])
        lgbm_prob_te = gbm.predict_proba(x[te])[:, 1]
        lgbm_metrics = compute_metrics(y[te], lgbm_prob_te).as_dict()
    except Exception as exc:  # pragma: no cover
        print("LightGBM experiment skipped:", exc)

    results = {
        "n_total": len(rows),
        "n_test": len(te),
        "test_metrics": {
            "rules": compute_metrics(y[te], rule_scores[te]).as_dict(),
            "lr": compute_metrics(y[te], lr_prob_te).as_dict(),
        },
    }
    if lgbm_metrics is not None:
        results["test_metrics"]["lgbm_monotone"] = lgbm_metrics

    for name, m in results["test_metrics"].items():
        print(
            f"{name:>14}  TPR@1%FPR {m['tpr_at_1fpr']:.3f}  TPR@5%FPR {m['tpr_at_5fpr']:.3f}  "
            f"PR-AUC {m['pr_auc']:.3f}  ECE {m['ece']:.3f}"
        )

    out = REPO / "eval" / "results" / "realcorpus.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")

    # NOTE: we deliberately do NOT retrain the shipped model on MAGE. MAGE labels by AUTHORSHIP
    # (machine vs human), not slop. Training the shipped slop scorer on authorship labels would
    # turn it into an authorship detector — the exact thing slopscore refuses to be. The shipped
    # model stays trained on the slop-labeled seed (scripts/eval/train.py). This experiment
    # MEASURES behavior on real AI-vs-human text and runs the LightGBM comparison.


if __name__ == "__main__":
    main()
