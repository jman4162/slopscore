# Benchmark and results

slopscore is evaluated on a committed, taxonomy-graded benchmark and on a held-out real-world
slice. Reproduce with `python scripts/eval/report.py`; full detail is in
[`eval/RESULTS.md`](https://github.com/jman4162/slopscore/blob/main/eval/RESULTS.md) and the
labeling rubric is in
[`eval/RUBRIC.md`](https://github.com/jman4162/slopscore/blob/main/eval/RUBRIC.md).

## Headline numbers (rule scorer, the default)

| Set | n | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (overt slop, in-sample, 13-40 words) | 141 | 0.87 | 0.89 | 0.56 | 0.27 |
| long-form (committed, 300+ words) | 180 | 0.61 | 0.47 | 0.08 | 0.30 |
| Wikipedia AI-Cleanup, full articles (held-out) | 180 | 0.80 | 0.82 | 0.14 | 0.47 |

Every benchmark row is 13 to 40 words, under the 100-word abstention floor, so its numbers
describe short-fragment discrimination only. The long-form set (v0.12) is the first evaluation on
documents the tool is meant for: 120 pre-LLM or unflagged human documents against 60 full
Wikipedia articles flagged as suspected AI-generated. Recommended thresholds derived from 522
human-good long-form documents are on the [Thresholds](thresholds.md) page.

slopscore separates overt formulaic slop from clean prose well. On real Wikipedia cases it is only
moderately better than chance and catches almost none at a strict 1%-false-positive operating
point. That gap is a real limitation, and it is why the accuracy claims stay modest.

## Fairness keeps the rule scorer the default

Per-subgroup false-positive rate on the benchmark:

| Subgroup | n | rules FPR | ml FPR |
|---|---|---|---|
| general | 107 | 0.00 | 0.05 |
| simple_english | 17 | 0.00 | 0.59 |
| non_native | 17 | 0.00 | 0.27 |

The learned model (`--scorer ml`) edges the rule scorer on raw metrics but over-flags plain and
non-native English. The replace-if-wins gate keeps the transparent rule scorer as the default; the
learned scorer stays opt-in. See [Limitations & authorship](limitations.md).
