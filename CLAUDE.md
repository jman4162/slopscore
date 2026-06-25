# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

`uv`-managed, src-layout. Common workflows:

```bash
uv pip install -e . --no-deps    # editable install (see install-stability note below)
uv run --no-sync slopscore-lint scan FILE   # scan a file/URL/'-' (stdin); --format console|json|markdown
uv run --no-sync pytest          # tests + coverage (pytest imports from src via pythonpath)
uv run --no-sync pytest tests/test_scorer.py::test_report_shape   # a single test
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .   # lint + format
uv run --no-sync mypy src        # type check (strict)
```

**Install stability:** `uv sync` installs the project NON-editable and the rebuild can land in a
broken namespace state (`slopscore.__file__` becomes `None` → `ModuleNotFoundError`). Do an
editable install once (`uv pip install -e . --no-deps`) and use `uv run --no-sync` so uv does not
re-sync and clobber it. pytest is insulated regardless via `pythonpath = ["src"]` in pyproject.

Optional features live behind extras: `[web]` (trafilatura), `[nlp]` (spaCy + sentence-transformers),
`[lang]` (lingua). Default install is lean; `scan <url>` without `[web]` exits 3 with a hint. For
the spaCy path: `uv pip install spacy && uv run --no-sync python -m spacy download en_core_web_sm`
(`is_nlp_available()` gates it; syntactic features auto-upgrade when present).

## Architecture (v0.2)

Pipeline in `src/slopscore/`: `ingest/` (text, markdown via marko, json via jsonpath-ng, website)
→ `normalize/` (ftfy `clean` + offset-preserving `OffsetMapper`, pysbd `segment`, `language`) →
`features/` → `scoring/` → `report/`. Orchestrated by `core.py:build_document` then
`scoring/scorer.py:score_document`; public API (`SlopScorer`, `scan_text/_path/_url`) in `__init__.py`.

Reports (v0.2.1): `report/` has console, json, markdown, `sarif.py` (2.1.0, hand-built; severity→
level), `html.py` (Jinja2 behind the `[report]` extra, highlighted spans), `batch.py` (directory/
multi-file aggregation), and `locations.py` (char→line/col). `Report.original_text` holds the text
offsets index into. The `scan` CLI takes multiple targets / a directory, `--recursive`, `--diff
<ref>`, `--fail-on {none|low|medium|high}` (exit codes 0/1/2/3), and `--format sarif|html`. CI
distribution: `action.yml` (composite) and `.pre-commit-hooks.yaml`.

Key invariants when extending:
- **Every feature is a `Feature`** (`features/base.py`): `extract(doc, profile) -> FeatureResult`
  with a [0,1] score and `Evidence` spans. Importing `slopscore.features` registers them; add a
  dimension by writing a class + `register()` AND a field in `models.Dimension`/`Dimensions` AND a
  weight in `scoring/weights.py`. The scorer iterates the registry.
- **Evidence offsets index the original text, not the cleaned text.** Features run on
  `doc.cleaned_text` and MUST build spans via `doc.evidence(...)`, which maps offsets back through
  `OffsetMapper`. The round-trip is enforced across the feature tests — keep it green.
- **`TextSpan` lives in `spans.py`** (not `document.py`) to avoid a normalize↔document import cycle.
- **Conservatism is in the scorer, not the features.** `scoring/scorer.py` applies a corroboration
  gate (`WEAK_DIMENSIONS` damped when they fire alone), `human_writing_signals` enters with a
  NEGATIVE weight, and `scoring/confidence.py:abstain_reason` caps the label at "mild" on short/
  non-English input. Don't make individual features "conservative" — let the scorer do it.
- **Rule data is YAML** under `src/slopscore/data/` (force-included into the wheel). `patterns/` is
  organized into category subdirs loaded by `_ruleset.load_rules_from_directory`; `lexicons/markers.yaml`
  carries `era`/`source` tags. The spaCy path lives behind `features/_nlp.py`.
- Dimensions: lexical_markers, formulaic_structure, significance_inflation, superficial_analysis,
  weasel_attribution, parallelism, copula_avoidance, genericity, redundancy, cadence_sameness,
  formatting_tells (weak), prompt_residue, human_writing_signals (negative). unsupported_claims has
  no feature yet (contributes 0).
- **Personal baseline:** `scoring/calibrate.py` builds robust per-dimension stats from a corpus;
  `scan --baseline <name>` attaches z-score deviations. Profiles (`scoring/profiles.py`) are hand-set
  (see `PROFILE_NOTES.md`); citations + fairness caveats live in `MODEL_CARD.md`.

Scoring engines (v0.3): `scoring/scorer.py` dispatches on `Settings.scorer` (`Scorer.rules` default
vs `Scorer.ml`). The ML path (`scoring/model.py`) is a pure-numpy logistic model loaded from
`data/model/slopscore-v0.3.json` over `FEATURE_ORDER`; sign-constrained (slop dims ≥0, human signal
≤0), Platt-calibrated. The corroboration gate is rules-only; abstention applies to both. Train with
`scripts/eval/train.py` (sklearn+scipy, OOF metrics); evaluate with `slopscore-lint eval` / the
`slopscore.eval/` package (metrics, fairness, selective, span_metrics). Promotion is gated by
`eval/harness.py:should_promote` (TPR@1%FPR + no subgroup-FPR regression) — currently rules wins, so
ML stays opt-in. Eval data: `eval/datasets/seed.jsonl` (committed) + `scripts/eval/fetch.py` (large
corpora, not committed); licensing in `DATA_SOURCES.md`. **Never train the shipped model on NC data;
never import sklearn at scan time** (the ML path is numpy-only).

Linter maturity (v0.4): `config_file.py` loads `slopscore.toml`/`[tool.slopscore]` via `tomllib`
(precedence CLI > slopscore.toml > pyproject > defaults; `resolve_settings` merges, `Settings`
carries `disabled_dimensions/rules`, `rule_severity`, `suggest`). The scorer skips disabled
dimensions and post-filters evidence for disabled rules, severity overrides, and inline suppression
(`suppress.py`, HTML-comment grammar). `report/baseline.py` fingerprints findings for
`scan --baseline-file --fail-on-new`. `unsupported_claims` is now a real `_PhrasePack`
(`data/patterns/claims/`). Opt-in `--suggest` adds `Evidence.suggestion` + SARIF `fixes`
(`features/suggestions.py`, `data/patterns/suggestions/`) — advisory, excluded from score/`--fail-on`
(`SUGGEST_*` skipped in `max_severity`). `detectors/` is an interface-only authorship adapter
(`AuthorshipDetector` protocol + no-op `ReferenceDetector`); its `DetectorResult` populates a
SEPARATE `Report.authorship` field with a mandatory caveat, never the score. **Wheel packaging:**
data files ship via hatchling's default package inclusion — do NOT re-add a `force-include` for
`data/` (it duplicates paths and breaks `uv build`). PyPI publish is OIDC trusted-publishing on tag
(`.github/workflows/publish.yml`); docs are mkdocs-material (`.github/workflows/docs.yml`).

## Project state

v0.1–v0.4 are implemented and green (ruff/mypy/pytest). The repository also holds two reference
documents:

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
