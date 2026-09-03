"""End-to-end scoring behavior and the slop-vs-clean separation."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.models import SCHEMA_VERSION, Label


def test_slop_scores_higher_than_clean(slop_text: str, clean_text: str) -> None:
    slop = scan_text(slop_text)
    clean = scan_text(clean_text)
    assert slop.score.slop_score > clean.score.slop_score
    assert slop.score.slop_score >= 75  # severe
    assert clean.score.slop_score < 50


def test_report_shape(slop_text: str) -> None:
    report = scan_text(slop_text)
    assert report.version == SCHEMA_VERSION
    assert report.input.word_count > 0
    assert report.score.label in set(Label)
    # Standard disclaimers always present.
    assert any("authorship" in w for w in report.warnings)


def test_short_text_lowers_confidence() -> None:
    report = scan_text("This is a short generic sentence about crucial robust synergy.")
    assert report.score.confidence < 0.5
    assert any("short" in w.lower() for w in report.warnings)


def test_strictness_changes_score(slop_text: str) -> None:
    conservative = scan_text(slop_text, strictness="conservative").score.slop_score
    sensitive = scan_text(slop_text, strictness="sensitive").score.slop_score
    assert sensitive >= conservative


def test_strictness_is_not_inverted_on_clean_text(clean_text: str) -> None:
    # Before v0.10 the gain multiplied the bias too, so "conservative" scored clean prose HIGHER
    # than "sensitive". The gain now scales only the evidence sum.
    conservative = scan_text(clean_text, strictness="conservative").score.slop_score
    balanced = scan_text(clean_text, strictness="balanced").score.slop_score
    sensitive = scan_text(clean_text, strictness="sensitive").score.slop_score
    assert conservative <= balanced <= sensitive


def test_json_round_trips_through_model(slop_text: str) -> None:
    from slopscore.models import Report

    report = scan_text(slop_text)
    restored = Report.model_validate_json(report.to_json())
    assert restored.score.slop_score == report.score.slop_score
    assert len(restored.evidence) == len(report.evidence)
