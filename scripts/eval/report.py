"""Run the committed benchmark (+ any cached external slices) and write eval/results.json.

Reproduces the numbers in eval/RESULTS.md. The committed benchmark is in-sample (it overlaps the
seed the model trained on); the cached Wikipedia AI-Cleanup slice is held-out and eval-only.

Run: python scripts/eval/report.py
"""

from __future__ import annotations

import json
from pathlib import Path

from slopscore.eval.datasets import load_jsonl
from slopscore.eval.harness import evaluate, should_promote

CACHE = Path.home() / ".cache" / "slopscore"


def _run(path: Path, name: str, eval_only: bool) -> dict:
    rows = load_jsonl(path)
    out = {"name": name, "path": str(path), "eval_only": eval_only, "n": len(rows)}
    for kind in ("rules", "ml"):
        out[kind] = evaluate(rows, profile="blog", scorer=kind)
    out["promote_ml"] = should_promote(out["rules"], out["ml"])
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    results = [_run(root / "eval" / "datasets" / "benchmark.jsonl", "benchmark", eval_only=False)]
    wiki = CACHE / "wiki_aicleanup.jsonl"
    if wiki.exists():
        results.append(_run(wiki, "wiki_aicleanup (held-out, eval-only)", eval_only=True))

    out = root / "eval" / "results.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for r in results:
        rm, mm = r["rules"]["metrics"], r["ml"]["metrics"]
        print(f"\n## {r['name']}  (n={r['n']})")
        print(
            f"  rules: AUROC={rm['auroc']:.3f} PR-AUC={rm['pr_auc']:.3f} "
            f"TPR@1%FPR={rm['tpr_at_1fpr']:.3f} ECE={rm['ece']:.3f}"
        )
        print(
            f"  ml   : AUROC={mm['auroc']:.3f} PR-AUC={mm['pr_auc']:.3f} "
            f"TPR@1%FPR={mm['tpr_at_1fpr']:.3f} ECE={mm['ece']:.3f}"
        )
        for g, gv in r["rules"]["fairness"].items():
            mv = r["ml"]["fairness"].get(g, {})
            print(
                f"    [{g}] n={gv['n']} rules_FPR={gv['fpr']:.2f} ml_FPR={mv.get('fpr', float('nan')):.2f}"
            )
        print(f"  promote ml -> default: {r['promote_ml']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
