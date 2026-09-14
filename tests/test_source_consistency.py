"""A rule must not fire under one ingester and not another, or on wrapped prose and not flat.

Two v0.14 review rounds found defects of exactly this shape. The worst: ``in_block_kind`` returns
False whenever ``doc.blocks`` is empty, so the guard meant to stop a metadiscourse run crossing a
section boundary applied to Markdown alone. On plain text -- stdin, extracted code comments, web
articles -- three signposts in three paragraphs read as one "run of 3 consecutive sentences", and
four made it ``high`` severity, which trips ``--fail-on high``. The test that claimed to cover it
passed only because it routed through the Markdown ingester.

Neither round found that by reading a diff; both found it by running the code. These are the
assertions ``scripts/eval/sweep_sources.py`` applies to the whole corpus at release time, on a
slice small enough to run on every CI job. The slice is chosen for power, not convenience: it
holds label-1 rows as well as label-0, the one corpus row that carries a ``META_`` finding, and
a real Markdown document with headings and lists.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from collections import Counter
from pathlib import Path

import pytest

from slopscore import SlopScorer
from slopscore.eval.datasets import load_jsonl
from slopscore.ingest.text import ingest_text, looks_like_markdown
from slopscore.models import Report, Severity, SourceType

_ROOT = Path(__file__).resolve().parents[1]

# The sweep script owns the comparison; import it rather than copy it, the way test_thresholds.py
# imports scripts/eval/thresholds.py, so the release-time sweep and this guard cannot drift.
_spec = importlib.util.spec_from_file_location(
    "sweep_sources", _ROOT / "scripts" / "eval" / "sweep_sources.py"
)
assert _spec and _spec.loader
sweep_sources = importlib.util.module_from_spec(_spec)
sys.modules["sweep_sources"] = sweep_sources
_spec.loader.exec_module(sweep_sources)

RULE_META_RUN = sweep_sources.RULE_META_RUN

# Enough plain-prose rows from each label to have power, few enough to stay cheap on four CI jobs.
_PER_LABEL = 6
# The one long-form row that carries a META_ finding (META_ENDOPHORIC_BACKREF), so the fixture
# is guaranteed to exercise the dimension's rules, not only its silence.
_META_ROW = 11


def _corpus() -> list[tuple[str, int]]:
    rows = load_jsonl(_ROOT / "eval" / "datasets" / "longform.jsonl")
    # Plain prose only: a row with Markdown syntax is sniffed onto the Markdown path by the text
    # ingester, and forcing the text path on it diverges for legitimate reasons.
    plain = [r for r in rows if not looks_like_markdown(r.text)]
    picked: list[tuple[str, int]] = []
    for label in (0, 1):
        picked.extend([(r.text, r.label) for r in plain if r.label == label][:_PER_LABEL])
    meta_row = rows[_META_ROW]
    assert not looks_like_markdown(meta_row.text)
    picked.append((meta_row.text, meta_row.label))
    return picked


@pytest.fixture(scope="module")
def scanned() -> list[dict[str, object]]:
    """Every corpus document scanned once per ingester, shared across the tests below."""
    scorer = SlopScorer()
    out: list[dict[str, object]] = []
    for text, label in _corpus():
        reports = {
            "text": sweep_sources.scan_plain(scorer, text),
            "markdown": sweep_sources.scan_markdown(scorer, text),
        }
        out.append({"text": text, "label": label, "reports": reports})
    return out


def _reports(entry: dict[str, object]) -> dict[str, Report]:
    reports = entry["reports"]
    assert isinstance(reports, dict)
    return reports


def test_the_text_path_is_what_a_user_gets() -> None:
    # The comparison is only meaningful if the "text" side is the path a .txt file or stdin
    # really takes. For these rows the ingester's own dispatch picks the text path; an earlier
    # version compared ".txt" against ".md" and 18 of its 33 documents were sniffed as Markdown on
    # both sides, a self-comparison.
    labels = set()
    for text, label in _corpus():
        labels.add(label)
        assert ingest_text(text).source_type is SourceType.text
    assert labels == {0, 1}


def test_fixture_exercises_the_metadiscourse_rules(scanned: list[dict[str, object]]) -> None:
    # Without this, a change that silenced every META_ rule would pass the tests below.
    meta = [
        e.rule_id
        for entry in scanned
        for report in _reports(entry).values()
        for e in report.findings
        if e.rule_id.startswith("META_")
    ]
    assert meta


def test_no_rule_fires_under_one_ingester_only(scanned: list[dict[str, object]]) -> None:
    divergent: dict[str, str] = {}
    for entry in scanned:
        reports = _reports(entry)
        # Both sides are asserted, so a regression that routed either one through the other
        # ingester turns this into a visible failure rather than a silent self-comparison.
        assert reports["text"].input.source_type is SourceType.text
        assert reports["markdown"].input.source_type is SourceType.markdown
        for rule in sweep_sources.ingester_divergence(reports["text"], reports["markdown"]):
            divergent.setdefault(rule, str(entry["text"])[:70])
    assert divergent == {}


def test_no_high_severity_run_on_clean_documents(scanned: list[dict[str, object]]) -> None:
    # Round 4's plain-text defect produced exactly this, and it trips --fail-on high for users.
    # README.md goes through the Markdown ingester because headings and lists are the structure
    # the run guard exists for, and no corpus row above has any.
    scorer = SlopScorer()
    readme = sweep_sources.scan_markdown(scorer, (_ROOT / "README.md").read_text(encoding="utf-8"))
    reports = [readme] + [
        r for entry in scanned if entry["label"] == 0 for r in _reports(entry).values()
    ]
    for report in reports:
        for e in report.findings:
            assert not (e.rule_id == RULE_META_RUN and e.severity is Severity.high)


def test_section_openers_under_headings_are_not_one_run() -> None:
    # The IMRaD shape: four sections each opening with a signpost. Headings break a run, so this
    # is four signposts, not a high-severity run of four.
    text = "\n\n".join(
        f"## {title}\n\nIn this section we will describe the {noun} we have taken here."
        for title, noun in [
            ("Introduction", "motivation"),
            ("Methods", "approach"),
            ("Results", "outcome"),
            ("Discussion", "interpretation"),
        ]
    )
    report = sweep_sources.scan_markdown(SlopScorer(), text)
    assert report.input.source_type is SourceType.markdown
    assert any(e.rule_id == "META_SECTION_PLAN" for e in report.findings)
    assert not any(e.rule_id == RULE_META_RUN for e in report.findings)


_RUN = (
    "To be clear, the framing here is what actually matters most of all. In short, the point "
    "is not really about any of that at all either. Simply put, none of this is about the "
    "subject at hand whatsoever."
)


def test_a_genuine_run_is_found_flat_and_never_invented_by_wrapping() -> None:
    """Flat text and Markdown report the run; wrapping may lose it but never adds to it.

    The negative tests above pass with the run term switched off; the flat half of this one does
    not. Wrapped prose is judged conservatively: a wrap fragment and its completion break a run.
    """
    scorer = SlopScorer()
    flat, wrapped = sweep_sources.wrap_variants(_RUN)
    assert "\n" in wrapped
    found = [sweep_sources.scan_plain(scorer, flat), sweep_sources.scan_markdown(scorer, flat)]
    for report in found:
        runs = [e for e in report.findings if e.rule_id == RULE_META_RUN]
        assert len(runs) == 1
        assert runs[0].severity is Severity.medium
    assert found[0].dimensions.metadiscourse == found[1].dimensions.metadiscourse
    wrapped_report = sweep_sources.scan_plain(scorer, wrapped)
    assert wrapped_report.dimensions.metadiscourse <= found[0].dimensions.metadiscourse
    assert len([e for e in wrapped_report.findings if e.rule_id == RULE_META_RUN]) <= 1


@pytest.mark.parametrize("path", ["text", "markdown"])
def test_signposts_in_separate_paragraphs_are_not_one_run(path: str) -> None:
    # Must hold on BOTH ingesters. It held only on Markdown until paragraph breaks were used as
    # the boundary, because doc.blocks is empty for every non-Markdown source.
    text = (
        "In this section we will describe the approach we have taken.\n\n"
        "As noted above, the framing here is what actually matters most of all.\n\n"
        "To be clear, the point is not really about any of that at all.\n"
    )
    scan = sweep_sources.scan_plain if path == "text" else sweep_sources.scan_markdown
    report = scan(SlopScorer(), text)
    assert not any(e.rule_id == RULE_META_RUN for e in report.findings)


def _meta(report: Report) -> list[tuple[str, str]]:
    return sorted(
        (e.rule_id, e.severity.value) for e in report.findings if e.rule_id.startswith("META_")
    )


def test_hard_wrapping_adds_no_metadiscourse_finding() -> None:
    """Hard-wrapped prose must never produce a metadiscourse finding flat prose does not.

    ``_ruleset.py`` compiles every pattern with ``re.MULTILINE``, so a ``^`` anchor is a LINE
    anchor, and pysbd splits hard-wrapped text on line breaks. Together those made a paragraph
    wrapped at 60 columns (a code comment, a plain-text file, a commit message) fire
    clause-anchored markers mid-sentence and escalate to a run. Compared as multisets, so a wrap
    that adds a second copy of a finding fails too, and at several widths plus a wrap after every
    bracket, quote, colon, and semicolon.
    """
    scorer = SlopScorer()
    no_meta = (
        "The team reviewed the two lists and the schedule, and precision matters more than "
        "speed for this path, and to be clear, they said the deadline had not moved, and "
        "overall, the next item was deferred to the spring."
    )
    one_meta = (
        "The team reviewed the two lists and the schedule and, in short, nothing about the "
        "plan had changed at all by then. To be clear, the deadline had not moved at all for "
        "anyone."
    )
    assert _meta(sweep_sources.scan_plain(scorer, no_meta)) == []
    assert _meta(sweep_sources.scan_plain(scorer, one_meta)) == [("META_CLARIFY_FRAME", "low")]
    for text in (no_meta, one_meta):
        flat = sweep_sources.scan_plain(scorer, text)
        variants = [textwrap.fill(text, w) for w in (40, 60, 72)]
        variants.append(sweep_sources.punctuation_wrap(text))
        for wrapped in variants:
            report = sweep_sources.scan_plain(scorer, wrapped)
            assert not (Counter(_meta(report)) - Counter(_meta(flat))), wrapped
            assert report.dimensions.metadiscourse <= flat.dimensions.metadiscourse


def test_wrapping_the_corpus_adds_no_metadiscourse_finding() -> None:
    # The invariant, on real rows rather than fixtures written to pass it.
    scorer = SlopScorer()
    for text, _label in _corpus():
        flat, wrapped = sweep_sources.wrap_variants(text)
        base = sweep_sources.scan_plain(scorer, flat)
        for variant in (wrapped, sweep_sources.punctuation_wrap(flat)):
            report = sweep_sources.scan_plain(scorer, variant)
            assert not (Counter(_meta(report)) - Counter(_meta(base)))
            assert report.dimensions.metadiscourse <= base.dimensions.metadiscourse
