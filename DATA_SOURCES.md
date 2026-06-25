# Evaluation data sources & licensing

slopscore separates **code** (MIT) from **evaluation data** (mixed upstream licenses) from the
**trained model** (weights licensed to match the most-restrictive *training* source). The shipped
model is trained only on permissive / CC-BY / CC-BY-SA data, so its weights stay redistributable.

## Committed seed set

`eval/datasets/seed.jsonl` (~54 rows) is a small, hand-authored, original corpus across the four
buckets the spec calls for, built by `scripts/eval/build_seed.py`. It is deliberately diverse to
limit leakage between the WP:AISIGNS-derived features and the labels. It is enough to exercise the
full eval + training pipeline and to back the CI fairness guardrails; it is **not** a substitute
for the large corpora below in a serious evaluation.

| bucket | label | what |
|---|---|---|
| human_good | 0 | specific, plain, factual prose (incl. a simple/plain-English fairness slice) |
| raw_llm | 1 | LLM-style slop: puffery, trailing "-ing" analyses, parallelism, AI vocab |
| edited_llm | 1 | slop with concrete details added (harder positives) |
| human_bad | 1 | vague human marketing/SEO copy (slop patterns, not AI-generated) |

## Large public corpora (fetched, not committed)

Pulled by `scripts/eval/fetch.py` into `~/.cache/slopscore/`; never redistributed.

| source | license | use |
|---|---|---|
| RAID (Dugan et al., ACL 2024) | permissive (verify upstream) | train + eval; paraphrase-robustness |
| MAGE (Li et al.) | CC-BY-4.0 | train + eval |
| Kobak et al. excess-vocabulary / Wikipedia | CC-BY-SA-3.0 | train + eval; real edited/humanized text |
| HC3 (Guo et al., 2023) | **CC-BY-NC-4.0** | **eval-only** — never used to train the shipped model |

## Rules we follow

- The shipped `data/model/slopscore-v0.3.json` is trained **only** on train-eligible (non-NC)
  sources. NC corpora are loaded for measurement only.
- Splits are domain/era-separated where possible to avoid leakage, since the features themselves
  derive from WP:AISIGNS (see the plan's leakage-guard notes).
- Fairness is measured per subgroup (plain/simple English, short text) and reported in
  `MODEL_CARD.md`; CI fails if subgroup false-positive rates regress.
