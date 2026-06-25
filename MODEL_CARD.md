# slopscore model card (v0.5)

## What it does

slopscore scores text for **AI-slop writing patterns**, formulaic, generic, low-specificity,
over-polished prose, and returns a 0-100 SlopScore with per-dimension breakdowns and evidence
spans. It is a transparent rule engine: every point comes from a visible rule with a quotable
span. It does **not** determine authorship.

## What it is not

It is not an AI-authorship detector and must not be used to accuse a writer. Authorship detectors
are unreliable and biased; slopscore deliberately reports patterns, not provenance.

## Intended use

Writers, editors, bloggers, maintainers, and content teams self-checking drafts. Not for
punitive or disciplinary decisions about people.

## How it scores

Rule-based features per dimension → each a [0,1] score → weighted sum → sigmoid → 0-100.
Conservatism guardrails (v0.2):

- **Corroboration gate.** Weak-alone tells (lexical markers, parallelism, copula avoidance,
  formatting) are damped when no other dimension co-fires. A single fancy word or em dash cannot
  by itself reach "severe".
- **Negative signal.** `human_writing_signals` (plain verbs, superlatives, hedges, concrete
  numbers) lowers the score for specific, plain prose.
- **Abstention.** On input under ~100 words, or detected non-English, the label is capped at
  "mild" and a reason is reported.

## Detection grounding (sources)

Dimensions and the lexicon are drawn from Wikipedia's "Signs of AI writing" (WP:AISIGNS) and the
research it cites:

- Juzek & Ward, "Why Does ChatGPT 'Delve' So Much?" (arXiv:2412.11385), overused vocabulary.
- Kobak et al., "Delving into LLM-assisted writing…" (Science Advances 2025), excess vocabulary.
- Reinhart et al., "Do LLMs write like humans?" (PNAS 2025), present-participle / rhetorical style.
- Geng & Trotta (arXiv:2404.08627), decline of "is/are" copulas in post-2022 writing.
- Russell et al. (ACL 2025), humans detect AI near chance; expert LLM-users rely on lexical cues.

Vocabulary drifts by model era (GPT-4 → GPT-4o → GPT-5); the lexicon tags terms with their era.

## Limitations and fairness

- **Non-native English false positives.** Liang et al. (Patterns 2023) found AI detectors flag
  non-native-English (e.g. TOEFL) essays at up to ~61%. slopscore mitigates with the corroboration
  gate, the negative human signal, and abstention, but residual risk remains. Do not treat a
  high score on plain or non-native English as evidence of anything about the author.
- **Short text.** Under ~300 words confidence is low; under ~100 the score abstains.
- **Genre.** Marketing and travel writing naturally resemble slop; use `--profile` to reweight.
- **Adversarial edits.** Light paraphrasing evades pattern matching, as it does all detectors.
- **Coverage.** Wikipedia/markup-specific and authorship-signal tells are intentionally excluded;
  slopscore is a general-prose tool.

## v0.3: learned scorer and evaluation

v0.3 adds an evaluation framework (`slopscore-lint eval`) and a transparent learned scorer: a
**sign-constrained, Platt-calibrated logistic regression** over the 13 interpretable dimensions
(slop dimensions weight ≥ 0, `human_writing_signals` ≤ 0). It is serialized as auditable JSON
(`data/model/slopscore-v0.5.json`) and runs with pure numpy at scan time, `--scorer ml`.

**The rule scorer remains the default.** Under the replace-if-wins gate, the learned model must
both (a) not lose on TPR@1%FPR and (b) not regress any subgroup false-positive rate. On the
committed seed set it does neither cleanly:

| scorer | TPR@1%FPR | PR-AUC | ECE | simple-English FPR |
|---|---|---|---|---|
| rules | 0.80 | 0.96 | 0.14 | 0.00 |
| ml (out-of-fold) | 0.77 | 0.96 | 0.12 | n/a |
| ml (in-sample, seed) | 0.80 | 0.98 | 0.06 | **0.62** |

The learned model improves calibration but **over-flags plain/simple English** (a fairness
regression on exactly the population detectors are known to harm) and does not beat the rules on
held-out TPR@1%FPR. So `--scorer ml` is available and opt-in; `rules` stays default. This is the
gate working as intended, not a failure.

Caveats: these numbers are from the small hand-authored seed set (~54 rows; in-sample for ml
unless noted out-of-fold). They are illustrative, not a serious benchmark, run `slopscore-lint eval`
on the fetched public corpora (`scripts/eval/fetch.py`, see `DATA_SOURCES.md`) for real figures.

### Real-corpus experiment (MAGE): and why it validates the design

Held-out test split of the committed seed + a fetched MAGE subset (CC-BY; ~1,450 rows total,
30% test), via `scripts/eval/experiment.py`:

| scorer | TPR@1%FPR | TPR@5%FPR | PR-AUC | ECE |
|---|---|---|---|---|
| rules | 0.06 | 0.08 | 0.51 | 0.29 |
| LR (sign-constrained) | 0.10 | 0.11 | 0.52 | 0.03 |
| LightGBM (monotone, **experiment only**) | 0.09 | 0.13 | **0.75** | 0.02 |

**MAGE labels by authorship (machine vs human), not by slop.** That the slop scorers sit near
chance at low FPR on MAGE is the design working, not failing: slopscore detects slop *patterns*,
not provenance, so it should *not* cleanly separate well-written machine text from human text.
The learned variants improve calibration sharply (ECE 0.29 → 0.02-0.03), and LightGBM extracts
more authorship signal from the same 13 features nonlinearly (PR-AUC 0.75). We **do not ship
LightGBM**: it needs trees at scan time (breaking the pure-numpy path), and optimizing it against
authorship labels would turn slopscore into an authorship detector, the one thing it refuses to be. The **shipped model stays the seed-trained, slop-labeled LR**, and
the **rule scorer stays the default**. The shipped model is never trained on MAGE.

## v0.5: slop-labeled benchmark

v0.5 adds a real slop-labeled benchmark and retrains the learned scorer on it. Full numbers and
reproduction are in `eval/RESULTS.md` (`python scripts/eval/report.py`). Two evaluation sets:

- `eval/datasets/benchmark.jsonl` (128 rows): hand-authored, taxonomy-graded (Shaib et al.,
  "Measuring AI Slop", arXiv:2509.19163) slop vs clean text, with `simple_english` and `non_native`
  fairness slices. In-sample (overlaps the training seed); measures discrimination on overt slop.
- Wikipedia AI-Cleanup (40 rows): articles editors flagged as suspected AI-generated vs random
  articles. Held-out and eval-only (subjective labels, never used for training).

| set | scorer | AUROC | PR-AUC | TPR@1%FPR | ECE |
|---|---|---|---|---|---|
| benchmark (overt slop, in-sample) | rules | 0.89 | 0.91 | 0.65 | 0.18 |
| benchmark | ml | 0.92 | 0.94 | 0.68 | 0.06 |
| Wikipedia AI-Cleanup (held-out) | rules | 0.69 | 0.65 | 0.00 | 0.39 |

**Honest reading.** slopscore separates overt formulaic slop from clean prose well, but on real
Wikipedia cases it is only moderately better than chance (AUROC 0.69) and catches essentially none
of the flagged articles at a strict 1%-false-positive threshold. That gap is the real limitation,
and it is why the accuracy framing stays modest rather than being relaxed.

Per-subgroup false-positive rate on the benchmark, which keeps the rule scorer the default:

| subgroup | n | rules FPR | ml FPR |
|---|---|---|---|
| general | 100 | 0.00 | 0.06 |
| simple_english | 14 | 0.00 | 0.71 |
| non_native | 14 | 0.00 | 0.33 |

The learned model, retrained on the benchmark (`slopscore-v0.5.json`), edges the rule scorer on raw
metrics but over-flags simple and non-native English. The replace-if-wins gate therefore keeps the
transparent rule scorer as the default; `--scorer ml` stays opt-in. The fairness guardrail is now
**measured on a non-native slice**, not just asserted: the rule scorer's false-positive rate on
that slice is 0.00.

## Changes from v0.1

Added significance inflation, superficial "-ing" analyses, vague/over-attribution, negative
parallelism / rule-of-three, copula avoidance, formatting tells, and a negative human-writing
signal; expanded the cited lexicon; added the corroboration gate, abstention, and personal-baseline
calibration. The default install stays lean (regex + scikit-learn); spaCy precision is behind `[nlp]`.
