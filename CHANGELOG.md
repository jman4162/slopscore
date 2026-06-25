# Changelog

All notable changes to slopscore. The PyPI distribution is `slopscore-lint`; the import package
and the tool are named `slopscore`.

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
