"""Genericity distinguishes specific from generic prose (regex and NER paths)."""

from __future__ import annotations

import pytest

from slopscore.core import build_document
from slopscore.features._nlp import is_nlp_available
from slopscore.features.specificity import Specificity
from slopscore.ingest import from_string

_SPECIFIC = (
    "Joseph Strauss built the Golden Gate Bridge in San Francisco in 1937, and crews "
    "poured 389,000 cubic yards of concrete over four years of work near the headlands."
)
_GENERIC = (
    "This solution provides real value and helps you achieve more in meaningful ways, "
    "empowering everyone to unlock their potential and reach the next level together."
)


def _genericity(text: str) -> float:
    return Specificity().extract(build_document(from_string(text)), "blog").score


def test_specific_prose_scores_lower_genericity() -> None:
    assert _genericity(_SPECIFIC) < _genericity(_GENERIC)


@pytest.mark.skipif(not is_nlp_available(), reason="requires the [nlp] extra (spaCy + model)")
def test_ner_path_active_when_available() -> None:
    # With spaCy, entity-dense text reads as highly specific (low genericity).
    assert _genericity(_SPECIFIC) < 0.5
