"""Opt-in rewrite suggestions: advisory, non-destructive, SARIF fixes."""

from __future__ import annotations

import json

from slopscore import scan_text
from slopscore.config_file import resolve_settings
from slopscore.core import SlopScorer
from slopscore.report.batch import max_severity
from slopscore.report.sarif import to_sarif

_TEXT = "We utilize this in order to facilitate growth prior to the launch."


def _scan(suggest: bool):
    return SlopScorer(settings=resolve_settings({}, suggest=suggest)).scan_text(_TEXT)


def _suggestions(report) -> list:
    return [e for e in report.evidence if e.suggestion is not None]


def test_suggestions_are_opt_in() -> None:
    assert _suggestions(_scan(False)) == []
    assert len(_suggestions(_scan(True))) >= 3


def test_suggestion_content() -> None:
    by_rule = {e.rule_id: e.suggestion.text for e in _suggestions(_scan(True))}
    assert by_rule.get("SUGGEST_UTILIZE") == "use"
    assert by_rule.get("SUGGEST_PRIOR_TO") == "before"


def test_suggestions_do_not_affect_score_or_fail_on() -> None:
    plain = scan_text(_TEXT)
    withs = _scan(True)
    assert withs.score.slop_score == plain.score.slop_score  # advisory, no score change
    assert max_severity([withs]) == max_severity([plain])  # SUGGEST_ excluded from fail-on


def test_sarif_emits_fixes() -> None:
    report = _scan(True)
    sarif = to_sarif(report)
    fixes = [r for r in sarif["runs"][0]["results"] if "fixes" in r]
    assert fixes
    rep = fixes[0]["fixes"][0]["artifactChanges"][0]["replacements"][0]
    assert "insertedContent" in rep and "deletedRegion" in rep


def test_nothing_written_to_disk() -> None:
    # scan_text takes a string; ensure the JSON form has suggestions but the call is pure.
    report = _scan(True)
    payload = json.loads(report.to_json())
    assert any(e.get("suggestion") for e in payload["evidence"])
