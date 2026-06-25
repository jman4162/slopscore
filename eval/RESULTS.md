# Evaluation results (v0.5)

Reproduce with `python scripts/eval/report.py` (writes `eval/results.json`). Two evaluation sets:

- **benchmark** (`eval/datasets/benchmark.jsonl`, 128 rows): hand-authored, taxonomy-graded slop vs
  clean text (see `eval/RUBRIC.md`). This is **in-sample**: it includes the seed the model trained
  on, so its numbers measure discrimination on *overt* slop, not generalization.
- **wiki_aicleanup** (40 rows): real Wikipedia articles editors flagged as suspected AI-generated
  (label 1) vs random articles (label 0), fetched via `scripts/eval/fetch.py wiki_aicleanup`.
  **Held-out and eval-only**: labels are subjective editor judgments; never used for training.

## Headline numbers (rule scorer, the shipped default)

| Set | n | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (in-sample, overt slop) | 128 | 0.888 | 0.910 | 0.651 | 0.177 |
| wiki_aicleanup (held-out, real wild slop) | 40 | 0.693 | 0.648 | 0.000 | 0.394 |

**Read this honestly.** slopscore separates overt formulaic slop from clean prose well (benchmark
PR-AUC 0.91). On real-world Wikipedia cases it is only moderately better than chance (AUROC 0.69)
and catches essentially none of the flagged articles at a strict 1%-false-positive operating point
(TPR@1%FPR 0.000). Two reasons: editor flags are subjective and often precautionary, and a flagged
article's lead paragraph is frequently clean even when later sections are not. The gap between the
two rows is the real limitation, and it is why the tool's accuracy claims stay modest.

## Fairness: why the rule scorer remains the default

Per-subgroup false-positive rate on the benchmark (decision threshold 50):

| Subgroup | n | rules FPR | ml FPR |
|---|---|---|---|
| general | 100 | 0.00 | 0.06 |
| simple_english | 14 | 0.00 | 0.71 |
| non_native | 14 | 0.00 | 0.33 |

The learned (`--scorer ml`) model edges the rule scorer on raw metrics (benchmark PR-AUC 0.933 vs
0.910) but **over-flags plain and non-native English**: 71% false positives on simple English and
33% on the non-native slice, versus 0% for the rule scorer. The replace-if-wins gate
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
