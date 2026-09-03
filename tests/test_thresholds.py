"""The threshold report's analysis is deterministic and refuses to state unsupported tails."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "thresholds", ROOT / "scripts" / "eval" / "thresholds.py"
)
assert spec and spec.loader
thresholds = importlib.util.module_from_spec(spec)
sys.modules["thresholds"] = thresholds
spec.loader.exec_module(thresholds)


def _rows(n_clean: int, n_slop: int, clean_scores, slop_scores):  # type: ignore[no-untyped-def]
    rows = []
    for i in range(n_clean):
        rows.append(
            {
                "label": 0,
                "subgroup": "web" if i % 2 else "wiki",
                "bucket": "human_good",
                "score": float(clean_scores(i)),
                "abstained": False,
                "words": 400,
            }
        )
    for i in range(n_slop):
        rows.append(
            {
                "label": 1,
                "subgroup": "wiki",
                "bucket": "wild_slop",
                "score": float(slop_scores(i)),
                "abstained": False,
                "words": 400,
            }
        )
    return rows


def test_recommended_cutoff_is_floored_at_p95_and_under_5pct_fpr() -> None:
    rows = _rows(200, 50, lambda i: i / 4, lambda i: 60 + i / 2)  # clean 0..50, slop 60..85
    result = thresholds.analyze(rows)
    rec = result["recommended_score_threshold"]
    assert rec is not None
    clean = [r["score"] for r in rows if r["label"] == 0]
    p95 = sorted(clean)[int(0.95 * len(clean))]
    assert rec >= p95
    row = next(t for t in result["cutoffs"] if t["cutoff"] == rec)
    assert row["fpr"] <= 0.05 and row["tpr"] == 1.0


def test_small_clean_sets_get_no_recommendation_or_tail_percentiles() -> None:
    result = thresholds.analyze(_rows(40, 10, lambda i: 5.0, lambda i: 70.0))
    assert result["recommended_score_threshold"] is None
    assert result["clean_percentiles"]["p95"] is None
    assert result["clean_percentiles"]["p50"] == 5.0


def test_never_pooled_subgroups_are_reported_but_excluded() -> None:
    rows = _rows(120, 20, lambda i: 3.0, lambda i: 70.0)
    for _i in range(30):
        rows.append(
            {
                "label": 0,
                "subgroup": "gutenberg",
                "bucket": "human_good",
                "score": 90.0,
                "abstained": False,
                "words": 400,
            }
        )
    result = thresholds.analyze(rows)
    assert result["n_clean_pooled"] == 120
    assert result["subgroups"]["gutenberg"]["pooled"] is False
    assert result["subgroups"]["gutenberg"]["fpr_at_recommended"] == 1.0
    assert result["clean_percentiles"]["p90"] == 3.0


def test_abstained_rows_are_dropped() -> None:
    rows = _rows(10, 0, lambda i: 99.0, lambda i: 0.0)
    for r in rows:
        r["abstained"] = True
    result = thresholds.analyze(rows)
    assert result["n_abstained"] == 10 and result["n_clean_pooled"] == 0


def test_markdown_render_has_one_row_per_profile() -> None:
    result = thresholds.analyze(_rows(150, 30, lambda i: i / 10, lambda i: 80.0))
    md = thresholds.render_markdown({"blog": result, "essay": result}, "conservative", ["x.jsonl"])
    assert md.count("| blog |") == 1 and md.count("| essay |") == 1
    assert "How to read this" in md


def test_longform_benchmark_is_committed_and_long() -> None:
    path = ROOT / "eval" / "datasets" / "longform.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    clean = [r for r in rows if r["label"] == 0]
    slop = [r for r in rows if r["label"] == 1]
    assert len(clean) >= 100 and len(slop) >= 50
    assert all(len(r["text"].split()) >= 300 for r in rows)
    assert all(r.get("url") for r in rows)  # attribution for CC-BY-SA / ODC-BY sources
