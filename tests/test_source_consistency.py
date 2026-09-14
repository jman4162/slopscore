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
holds label-1 rows as well as label-0, and the one corpus row that carries a ``META_`` finding,
so a change that silenced the dimension outright turns it red.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

from slopscore import SlopScorer
from slopscore.eval.datasets import load_jsonl
from slopscore.ingest.text import looks_like_markdown
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
    plain = [(i, r) for i, r in enumerate(rows) if not looks_like_markdown(r.text)]
    picked: list[tuple[str, int]] = []
    for label in (0, 1):
        picked.extend((r.text, r.label) for _, r in plain if r.label == label)
        picked = picked[: _PER_LABEL * (label + 1)]
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


def test_the_two_paths_really_are_two_ingesters(scanned: list[dict[str, object]]) -> None:
    # An earlier version of this file compared ".txt" against ".md" through the suffix dispatch,
    # and 18 of its 33 documents were sniffed as Markdown on both sides: a self-comparison.
    assert {int(e["label"]) for e in scanned} == {0, 1}  # type: ignore[call-overload]
    for entry in scanned:
        reports = _reports(entry)
        assert reports["text"].input.source_type is SourceType.text
        assert reports["markdown"].input.source_type is SourceType.markdown


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
    for entry in scanned:
        if entry["label"] != 0:
            continue
        for report in _reports(entry).values():
            for e in report.findings:
                assert not (e.rule_id == RULE_META_RUN and e.severity is Severity.high)


_RUN = (
    "To be clear, the framing here is what actually matters most of all. In short, the point "
    "is not really about any of that at all either. Simply put, none of this is about the "
    "subject at hand whatsoever."
)


def test_a_genuine_run_is_found_on_every_path() -> None:
    """The positive direction: flat, hard-wrapped, and Markdown all report the same run.

    The negative tests above pass with the run term switched off; this one does not. Wrapping
    used to lose the run entirely: each wrapped meta sentence became a marker-less tail that
    ended it, so a hard-wrapped .txt scored 0.09 where the same prose flat scored 0.55.
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
    scan = getattr(sweep_sources, f"scan_{'plain' if path == 'text' else 'markdown'}")
    report = scan(SlopScorer(), text)
    assert not any(e.rule_id == RULE_META_RUN for e in report.findings)


def test_hard_wrapping_does_not_create_a_metadiscourse_run() -> None:
    """Hard-wrapped prose must not manufacture a run.

    ``_ruleset.py`` compiles every pattern with ``re.MULTILINE``, so a ``^`` anchor is a LINE
    anchor, and the marker lexicon is matched against each sentence in isolation, where ``\\A``
    is the head of that sentence. pysbd also splits hard-wrapped text on line breaks. Together
    those made a paragraph wrapped at 60 columns -- a code comment, a plain-text file, a commit
    message -- arrive as fragments each of which matched a clause-anchored marker, escalating
    text with no metadiscourse in it to a run. Two fixtures: one where no wrapped line starts at
    a marker, and one where a wrap puts a marker at the head of a line mid-sentence.
    """
    scorer = SlopScorer()
    fixtures = [
        "The team reviewed the two lists and the schedule, and precision matters more than "
        "speed for this path, and to be clear, they said the deadline had not moved, and "
        "overall, the next item was deferred to the spring.",
        "The team reviewed the two lists and the schedule and,\nin short, nothing about the "
        "plan had changed at all by then.\nTo be clear, the deadline had not moved at all for "
        "anyone.",
    ]
    for text in fixtures:
        for variant in (text, "\n".join(textwrap.wrap(" ".join(text.split()), 60))):
            findings = sweep_sources.scan_plain(scorer, variant).findings
            assert not any(e.rule_id == RULE_META_RUN for e in findings)
