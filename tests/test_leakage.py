"""Leakage guard: feature extraction must be deterministic and label-independent.

The features derive from WP:AISIGNS, so the model could "teach to the test" if features depended
on anything but the text. This asserts the feature vector is a pure function of the input.
"""

from __future__ import annotations

from slopscore.core import SlopScorer
from slopscore.scoring.model import feature_vector

_TEXT = (
    "The platform stands as a testament to innovation, reflecting its broader significance "
    "and fostering a vibrant, dynamic ecosystem across the evolving landscape."
)


def test_feature_vector_is_deterministic() -> None:
    scorer = SlopScorer(profile="blog")
    v1 = feature_vector(scorer.scan_text(_TEXT).dimensions)
    v2 = feature_vector(scorer.scan_text(_TEXT).dimensions)
    assert v1 == v2


def test_feature_vector_independent_of_scorer_choice() -> None:
    # The dimension vector (the model's input) is the same regardless of which scorer combines it.
    rules = feature_vector(SlopScorer(profile="blog", scorer="rules").scan_text(_TEXT).dimensions)
    ml = feature_vector(SlopScorer(profile="blog", scorer="ml").scan_text(_TEXT).dimensions)
    assert rules == ml
