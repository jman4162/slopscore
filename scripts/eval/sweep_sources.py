"""Scan the same documents through every ingester and diff the findings.

Two review rounds found defects of one shape: behavior that differs by ingester. v0.14's worst was
``Document.in_block_kind`` returning False whenever ``doc.blocks`` is empty, so the guard meant to
stop a metadiscourse run crossing a section boundary applied to Markdown alone. On plain text --
stdin, extracted code comments, web articles -- three signposts in three paragraphs read as one
"run of 3 consecutive sentences", and four made it high severity, tripping ``--fail-on high``. The
test that claimed to cover it passed only because it routed through the Markdown ingester.

Neither round found that by reading a diff; both found it by running the code. So this sweeps the
committed long-form corpus and the repository's own prose through each applicable ingester and
reports every rule that fires under one and not another.

Run: python scripts/eval/sweep_sources.py
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from slopscore import SlopScorer
from slopscore.eval.datasets import load_jsonl
from slopscore.models import Severity

# Rules that legitimately depend on document structure, so their absence on plain text is correct
# rather than a bug. Anything NOT listed here firing under one ingester and not another is a
# finding: write the exception down or fix the rule.
STRUCTURE_DEPENDENT = frozenset(
    {
        "STRUCTURE_EMOJI_HEADING",
        "STRUCTURE_INLINE_HEADER_LIST",
        "STRUCTURE_SKIPPED_HEADING_LEVEL",
        "STRUCTURE_THEMATIC_BREAKS",
        "STRUCTURE_BOLD_DENSITY",
        "STRUCTURE_TITLE_CASE_HEADING",
        # Markdown emphasis markers hide phrases from the text ingester, and headings and list
        # items are excluded from cadence and from metadiscourse runs only when blocks exist.
        "CADENCE_UNIFORM_RUN",
    }
)


def _scan(scorer: SlopScorer, tmp: Path, text: str, suffix: str) -> Any:
    """Scan through the real suffix dispatch in ``ingest.from_path``.

    Not ``from_string``: it ignores the source name and always uses the text ingester, so
    comparing from_string(text, "x.md") against from_string(text, "x.txt") compares a document
    with itself. An earlier version of this script did exactly that and reported no divergence
    on 193 documents, which is the same empty assertion a review round caught elsewhere in this
    release.
    """
    path = tmp / f"doc{suffix}"
    path.write_text(text, encoding="utf-8")
    return scorer.scan_file(path)


def sweep(scorer: SlopScorer, documents: list[tuple[str, str, int]]) -> dict[str, Any]:
    """Scan each document as .txt and as .md; report rules that differ."""
    divergent: Counter[str] = Counter()
    high_runs: list[str] = []
    meta_hits: Counter[str] = Counter()
    examples: dict[str, str] = {}

    tmp = Path(tempfile.mkdtemp(prefix="slopscore-sweep-"))
    for name, text, label in documents:
        txt = _scan(scorer, tmp, text, ".txt")
        md = _scan(scorer, tmp, text, ".md")
        as_txt = {e.rule_id for e in txt.findings}
        as_md = {e.rule_id for e in md.findings}

        for rule in (as_txt ^ as_md) - STRUCTURE_DEPENDENT:
            divergent[rule] += 1
            examples.setdefault(rule, name)

        for report in (txt, md):
            for e in report.findings:
                if e.rule_id.startswith("META_"):
                    meta_hits[e.rule_id] += 1
                if (
                    e.rule_id == "META_RUN_OF_META_SENTENCES"
                    and e.severity is Severity.high
                    and label == 0
                ):
                    high_runs.append(name)

    return {
        "n_documents": len(documents),
        "divergent_rules": dict(divergent),
        "divergent_examples": examples,
        "high_severity_runs_on_clean_rows": sorted(set(high_runs)),
        "meta_hits": dict(meta_hits),
    }


def by_paragraph_ranks_by_density(scorer: SlopScorer) -> bool:
    """A short dense paragraph must outrank a long mild one.

    The invariant the reverted global density floor broke: under a floor a paragraph's score
    tracks its absolute hit count rather than its density, and ``--by-paragraph`` exists to rank.
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


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    scorer = SlopScorer()
    documents = collect(root)
    result = sweep(scorer, documents)
    result["by_paragraph_ranks_by_density"] = by_paragraph_ranks_by_density(scorer)

    out = root / "eval" / "results" / "source_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"swept {result['n_documents']} documents as .txt and .md")
    print(f"  rules differing by ingester : {result['divergent_rules'] or 'none'}")
    print(f"  high-severity runs on clean : {result['high_severity_runs_on_clean_rows'] or 'none'}")
    print(f"  META_ hits                  : {result['meta_hits'] or 'none'}")
    print(f"  --by-paragraph by density   : {result['by_paragraph_ranks_by_density']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
