"""FORMATTING_EM_DASH: a visible, traceable dash metric when the dash-heavy signal fires."""

from __future__ import annotations

import pytest

from slopscore import SlopScorer, scan_text

_DASHY = "Costs fell — fast — and revenue rose — sharply — again."
_CLEAN = "A normal sentence, with one comma only, and nothing unusual about its punctuation."
_DASH_CHARS = {"—", "–", "--", "---"}  # em dash, en dash, ASCII  # noqa: RUF001


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


# --- ASCII dashes ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Costs fell -- fast -- and revenue rose -- sharply -- again.",
        "Costs fell--fast--and revenue rose--sharply--again.",
        "Costs fell --- fast --- and revenue rose --- sharply --- again.",
    ],
    ids=["spaced", "unspaced-lowercase", "spaced-triple"],
)
def test_ascii_dashes_count_as_dashes(text: str) -> None:
    ev = _emdash_evidence(text)
    assert len(ev) == 1
    assert ev[0].span in {"--", "---"}
    assert 'typed as "--"' in ev[0].explanation
    report = scan_text(text)
    assert report.original_text[ev[0].start_char : ev[0].end_char] == ev[0].span


def test_one_unicode_and_one_ascii_dash_reach_the_threshold_together() -> None:
    # Two dashes are the minimum. Counted as separate kinds, one of each would never fire.
    assert len(_emdash_evidence("Costs fell — fast, and revenue rose -- sharply.")) == 1


def test_anchor_stays_on_the_unicode_dash_when_both_kinds_appear() -> None:
    # report/baseline.py fingerprints the span text. A document that fired before ASCII dashes
    # counted must keep the same span, or --fail-on-new reports an old finding as new.
    ev = _emdash_evidence("Costs fell -- fast -- and revenue rose — sharply — again.")
    assert len(ev) == 1
    assert ev[0].span == "—"
    assert 'typed as "--"' in ev[0].explanation


@pytest.mark.parametrize(
    "text",
    [
        "Run slopscore-lint scan --broad --fail-on medium --by-paragraph to see the report.",
        "Text here <!-- slopscore-disable-line LEXICAL_MARKERS --> and more <!-- a note --> end.",
        "First part of the note.\n---\nSecond part of the note.\n---\nThird part of the note.",
        "Pages 12--14 and the years 1990--2000 were covered in the review.",
        "The loop runs i-- and j-- until both counters reach zero.",
        "The Wenner--Gren Foundation and Eulalie--A Song were both cited.",
    ],
    ids=["cli-flags", "html-comments", "rule-lines", "numeric-ranges", "decrements", "capitals"],
)
def test_double_hyphens_that_are_not_dashes_do_not_count(text: str) -> None:
    assert _emdash_evidence(text) == []


def test_backticked_flags_in_markdown_do_not_count(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "doc.md"
    p.write_text(
        "Run `slopscore-lint scan --broad` and then `--fail-on medium`.\n\n---\n\n"
        "Use `--by-paragraph` for long files.\n",
        encoding="utf-8",
    )
    report = SlopScorer().scan_file(p)
    assert not any(e.rule_id == "FORMATTING_EM_DASH" for e in report.evidence)


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        ("The update is not a fix -- it's a patch.", "PARALLEL_NOT_EMDASH_ITS"),
        ("The update is not a fix--it's a patch.", "PARALLEL_NOT_EMDASH_ITS"),
        ("It's not a bug -- it's a feature.", "PARALLEL_ITS_NOT_ITS"),
        ("The tool is not just a linter -- it's a gate.", "PARALLEL_NOT_JUST"),
        ("It's not a binary -- it's both.", "PARALLEL_BOTH_AND"),
    ],
)
def test_dash_antithesis_rules_match_ascii_dashes(text: str, rule_id: str) -> None:
    assert rule_id in {e.rule_id for e in scan_text(text).evidence}
