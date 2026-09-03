"""Recommended score thresholds from labeled long-form corpora.

For each genre profile, scores every document of at least ``--min-words`` words, drops the ones
that abstained, and reports:

- the human-good score distribution (P50 / P90 / P95 / P99), pooled and per subgroup;
- the false-positive rate (clean docs at or above the cutoff) and true-positive rate (slop docs at
  or above it) for each candidate cutoff;
- a recommended ``score_threshold``: the smallest cutoff with pooled FPR <= 5%, floored at the
  pooled human-good P95, and the per-subgroup FPR at that cutoff.

Subgroups listed in ``NEVER_POOLED`` (pre-1929 essays, whose register trips modern-prose rules)
are reported on their own and excluded from the pooled numbers. P95 is reported only when the
pooled clean set has at least 100 documents and P99 only at 300, so the table cannot state a
tail percentile the data cannot support.

Writes ``docs/thresholds.md`` (Markdown) and ``eval/thresholds.json``. numpy only; no scikit-learn.

Run: python scripts/eval/thresholds.py [--dataset PATH ...] [--profile blog ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from slopscore.config import Settings, Strictness  # noqa: E402
from slopscore.core import SlopScorer  # noqa: E402
from slopscore.eval.datasets import LabeledRow, load_jsonl  # noqa: E402
from slopscore.scoring.profiles import KNOWN_PROFILES  # noqa: E402

CACHE = Path.home() / ".cache" / "slopscore"
NEVER_POOLED = {"gutenberg"}
CUTOFFS = (25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75)
MIN_N_P95 = 100
MIN_N_P99 = 300


def _score(rows: list[LabeledRow], profile: str, strictness: str) -> list[dict]:
    engine = SlopScorer(settings=Settings(profile=profile, strictness=Strictness(strictness)))
    out = []
    for r in rows:
        rep = engine.scan_text(r.text)
        out.append(
            {
                "label": r.label,
                "subgroup": r.subgroup,
                "bucket": r.bucket,
                "score": rep.score.slop_score,
                "abstained": rep.score.abstained,
                "words": rep.input.word_count,
            }
        )
    return out


def _percentiles(scores: np.ndarray) -> dict[str, float | None]:
    n = len(scores)
    out: dict[str, float | None] = {"p50": None, "p90": None, "p95": None, "p99": None}
    if n == 0:
        return out
    out["p50"] = round(float(np.percentile(scores, 50)), 1)
    out["p90"] = round(float(np.percentile(scores, 90)), 1)
    if n >= MIN_N_P95:
        out["p95"] = round(float(np.percentile(scores, 95)), 1)
    if n >= MIN_N_P99:
        out["p99"] = round(float(np.percentile(scores, 99)), 1)
    return out


def _rates(clean: np.ndarray, slop: np.ndarray, cutoff: float) -> tuple[float | None, float | None]:
    fpr = float(np.mean(clean >= cutoff)) if len(clean) else None
    tpr = float(np.mean(slop >= cutoff)) if len(slop) else None
    return fpr, tpr


def analyze(scored: list[dict]) -> dict:
    kept = [s for s in scored if not s["abstained"]]
    pooled = [s for s in kept if s["subgroup"] not in NEVER_POOLED]
    clean = np.array([s["score"] for s in pooled if s["label"] == 0], dtype=float)
    slop = np.array([s["score"] for s in pooled if s["label"] == 1], dtype=float)

    by_group: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    for group in sorted({s["subgroup"] for s in kept}):
        by_group[group]["clean"] = np.array(
            [s["score"] for s in kept if s["subgroup"] == group and s["label"] == 0]
        )
        by_group[group]["slop"] = np.array(
            [s["score"] for s in kept if s["subgroup"] == group and s["label"] == 1]
        )

    table = []
    for c in CUTOFFS:
        fpr, tpr = _rates(clean, slop, c)
        table.append({"cutoff": c, "fpr": fpr, "tpr": tpr})

    recommended: float | None = None
    if len(clean) >= MIN_N_P95:
        p95 = float(np.percentile(clean, 95))
        for c in CUTOFFS:
            if float(np.mean(clean >= c)) <= 0.05 and c >= p95:
                recommended = float(c)
                break
        if recommended is None:
            recommended = float(CUTOFFS[-1])

    per_group = {}
    for group, arrs in by_group.items():
        entry: dict = {
            "n_clean": len(arrs["clean"]),
            "n_slop": len(arrs["slop"]),
            "clean_percentiles": _percentiles(arrs["clean"]),
            "pooled": group not in NEVER_POOLED,
        }
        if recommended is not None:
            fpr, tpr = _rates(arrs["clean"], arrs["slop"], recommended)
            entry["fpr_at_recommended"] = fpr
            entry["tpr_at_recommended"] = tpr
        per_group[group] = entry

    return {
        "n_scored": len(scored),
        "n_abstained": len(scored) - len(kept),
        "n_clean_pooled": len(clean),
        "n_slop_pooled": len(slop),
        "clean_percentiles": _percentiles(clean),
        "cutoffs": table,
        "recommended_score_threshold": recommended,
        "subgroups": per_group,
    }


def _fmt(x: float | None, pct: bool = False) -> str:
    if x is None:
        return "n/a"
    return f"{x:.2f}" if pct else f"{x:.1f}"


def render_markdown(results: dict[str, dict], strictness: str, sources: list[str]) -> str:
    lines = [
        "# Recommended score thresholds",
        "",
        "Generated by `python scripts/eval/thresholds.py`; do not edit by hand. Strictness "
        f"`{strictness}`. Documents under 100 words abstain and are excluded. Sources: "
        + ", ".join(f"`{s}`" for s in sources)
        + ".",
        "",
        "A **recommended `score_threshold`** is the smallest cutoff with pooled false-positive rate "
        "at or under 5% on human-good documents, floored at that set's P95. It is stated only when "
        f"the pooled clean set has at least {MIN_N_P95} documents. P99 needs {MIN_N_P99}.",
        "",
        "## How to read this",
        "",
        "- **Stay under the clean P95** for the profile you write in: that is where documented "
        "human prose lands, and a draft above it is unusual enough to be worth a look at the "
        "findings.",
        "- **Gate CI at the recommended cutoff** with `score_threshold` (or `--fail-on-score`); "
        "the FPR column is the share of human-good documents that would fail.",
        "- **The TPR column is the recall on Wikipedia articles editors flagged as suspected "
        "AI-generated.** It is low. Those labels are subjective and often about citations or "
        "markup rather than prose, and the flagged articles are encyclopedic prose without the "
        'blog-style tells the rule packs target. Read a low TPR as "this gate will not catch '
        'wild Wikipedia slop", not as "the threshold is wrong".',
        "- Human-good sources: FineWeb-Edu pages from Common Crawl dumps dated 2021 or earlier "
        "(pre-LLM by construction), arXiv abstracts through 2021, random Wikipedia articles from "
        'the 2023-11 snapshot ("not flagged", not "pre-LLM"), and pre-1929 essays '
        "(reported separately, never pooled).",
        "",
        "| profile | n clean | n slop | clean P50 | P90 | P95 | P99 | recommended | FPR | TPR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile, r in results.items():
        p = r["clean_percentiles"]
        rec = r["recommended_score_threshold"]
        fpr = tpr = None
        if rec is not None:
            row = next(t for t in r["cutoffs"] if t["cutoff"] == rec)
            fpr, tpr = row["fpr"], row["tpr"]
        lines.append(
            f"| {profile} | {r['n_clean_pooled']} | {r['n_slop_pooled']} | {_fmt(p['p50'])} | "
            f"{_fmt(p['p90'])} | {_fmt(p['p95'])} | {_fmt(p['p99'])} | "
            f"{_fmt(rec)} | {_fmt(fpr, True)} | {_fmt(tpr, True)} |"
        )
    lines += ["", "## Cutoff sweep (pooled)", ""]
    for profile, r in results.items():
        lines += [f"### {profile}", "", "| cutoff | FPR | TPR |", "|---:|---:|---:|"]
        for t in r["cutoffs"]:
            lines.append(f"| {t['cutoff']} | {_fmt(t['fpr'], True)} | {_fmt(t['tpr'], True)} |")
        lines.append("")
    lines += ["## Per subgroup at the recommended cutoff", ""]
    for profile, r in results.items():
        lines += [
            f"### {profile}",
            "",
            "| subgroup | pooled | n clean | n slop | clean P50 | P90 | P95 | FPR | TPR |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for group, g in r["subgroups"].items():
            p = g["clean_percentiles"]
            lines.append(
                f"| {group} | {'yes' if g['pooled'] else 'no'} | {g['n_clean']} | {g['n_slop']} | "
                f"{_fmt(p['p50'])} | {_fmt(p['p90'])} | {_fmt(p['p95'])} | "
                f"{_fmt(g.get('fpr_at_recommended'), True)} | "
                f"{_fmt(g.get('tpr_at_recommended'), True)} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", action="append", type=Path, help="labeled JSONL (repeatable)")
    ap.add_argument("--profile", action="append", choices=KNOWN_PROFILES)
    ap.add_argument("--strictness", default="conservative")
    ap.add_argument("--min-words", type=int, default=100)
    ap.add_argument("--output", type=Path, default=ROOT / "docs" / "thresholds.md")
    ap.add_argument("--json", type=Path, default=ROOT / "eval" / "thresholds.json")
    args = ap.parse_args()

    paths = args.dataset or sorted(CACHE.glob("*.jsonl"))
    rows = [r for p in paths for r in load_jsonl(p) if len(r.text.split()) >= args.min_words]
    if not rows:
        sys.exit("no rows; fetch corpora first (scripts/eval/fetch.py)")
    profiles = args.profile or list(KNOWN_PROFILES)
    results = {}
    for profile in profiles:
        print(f"[{profile}] scoring {len(rows)} rows ...", flush=True)
        results[profile] = analyze(_score(rows, profile, args.strictness))
    payload = {
        "strictness": args.strictness,
        "min_words": args.min_words,
        "sources": [str(p) for p in paths],
        "profiles": results,
    }
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.output.write_text(
        render_markdown(results, args.strictness, [p.name for p in paths]) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} and {args.json}")


if __name__ == "__main__":
    main()
