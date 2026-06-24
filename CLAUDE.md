# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

`uv`-managed, src-layout. Common workflows:

```bash
uv sync                          # create .venv and install deps + dev group
uv run slopscore scan FILE       # scan a file/URL/'-' (stdin); --format console|json|markdown
uv run pytest                    # tests + coverage (configured in pyproject)
uv run pytest tests/test_scorer.py::test_report_shape   # a single test
uv run ruff check . && uv run ruff format --check .      # lint + format
uv run mypy src                  # type check (strict)
```

Optional features live behind extras: `uv sync --extra web` (trafilatura website extraction),
`--extra nlp` (spaCy/sentence-transformers), `--extra lang` (lingua language detection). The
default install is intentionally lean; `scan <url>` without `[web]` exits 3 with an install hint.

## Architecture (v0.1 implemented)

Pipeline in `src/slopscore/`: `ingest/` (text, markdown via marko, json via jsonpath-ng,
website) → `normalize/` (ftfy `clean` + offset-preserving `OffsetMapper`, pysbd `segment`,
`language`) → `features/` → `scoring/` → `report/`. Orchestrated by `core.py:build_document`
then `scoring/scorer.py:score_document`; public API (`SlopScorer`, `scan_text/_path/_url`) in
`__init__.py`.

Key invariants when extending:
- **Every feature is a `Feature`** (`features/base.py`): `extract(doc, profile) -> FeatureResult`
  with a [0,1] score and `Evidence` spans. Importing `slopscore.features` registers them; add a
  dimension by writing a class and calling `register()`. The scorer iterates the registry.
- **Evidence offsets index the original text, not the cleaned text.** Features run on
  `doc.cleaned_text` and MUST build spans via `doc.evidence(...)`, which maps offsets back
  through `OffsetMapper`. The round-trip is enforced by `tests/test_normalize_offsets.py` and
  `test_features.py` — keep it green.
- **`TextSpan` lives in `spans.py`** (not `document.py`) to avoid a normalize↔document import
  cycle. Don't move it back.
- Live dimensions: lexical_markers, formulaic_structure, prompt_residue (rule data in
  `data/*.yaml`). genericity/redundancy/cadence are thin real implementations; unsupported_claims
  has no feature yet (contributes 0). Weights/bias in `scoring/weights.py`, genre reweighting in
  `scoring/profiles.py`, sigmoid + label in `scorer.py`.
- Rule data is YAML under `src/slopscore/data/` (force-included into the wheel via pyproject).
  Add markers/patterns there, not in code.

## Project state

v0.1 scaffold is implemented and green (ruff/mypy/pytest). The spec and roadmap below still
govern v0.2+. The repository also holds two reference documents:

- `BACKGROUND_INFORMATION.local.md` — the authoritative spec. Defines the product concept,
  what to detect, the scoring model, the planned package layout, dependencies, evaluation
  plan, and a versioned MVP build plan (v0.1 → v1.0). **Read this before writing code or
  proposing structure** — it is the source of truth for design decisions.
- `AI_WRITING_SLOP_Guide.local.md` — a ~1,650-line catalog of real AI-slop writing examples
  and patterns. Use it as a corpus of concrete patterns/phrases to detect and as raw material
  for test fixtures and the evaluation benchmark.

The `.local.md` suffix marks these as local-only working files. Do not assume they ship with
the package or are public.

## What this project is (and is not)

`slopscore` is a transparent **AI-slop pattern detector** — not an AI-authorship detector.
This distinction is load-bearing and shapes every API/report decision:

- It outputs a 0–100 **SlopScore** measuring density of formulaic, generic, low-specificity,
  over-polished, LLM-associated writing patterns — plus per-dimension scores, a separate
  confidence score, and **evidence spans** (exact char offsets that triggered each finding).
- It must **never** claim "this was written by AI." Any authorship signal (v0.4+ detector
  adapters) is kept in a separate field (`ai_authorship_signal`), never folded into the
  `slop_score`. The rationale (detector brittleness, false positives on non-native English,
  paraphrase evasion) is documented in the spec — preserve that separation.
- Positioning is "Vale/ruff for AI-slop writing patterns," not "another GPTZero clone."
  Conservative by default: prefer false negatives over false accusations.

## Key design decisions (from the spec)

- **Python first**, not Rust. The hard part is NLP feature extraction, calibration, and
  evaluation iteration — not raw speed. Rust only later for speed-critical parsing if needed.
- **Three separate questions, kept distinct:** authorship likelihood (optional, fragile),
  slop-pattern density (the core score), editorial-quality risk (most useful to writers).
- **Heavyweight model deps live behind extras** (`[web]`, `[nlp]`, `[detectors]`, `[all]`).
  The default install and the default score must be **rule-based and transparent** — no
  black-box detector in the default path.
- **Genre profiles** (`blog`, `essay`, `academic`, `marketing`, `technical`, `social`)
  reweight dimensions; default `profile=blog`, `strictness=conservative`. The same feature
  can be legitimate in one genre and slop in another (e.g. "robust" in a technical paper).
- **Suppress/heavily qualify scores on short text** (<300 words) and low-confidence inputs
  (non-English, heavy quotes/code/tables, uncertain web extraction).
- **Evaluation from day one.** Credibility depends on shipping a benchmark (human-good,
  raw-LLM, edited-LLM, human-bad) and reporting TPR at fixed low FPR, span-level
  precision/recall, and per-domain false-positive rates — not just AUROC.

## Roadmap (per spec)

v0.2: genre profile tuning + `calibrate` (personal baseline from your own corpus), HTML report
with highlighted spans, batch/recursive scanning. v0.3: trained interpretable model (logistic
regression / LightGBM over the same features). v0.4: optional authorship-signal detector adapters
(Binoculars, Fast-DetectGPT) in a separate `ai_authorship_signal` field — never folded into
`slop_score`. v1.0: GitHub Action, SARIF output, evaluation benchmark, model card, docs site.
See `BACKGROUND_INFORMATION.local.md` for the full plan and the target JSON schema.

## Writing discipline (applies to this repo specifically)

This is a tool that detects AI-slop writing, so its own prose must be exemplary. Scrub all
READMEs, docs, docstrings, reports, and commit/PR text for the patterns the tool itself flags:
puffery, AI-vocabulary (delve, crucial, pivotal, robust, seamless, leverage, showcase,
underscore, tapestry), rule-of-three padding, gratuitous em-dashes, and formulaic scaffolding.
Prefer specific, concrete, falsifiable wording. Dogfooding: prose here should pass `slopscore`.
