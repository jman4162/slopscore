"""Learned scorer: pure-numpy inference from a JSON logistic-regression model.

The model is the same shape as the hand-set rule scorer — ``bias + sum(wᵢ·featureᵢ)`` then a
sigmoid — so swapping in learned weights is a drop-in. Loaded from a diff-able JSON file; no
sklearn is imported at scan time. Per-feature contributions (``wᵢ·featureᵢ``) are exposed so the
report can still trace each point of the score to a dimension and its evidence spans.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from slopscore.config import data_path
from slopscore.models import Dimension, Dimensions

# Canonical feature order = the scored dimensions, fixed so weights line up with values.
FEATURE_ORDER: tuple[Dimension, ...] = (
    Dimension.lexical_markers,
    Dimension.formulaic_structure,
    Dimension.genericity,
    Dimension.redundancy,
    Dimension.cadence_sameness,
    Dimension.unsupported_claims,
    Dimension.prompt_residue,
    Dimension.significance_inflation,
    Dimension.superficial_analysis,
    Dimension.weasel_attribution,
    Dimension.parallelism,
    Dimension.copula_avoidance,
    Dimension.formatting_tells,
    Dimension.human_writing_signals,
)

_MODEL_FILE = ("model", "slopscore-v0.5.json")


def feature_vector(dims: Dimensions) -> list[float]:
    """Project a Dimensions record onto FEATURE_ORDER."""
    d = dims.model_dump()
    return [float(d[dim.value]) for dim in FEATURE_ORDER]


@dataclass(frozen=True)
class LogisticModel:
    bias: float
    weights: tuple[float, ...]
    feature_order: tuple[str, ...]
    # Optional Platt calibration applied to the logit: sigmoid(a*logit + b).
    cal_a: float = 1.0
    cal_b: float = 0.0

    def logit(self, features: list[float]) -> float:
        return self.bias + sum(w * x for w, x in zip(self.weights, features, strict=True))

    def probability(self, features: list[float]) -> float:
        z = self.cal_a * self.logit(features) + self.cal_b
        return 1.0 / (1.0 + math.exp(-z))

    def slop_score(self, features: list[float]) -> float:
        return round(100.0 * self.probability(features), 1)

    def contributions(self, features: list[float]) -> dict[str, float]:
        return {
            name: round(w * x, 4)
            for name, w, x in zip(self.feature_order, self.weights, features, strict=True)
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LogisticModel:
        cal = d.get("calibration") or {}
        return cls(
            bias=float(d["bias"]),
            weights=tuple(float(w) for w in d["weights"]),
            feature_order=tuple(str(f) for f in d["feature_order"]),
            cal_a=float(cal.get("a", 1.0)),
            cal_b=float(cal.get("b", 0.0)),
        )


class ModelNotTrained(RuntimeError):
    """Raised when the learned scorer is requested but no model JSON is packaged."""


@lru_cache(maxsize=1)
def load_model() -> LogisticModel:
    path = data_path(*_MODEL_FILE)
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise ModelNotTrained(
            "No trained model is packaged. Train one with scripts/eval/train.py "
            "or use --scorer rules."
        ) from exc
    return LogisticModel.from_dict(json.loads(text))


def model_available() -> bool:
    return Path(str(data_path(*_MODEL_FILE))).exists()
