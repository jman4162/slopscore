# slopscore model card (v0.2)

## What it does

slopscore scores text for **AI-slop writing patterns** — formulaic, generic, low-specificity,
over-polished prose — and returns a 0–100 SlopScore with per-dimension breakdowns and evidence
spans. It is a transparent rule engine: every point comes from a visible rule with a quotable
span. It does **not** determine authorship.

## What it is not

It is not an AI-authorship detector and must not be used to accuse a writer. Authorship detectors
are unreliable and biased; slopscore deliberately reports patterns, not provenance.

## Intended use

Writers, editors, bloggers, maintainers, and content teams self-checking drafts. Not for
punitive or disciplinary decisions about people.

## How it scores

Rule-based features per dimension → each a [0,1] score → weighted sum → sigmoid → 0–100.
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

- Juzek & Ward, "Why Does ChatGPT 'Delve' So Much?" (arXiv:2412.11385) — overused vocabulary.
- Kobak et al., "Delving into LLM-assisted writing…" (Science Advances 2025) — excess vocabulary.
- Reinhart et al., "Do LLMs write like humans?" (PNAS 2025) — present-participle / rhetorical style.
- Geng & Trotta (arXiv:2404.08627) — decline of "is/are" copulas in post-2022 writing.
- Russell et al. (ACL 2025) — humans detect AI near chance; expert LLM-users rely on lexical cues.

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

## Changes from v0.1

Added significance inflation, superficial "-ing" analyses, vague/over-attribution, negative
parallelism / rule-of-three, copula avoidance, formatting tells, and a negative human-writing
signal; expanded the cited lexicon; added the corroboration gate, abstention, and personal-baseline
calibration. The default install stays lean (regex + scikit-learn); spaCy precision is behind `[nlp]`.
