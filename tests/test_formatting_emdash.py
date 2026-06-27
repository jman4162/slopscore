"""FORMATTING_EM_DASH: a visible, traceable em-dash metric when the dash-heavy signal fires."""

from __future__ import annotations

from slopscore import scan_text

_DASHY = "Costs fell — fast — and revenue rose — sharply — again."
_CLEAN = "A normal sentence, with one comma only, and nothing unusual about its punctuation."
_DASH_CHARS = {"—", "–"}  # em dash, en dash  # noqa: RUF001


def _emdash_evidence(text: str) -> list:
    return [e for e in scan_text(text).evidence if e.rule_id == "FORMATTING_EM_DASH"]


def test_dash_heavy_text_yields_one_metric_span() -> None:
    ev = _emdash_evidence(_DASHY)
    assert len(ev) == 1  # a single summary span, not one per dash
    assert "em dashes" in ev[0].explanation and "ratio" in ev[0].explanation
    assert ev[0].span in _DASH_CHARS


def test_clean_text_yields_no_emdash_evidence() -> None:
    assert _emdash_evidence(_CLEAN) == []


def test_emdash_span_round_trips_to_original() -> None:
    report = scan_text(_DASHY)
    for e in report.evidence:
        assert report.original_text[e.start_char : e.end_char] == e.span
