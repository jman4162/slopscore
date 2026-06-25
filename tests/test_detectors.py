"""Authorship adapter interface: separate field, never affects the score, mandatory caveat."""

from __future__ import annotations

from slopscore.core import SlopScorer
from slopscore.detectors.base import (
    AuthorshipDetector,
    DetectorResult,
    ReferenceDetector,
)

_TEXT = "Everyone knows this stands as a testament to innovation."


def test_reference_detector_satisfies_protocol() -> None:
    assert isinstance(ReferenceDetector(), AuthorshipDetector)


def test_authorship_is_separate_and_does_not_change_score() -> None:
    plain = SlopScorer().scan_text(_TEXT)
    withd = SlopScorer(detector=ReferenceDetector()).scan_text(_TEXT)
    assert plain.authorship is None
    assert withd.score.slop_score == plain.score.slop_score
    assert withd.dimensions == plain.dimensions


def test_authorship_carries_caveat() -> None:
    report = SlopScorer(detector=ReferenceDetector()).scan_text(_TEXT)
    assert report.authorship is not None
    assert "NOT evidence of authorship" in report.authorship.caveat


def test_custom_detector_plugs_in() -> None:
    class Always1:
        name = "always-1"

        def detect(self, text: str) -> DetectorResult:
            return DetectorResult(score=1.0, method=self.name)

    report = SlopScorer(detector=Always1()).scan_text(_TEXT)
    assert report.authorship.score == 1.0
    assert report.authorship.method == "always-1"
