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


def _rule_ids(text: str) -> set[str]:
    return {e.rule_id for e in scan_text(text).evidence}


def test_antithesis_variants_fire() -> None:
    assert "PARALLEL_NOT_MERELY_BUT" in _rule_ids("This is not merely a tweak, but a rethink.")
    assert "PARALLEL_LESS_ABOUT_MORE_ABOUT" in _rule_ids(
        "It is less about speed and more about trust."
    )
    assert "PARALLEL_NOT_EMDASH_ITS" in _rule_ids("The design is not decoration—it is structure.")
    assert "PARALLEL_BOTH_AND" in _rule_ids("It is not either or; the answer is both.")


def test_emdash_variant_does_not_double_fire_on_it_subject() -> None:
    # With an "it" subject, PARALLEL_ITS_NOT_ITS already covers it; the new em-dash rule must not
    # also fire on the same span (avoids double-counting the parallelism dimension).
    ids = _rule_ids("It is not decoration—it is structure.")
    assert "PARALLEL_ITS_NOT_ITS" in ids
    assert "PARALLEL_NOT_EMDASH_ITS" not in ids
