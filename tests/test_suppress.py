"""Inline suppression + per-rule disable + severity overrides."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.config_file import resolve_settings
from slopscore.core import SlopScorer
from slopscore.suppress import parse_suppressions

_CLAIM = "Everyone knows this is essential."  # fires CLAIM_EVERYONE_KNOWS


def _claims(report) -> int:
    return sum(e.rule_id.startswith("CLAIM_") for e in report.evidence)


def test_disable_next_line() -> None:
    text = f"<!-- slopscore-disable-next-line unsupported_claims -->\n{_CLAIM}"
    assert _claims(scan_text(_CLAIM)) == 1
    assert _claims(scan_text(text)) == 0


def test_disable_line_same_line() -> None:
    text = f"{_CLAIM} <!-- slopscore-disable-line CLAIM_EVERYONE_KNOWS -->"
    assert _claims(scan_text(text)) == 0


def test_block_disable_enable() -> None:
    text = (
        "<!-- slopscore-disable unsupported_claims -->\n"
        f"{_CLAIM}\n"
        "<!-- slopscore-enable unsupported_claims -->\n"
        f"{_CLAIM}"
    )
    # First occurrence suppressed, second (after enable) counted.
    assert _claims(scan_text(text)) == 1


def test_disable_file() -> None:
    text = f"<!-- slopscore-disable-file -->\n{_CLAIM}\n{_CLAIM}"
    assert _claims(scan_text(text)) == 0


def test_dimension_scoped_suppression_leaves_others() -> None:
    text = (
        "<!-- slopscore-disable-next-line unsupported_claims -->\n"
        "Everyone knows it stands as a testament to innovation."
    )
    report = scan_text(text)
    assert _claims(report) == 0
    assert any(e.rule_id.startswith("SIGNIF_") for e in report.evidence)  # other dim survives


def test_unknown_name_warns() -> None:
    report = scan_text(f"<!-- slopscore-disable not_a_rule -->\n{_CLAIM}")
    assert any("Unknown name" in w for w in report.warnings)


def test_per_rule_disable_via_config() -> None:
    settings = resolve_settings({"disabled_rules": ["CLAIM_EVERYONE_KNOWS"]})
    report = SlopScorer(settings=settings).scan_text(_CLAIM)
    assert _claims(report) == 0


def test_severity_override_via_config() -> None:
    settings = resolve_settings({"rule_severity": {"CLAIM_EVERYONE_KNOWS": "high"}})
    report = SlopScorer(settings=settings).scan_text(_CLAIM)
    e = next(e for e in report.evidence if e.rule_id == "CLAIM_EVERYONE_KNOWS")
    assert e.severity.value == "high"


def test_parse_suppressions_ranges() -> None:
    sup = parse_suppressions("<!-- slopscore-disable-file foo -->\nhello", frozenset({"foo"}))
    assert not sup.unknown_names
    assert sup.is_suppressed(40, "foo", "any_dim")  # name-scoped range matches "foo"
    assert not sup.is_suppressed(40, "other", "any_dim")  # but not other rules
