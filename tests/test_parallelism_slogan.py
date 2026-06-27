"""PARALLEL_X_NOT_Y: the elliptical 'X, not Y' antithesis slogan (scoped to avoid mid-sentence)."""

from __future__ import annotations

from slopscore import scan_text


def _fires(text: str) -> bool:
    return any(e.rule_id == "PARALLEL_X_NOT_Y" for e in scan_text(text).evidence)


def test_fires_on_slogans() -> None:
    assert _fires("A haircut, not a crash.")
    assert _fires("Progress, not perfection.")
    assert _fires("It is a haircut, not a crash.")
    assert _fires("Key takeaway: **A haircut, not a crash.**")  # bolded takeaway


def test_quiet_on_ordinary_midsentence_not() -> None:
    # "..., not ..." inside a longer clause is normal prose, not a slogan.
    assert not _fires("I went to the store, bought milk, not eggs, and left.")
    assert not _fires("She asked for the report, not the summary, before the meeting on Tuesday.")
