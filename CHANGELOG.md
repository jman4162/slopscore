# Changelog

All notable changes to slopscore. The PyPI distribution is `slopscore-lint`; the import package
and the tool are named `slopscore`.

## 0.7.3

- Detect the elliptical antithesis slogan `PARALLEL_X_NOT_Y` ("A haircut, not a crash.",
  "Progress, not perfection.", bolded **Key Takeaways**). Scoped to standalone short clauses so it
  does not fire on ordinary mid-sentence "..., not ...". Lands in the weak, gated `parallelism`
  dimension; fairness gate stays 0% on the plain/non-native slices.
- `formatting_tells` now emits a visible `FORMATTING_EM_DASH` evidence item (with the em-dash count
  and the dash-to-comma ratio) when the dash-heavy signal fires, so the score is traceable. The
  density metric stays the dash-to-comma ratio (length- and structure-invariant); it is not
  per-paragraph. The numeric score is unchanged.

## 0.7.2

- GitHub Action is Marketplace-ready: renamed to `slopscore-lint` (unique listing name) and the
  SARIF upload step no longer hard-fails when the caller lacks `security-events: write`
  (`continue-on-error`; the scan still fails the job via `--fail-on`). README pins the example to
  `@v0`. No library behavior change.

## 0.7.1

- Fix: inline `<!-- slopscore-disable... -->` suppression now works in Markdown. The Markdown
  ingester dropped HTML comment blocks before the suppression parser saw them, so
  `disable-next-line`, `disable`/`enable`, and `disable-file` silently did nothing in `.md` files
  (the documented primary format). slopscore control comments are now preserved and kept adjacent to
  the line they guard; other HTML is still stripped. Inline end-of-line `disable-line` already worked.

## 0.7.0

- Fix (reported): Markdown posts with code blocks no longer score "severe". The ``` fences inflated
  `prompt_residue` when ingested as plain text (`.txt`, `.mdx`, stdin, or `scan_text` on a raw
  Markdown string); `ingest_text` now strips fenced code, and `.mdx` routes to the Markdown ingester.
- `[nlp]` genericity (W5): with spaCy + the English model, named-entity density replaces the
  proper-noun regex for the genericity dimension (regex stays the fallback). Validated: fairness gate
  holds at 0% FPR on the plain and non-native slices; benchmark AUROC 0.888 -> 0.902.
- `[nlp]` redundancy (W6): with sentence-transformers, dense MiniLM embedding similarity on adjacent
  sentences catches rephrased repetition TF-IDF misses (threshold 0.50, fairness-validated).
- Rhetorical question-and-answer scaffolds added to `formulaic_structure` ("But what does this
  mean?", "Sound familiar?", "Here's the thing:", "The answer is simple").
- `slopscore-lint explain`: lists the 14 dimensions and what each detects.
- Tried and reverted a sentence-length burstiness signal in `cadence_sameness` (regressed the
  non-native slice, FPR 0.00 -> 0.17). Recorded in `cadence.py`.

## 0.6.1

- Fix: `slopscore-lint fairness` (and `eval`) failed after `pip install` because the committed eval
  datasets were not shipped in the wheel. They are now force-included under `slopscore/data/eval/`
  and loaded via `eval.datasets.dataset_path` (packaged copy in installs, repo-root in a checkout).
  `fairness` degrades with a clear message and `--dataset` hint if no dataset is found.

## 0.6.0

- Prose-in-code linting: `scan` extracts and scores the natural-language prose in source files
  (Python docstrings/comments via `ast`/`tokenize`, JS/TS JSDoc and comments) and ignores the code.
  Directory and recursive scans pick up code files; offsets round-trip to the extracted prose.
- `slopscore-lint fairness`: reports per-rule false-positive rates on the plain (`simple_english`)
  and non-native (`non_native`) benchmark slices, and flags rules over a threshold.
- `scan --by-paragraph`: scores each paragraph worst-first, surfacing a sloppy section in an
  otherwise-clean document.
- Decided non-goals (recorded in `MODEL_CARD.md`): no model retrain and no XGBoost/gradient boosting.
  The held-out ceiling is set by features, not the model class; trees break the numpy-only scan path,
  per-span traceability, and the fairness gate.
- Interpretable feature work (spaCy NER genericity, semantic redundancy, burstiness) deferred to v0.7.

## 0.5.0

- Real slop-labeled benchmark: `eval/datasets/benchmark.jsonl` (128 rows, hand-authored and
  taxonomy-graded per `eval/RUBRIC.md`), with `simple_english` and `non_native` fairness slices.
- Held-out, eval-only real-world slice via `scripts/eval/fetch.py wiki_aicleanup` (Wikipedia
  WikiProject AI Cleanup); lightweight HTTP fetchers for FineWeb-Edu and FinerWeb too.
- Committed evaluation report (`eval/RESULTS.md`, `eval/results.json`, `scripts/eval/report.py`)
  with measured numbers: benchmark PR-AUC 0.91, and a held-out Wikipedia AUROC of 0.69 that keeps
  the accuracy framing modest.
- Retrained the opt-in learned scorer on the benchmark (`slopscore-v0.5.json`). It improves
  calibration but over-flags simple and non-native English (FPR 0.71 / 0.33 vs 0.00 for rules), so
  the replace-if-wins gate keeps the transparent rule scorer as the default.
- README badges; docs site `site_url`, a Benchmark page, and a Model Card nav link.

## 0.4.2

- Scrubbed the README, docs, and model card of the writing patterns the tool flags (em dashes and
  over-polished verbs), so the published prose passes slopscore itself.
- Config: reject a bare string for `disabled_rules` / `disabled_dimensions` (previously it iterated
  into per-character entries) with a clear error.
- CLI: create missing parent directories for `--output` and `baseline -o`; report a friendly error
  on a malformed `--baseline-file` instead of a traceback; skip non-UTF-8 files in a batch with a
  warning rather than aborting the run.
- Added `CHANGELOG.md` and `SECURITY.md`.

## 0.4.1

- Renamed the PyPI distribution and the CLI command to `slopscore-lint` (the name `slopscore` was
  already taken on PyPI). The import package stays `slopscore`.

## 0.4.0

- Project config via `slopscore.toml` and `[tool.slopscore]` in `pyproject.toml`, with per-rule and
  per-dimension toggles and severity overrides (`slopscore-lint config`).
- Inline suppression through `<!-- slopscore-disable ... -->` comments.
- Findings baseline: `slopscore-lint baseline` plus `scan --baseline-file --fail-on-new` to adopt
  the linter on an existing repo and gate CI on new findings only.
- Implemented the `unsupported_claims` dimension (universal and inflated claims).
- Opt-in rewrite suggestions (`--suggest`) with SARIF `fixes`, advisory and never auto-applied.
- Authorship-adapter interface (`AuthorshipDetector` protocol) behind the `[detectors]` extra. No
  detector is bundled; any result is reported separately and never folded into the score.
- PyPI trusted-publishing workflow and an mkdocs-material docs site.

## 0.3.0

- Transparent learned scorer (`--scorer ml`): a sign-constrained, calibrated logistic regression
  over the 13 dimensions, serialized as auditable JSON and run with pure numpy. The rule scorer
  stays the default under a replace-if-wins gate.
- Evaluation harness/framework (`slopscore-lint eval`): TPR@FPR, PR-AUC, calibration, and
  per-subgroup false-positive rates. See `MODEL_CARD.md` and `DATA_SOURCES.md`.

## 0.2.1

- console/JSON/Markdown/SARIF/HTML reports, recursive and changed-files (`--diff`) batch scanning
  with CI exit codes, a GitHub Action, and a pre-commit hook.

## 0.2.0

- Detection expansion grounded in Wikipedia's "Signs of AI writing" guide: significance inflation,
  superficial analysis, weasel attribution, negative parallelism, copula avoidance, formatting
  tells, and a negative human-writing signal. Conservative scoring with a corroboration gate and
  abstention on short or non-English input.

## 0.1.0

- Initial release: ingestion (text, Markdown, JSON, websites), offset-preserving normalization, a
  feature registry, and the first dimensions with evidence spans.
