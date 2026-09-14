"""Scan the same documents through every ingester and diff the findings.

Two review rounds found defects of one shape: behavior that differs by ingester. v0.14's worst was
``Document.in_block_kind`` returning False whenever ``doc.blocks`` is empty, so the guard meant to
stop a metadiscourse run crossing a section boundary applied to Markdown alone. On plain text --
stdin, extracted code comments, web articles -- three signposts in three paragraphs read as one
"run of 3 consecutive sentences", and four made it high severity, tripping ``--fail-on high``. The
test that claimed to cover it passed only because it routed through the Markdown ingester.

Neither round found that by reading a diff; both found it by running the code. So this sweeps the
committed long-form corpus and the repository's own prose through each applicable ingester and
reports every rule that fires under one and not another. The comparisons that are assertions
exit non-zero when they fail; the rest are recorded in ``eval/results/source_sweep.json`` to be
diffed between releases.

Run: python scripts/eval/sweep_sources.py
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any

import regex as re

from slopscore import SlopScorer
from slopscore.core import build_document
from slopscore.eval.datasets import load_jsonl
from slopscore.features.cadence import RULE_UNIFORM_RUN
from slopscore.features.metadiscourse import RULE_META_RUN
from slopscore.features.structure import StructureTells
from slopscore.ingest import RawSource
from slopscore.ingest.markdown import ingest_markdown
from slopscore.ingest.text import ingest_text, looks_like_markdown, strip_fenced_code
from slopscore.models import Report, Severity, SourceType
from slopscore.scoring.scorer import score_document

# Rules that legitimately depend on document structure, so their absence on plain text is correct
# rather than a bug. Derived, not copied: the next STRUCTURE_ rule joins it automatically.
# CADENCE_UNIFORM_RUN is here because headings and list items are excluded from cadence only when
# blocks exist. Anything NOT in this set firing under one ingester and not another is a finding:
# write the exception down or fix the rule.
STRUCTURE_DEPENDENT: frozenset[str] = StructureTells().rule_ids() | {RULE_UNIFORM_RUN}

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


def scan_plain(scorer: SlopScorer, text: str) -> Report:
    """The text ingester, with Markdown sniffing bypassed only where it would fire.

    ``ingest_text`` routes anything that looks like Markdown (two or more heading, list, bold or
    fence lines) through ``ingest_markdown``, so ``scan_file("x.txt")`` on such a document is
    the Markdown path under another name. An earlier version of this sweep compared the two
    suffixes and had 38 of 193 documents comparing a report with itself. Text that does not look
    like Markdown goes through ``ingest_text`` itself, so a change to that path is exercised here
    rather than shadowed by a copy; only sniffed documents get a hand-built text source.
    """
    if looks_like_markdown(text):
        raw = RawSource(text=strip_fenced_code(text), source_type=SourceType.text, source="doc.txt")
    else:
        raw = ingest_text(text, source="doc.txt")
    return score_document(build_document(raw), scorer.settings)


def scan_markdown(scorer: SlopScorer, text: str) -> Report:
    return score_document(build_document(ingest_markdown(text, source="doc.md")), scorer.settings)


def _rule_ids(report: Report) -> set[str]:
    return {e.rule_id for e in report.findings}


def ingester_divergence(text_report: Report, markdown_report: Report) -> set[str]:
    """Rules whose findings differ between the text and Markdown paths in a way that is a defect.

    Every rule must agree, with two exceptions that are correct by design. STRUCTURE_DEPENDENT
    rules read Markdown block structure the text path does not have. And the metadiscourse
    dimension judges a paragraph that contains a line break conservatively (no run, evidence over
    the whole paragraph), while the Markdown ingester joins soft line breaks into one line. So on
    the text path a ``META_`` finding may be missing, but it may never be extra, and that is
    compared as a multiset.
    """
    text_counts = Counter(e.rule_id for e in text_report.findings)
    markdown_counts = Counter(e.rule_id for e in markdown_report.findings)
    out: set[str] = set()
    for rule in set(text_counts) | set(markdown_counts):
        if rule in STRUCTURE_DEPENDENT:
            continue
        if rule.startswith("META_"):
            if text_counts[rule] > markdown_counts[rule]:
                out.add(rule)
        elif (text_counts[rule] > 0) != (markdown_counts[rule] > 0):
            out.add(rule)
    return out


def sweep(scorer: SlopScorer, documents: list[tuple[str, str, int]]) -> dict[str, Any]:
    """Scan each plain-prose document as text and as Markdown; report rules that differ.

    Only documents with no Markdown syntax are compared across ingesters: forcing the text path
    on a Markdown file is an expected divergence (emphasis markers hide phrases, tables and
    fences become prose), not a defect. Markdown documents are still scanned, through their own
    ingester, for the META_ counts and the high-severity check.
    """
    divergent: Counter[str] = Counter()
    high_runs: list[str] = []
    meta_hits: Counter[str] = Counter()
    examples: dict[str, str] = {}
    compared = 0

    for name, text, label in documents:
        if looks_like_markdown(text):
            reports = [scan_markdown(scorer, text)]
        else:
            compared += 1
            reports = [scan_plain(scorer, text), scan_markdown(scorer, text)]
            assert reports[0].input.source_type is SourceType.text
            assert reports[1].input.source_type is SourceType.markdown
            for rule in ingester_divergence(reports[0], reports[1]):
                divergent[rule] += 1
                examples.setdefault(rule, name)

        for report in reports:
            for e in report.findings:
                if e.rule_id.startswith("META_"):
                    meta_hits[e.rule_id] += 1
                if e.rule_id == RULE_META_RUN and e.severity is Severity.high and label == 0:
                    high_runs.append(name)

    return {
        "n_documents": len(documents),
        "n_compared_across_ingesters": compared,
        "divergent_rules": dict(divergent),
        "divergent_examples": examples,
        "high_severity_runs_on_clean_rows": sorted(set(high_runs)),
        "meta_hits": dict(meta_hits),
    }


def by_paragraph_ranks_by_density(scorer: SlopScorer) -> bool:
    """A short dense paragraph must outrank a long mild one.

    The invariant the reverted global density floor broke: under a floor a paragraph's score
    tracks its absolute hit count rather than its density, and ``--by-paragraph`` exists to rank.
    ``tests/test_conservatism.py`` pins the same pair.
    """
    short_dense = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders."
    )
    long_mild = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders. "
        "Costs rose 12 percent since the previous quarter, largely because of steel prices. "
        "Members asked the contractor for a revised schedule before the next session begins. "
        "The minutes record four abstentions and no dissent at all on the final vote taken. "
    )
    return (
        scorer.scan_text(short_dense).score.slop_score
        > scorer.scan_text(long_mild).score.slop_score
    )


def collect(root: Path) -> list[tuple[str, str, int]]:
    docs: list[tuple[str, str, int]] = []
    for row in load_jsonl(root / "eval" / "datasets" / "longform.jsonl"):
        docs.append((f"longform:{len(docs)}", row.text, row.label))
    for rel in ("README.md", "MODEL_CARD.md", "CHANGELOG.md", "CLAUDE.md", "DATA_SOURCES.md"):
        p = root / rel
        if p.exists():
            docs.append((f"repo:{rel}", p.read_text(encoding="utf-8"), 0))
    for p in sorted((root / "docs").glob("*.md")):
        docs.append((f"docs:{p.name}", p.read_text(encoding="utf-8"), 0))
    return docs


def wrap_variants(text: str, width: int = 60) -> tuple[str, str]:
    """The same prose flat and hard-wrapped, with its paragraph breaks kept in both.

    Paragraphs are preserved so the paragraph guard and the blank-line arm of the clause anchor
    are exercised; an earlier version collapsed every document to one paragraph, so the flat
    variant could never contain a run that crossed one. Hyphen and long-word breaking are off:
    "ever-\\nevolving" is an artifact of ``textwrap``, not a property of wrapped prose.
    """
    paragraphs = [" ".join(p.split()) for p in _PARAGRAPH_BREAK.split(text) if p.strip()]
    flat = "\n\n".join(paragraphs)
    wrapped = "\n\n".join(
        "\n".join(textwrap.wrap(p, width, break_on_hyphens=False, break_long_words=False))
        for p in paragraphs
    )
    return flat, wrapped


_WRAP_AFTER = re.compile(r"""(?<=[)\]"':;]) """)


def punctuation_wrap(flat: str) -> str:
    """Break the line after every closing bracket, quote, colon, and semicolon a space follows.

    The adversarial wrap. ``textwrap`` breaks wherever the column falls, so it rarely lands on the
    characters that matter: review round 9 found that wrapping after ``)``, a closing quote, or a
    colon created metadiscourse runs, and no width-based wrap of the corpus had exercised it.
    """
    return "\n\n".join(_WRAP_AFTER.sub("\n", p) for p in flat.split("\n\n"))


def sweep_wrapping(scorer: SlopScorer, documents: list[tuple[str, str, int]]) -> dict[str, Any]:
    """The same text, hard-wrapped and not, through the SAME ingester.

    This is the comparison that catches the MULTILINE class, and comparing .txt against .md does
    not: wrapping a Markdown document breaks its syntax, so the two ingesters legitimately see
    different prose and the cross-ingester diff is full of expected noise. Holding the ingester
    fixed and varying only line breaks isolates the defect.

    Asserted: for every document and both wrap variants (60 columns, and a line break after every
    bracket, quote, colon, and semicolon), no metadiscourse finding appears more often wrapped
    than flat, and the metadiscourse score does not rise. The feature guarantees this by
    construction (a line-structured paragraph forms no run and is judged as a whole), and this is
    the check that the construction holds on real text. Wrapping may REMOVE findings; that false
    negative is accepted.

    Recorded, not asserted: the other rules that differ at 60 columns. Most of that set is
    whole-text patterns with a literal space ("studies show") that cannot match across a line
    break, plus pysbd re-segmenting at line breaks for the sentence-level features. It predates
    v0.14 and is written down to be diffed rather than gated on.
    """
    divergent: Counter[str] = Counter()
    examples: dict[str, str] = {}
    flat_runs = wrapped_runs = 0
    added: list[str] = []
    for name, text, _label in documents:
        if looks_like_markdown(text):
            continue
        flat, wrapped = wrap_variants(text)
        a = scan_plain(scorer, flat)
        meta_a = Counter(e.rule_id for e in a.findings if e.rule_id.startswith("META_"))
        for variant_name, variant in (("60col", wrapped), ("punct", punctuation_wrap(flat))):
            b = scan_plain(scorer, variant)
            meta_b = Counter(e.rule_id for e in b.findings if e.rule_id.startswith("META_"))
            if (meta_b - meta_a) or b.dimensions.metadiscourse > a.dimensions.metadiscourse:
                added.append(f"{name}:{variant_name}")
            if variant_name == "60col":
                flat_runs += meta_a[RULE_META_RUN]
                wrapped_runs += meta_b[RULE_META_RUN]
                for rule in _rule_ids(a) ^ _rule_ids(b):
                    divergent[rule] += 1
                    examples.setdefault(rule, name)
    return {
        "wrap_divergent_rules": dict(divergent),
        "wrap_divergent_examples": examples,
        "meta_runs_flat": flat_runs,
        "meta_runs_wrapped": wrapped_runs,
        "meta_findings_added_by_wrapping": added,
    }


def sweep_code(scorer: SlopScorer, root: Path) -> dict[str, Any]:
    """The code ingester against the text ingester on the same source files.

    ``.py`` prose is docstrings and comments only; through the text path the whole file is prose.
    Rules that fire on one and not the other are expected here -- the point is to record WHICH,
    so a change in that set is visible. The text side bypasses sniffing: a Python file with a
    few ``# - item`` comment lines otherwise routes through the Markdown ingester.
    """
    divergent: Counter[str] = Counter()
    files = sorted((root / "src" / "slopscore").rglob("*.py"))
    for f in files:
        source = f.read_text(encoding="utf-8")
        as_code = scorer.scan_file(f)
        as_text = scan_plain(scorer, source)
        for rule in _rule_ids(as_code) ^ _rule_ids(as_text):
            divergent[rule] += 1
    return {"n_files": len(files), "code_vs_text_divergence": dict(divergent)}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    scorer = SlopScorer()
    documents = collect(root)
    result = sweep(scorer, documents)
    result["by_paragraph_ranks_by_density"] = by_paragraph_ranks_by_density(scorer)
    result.update(sweep_wrapping(scorer, documents))
    result["code_ingester"] = sweep_code(scorer, root)

    out = root / "eval" / "results" / "source_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    failures: list[str] = []
    if result["divergent_rules"]:
        failures.append(f"rules differing by ingester: {result['divergent_rules']}")
    if result["high_severity_runs_on_clean_rows"]:
        failures.append(
            f"high-severity runs on clean rows: {result['high_severity_runs_on_clean_rows']}"
        )
    if not result["by_paragraph_ranks_by_density"]:
        failures.append("--by-paragraph ranks by length, not density")
    if result["meta_findings_added_by_wrapping"]:
        failures.append(
            f"wrapping added a metadiscourse finding or raised the score: {result['meta_findings_added_by_wrapping']}"
        )

    print(
        f"swept {result['n_documents']} documents "
        f"({result['n_compared_across_ingesters']} plain-prose, compared text vs Markdown)"
    )
    print(f"  rules differing by ingester : {result['divergent_rules'] or 'none'}  (asserted)")
    print(
        f"  high-severity runs on clean : "
        f"{result['high_severity_runs_on_clean_rows'] or 'none'}  (asserted)"
    )
    print(f"  META_ hits                  : {result['meta_hits'] or 'none'}")
    print(f"  --by-paragraph by density   : {result['by_paragraph_ranks_by_density']}  (asserted)")
    print(
        f"  META runs flat / wrapped    : {result['meta_runs_flat']} / {result['meta_runs_wrapped']}"
        f"  (asserted: wrapping adds no finding; added: {result['meta_findings_added_by_wrapping'] or 'none'})"
    )
    print(
        f"  rules differing by wrapping : {len(result['wrap_divergent_rules'])} rules "
        "(recorded, repo-wide, not gated)"
    )
    code = result["code_ingester"]
    print(
        f"  code vs text on {code['n_files']:3d} .py files : {code['code_vs_text_divergence'] or 'none'}"
    )
    print(f"wrote {out}")
    for f in failures:
        print(f"FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
