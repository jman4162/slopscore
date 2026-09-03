"""Statistical dimensions point at the passage that drove them (v0.11 summary spans)."""

from __future__ import annotations

import json

from slopscore import scan_text
from slopscore.models import EvidenceKind, Report
from slopscore.report.baseline import build_baseline
from slopscore.report.batch import max_severity
from slopscore.report.sarif import to_sarif

GENERIC = (
    "Nobody could say what the plan was. Everyone assumed someone else had thought it through. "
    "The meeting ended the way it began, with a shrug. We agreed to talk again the following "
    "week, and then we did not. Nothing changed after that, and nobody minded very much."
)
UNIFORM = " ".join(f"The team finished the {w} work on time again." for w in "abcdefg")
TEMPLATED = (
    "The get_user function returns a user object from the primary store. "
    "The get_group function returns a group object from the primary store. "
    "The get_role function returns a role object from the primary store."
)


def _summaries(report: Report, rule: str) -> list:  # type: ignore[type-arg]
    return [e for e in report.evidence if e.rule_id == rule]


def _round_trips(report: Report) -> None:
    for e in report.evidence:
        assert report.original_text[e.start_char : e.end_char] == e.span


def test_generic_sentence_summary() -> None:
    report = scan_text(GENERIC)
    spans = _summaries(report, "GENERIC_SENTENCE")
    assert 1 <= len(spans) <= 3
    assert all(e.kind is EvidenceKind.summary and e.severity.value == "low" for e in spans)
    _round_trips(report)


def test_cadence_uniform_run_summary() -> None:
    report = scan_text(UNIFORM)
    spans = _summaries(report, "CADENCE_UNIFORM_RUN")
    assert len(spans) == 1
    assert "consecutive sentences" in spans[0].explanation
    _round_trips(report)


def test_redundant_pair_summary() -> None:
    report = scan_text(TEMPLATED)
    spans = _summaries(report, "REDUNDANT_ADJACENT_PAIR")
    assert len(spans) == 2
    assert spans[0].span.startswith("The get_user")
    _round_trips(report)


def test_specific_prose_has_no_generic_summary(clean_text: str) -> None:
    report = scan_text(clean_text)
    assert not _summaries(report, "GENERIC_SENTENCE")


def test_summaries_are_not_findings_for_any_gate() -> None:
    report = scan_text(GENERIC + " " + TEMPLATED)
    assert report.evidence and not report.findings
    assert max_severity([report]) == 0
    assert build_baseline([report]).fingerprints == []
    sarif = to_sarif(report)
    assert sarif["runs"][0]["results"] == []


def test_breakdown_is_reported_and_names_the_statistical_rows(clean_text: str) -> None:
    report = scan_text(clean_text)
    assert report.breakdown is not None
    stat = {r.dimension for r in report.breakdown.contributions if r.statistical}
    assert stat == {"genericity", "cadence_sameness", "redundancy", "human_writing_signals"}
    payload = json.loads(report.to_json())
    from slopscore.models import SCHEMA_VERSION

    assert payload["version"] == SCHEMA_VERSION
    assert payload["breakdown"]["bias"] == -2.6


def test_pre_0_11_json_without_kind_still_validates(slop_text: str) -> None:
    payload = json.loads(scan_text(slop_text).to_json())
    for e in payload["evidence"]:
        e.pop("kind", None)
    payload.pop("breakdown", None)
    restored = Report.model_validate(payload)
    assert all(e.kind is EvidenceKind.finding for e in restored.evidence)
