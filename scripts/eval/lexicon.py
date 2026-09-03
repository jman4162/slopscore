"""Corpus-derived slop lexicon candidates (the slop-forensics / Antislop method).

Counts the DOCUMENT frequency of unigrams, bigrams, and trigrams in a SLOP corpus and a HUMAN
baseline corpus, and ranks n-grams by the smoothed ratio of those shares. An n-gram is a candidate
when it occurs in at least ``--min-count`` slop documents and its document share is at least
``--min-ratio`` times the baseline's. Function-word-only n-grams, n-grams with digits, and n-grams
that are capitalized mid-sentence in most documents (proper nouns) are dropped.

The output is a REVIEW file (``eval/lexicon_candidates.yaml``), not a rule pack: a ratio says a
model over-produces a phrase relative to the baseline, not that the phrase is slop in every
register. Promote reviewed entries into ``data/lexicons/markers.yaml`` by hand, with the ratio
and the corpora recorded in ``source``.

Run:
  python scripts/eval/lexicon.py --slop ~/.cache/slopscore/mage.jsonl:1 \\
      --human ~/.cache/slopscore/mage.jsonl:0 --human ~/.cache/slopscore/fineweb_edu_pre2022.jsonl
``PATH:LABEL`` restricts a JSONL file to one label; a bare path uses every row.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import regex as re

_TOKEN = re.compile(r"[a-z][a-z'-]*")
_STOP = frozenset(
    """a an the and or but if so of to in on at by for from with as is are was were be been being
    it its this that these those there here he she they we you i me him her them us my your his
    their our not no nor do does did done have has had can could will would shall should may
    might must than then when where which who whom whose what why how all any each every some
    such only own same too very just also into onto over under up down out about after before
    between through during while because until again further once s t d ll re ve m""".split()
)


def _load(spec: str) -> list[str]:
    path, _, label = spec.partition(":")
    texts = []
    with Path(path).expanduser().open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if label and str(row.get("label")) != label:
                continue
            texts.append(row["text"])
    return texts


_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _doc_grams(text: str, n: int) -> tuple[set[str], set[str]]:
    """Distinct n-grams in one document, and the n-grams that contained a capitalized word not
    at sentence start (proper-noun evidence)."""
    words = _WORD.findall(text)
    grams: set[str] = set()
    proper: set[str] = set()
    for i in range(len(words) - n + 1):
        window = words[i : i + n]
        low = [w.lower() for w in window]
        if all(t in _STOP for t in low):
            continue
        gram = " ".join(low)
        grams.add(gram)
        for j, w in enumerate(window):
            at_start = (i + j == 0) or words[i + j - 1][-1:] in ".!?" if i + j else True
            if w[0].isupper() and not at_start:
                proper.add(gram)
                break
    return grams, proper


def _doc_freq(texts: list[str], n: int) -> tuple[Counter[str], Counter[str]]:
    df: Counter[str] = Counter()
    proper: Counter[str] = Counter()
    for text in texts:
        grams, prop = _doc_grams(text, n)
        df.update(grams)
        proper.update(prop)
    return df, proper


def candidates(
    slop: list[str], human: list[str], *, n: int, min_count: int, min_ratio: float
) -> list[dict]:
    """Rank by DOCUMENT-frequency ratio: the share of slop documents containing the n-gram over
    the share of human documents containing it. Token counts reward a phrase repeated inside a
    few documents (a shared prompt); document frequency does not. N-grams that were capitalized
    mid-sentence in most of their documents are dropped as proper nouns."""
    sdf, sprop = _doc_freq(slop, n)
    hdf, _ = _doc_freq(human, n)
    ns, nh = len(slop), len(human)
    out = []
    for gram, c in sdf.items():
        if c < min_count or any(ch.isdigit() for ch in gram):
            continue
        if sprop.get(gram, 0) / c > 0.5:
            continue
        slop_share = (c + 0.5) / (ns + 1)
        human_share = (hdf.get(gram, 0) + 0.5) / (nh + 1)
        ratio = slop_share / human_share
        if ratio >= min_ratio:
            out.append(
                {
                    "ngram": gram,
                    "n": n,
                    "slop_docs": c,
                    "human_docs": hdf.get(gram, 0),
                    "slop_share": round(slop_share, 4),
                    "human_share": round(human_share, 4),
                    "ratio": round(ratio, 1),
                    "log_ratio": round(math.log10(ratio), 2),
                }
            )
    out.sort(key=lambda d: (-d["ratio"], -d["slop_docs"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slop", action="append", required=True, help="JSONL[:label] of slop text")
    ap.add_argument("--human", action="append", required=True, help="JSONL[:label] baseline")
    ap.add_argument("--min-count", type=int, default=20)
    ap.add_argument("--min-ratio", type=float, default=10.0)
    ap.add_argument("--top", type=int, default=60, help="candidates kept per n-gram order")
    ap.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "eval" / "lexicon_candidates.yaml",
    )
    args = ap.parse_args()

    slop = [t for s in args.slop for t in _load(s)]
    human = [t for h in args.human for t in _load(h)]
    if not slop or not human:
        sys.exit("empty corpus")
    lines = [
        "# Corpus-derived slop lexicon CANDIDATES. Generated by scripts/eval/lexicon.py; review",
        "# before promoting anything into data/lexicons/markers.yaml. A ratio is over-production",
        "# relative to the baseline, not proof of slop in every register.",
        f"# slop corpora: {args.slop}",
        f"# human corpora: {args.human}",
        f"# slop docs: {len(slop)}  human docs: {len(human)}  min_count: {args.min_count}"
        f"  min_ratio: {args.min_ratio}",
        "candidates:",
    ]
    for n in (1, 2, 3):
        rows = candidates(slop, human, n=n, min_count=args.min_count, min_ratio=args.min_ratio)
        lines.append(f"  ngram_{n}:")
        for d in rows[: args.top]:
            lines.append(
                f"    - {{ngram: {json.dumps(d['ngram'])}, ratio: {d['ratio']}, "
                f"slop_docs: {d['slop_docs']}, human_docs: {d['human_docs']}}}"
            )
        print(f"{n}-grams: {len(rows)} candidates (showing {min(len(rows), args.top)})")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
