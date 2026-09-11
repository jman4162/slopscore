"""A rule must not fire under one ingester and not another.

Two v0.14 review rounds found defects of exactly this shape. The worst: ``in_block_kind`` returns
False whenever ``doc.blocks`` is empty, so the guard meant to stop a metadiscourse run crossing a
section boundary applied to Markdown alone. On plain text -- stdin, extracted code comments, web
articles -- three signposts in three paragraphs read as one "run of 3 consecutive sentences", and
four made it ``high`` severity, which trips ``--fail-on high``. The test that claimed to cover it
passed only because it routed through the Markdown ingester.

Neither round found that by reading a diff; both found it by running the code. These assertions
are the ones ``scripts/eval/sweep_sources.py`` applies at release time, kept here so they hold
afterwards too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from slopscore import SlopScorer, scan_text
from slopscore.eval.datasets import load_jsonl
from slopscore.models import Severity

_ROOT = Path(__file__).resolve().parents[1]

# Rules that legitimately depend on document structure, so their absence on plain text is correct.
# Anything not listed here differing by ingester is a defect, not an exception.
STRUCTURE_DEPENDENT = frozenset(
    {
        "STRUCTURE_EMOJI_HEADING",
        "STRUCTURE_INLINE_HEADER_LIST",
        "STRUCTURE_SKIPPED_HEADING_LEVEL",
        "STRUCTURE_THEMATIC_BREAKS",
        "STRUCTURE_BOLD_DENSITY",
        "STRUCTURE_TITLE_CASE_HEADING",
        "CADENCE_UNIFORM_RUN",
    }
)


def _corpus() -> list[tuple[str, int]]:
    # A slice, not the whole set: scripts/eval/sweep_sources.py runs all 193 documents at release
    # time and commits the artifact. This is the regression guard, and it runs on three Python
    # versions in CI, so it stays cheap.
    rows = load_jsonl(_ROOT / "eval" / "datasets" / "longform.jsonl")
    docs = [(r.text, r.label) for r in rows[:30]]
    for rel in ("README.md", "MODEL_CARD.md", "CLAUDE.md"):
        docs.append(((_ROOT / rel).read_text(encoding="utf-8"), 0))
    return docs


@pytest.fixture(scope="module")
def scanned(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, object]]:
    """Every corpus document scanned once per ingester, shared across the tests below."""
    tmp = tmp_path_factory.mktemp("sources")
    scorer = SlopScorer()
    out: list[dict[str, object]] = []
    for i, (text, label) in enumerate(_corpus()):
        reports = {}
        for suffix in (".txt", ".md"):
            p = tmp / f"doc{i}{suffix}"
            p.write_text(text, encoding="utf-8")
            reports[suffix] = scorer.scan_file(p)
        out.append({"text": text, "label": label, "reports": reports})
    return out


def test_no_rule_fires_under_one_ingester_only(scanned: list[dict[str, object]]) -> None:
    divergent: dict[str, str] = {}
    differing_source_types = 0
    for entry in scanned:
        reports = entry["reports"]
        if reports[".txt"].input.source_type != reports[".md"].input.source_type:
            differing_source_types += 1
        ids = {s: {e.rule_id for e in reports[s].findings} for s in reports}
        for rule in (ids[".txt"] ^ ids[".md"]) - STRUCTURE_DEPENDENT:
            divergent.setdefault(rule, str(entry["text"])[:70])
    # Guard against the assertion going vacuous: the two paths must really be different ingesters.
    assert differing_source_types > 10
    assert divergent == {}


def test_no_high_severity_run_on_clean_documents(scanned: list[dict[str, object]]) -> None:
    # Round 4's plain-text defect produced exactly this, and it trips --fail-on high for users.
    for entry in scanned:
        if entry["label"] != 0:
            continue
        for report in entry["reports"].values():
            for e in report.findings:
                assert not (
                    e.rule_id == "META_RUN_OF_META_SENTENCES" and e.severity is Severity.high
                )


def test_by_paragraph_ranks_by_density_not_length() -> None:
    # The invariant the reverted global density floor broke: under a floor a paragraph's score
    # tracks its absolute hit count, so a long mild paragraph outranked a short dense one.
    short_dense = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders."
    )
    long_mild = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders. "
        "Costs rose 12 percent since the previous quarter, largely because of steel prices. "
        "Members asked the contractor for a revised schedule before the next session begins. "
        "The minutes record four abstentions and no dissent at all on the final vote taken. "
    )
    assert scan_text(short_dense).score.slop_score > scan_text(long_mild).score.slop_score


@pytest.mark.parametrize("suffix", [".txt", ".md"])
def test_signposts_in_separate_paragraphs_are_not_one_run(tmp_path: Path, suffix: str) -> None:
    # Must hold on BOTH ingesters. It held only on Markdown until paragraph breaks were used as
    # the boundary, because doc.blocks is empty for every non-Markdown source.
    text = (
        "In this section we will describe the approach we have taken.\n\n"
        "As noted above, the framing here is what actually matters most of all.\n\n"
        "To be clear, the point is not really about any of that at all.\n"
    )
    p = tmp_path / f"doc{suffix}"
    p.write_text(text, encoding="utf-8")
    report = SlopScorer().scan_file(p)
    assert not any(e.rule_id == "META_RUN_OF_META_SENTENCES" for e in report.findings)
