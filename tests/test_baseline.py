"""Findings baseline: fingerprints, build, and new-finding detection."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.report.baseline import (
    BaselineFile,
    build_baseline,
    fingerprint,
    new_findings,
)

_BASE = "Everyone knows this stands as a testament to innovation."
_MORE = _BASE + " In an increasingly digital world, teams must adapt."


def test_fingerprint_stable_and_distinct() -> None:
    a = fingerprint("f.txt", "RULE", "span")
    assert a == fingerprint("f.txt", "RULE", "span")
    assert a != fingerprint("f.txt", "RULE", "other")


def test_build_and_roundtrip() -> None:
    report = scan_text(_BASE, source="a.txt")
    baseline = build_baseline([report])
    assert baseline.fingerprints
    restored = BaselineFile.model_validate_json(baseline.to_json())
    assert restored.as_set() == baseline.as_set()


def test_no_new_findings_when_unchanged() -> None:
    report = scan_text(_BASE, source="a.txt")
    known = build_baseline([report]).as_set()
    assert new_findings(scan_text(_BASE, source="a.txt"), known) == 0


def test_detects_new_findings() -> None:
    known = build_baseline([scan_text(_BASE, source="a.txt")]).as_set()
    assert new_findings(scan_text(_MORE, source="a.txt"), known) >= 1
