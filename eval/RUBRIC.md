# Slop labeling rubric

The labels in `eval/datasets/benchmark.jsonl` follow the slop taxonomy from Shaib et al.,
"Measuring AI Slop" (arXiv:2509.19163), adapted to a binary label for slopscore. The paper defines
slop as low-quality text along several axes; we grade text on those axes and set `label = 1` (slop)
when enough of them fire, `label = 0` (clean) otherwise. This keeps the benchmark about **writing
quality**, not authorship: human marketing copy can be slop, and raw LLM output need not be.

## Axes (Shaib et al.) and the slopscore dimensions they map to

| Taxonomy axis | What it means | slopscore dimension(s) |
|---|---|---|
| Density | Low information per word; filler | genericity, redundancy |
| Relevance | Off-topic or padding sentences | superficial_analysis |
| Templatedness | Formulaic scaffolding, transitions | formulaic_structure, parallelism |
| Repetition | Restated points, echoed phrasing | redundancy, cadence_sameness |
| Verbosity | Wordy where plain would do | genericity, copula_avoidance |
| Tone | Promotional, inflated, "marketingese" | significance_inflation, lexical_markers |
| Coherence | Vague connective tissue, no throughline | superficial_analysis |
| Factuality | Sweeping claims without support | unsupported_claims, weasel_attribution |
| Fluency artifacts | Prompt residue, "as an AI", boilerplate | prompt_residue, formatting_tells |

A clean counter-signal (specific facts, dates, numbers, named entities, plain syntax) corresponds to
slopscore's negative `human_writing_signals` dimension.

## Binary decision

- `label = 1` (slop): the text is dominated by inflated tone, formulaic scaffolding, generic or
  redundant content, or unsupported sweeping claims, with little specific information. Applies
  regardless of author (LLM or human marketing/SEO).
- `label = 0` (clean): the text carries specific, checkable information (who/when/where/how much) in
  plain prose, even if simple or non-native. Simplicity is **not** slop.

## Buckets (provenance, not the label)

- `human_good`: specific, factual human prose. label 0.
- `raw_llm`: unedited LLM output dense with tells. label 1.
- `edited_llm`: LLM slop with real details grafted in (hard positives). label 1.
- `human_bad`: human marketing/SEO/puffery. label 1.
- `web_quality`: web text graded by quality (clean reference text → 0; boilerplate / promotional /
  navigation / spam → 1). From FinerWeb / FineWeb-Edu.
- `wild_slop`: real-world articles editors flagged as suspected AI-generated (Wikipedia AI Cleanup).
  label 1, **eval-only and subjective** (editor judgment, no rubric); reported as its own slice.

## Subgroups (fairness slices)

- `general`: standard English.
- `simple_english`: short, plain sentences.
- `non_native`: ESL-style English (clean content, non-idiomatic phrasing). Mostly label 0; the point
  is to measure the false-positive rate on competent non-native writing, which pattern detectors are
  known to over-flag. A high `non_native` FPR is a fairness failure, not a success.
