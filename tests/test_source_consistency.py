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
        ids = {s: {e.rule_id for e in reports[s].findings} for s in reports}
        for rule in (ids["text"] ^ ids["markdown"]) - sweep_sources.STRUCTURE_DEPENDENT:
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


def test_a_genuine_run_is_found_on_every_path() -> None:
    """The positive direction: flat, hard-wrapped, and Markdown all report the same run.

    The negative tests above pass with the run term switched off; this one does not. Wrapping
    once lost the run entirely: each wrapped meta sentence became a marker-less tail that ended
    it, so a hard-wrapped .txt scored 0.09 where the same prose flat scored 0.55.
    """
    scorer = SlopScorer()
    flat, wrapped = sweep_sources.wrap_variants(_RUN)
    assert "\n" in wrapped
    reports = [
        sweep_sources.scan_plain(scorer, flat),
        sweep_sources.scan_plain(scorer, wrapped),
        sweep_sources.scan_markdown(scorer, flat),
    ]
    for report in reports:
        runs = [e for e in report.findings if e.rule_id == RULE_META_RUN]
        assert len(runs) == 1
        assert runs[0].severity is Severity.medium
    assert len({r.dimensions.metadiscourse for r in reports}) == 1


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


def test_hard_wrapping_changes_no_metadiscourse_finding() -> None:
    """Hard-wrapped prose must produce exactly the metadiscourse findings flat prose does.

    ``_ruleset.py`` compiles every pattern with ``re.MULTILINE``, so a ``^`` anchor is a LINE
    anchor, and pysbd splits hard-wrapped text on line breaks. Together those made a paragraph
    wrapped at 60 columns -- a code comment, a plain-text file, a commit message -- fire
    clause-anchored markers mid-sentence and escalate to a run. Two fixtures: one with no
    metadiscourse at all, where a wrap puts "precision matters" at the head of a line, and one
    where a wrap puts "in short," at the head of a line mid-sentence beside a genuine marker.
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
    for text, expected in [(no_meta, []), (one_meta, [("META_CLARIFY_FRAME", "low")])]:
        for variant in (text, "\n".join(textwrap.wrap(text, 60))):
            assert _meta(sweep_sources.scan_plain(scorer, variant)) == expected, variant
