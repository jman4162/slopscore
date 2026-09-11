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

**Install stability:** if `import slopscore` yields an empty namespace package
(`slopscore.__file__` is `None`, `ModuleNotFoundError: slopscore.cli`), the cause is almost always
the macOS hidden flag on the venv's `.pth` files: CPython 3.12.13+ and 3.13 skip hidden `.pth`
files (`uv run python -v -c pass 2>&1 | grep pth` shows "Skipping hidden .pth file"), files under a
synced `Documents` folder acquire the flag, and the force-included eval datasets under
`site-packages/slopscore/data/eval/` then resolve as a namespace package. `chflags nohidden
.venv/lib/python3.12/site-packages/*.pth` fixes it, but the flag has been observed to return within
minutes on this machine, so the dependable form is `PYTHONPATH=src uv run --no-sync python -m
slopscore.cli ...` (no `.pth` involved). Reinstall with `uv pip install -e . --no-deps` if the
`.pth` is gone; use `uv run --no-sync` so uv does not re-sync a non-editable copy. pytest is
insulated regardless via `pythonpath = ["src"]` in pyproject.

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
  gate: every `WEAK_DIMENSION` is damped (x0.3) unless the strongest `CORROBORATING_DIMENSION`
  (strong AND span-backed; never genericity/cadence/redundancy/human) is elevated, ramping to full
  weight between 0.25 and 0.5 (`weights.py:weak_gate`). The score is continuous and non-decreasing
  in every dimension; keep it that way. `human_writing_signals` enters with a NEGATIVE weight
  (unscaled by strictness); `STRICTNESS_GAIN` scales only the positive evidence sum, never the
  bias; `scoring/confidence.py:abstain_reason` caps the label at "mild" on short/non-English
  input. Don't make individual features "conservative" — let the scorer do it.
- **Filter, then score.** Span-backed features implement `SpanScored.score_spans` (`features/
  base.py`) and route `extract` through it, so `score_spans(all_spans) == extract().score`. The
  scorer drops disabled/suppressed spans and applies severity overrides BEFORE computing `by_dim`
  (`scorer.py:_extract_filtered`). A new rule-driven feature must implement `score_spans` and
  `rule_ids` (the latter feeds `features/catalog.py`, which validates suppression names).
- **Rule data is YAML** under `src/slopscore/data/` (force-included into the wheel). `patterns/` is
  organized into category subdirs loaded by `_ruleset.load_rules_from_directory`; `lexicons/markers.yaml`
  carries `era`/`source` tags. The spaCy path lives behind `features/_nlp.py`.
- Dimensions: lexical_markers, formulaic_structure, significance_inflation, insight_signaling,
  performative_candor (weak), superficial_analysis, weasel_attribution, parallelism,
  copula_avoidance, genericity, redundancy, cadence_sameness, formatting_tells (weak),
  structure_tells (weak, v0.13: Markdown block shape from `Document.blocks`),
  prompt_residue, metadiscourse, human_writing_signals (negative). `genericity`, `cadence_sameness`, `redundancy`,
  and `human_writing_signals` are STATISTICAL (no spans, low weight, never corroborate).
  `insight_signaling` (v0.7) and `performative_candor` (v0.9) are rules-only — deliberately
  excluded from the ML `FEATURE_ORDER`, so they need no model retrain.
- **Personal baseline:** `scoring/calibrate.py` builds robust per-dimension stats from a corpus;
  `scan --baseline <name>` attaches z-score deviations. Profiles (`scoring/profiles.py`) are hand-set
  (see `PROFILE_NOTES.md`); citations + fairness caveats live in `MODEL_CARD.md`.

Scoring engines (v0.3): `scoring/scorer.py` dispatches on `Settings.scorer` (`Scorer.rules` default
vs `Scorer.ml`). The ML path (`scoring/model.py`) is a pure-numpy logistic model loaded from
`data/model/slopscore-v0.5.json` over `FEATURE_ORDER`; sign-constrained (slop dims ≥0, human signal
≤0), Platt-calibrated. The corroboration gate is rules-only; abstention applies to both. Train with
`scripts/eval/train.py` (sklearn+scipy, OOF metrics); evaluate with `slopscore-lint eval` / the
`slopscore.eval/` package (metrics, fairness, selective, span_metrics). Promotion is gated by
`eval/harness.py:should_promote` (TPR@1%FPR + no subgroup-FPR regression) — currently rules wins, so
ML stays opt-in. Eval data: `eval/datasets/seed.jsonl` (committed) + `scripts/eval/fetch.py` (large
corpora, not committed); licensing in `DATA_SOURCES.md`. **Never train the shipped model on NC data;
never import sklearn at scan time** (the ML path and `features/redundancy.py` are numpy-only;
scikit-learn is the `[eval]` extra and `tests/test_redundancy_numpy.py` asserts it stays out of the
scan path).

Linter maturity (v0.4): `config_file.py` loads `slopscore.toml`/`[tool.slopscore]` via `tomllib`
(precedence CLI > slopscore.toml > pyproject > defaults; `resolve_settings` merges, `Settings`
carries `disabled_dimensions/rules`, `rule_severity`, `suggest`). The scorer skips disabled
dimensions and post-filters evidence for disabled rules, severity overrides, and inline suppression
(`suppress.py`, HTML-comment grammar). `report/baseline.py` fingerprints findings for
`scan --baseline-file --fail-on-new`. `unsupported_claims` is now a real `PhrasePack`
(`data/patterns/claims/`). Opt-in `--suggest` adds `Evidence.suggestion` + SARIF `fixes`
(`features/suggestions.py`, `data/patterns/suggestions/`) — advisory, excluded from score/`--fail-on`
(`SUGGEST_*` skipped in `max_severity`). `detectors/` is an interface-only authorship adapter
(`AuthorshipDetector` protocol + no-op `ReferenceDetector`); its `DetectorResult` populates a
SEPARATE `Report.authorship` field with a mandatory caveat, never the score. **Wheel packaging:**
data files ship via hatchling's default package inclusion — do NOT re-add a `force-include` for
`data/` (it duplicates paths and breaks `uv build`). PyPI publish is OIDC trusted-publishing on tag
(`.github/workflows/publish.yml`); docs are mkdocs-material (`.github/workflows/docs.yml`).

Differentiation (v0.6): `ingest/code.py` extracts prose from source files (Python docstrings/comments
via `ast`/`tokenize`; JS/TS JSDoc/comments via regex) and routes by suffix in `ingest/__init__.py`
(`CODE_SUFFIXES`, also added to the batch/diff walkers); `SourceType.code`. Offsets index the
extracted prose (same contract as markdown). `cli.py:fairness_cmd` (`slopscore-lint fairness`)
reports per-rule false-positive rate on the `simple_english`/`non_native` benchmark slices; `scan
--by-paragraph` scores each paragraph worst-first. **Decided non-goals** (in `MODEL_CARD.md`): no
model retrain, no XGBoost/GBDT (features are the ceiling, not the model class; trees break the
numpy-only path + transparency + fairness). The `[nlp]` feature work (NER genericity, semantic
redundancy, burstiness) is the v0.7 roadmap.

Insight-signaling (v0.7): a new `insight_signaling` dimension flags pseudo-profundity tells that
announce insight rather than contain it ("load-bearing", "doing the real work", "the crux of the
issue", "pressure-test the claim") — a distinct phenomenon from the WP:AILEGACY puffery in
`significance_inflation`. Core rules (`data/patterns/insight_signaling/`, context-gated so literal
uses like "load-bearing wall" are safe) score by default; an opt-in broad tier
(`data/patterns/insight_signaling_broad/`, enabled by `--broad` / `[tool.slopscore] broad`) adds
rationalist/essayist jargon (steelman, epistemic humility, first principles) that is legitimate in
philosophy/tech writing and so carries higher FPR. `--broad` re-scores the dimension over core+broad
in `scorer.py` (mirrors the `settings.suggest` special-case), so it affects the score, evidence, and
`--fail-on`. The dimension is **rules-only**: it is excluded from the ML `FEATURE_ORDER`, so the
committed model needs no retrain (`--scorer ml` computes but ignores it). Antithesis coverage in
`parallelism` gained "not merely X but Y", "less about X, more about Y", the non-'it' em-dash
variant, and the "both/and" reframe. Genre profiles boost insight_signaling in essay/blog/social and
soften it in academic/technical.

Weasel words (v0.7): the complementary axis — slop phrases signal fake *insight*,
`weasel_attribution` signals fake *evidence*. The existing dimension was expanded (data-only) with
impersonal-passive attribution (`attribution/impersonal.yaml`: "it is widely believed", "sources
say", passive dodges), unearned-certainty "reasoning smells" (`attribution/certainty.yaml`:
clause-initial "Clearly,"/"Obviously,", "needless to say", "it goes without saying" — classic
WP:AIWEASEL weasels), and hedge+vague-adjective (`attribution/hedging.yaml`: "somewhat successful").
Bare quantifiers/hedges/intensifiers (many/very/may) are **`--broad`-only**
(`data/patterns/attribution_broad/`): they have no discriminative power on the ESL/simple-English
fairness slices (they appear in both clean and slop rows), so flagging them by default would
over-flag exactly the protected population. The broad tier deliberately EXCLUDES the hedges
`human_signals.py` rewards as a positive human signal (perhaps/maybe/arguably/likely) so the two
dimensions never contradict. The `--broad` mechanism was generalized: `features/phrase_packs.py`
exposes `broad_packs()` and `scorer.py` re-scores every broad-capable pack (insight_signaling and
weasel_attribution today). Bureaucratese (utilize/facilitate/"due to the fact that") stays advisory
in `--suggest`; `ascertain` was added there. Prose-fiction frequency tics (just/that/really) are a
deliberate non-goal — per-author frequency, not a static list (a future `calibrate.py` baseline
feature).

Performative candor (v0.9): the third axis after fake insight (`insight_signaling`) and fake
evidence (`weasel_attribution`) — fake *vulnerability*. `performative_candor` flags a point framed
as a difficult confession ("I have to be honest", "truth be told", "let me be candid"), a sincerity
adjective on an abstract noun ("honest framing", "honest limits" for "limitations"), clause-initial
"Honestly,"/"Frankly," (comma required), the `genuinely interesting` collocation, and manufactured
reluctance ("I don't say this lightly"). Rules in `data/patterns/performative_candor/`; bare
sincerity adverbs are `--broad`-only in `performative_candor_broad/`. **It is a separate dimension
specifically because the genre multipliers invert** — `social` is 0.6 here vs 1.15 for
insight_signaling, `marketing` 1.2 vs 0.9 — so folding these rules into insight_signaling would
boost the genre where "honestly" is legitimate human speech. `full_scale` is 4.0 (not the usual
3.0) because at 3.0 a single low-severity hit in a 60-word doc crosses the corroboration gate.
Weak-alone, which means concrete first-person prose with heavy candor filler deliberately scores
low (see the MODEL_CARD limitation). The comma requirement in `CANDOR_ADVERB_PARENTHETICAL` is what
keeps the ESL calques "Honestly speaking"/"Frankly speaking" quiet — do not relax it. Do not add
"Sincerely,"/"Truly," to that rule: patterns compile under MULTILINE, so `^` matches every line
start and they would fire on email sign-offs.

Metadiscourse (v0.14): writing that refers to the text rather than to its subject. This is
Hyland's
(2005) *interactive* metadiscourse (frame markers, endophoric markers, code glosses), where the
interactional half was already covered by `weasel_attribution`, `significance_inflation`, and
`performative_candor`. Rules in `data/patterns/metadiscourse/` plus a `--broad` tier. Three things
make it unlike the other packs.

- **It subclasses `PhrasePack` rather than instantiating one** (`features/metadiscourse.py`),
  because hits-per-100-words cannot see this defect in long-form prose: the originating passage
  reads 1.0 at 123 words and 0.064 at 3,373. It scores `max(rate, concentration)`. The
  concentration term is the longest run of consecutive sentences that carry a marker and **no**
  concrete evidence, mapped `{2: 0.35, 3: 0.55, 4: 0.75, 5+: 0.90}` and length-invariant. Its
  `Evidence` must be excluded from the rate term (no double-charging), must honor `rule_severity`
  overrides (`_severity_factor`), and **anchors on the run's first sentence only** — a
  multi-sentence finding span makes `report/html.py` swallow every phrase highlight inside it and
  makes `report/baseline.py` fingerprints change on unrelated edits. Run length is therefore
  recovered by re-deriving runs from the document, never from the span text. Non-prose blocks
  (`heading`, `list_item`) **break** a run; only a too-short factless sentence is neutral.
  A terminal-recap term was built and dropped: see CHANGELOG 0.14.0.
- **It is in neither `WEAK_DIMENSIONS` nor `CORROBORATING_DIMENSIONS`.** Weak means damped x0.3
  alone, which is the failure it exists to fix. But left in the derived corroborating set, a
  length-invariant 0.55 clears the gate on its own: three meta sentences took an otherwise
  identical 600-word document from 46.4 "mild" to 97.6 "severe" by counting every weak dimension
  at full weight. `weights.py:NON_CORROBORATING_DIMENSIONS` subtracts it: full weight for
  itself, no vote on anyone else.
- **The evidence gate is the fairness gate.** A marker over a concrete fact is exempt, because
  restatement scaffolding over facts is an ESL clarity strategy. `concrete_evidence_count()` in
  `specificity.py` is the shared predicate, with an opt-in `spelled_numbers` flag used only here
  (genericity is calibrated on digits only). Cut the marker's own characters out before counting
  or a marker exempts itself ("In plain English" contains "English"). The density denominator is
  floored at 100 words; that is a local fix for a defect every `severity_rate_score` pack shares.

No rules were migrated out of `formulaic.yaml`, which would break rule-id suppressions and
baseline fingerprints; the run detector reads `data/lexicons/metadiscourse_markers.yaml`, a
non-scoring superset compiled with the same `regex` flags as the YAML rule files, so it sees the
whole surface without them moving.

## Project state

v0.1–v0.6 are implemented and green (ruff/mypy/pytest). The repository also holds two reference
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
This distinction shapes every API and report decision:

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
