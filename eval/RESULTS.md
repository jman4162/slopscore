# Evaluation results (v0.14)

Reproduce with `python scripts/eval/report.py` (writes `eval/results.json`). Two evaluation sets:

- **benchmark** (`eval/datasets/benchmark.jsonl`, 149 rows): hand-authored, taxonomy-graded slop vs
  clean text (see `eval/RUBRIC.md`). This is **in-sample**: it includes the seed the model trained
  on, so its numbers measure discrimination on *overt* slop, not generalization.
- **longform** (`eval/datasets/longform.jsonl`, 180 rows, all 300+ words, committed): 60
  FineWeb-Edu pages from Common Crawl dumps dated 2021 or earlier (pre-LLM by construction,
  ODC-BY), 60 random Wikipedia articles from the 2023-11 snapshot (CC-BY-SA), and 60 full
  Wikipedia articles editors flagged as suspected AI-generated (CC-BY-SA). Every row carries a
  `url`. **Eval-only**: the positives are subjective editor judgments.
- **wiki_aicleanup** (180 rows, full articles via `scripts/eval/fetch.py wiki_aicleanup --full
  --per-class 90`; not committed): flagged articles (label 1) vs random articles (label 0).
  **Held-out and eval-only**. The earlier 40-row slice used lead sections only.

## Headline numbers (rule scorer, the shipped default)

**v0.14 note on the benchmark row.** The set gained eight `label 0` rows exercising
metadiscourse. They were written to be hard, and one of them exposed a pre-existing false positive
that had never been measured because no row exercised it: `FORMULAIC_SIMPLY_PUT` scoring "In other
words, you need two coins before you get on" at 66.0, because one low-severity hit saturates a
16-word document. On the 149-row set that row alone takes TPR@1%FPR from 0.571 to 0.329 and
`simple_english` FPR to 0.05, by raising the 1%-FPR operating point. With `metadiscourse` disabled
the same set gives the same threshold and the same TPR, so this is a measurement the new rows
expose, not a regression they cause. The v0.13 figure of 0.571 was measured on a set that did not
contain the row. Fixing it by flooring the density denominator globally was tried for this release
and reverted, for the reasons in `MODEL_CARD.md`.

| Set | n | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (in-sample, overt slop, 13-40 words) | 149 | 0.857 | 0.863 | 0.329 | 0.213 |
| longform (committed, 300+ words, eval-only) | 180 | 0.705 | 0.593 | 0.133 | 0.251 |
| wiki_aicleanup, full articles (held-out) | 180 | 0.746 | 0.770 | 0.111 | 0.415 |
| wiki_aicleanup, lead sections only (v0.10 slice) | 40 | 0.647 | 0.627 | 0.000 | 0.463 |

v0.12 measured 0.613 / 0.083 on longform and 0.802 / 0.144 on the full-article slice. v0.13's
structure tells, quote skipping, and the human-signal cap raised the long-form numbers and
lowered the full-article ones: flagged Wikipedia articles quote sources heavily (quoted tells are
now skipped by design) and their unflagged neighbours carry many numbers (the cap limits how far
those pull a clean article down). Both sets are reported; neither was tuned to.

Full articles separate far better than leads (AUROC 0.80 vs 0.65): the flagged article's lead is
often clean while later sections carry the tells. The mixed long-form set is harder because its
negatives are pre-LLM web pages and 2023 Wikipedia, both of which score very low, while the
positives are encyclopedic prose whose tells are sparse; per-100-word rates dilute them, so
flagged articles sit at P50 3.3 against 1.2 for unflagged ones (see `docs/thresholds.md`).

v0.9.1 scored 0.900 / 0.914 / 0.657 / 0.159 on the benchmark and 0.693 / 0.648 / 0.000 / 0.394
on the Wikipedia slice. v0.10 traded those points for correctness: the corroboration gate is
monotone, silenced rules no longer keep their points, genericity's weight was halved because it
read 1.0 on abstract human prose, and prompt residue decays in long documents. Every benchmark
row is 13 to 40 words, below the 100-word abstention floor, and its clean rows were written with
dates and prices so genericity would not fire on them, so the set cannot reward the genericity
fix and it penalizes the residue decay on short rows. The abstract-human false positive it could
not see went from 43.7 to under 5 (`tests/test_golden_scores.py`).

**Read this honestly.** slopscore separates overt formulaic slop from clean prose well (benchmark
PR-AUC 0.89). On real-world Wikipedia cases it ranks flagged articles above random ones (AUROC
0.75 on full articles) but catches only one in nine at a strict 1%-false-positive operating point
(TPR@1%FPR 0.111), and on the mixed long-form set one in eight (0.133). Two reasons: editor flags are subjective and often precautionary, and a flagged
article's lead paragraph is frequently clean even when later sections are not. The gap between the
two rows is the real limitation, and it is why the tool's accuracy claims stay modest.

## Thresholds

`scripts/eval/thresholds.py` scores 522 pooled human-good documents of 100+ words (FineWeb-Edu
pre-2022, arXiv abstracts through 2021, Wikipedia 2023) under every profile. Clean prose sits at
P50 7.4 to 7.6 and P95 at or under 11.7; a `score_threshold` of 25 gives a 1% false-positive
rate on every profile. The generated table is `docs/thresholds.md`.

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
keeps the transparent rule scorer as the default. ml stays opt-in. On the long-form and full-
article Wikipedia sets the learned model has the higher AUROC and the advisory gate would promote
it; it still fails the fairness half of the gate on the benchmark slices, and it ignores
`--strictness` and `--profile`, so it remains research-only.

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
  this 149-row set, and has zero weight on `prompt_residue`. Treat it as research-only.
