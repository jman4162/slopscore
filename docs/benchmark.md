# Benchmark and results

slopscore is evaluated on a committed, taxonomy-graded benchmark and on a held-out real-world
slice. Reproduce with `python scripts/eval/report.py`; full detail is in
[`eval/RESULTS.md`](https://github.com/jman4162/slopscore/blob/main/eval/RESULTS.md) and the
labeling rubric is in
[`eval/RUBRIC.md`](https://github.com/jman4162/slopscore/blob/main/eval/RUBRIC.md).

## Headline numbers (rule scorer, the default)

| Set | n | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (overt slop, in-sample) | 128 | 0.89 | 0.91 | 0.65 | 0.18 |
| Wikipedia AI-Cleanup (held-out, real wild slop) | 40 | 0.69 | 0.65 | 0.00 | 0.39 |

slopscore separates overt formulaic slop from clean prose well. On real Wikipedia cases it is only
moderately better than chance and catches almost none at a strict 1%-false-positive operating
point. That gap is a real limitation, and it is why the accuracy claims stay modest.

## Fairness keeps the rule scorer the default

Per-subgroup false-positive rate on the benchmark:

| Subgroup | n | rules FPR | ml FPR |
|---|---|---|---|
| general | 100 | 0.00 | 0.06 |
| simple_english | 14 | 0.00 | 0.71 |
| non_native | 14 | 0.00 | 0.33 |

The learned model (`--scorer ml`) edges the rule scorer on raw metrics but over-flags plain and
non-native English. The replace-if-wins gate keeps the transparent rule scorer as the default; the
learned scorer stays opt-in. See [Limitations & authorship](limitations.md).
