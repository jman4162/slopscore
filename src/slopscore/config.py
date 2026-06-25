"""Runtime configuration for a scan."""

from __future__ import annotations

from enum import StrEnum
from importlib import resources

from pydantic import BaseModel


class Strictness(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    sensitive = "sensitive"


# Strictness scales the final logit before the sigmoid: conservative pulls scores
# down (fewer false accusations), sensitive pushes them up.
STRICTNESS_GAIN: dict[Strictness, float] = {
    Strictness.conservative: 0.8,
    Strictness.balanced: 1.0,
    Strictness.sensitive: 1.25,
}


class Scorer(StrEnum):
    rules = "rules"  # hand-set weights + corroboration gate
    ml = "ml"  # learned logistic-regression model (data/model/slopscore-v0.3.json)


class Settings(BaseModel):
    profile: str = "blog"
    strictness: Strictness = Strictness.conservative
    scorer: Scorer = Scorer.rules
    # Below this word count, confidence is heavily suppressed (spec: <300 words).
    min_reliable_words: int = 300


def data_path(*parts: str) -> resources.abc.Traversable:
    """Locate a packaged data file, e.g. ``data_path("lexicons", "markers.yaml")``."""
    return resources.files("slopscore").joinpath("data", *parts)
