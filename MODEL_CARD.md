# slopscore model card (v0.5)

## What it does

slopscore scores text for **AI-slop writing patterns**, formulaic, generic, low-specificity,
over-polished prose, and returns a 0-100 SlopScore with per-dimension breakdowns and evidence
spans. It is a transparent rule engine: every finding comes from a visible rule with a quotable
span, and the four span-less statistical dimensions (genericity, cadence, redundancy, human
signals) are low-weighted and reported per dimension. It does **not** determine authorship.

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
- **Formatting metric.** Em-dash overuse is measured as a dash-to-comma ratio (choosing a dash
  where a comma would do), which is invariant to document length and paragraph structure. It is not
  per-paragraph: the pipeline rejoins paragraphs and short inputs make that denominator degenerate.
  When the signal fires, a `FORMATTING_EM_DASH` span reports the count and ratio.

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

## v0.10 to v0.13: score correctness, long-form evaluation, and structure tells

An adversarial review (September 2026) found that silenced rules kept their points, the
corroboration gate was non-monotone, strictness was inverted on clean text, and the genericity
dimension read abstract human prose as slop. v0.10 fixed those (`CHANGELOG.md`), v0.11 added a
per-dimension `breakdown` and summary evidence for the statistical dimensions, and v0.12 added
the first long-form evaluation and data-derived thresholds; v0.13 added the `structure_tells`
dimension (chatbot Markdown shape), quote-aware sincerity and sourcing rules, and a cap on the
human-signal counterweight. Current numbers (`eval/RESULTS.md`):

| set | n | AUROC | PR-AUC | TPR@1%FPR |
|---|---:|---:|---:|---:|
| benchmark (13-40 words, in-sample) | 149 | 0.86 | 0.86 | 0.33 |
| long-form (300+ words, committed, eval-only) | 180 | 0.71 | 0.59 | 0.13 |
| Wikipedia AI-Cleanup, full articles (held-out) | 180 | 0.75 | 0.77 | 0.11 |

Thresholds (`docs/thresholds.md`): on 522 human-good long-form documents, clean prose sits at
P50 2.4 and P95 about 11 under every profile; `score_threshold = 25` gives a 1% false-positive
rate. Recall on flagged Wikipedia articles at that cutoff is 1%: their tells are sparse and
per-100-word rates dilute them. Closing that gap is the v0.13 detection work, not a threshold
change.

## v0.5: slop-labeled benchmark

v0.5 adds a real slop-labeled benchmark and retrains the learned scorer on it. Full numbers and
reproduction are in `eval/RESULTS.md` (`python scripts/eval/report.py`). Two evaluation sets:

- `eval/datasets/benchmark.jsonl` (149 rows): hand-authored, taxonomy-graded (Shaib et al.,
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
| general | 107 | 0.00 | 0.05 |
| simple_english | 17 | 0.00 | 0.59 |
| non_native | 17 | 0.00 | 0.27 |

(Current numbers; the v0.5 release reported 100 / 14 / 14 rows and 0.71 / 0.33. A 0.00 rate on
17 rows has a 95% upper bound near 0.20.)

The learned model, retrained on the benchmark (`slopscore-v0.5.json`), edges the rule scorer on raw
metrics but over-flags simple and non-native English. The replace-if-wins gate therefore keeps the
transparent rule scorer as the default; `--scorer ml` stays opt-in. The fairness guardrail is now
**measured on a non-native slice**, not just asserted: the rule scorer's false-positive rate on
that slice is 0.00.

## v0.7: interpretable feature upgrades (behind [nlp])

Following the v0.6 conclusion that features, not the model class, are the ceiling, v0.7 upgrades two
dimensions with interpretable signals, both validated to keep the fairness gate at 0% FPR on the
plain and non-native English slices:

- **Genericity** uses spaCy named-entity density (people, places, organizations, dates, quantities)
  instead of a proper-noun regex when `[nlp]` is installed. Benchmark AUROC rises 0.888 -> 0.902.
- **Redundancy** uses sentence-transformer (MiniLM) embedding similarity on adjacent sentences to
  catch rephrased repetition that TF-IDF misses (threshold 0.50, set from measured cosines).

Both are opt-in (`[nlp]`); the default install keeps the regex/TF-IDF paths. A sentence-length
burstiness signal was tried and reverted: it regressed the non-native slice (FPR 0.00 -> 0.17),
a reminder that sentence-length features are entangled with non-native style.

v0.7 also adds an **insight_signaling** dimension for pseudo-profundity tells that announce insight
rather than contain it ("load-bearing", "doing the real work", "the crux of the issue",
"pressure-test the claim") — borrowed from a higher-prestige essayist/rationalist register and empty
only at density, which is why the patterns are context-gated (e.g. "load-bearing wall" is not
flagged) and mostly low/medium severity. It is **rules-only**: excluded from the ML `FEATURE_ORDER`
so the committed `slopscore-v0.5.json` model needs no retrain (`--scorer ml` computes but ignores
it). An opt-in broad tier (`--broad`) adds rationalist jargon (steelman, epistemic humility, first
principles) that is legitimate in philosophy/tech writing; it is off by default because its
false-positive risk is higher, and its home register is exactly where this jargon is earned.
**Fairness caveat:** the `simple_english`/`non_native` benchmark slices (plain and ESL prose) do not
exercise competent native analytical writing, where these phrases legitimately appear; that
population is guarded instead by concrete-prose negative fixtures in `benchmark.jsonl` and by
`test_conservatism.py` (a lone insight phrase in long, specific prose stays below "severe").

v0.7 also expands the **weasel_attribution** dimension — the complementary "fake evidence" axis to
slop's "fake insight". Added (scored by default): impersonal-passive attribution ("it is widely
believed", "sources say"), unearned-certainty reasoning smells ("Clearly,", "needless to say", "it
goes without saying" — WP:AIWEASEL classes these as weasel words), and hedge+vague-adjective
("somewhat successful"). The textbook bare weasels — quantifiers (many/most), hedges (may/might),
intensifiers (very/really) — are **`--broad`-only** and off by default. That is a deliberate
fairness decision: in the fairness slices those words appear in *both* clean and slop rows (e.g.
"very"/"most"), so a default bare-word rule would have no discriminative power and would over-flag
non-native/simple English — the exact failure the tool exists to avoid. `--broad` reframes them as
an opt-in self-editing highlighter, not an accusation. The broad tier also excludes the hedges
`human_signals.py` credits as a positive human signal (perhaps/maybe/arguably/likely), since hedging
is correct epistemics in calibrated writing; only the *hedge + vague adjective* construction is
treated as a tell.

v0.14 adds a **metadiscourse** dimension for writing that refers to the text rather than to its
subject. This is Hyland's (2005) *interactive* metadiscourse (frame markers, endophoric markers,
code glosses), and the interactional half of his taxonomy was already covered here: hedges by
`weasel_attribution`, boosters by `significance_inflation`, attitude markers by
`performative_candor`. Rules-only, excluded from the ML `FEATURE_ORDER`.

It is a separate dimension rather than more `formulaic_structure` rules for the same reason
`performative_candor` is separate from `insight_signaling`: the genre multipliers must invert
harder than `formulaic_structure`'s 0.9-1.2 range can express. Academic and technical prose
signposts by design ("In this section we describe...", "As noted above"), so both are set to 0.5
against 1.15 for `blog`. `formulaic_structure` also carries unrelated template rules that should
not move with them. No rules were migrated out of `formulaic.yaml`: that would break rule-id
suppressions and `report/baseline.py` fingerprints in the wild, and the run detector reads a
separate non-scoring marker lexicon that is a superset of both, so it sees the whole surface
without needing them moved. Where the two would overlap the new rule is narrowed instead:
`META_RESTATEMENT_COLON` takes only the colon form `FORMULAIC_SIMPLY_PUT`'s comma gate misses.

**Why it scores concentration and not only density.** Every other rule pack scores
severity-weighted hits per 100 words. That normalizer cannot see this defect in long-form prose,
which is where it occurs. Measured: the passage that prompted the dimension saturates
`formulaic_structure` at 1.0 at 123 words and scores 0.064 at 3,373 words, taking the document to
9.6/low. That is the same effect this card already reports on the Wikipedia slice, where recall
is 1% because "their tells are sparse and per-100-word rates dilute them". So the dimension scores
`max(rate, concentration, recap)`, where the latter two are independent of document length.

**The evidence gate is the fairness gate.** A marker only counts toward a run when its sentence
carries no name, number, date, URL, or identifier. "In summary, Japan took 34 years to recover
from 1989" is a real summary sentence; "Precision matters here because the counter-argument will
not survive sloppy phrasing" is not. Restatement scaffolding over a concrete fact is a documented
ESL and simple-English clarity strategy, and this is what keeps the dimension off it. The same
predicate drops individual code-gloss and back-reference spans whose sentence carries a fact; the
prose-grading and frame-marker rules are deliberately not gated, since "the defensible version is"
announces the writing whatever facts sit beside it.

**Not weak, and what that costs.** `metadiscourse` is deliberately not a `WEAK_DIMENSION`: weak
means damped to 0.3 when alone, which is the exact failure the dimension exists to fix: a
2,592-word post whose other dimensions were clean scored 7.0 with the flagged passage unflagged.
Since `CORROBORATING_DIMENSIONS` is derived, that makes it a corroborator that can unlock the weak
dimensions. Three things contain it: the core tier is high-precision only with every ESL-risky
bare code gloss held in `--broad`, the dimension saturates at 4.0 rather than 3.0, and the density
denominator is floored at 100 words. That floor was added because the eval negatives showed a
single low-severity marker in a 17-word document saturating the dimension at 1.0 and taking two
clean rows from 13.8 to 50.2; `per_hundred_words` amplifies a document that short by 5.9x. The
other packs survive this by being weak-damped, which this one is not.

**Fairness.** Bare code glosses ("that is to say", "meaning that", clause-initial "Overall,") are
`--broad`-only, matching the decision made for bare quantifiers and bare sincerity adverbs above.
WP:AISIGNS is explicit that transition words in isolation "[have] precedence in essay-like writing
by humans and [are] accepted by many style guides, so this is not a strong tell". `benchmark.jsonl`
carries eight `label 0` rows exercising this dimension across `general`, `simple_english`, and
`non_native`; no positive rows were added, because rows written to contain the constructions the
rules were written to match would raise TPR without measuring anything. No `META_` rule fires on
either protected slice.

**Vintage caveat.** WP:AISIGNS files its section-summary and didactic-disclaimer signs under
*Historical indicators*, "much less frequent in newer models". That is true of the forms it lists,
and slopscore's pre-0.14 coverage matched that vintage exactly: of 16 probe constructions, the
four that matched a rule were all legacy closers ("in summary", "in other words", "the bottom line
is", "it's worth noting") and all twelve misses were forms current models produce. The behaviour
did not disappear; the form changed. Treat the legacy closers as the weak half of this dimension
and the prose-grading and frame-marker rules as the current half.

**Known limitations.** The residual `simple_english` FPR of 0.05 is `FORMULAIC_SIMPLY_PUT`, a
pre-existing rule, firing on "In other words, you need two coins before you get on" at 66.0. That
one row also moves the benchmark's headline TPR@1%FPR from 0.571 to 0.329 by raising the 1%-FPR
operating point; with `metadiscourse` disabled the same set gives the same threshold and the same
TPR, so it is a measurement these rows expose rather than a regression they cause. The recap term
measures shared vocabulary, not shared claims, so a paraphrase and a half-new closer land close
together. The 100-word density floor is a local fix for a defect every `severity_rate_score` pack
shares. Continuing: — a false
positive these rows made visible rather than one this dimension introduced. Separately, a
`METADISCOURSE` marker and a `formulaic_structure` template can both fire on one sentence ("In
summary," is a template *and* a frame marker). These are two measurements of one sentence rather
than one charged twice, and the run detector avoids compounding it by emitting a single span for
the whole run.

v0.9 adds a **performative_candor** dimension for manufactured sincerity: a point framed as a
difficult confession ("I have to be honest", "truth be told", "let me be candid"), a sincerity
adjective bolted to an abstract noun ("honest framing", "honest limits" standing in for
"limitations"), and manufactured reluctance ("I don't say this lightly"). It is the third axis
alongside the two above: `insight_signaling` flags fake *insight*, `weasel_attribution` fake
*evidence*, and this one fake *vulnerability*. Like `insight_signaling` it is **rules-only**,
excluded from the ML `FEATURE_ORDER` so the committed model needs no retrain.

It is a separate dimension rather than extra `insight_signaling` rules because the genre
multipliers point the opposite way. `insight_signaling` boosts `social` to 1.15; candor sets it to
**0.6**, because conversational "honestly" and "to be fair" are native human speech, and sets
`marketing` to 1.2 where `insight_signaling` softens to 0.9, because manufactured sincerity is
marketing's native failure mode. A shared dimension could not express either.

Two conservatism choices, both measured. The dimension saturates at 4.0 weighted hits per 100
words rather than the 3.0 the other packs use, because at 3.0 a single low-severity hit in a
60-word document scores 0.56 and crosses the corroboration gate's threshold. And it is a
`WEAK_DIMENSION`, so it is damped when it fires alone.

**Known limitation.** That damping means concrete, specific, first-person prose carrying heavy
candor filler scores low: a 119-word passage firing 13 candor rules scores 5.6, because
`performative_candor` is the only elevated dimension (damped to 0.3) while `human_writing_signals`
saturates at 1.0 on its dates and figures. This is deliberate. Such a passage reads as plausible
human memoir, and the benchmark contains no positive fixture of that shape on purpose — labeling
it slop would teach the eval set to punish specific writing. The findings are still reported as
evidence spans; only the composite score stays low. The tells the dimension does catch are candor
filler over generic prose, which is where it was reported.

**Fairness.** Bare sincerity adverbs (`genuinely`, `honestly` outside a clause opener) are
`--broad`-only, matching the decision made for bare quantifiers above: they carry no discriminative
power and appear throughout ESL prose. The core tier's most important property is that ESL calques
("Honestly speaking", "Frankly speaking") do not fire, because `CANDOR_ADVERB_PARENTHETICAL`
requires the comma directly after the adverb; `benchmark.jsonl` carries `non_native` rows asserting
this rather than leaving it to unit tests. One core rule does fire on the protected slices:
`CANDOR_TO_BE_HONEST` at 0.07 (1/15) on `non_native` and `CANDOR_ADVERB_PARENTHETICAL` at 0.06
(1/17) on `simple_english`. Both are under the 0.10/0.15 acceptance bars and document-level FPR
stays 0.00 on both slices, but the rates are published rather than tuned away.

**Gap in the fairness command.** `fairness_cmd` builds `SlopScorer(profile="blog")` with default
settings, so it never measures the `--broad` tier — and `CANDOR_BROAD_BARE_CANDOR` fires on ESL
rows by construction. That unmeasured risk is the reason the tier is off by default.

## v0.6: decided modeling non-goals

After the v0.5 benchmark, two modeling directions were evaluated and rejected:

- **No model retrain.** Held-out Wikipedia AUROC is 0.69 for *both* the rule scorer and the learned
  model, and 5 of 14 learned weights are already 0.0. The ceiling is set by the features, not the
  model fit, so retraining the same features on the same-size data cannot close the real-world gap.
- **No XGBoost / gradient boosting.** It is the same tree class as the LightGBM already rejected in
  v0.3: it breaks the numpy-only scan path, removes per-span traceability (the transparency
  mandate), over-flags plain and non-native English (the fairness gate), and tends to learn
  authorship rather than slop. What would actually help is interpretable feature work (entity
  density, semantic redundancy, sentence burstiness) and more real labeled data, planned for v0.7.

## Changes from v0.1

Added significance inflation, superficial "-ing" analyses, vague/over-attribution, negative
parallelism / rule-of-three, copula avoidance, formatting tells, and a negative human-writing
signal; expanded the cited lexicon; added the corroboration gate, abstention, and personal-baseline
calibration. The default install stays lean (regex + scikit-learn); spaCy precision is behind `[nlp]`.
