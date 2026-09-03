"""Silencing a rule removes its points, not only its evidence (v0.10)."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.base import SpanScored, registry
from slopscore.ingest import from_string
from slopscore.models import Report
from slopscore.scoring.weights import STATISTICAL_DIMENSIONS

_STATISTICAL = {d.value for d in STATISTICAL_DIMENSIONS} | {"optional_ai_detector"}


def _span_dims(report: Report) -> dict[str, float]:
    return {k: v for k, v in report.dimensions.model_dump().items() if k not in _STATISTICAL}


def test_score_spans_matches_extract_for_every_span_backed_feature(slop_text: str) -> None:
    doc = build_document(from_string(slop_text))
    for feature in registry():
        if not isinstance(feature, SpanScored):
            continue
        result = feature.extract(doc, "blog")
        assert feature.score_spans(doc, "blog", result.spans) == result.score, feature.dimension


def test_disabling_every_fired_rule_zeroes_the_span_backed_dimensions(slop_text: str) -> None:
    full = scan_text(slop_text)
    fired = frozenset(e.rule_id for e in full.evidence)
    assert fired
    muted = SlopScorer(settings=Settings(disabled_rules=fired)).scan_text(slop_text)
    assert muted.evidence == []
    assert all(v == 0.0 for v in _span_dims(muted).values()), _span_dims(muted)
    assert muted.score.slop_score < 50 < full.score.slop_score


def test_disable_file_comment_matches_disabling_every_rule(slop_text: str) -> None:
    full = scan_text(slop_text)
    fired = frozenset(e.rule_id for e in full.evidence)
    by_config = SlopScorer(settings=Settings(disabled_rules=fired)).scan_text(slop_text)
    by_comment = scan_text("<!-- slopscore-disable-file -->\n" + slop_text)
    assert by_comment.evidence == []
    assert all(v == 0.0 for v in _span_dims(by_comment).values())
    # The comment itself adds two words, which nudges the statistical dimensions slightly.
    assert abs(by_comment.score.slop_score - by_config.score.slop_score) < 1.0


def test_severity_override_moves_the_dimension(clean_text: str) -> None:
    text = clean_text + " It stands as a testament to modern engineering."
    base = scan_text(text).dimensions.significance_inflation
    assert 0 < base < 1
    lowered = SlopScorer(
        settings=Settings(rule_severity={"SIGNIF_STANDS_AS_TESTAMENT": "low"})
    ).scan_text(text)
    assert lowered.dimensions.significance_inflation < base
    assert all(
        e.severity.value == "low"
        for e in lowered.evidence
        if e.rule_id == "SIGNIF_STANDS_AS_TESTAMENT"
    )


def test_suppressing_one_marker_removes_the_cluster_bonus(clean_text: str) -> None:
    # Three markers in one sentence earn the cluster bonus. Muting the one that sits in a
    # different lexicon category drops the sentence below the cluster threshold, so the
    # dimension must fall by more than that single marker's weight.
    text = clean_text + " The robust, seamless, holistic design shipped in 1962."
    full = scan_text(text)
    hits = [e for e in full.evidence if e.rule_id.startswith("LEXICAL_")]
    assert len(hits) == 3
    full_dim = full.dimensions.lexical_markers
    muted = SlopScorer(
        settings=Settings(disabled_rules=frozenset({"LEXICAL_GENERIC_IMPORTANCE"}))
    ).scan_text(text)
    muted_dim = muted.dimensions.lexical_markers
    assert 0 < muted_dim < full_dim
    one_marker_share = full_dim / 3.5  # three unit weights plus the 0.5 cluster bonus
    assert full_dim - muted_dim > one_marker_share


def test_known_rule_that_did_not_fire_is_not_reported_unknown() -> None:
    known = "<!-- slopscore-disable-file SIGNIF_STANDS_AS_TESTAMENT -->\nThe sky is blue."
    assert not any("Unknown name" in w for w in scan_text(known).warnings)
    unknown = "<!-- slopscore-disable-file NOT_A_REAL_RULE -->\nThe sky is blue."
    assert any("NOT_A_REAL_RULE" in w for w in scan_text(unknown).warnings)
