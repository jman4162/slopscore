"""Shared training/eval helpers for the scripts (feature extraction, constrained LR, Platt)."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression

from slopscore.core import SlopScorer
from slopscore.scoring.model import FEATURE_ORDER, feature_vector

# Sign bounds per FEATURE_ORDER: slop dims >= 0; the final human-writing signal <= 0.
SIGN_BOUNDS = [(0.0, None)] * (len(FEATURE_ORDER) - 1) + [(None, 0.0)]
# LightGBM monotone constraints in the same order: +1 increasing, -1 decreasing.
MONOTONE = [1] * (len(FEATURE_ORDER) - 1) + [-1]


def extract_features(texts: list[str], profile: str = "blog") -> np.ndarray:
    scorer = SlopScorer(profile=profile)
    return np.array([feature_vector(scorer.scan_text(t).dimensions) for t in texts], dtype=float)


def fit_constrained_lr(x: np.ndarray, y: np.ndarray, l2: float = 1.0) -> tuple[float, np.ndarray]:
    """L2-regularized logistic loss minimized under the sign bounds (bias unconstrained)."""
    n, k = x.shape

    def nll(theta: np.ndarray) -> float:
        bias, w = theta[0], theta[1:]
        z = bias + x @ w
        ys = 2 * y - 1
        return float(np.logaddexp(0.0, -ys * z).mean() + l2 / (2 * n) * (w @ w))

    res = minimize(nll, np.zeros(k + 1), method="L-BFGS-B", bounds=[(None, None), *SIGN_BOUNDS])
    return float(res.x[0]), res.x[1:]


def platt(logits: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6)
    lr.fit(logits.reshape(-1, 1), y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])
