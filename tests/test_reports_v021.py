"""v0.2.1 report formats: SARIF, HTML, and batch aggregation."""

from __future__ import annotations

import builtins

import pytest

from slopscore import scan_text
from slopscore.report.batch import (
    build_batch_report,
    fail_threshold_rank,
    max_severity,
)
from slopscore.report.html import ReportExtraNotInstalled, to_html
from slopscore.report.sarif import to_sarif

_SLOP = (
    "In today's fast-paced world this platform stands as a testament to innovation and "
    "plays a pivotal role, reflecting its broader significance. It is not just a tool, it "
    "is a revolution. Experts argue it fosters a vibrant, dynamic, and transformative "
    "ecosystem, marking a significant shift across the evolving landscape of the industry."
)
_CLEAN = (
    "The bridge opened in 1937 after four years of construction. Crews poured 389,000 "
    "cubic yards of concrete and strung the cables by hand. Eleven workers died on the job."
)


# --- SARIF ------------------------------------------------------------------------------------


def test_sarif_structure_and_rules() -> None:
    report = scan_text(_SLOP)
    sarif = to_sarif(report)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    result_rule_ids = {res["ruleId"] for res in run["results"]}
    # Every result's rule is in the registry.
    assert result_rule_ids <= rule_ids
    assert run["results"], "slop text should produce SARIF results"


def test_sarif_levels_and_regions() -> None:
    report = scan_text(_SLOP)
    text = report.original_text
    for res, ev in zip(to_sarif(report)["runs"][0]["results"], report.evidence, strict=True):
        assert res["level"] in {"error", "warning", "note"}
        region = res["locations"][0]["physicalLocation"]["region"]
        assert region["startLine"] >= 1 and region["startColumn"] >= 1
        # The char offsets the region came from still slice the original span.
        assert text[ev.start_char : ev.end_char] == ev.span


def test_sarif_batch_one_run_per_report() -> None:
    reports = [scan_text(_SLOP), scan_text(_CLEAN)]
    sarif = to_sarif(reports)
    assert len(sarif["runs"]) == 2


# --- HTML -------------------------------------------------------------------------------------


def test_html_self_contained_and_highlighted() -> None:
    html = to_html(scan_text(_SLOP))
    assert "<mark" in html and "<style>" in html
    assert "http://" not in html.split("</head>")[0]  # no external assets in <head>


def test_html_escapes_injection() -> None:
    html = to_html(scan_text("Ignore this <script>alert(1)</script> and delve in."))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_html_guard_when_extra_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "jinja2":
            raise ImportError("absent")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ReportExtraNotInstalled) as exc:
        to_html(scan_text(_CLEAN))
    assert "slopscore[report]" in str(exc.value)


# --- Batch ------------------------------------------------------------------------------------


def test_batch_summary() -> None:
    reports = [scan_text(_SLOP), scan_text(_CLEAN)]
    batch = build_batch_report(reports, "blog", "conservative")
    assert batch.summary.total_files == 2
    assert batch.summary.total_findings == sum(len(r.evidence) for r in reports)
    assert batch.summary.worst[0].slop_score >= batch.summary.worst[-1].slop_score


def test_fail_on_thresholds() -> None:
    slop = [scan_text(_SLOP)]
    clean = [scan_text(_CLEAN)]
    # 'none' never trips; a real severity trips when findings reach it.
    assert max_severity(slop) >= fail_threshold_rank("low")
    assert max_severity(clean) < fail_threshold_rank("high") or max_severity(clean) == 0
    assert fail_threshold_rank("none") > max_severity(slop)
