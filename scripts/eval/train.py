"""Train the transparent v0.3 scorer: a sign-constrained, calibrated logistic regression over
the 13 interpretable dimensions (+ the negative human-writing signal).

- Features = the dimension vector (FEATURE_ORDER), frozen — not raw rule counts.
- Sign constraints: slop dimensions have weight >= 0, ``human_writing_signals`` <= 0, so "more
  tells never lowers the score" (domain-driven monotonicity).
- Calibration: Platt (a, b) fit on cross-validated out-of-fold logits; metrics are reported on
  those OOF predictions (honest, leakage-free). Final weights are refit on all data.
- Output: ``src/slopscore/data/model/slopscore-v0.3.json`` (diff-able; pure-numpy at scan time).

Run: ``python scripts/eval/train.py``  (uses the committed seed set by default).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from slopscore.core import SlopScorer
from slopscore.eval.datasets import load_jsonl
from slopscore.eval.metrics import compute_metrics
from slopscore.scoring.model import FEATURE_ORDER, feature_vector

# Train on the committed benchmark (hand-authored, permissive, train-eligible). It includes the
# seed and adds simple-English / non-native negatives so the learned model sees the fairness slices.
_BENCHMARK = Path(__file__).resolve().parents[2] / "eval" / "datasets" / "benchmark.jsonl"

SEED = 13
# Sign bounds per FEATURE_ORDER: slop dims >= 0; the final human-writing signal <= 0.
_BOUNDS = [(0.0, None)] * (len(FEATURE_ORDER) - 1) + [(None, 0.0)]
_L2 = 1.0  # inverse of C; modest regularization for a small feature set


def _features(texts: list[str]) -> np.ndarray:
    scorer = SlopScorer(profile="blog")
    return np.array([feature_vector(scorer.scan_text(t).dimensions) for t in texts], dtype=float)


def _fit_constrained(x: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    """L2-regularized logistic loss minimized under the sign bounds (bias unconstrained)."""
    n, k = x.shape

    def neg_log_likelihood(theta: np.ndarray) -> float:
        bias, w = theta[0], theta[1:]
        z = bias + x @ w
        # stable log(1+exp(-y'z)) with y' in {-1,+1}
        ys = 2 * y - 1
        loss = np.logaddexp(0.0, -ys * z).mean()
        return float(loss + _L2 / (2 * n) * (w @ w))

    bounds = [(None, None), *_BOUNDS]
    theta0 = np.zeros(k + 1)
    res = minimize(neg_log_likelihood, theta0, method="L-BFGS-B", bounds=bounds)
    return float(res.x[0]), res.x[1:]


def _platt(logits: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Fit sigmoid(a*logit + b) by 1-D logistic regression of labels on logits."""
    lr = LogisticRegression(C=1e6)  # near-unregularized 1-D fit
    lr.fit(logits.reshape(-1, 1), y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def main() -> None:
    rows = load_jsonl(_BENCHMARK)
    texts = [r.text for r in rows]
    y = np.array([r.label for r in rows])
    x = _features(texts)

    # Out-of-fold logits for honest, leakage-free metrics + calibration fitting.
    oof_logit = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for tr, va in skf.split(x, y):
        bias, w = _fit_constrained(x[tr], y[tr])
        oof_logit[va] = bias + x[va] @ w

    a, b = _platt(oof_logit, y)
    oof_prob = 1.0 / (1.0 + np.exp(-(a * oof_logit + b)))
    metrics = compute_metrics(y, oof_prob).as_dict()

    # Final model on all data, paired with the OOF-derived calibration.
    bias, w = _fit_constrained(x, y)
    model = {
        "model_version": "0.5.0",
        "model_type": "logistic_regression_sign_constrained",
        "n_train": len(y),
        "n_positive": int(y.sum()),
        "feature_order": [d.value for d in FEATURE_ORDER],
        "bias": round(bias, 6),
        "weights": [round(float(v), 6) for v in w],
        "calibration": {"method": "platt", "a": round(a, 6), "b": round(b, 6)},
        "metrics_oof": metrics,
        "training_sources": ["benchmark.jsonl (hand-authored, permissive)"],
        "notes": "Trained on the committed benchmark; opt-in (--scorer ml). The rule scorer stays "
        "the default under the replace-if-wins gate. See DATA_SOURCES.md and MODEL_CARD.md.",
    }

    out = Path(__file__).resolve().parents[2] / "src" / "slopscore" / "data" / "model"
    out.mkdir(parents=True, exist_ok=True)
    (out / "slopscore-v0.5.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    print("OOF metrics:", metrics)
    print("weights:", dict(zip([d.value for d in FEATURE_ORDER], model["weights"], strict=True)))
    print(f"wrote {out / 'slopscore-v0.5.json'}")


if __name__ == "__main__":
    main()
