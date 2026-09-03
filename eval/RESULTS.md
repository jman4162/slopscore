# Evaluation results (v0.10)

Reproduce with `python scripts/eval/report.py` (writes `eval/results.json`). Two evaluation sets:

- **benchmark** (`eval/datasets/benchmark.jsonl`, 141 rows): hand-authored, taxonomy-graded slop vs
  clean text (see `eval/RUBRIC.md`). This is **in-sample**: it includes the seed the model trained
  on, so its numbers measure discrimination on *overt* slop, not generalization.
- **wiki_aicleanup** (40 rows): real Wikipedia articles editors flagged as suspected AI-generated
  (label 1) vs random articles (label 0), fetched via `scripts/eval/fetch.py wiki_aicleanup`.
  **Held-out and eval-only**: labels are subjective editor judgments; never used for training.

## Headline numbers (rule scorer, the shipped default)

| Set | n | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (in-sample, overt slop) | 141 | 0.873 | 0.886 | 0.557 | 0.274 |
| wiki_aicleanup (held-out, real wild slop) | 40 | 0.647 | 0.627 | 0.000 | 0.463 |

v0.9.1 scored 0.900 / 0.914 / 0.657 / 0.159 on the benchmark and 0.693 / 0.648 / 0.000 / 0.394
on the Wikipedia slice. v0.10 traded those points for correctness: the corroboration gate is
monotone, silenced rules no longer keep their points, genericity's weight was halved because it
read 1.0 on abstract human prose, and prompt residue decays in long documents. Every benchmark
row is 13 to 40 words, below the 100-word abstention floor, and its clean rows were written with
dates and prices so genericity would not fire on them, so the set cannot reward the genericity
fix and it penalizes the residue decay on short rows. The abstract-human false positive it could
not see went from 43.7 to under 5 (`tests/test_golden_scores.py`).

**Read this honestly.** slopscore separates overt formulaic slop from clean prose well (benchmark
PR-AUC 0.89). On real-world Wikipedia cases it is only moderately better than chance (AUROC 0.65)
and catches essentially none of the flagged articles at a strict 1%-false-positive operating point
(TPR@1%FPR 0.000). Two reasons: editor flags are subjective and often precautionary, and a flagged
article's lead paragraph is frequently clean even when later sections are not. The gap between the
two rows is the real limitation, and it is why the tool's accuracy claims stay modest.

## Fairness: why the rule scorer remains the default

Per-subgroup false-positive rate on the benchmark (decision threshold 50):

| Subgroup | n | rules FPR | ml FPR |
|---|---|---|---|
| general | 107 | 0.00 | 0.05 |
| simple_english | 17 | 0.00 | 0.59 |
| non_native | 17 | 0.00 | 0.27 |

The learned (`--scorer ml`) model edges the rule scorer on raw metrics (benchmark PR-AUC 0.929 vs
0.886) but **over-flags plain and non-native English**: 59% false positives on simple English and
27% on the non-native slice, versus 0% for the rule scorer. The replace-if-wins gate
(`eval.harness.should_promote`: no loss on TPR@1%FPR **and** no subgroup-FPR regression) therefore
keeps the transparent rule scorer as the default. ml stays opt-in.

## Authorship null check

slopscore detects slop patterns, not authorship. On the MAGE machine-vs-human corpus it is near
chance at low FPR (see `MODEL_CARD.md`), as intended: a high SlopScore means "dense with slop
patterns," not "written by AI."

## Caveats

- The benchmark is hand-authored and overlaps training; treat its numbers as an upper bound.
- The web-quality proxy sources (FinerWeb, FineWeb-Edu) label boilerplate/educational quality, which
  is slop-adjacent but not the same construct; the fetchers exist but those slices are not in these
  headline numbers.
- The Wikipedia slice is small (40) and subjectively labeled; its numbers carry wide error bars.
- TPR@1%FPR on 71 clean rows is TPR at zero false positives (the grid is 1/71 = 1.4%).
- The fairness slices are 17 and 15 self-authored clean rows; a 0.00 rate on 15 rows has a 95%
  upper bound near 0.22. `slopscore-lint fairness` reports the per-rule rates.
- `--scorer ml` ignores `--strictness` and `--profile`, was trained on a 128-row snapshot of
  this 141-row set, and has zero weight on `prompt_residue`. Treat it as research-only.
