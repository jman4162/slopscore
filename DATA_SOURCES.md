# Evaluation data sources & licensing

slopscore separates **code** (MIT) from **evaluation data** (mixed upstream licenses) from the
**trained model** (weights licensed to match the most-restrictive *training* source). The shipped
model is trained only on permissive / CC-BY / CC-BY-SA data, so its weights stay redistributable.

## Committed corpora

- `eval/datasets/seed.jsonl` (54 rows): the original hand-authored seed (`scripts/eval/build_seed.py`).
- `eval/datasets/benchmark.jsonl` (128 rows): the v0.5 benchmark (`scripts/eval/build_benchmark.py`),
  the seed plus a taxonomy-graded expansion. Labels follow `eval/RUBRIC.md` (Shaib et al.,
  "Measuring AI Slop", arXiv:2509.19163). All rows are original and hand-authored, so this set is
  committed and train-eligible. The shipped learned model is trained on it.

| bucket | label | what |
|---|---|---|
| human_good | 0 | specific, plain, factual prose (incl. simple-English and non-native slices) |
| raw_llm | 1 | LLM-style slop: puffery, trailing "-ing" analyses, parallelism, AI vocab |
| edited_llm | 1 | slop with concrete details added (harder positives) |
| human_bad | 1 | vague human marketing/SEO copy (slop patterns, not AI-generated) |
| web_quality | 0/1 | reference-style web text (0) vs boilerplate/spam (1) |

Fairness subgroups: `general`, `simple_english`, `non_native` (clean ESL-style writing, mostly
label 0, to measure the false-positive rate on competent non-native English).

## Large public corpora (fetched, not committed)

Pulled by `scripts/eval/fetch.py` into `~/.cache/slopscore/`; never redistributed. Verified mid-2026.

| source | id / access | license | label | use |
|---|---|---|---|---|
| Wikipedia AI Cleanup | category API (`wiki_aicleanup`) | CC-BY-SA-4.0 | suspected-AI (subjective) | **eval-only** real-world slop slice |
| FineWeb-Edu | `HuggingFaceFW/fineweb-edu` | ODC-BY | educational quality 0-5 | train + eval (web-quality proxy) |
| FinerWeb-10BT | `TurkuNLP/finerweb-10bt` | Apache-2.0 | line quality | train + eval (web-quality proxy) |
| MAGE (Li et al.) | `yaful/MAGE` | CC-BY-4.0 | authorship (not slop) | authorship-null panel only |
| HC3 (Guo et al., 2023) | `Hello-SimpleAI/HC3` | **CC-BY-NC-4.0** | authorship | **eval-only**, never trains |
| "Measuring AI Slop" | `cshaib/slop` (arXiv:2509.19163) | MIT | span-level slop | dataset not yet released (taxonomy used as the rubric) |

Notes on accuracy of the above: Wikipedia AI-Cleanup labels are subjective editor judgments (a
real-world signal, but noisy), so they are eval-only. MAGE/RAID label authorship, not slop, so they
serve only as the authorship-null check, not as slop training data. Grokipedia is excluded (a
non-commercial clause covers part of its corpus). The web-quality sources are a proxy for slop, not
the same construct, and are not in the headline numbers.

## Rules we follow

- The shipped `data/model/slopscore-v0.5.json` is trained **only** on train-eligible (non-NC,
  non-subjective) sources, currently the committed benchmark. NC and eval-only corpora are loaded
  for measurement only.
- Splits are domain/era-separated where possible to avoid leakage, since the features themselves
  derive from WP:AISIGNS (see the plan's leakage-guard notes).
- Fairness is measured per subgroup (plain/simple English, short text) and reported in
  `MODEL_CARD.md`; CI fails if subgroup false-positive rates regress.
