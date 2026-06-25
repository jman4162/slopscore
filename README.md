# slopscore

[![PyPI](https://img.shields.io/pypi/v/slopscore-lint.svg)](https://pypi.org/project/slopscore-lint/)
[![Python](https://img.shields.io/pypi/pyversions/slopscore-lint.svg)](https://pypi.org/project/slopscore-lint/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/jman4162/slopscore/actions/workflows/ci.yml/badge.svg)](https://github.com/jman4162/slopscore/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://jman4162.github.io/slopscore/)

A transparent **linter for AI-slop writing patterns** in essays, blog posts, Markdown, JSON, and
websites.

`slopscore` reads text and returns a 0 to 100 **SlopScore** measuring the density of formulaic,
generic, low-specificity, over-polished writing patterns associated with low-effort LLM output.
It reports per-dimension scores and **evidence spans** (the exact phrases that triggered each
finding), so you can see and fix what it flags.

> ### ⚠️ What slopscore is NOT
> It does **not** detect whether text was written by AI, and must never be used to accuse a writer.
> It flags writing *patterns* in *text* (not authorship, not authors): patterns common in
> low-effort or AI-like prose **and** in plenty of human writing. Use it as a prose linter to nudge
> toward clearer, more specific writing, not as an AI detector. Authorship detectors are unreliable
> and biased; slopscore deliberately is not one.

## What it is, and what it is not

slopscore detects **writing patterns**, not authorship. It does not claim a text was written by
AI, and it should never be used to accuse a writer. AI-authorship detectors are unreliable on
short, edited, translated, and non-native-English text, so slopscore takes a more honest and more
useful position:

> "This text has a high concentration of generic, formulaic, low-evidence writing patterns."

not

> "This was written by AI."

Think of it as a linter for slop, closer to Vale or ruff than to a black-box AI detector.
Every point in the score comes from a visible rule with an evidence span.

## Install

```bash
pip install slopscore-lint            # lean, rule-based core
pip install "slopscore-lint[web]"     # + website extraction (trafilatura)
pip install "slopscore-lint[nlp]"     # + spaCy NER and sentence-transformer embeddings
pip install "slopscore-lint[lang]"    # + non-English language detection
pip install "slopscore-lint[report]"  # + HTML report rendering (Jinja2)
pip install "slopscore-lint[all]"     # everything
```

> **Name note:** the PyPI package is `slopscore-lint` (plain `slopscore` belongs to a different
> tool). The import stays `import slopscore`, and the command is `slopscore-lint`.

## Usage

```bash
slopscore-lint scan post.md
slopscore-lint scan essay.txt --format json
slopscore-lint scan content.json --json-path "$.article.body"
slopscore-lint scan https://example.com/post        # requires slopscore-lint[web]
slopscore-lint scan src/app.py                       # lints docstring/comment prose, ignores code
slopscore-lint scan post.md --by-paragraph           # surfaces a sloppy section in a clean doc
```

### Lint the prose inside code

`scan` reads the natural-language prose out of source files (Python docstrings and comments, JS/TS
JSDoc) and ignores the code itself, so it catches slop in documentation that code linters skip:

```bash
slopscore-lint scan src/                  --recursive   # docstrings + comments across a package
slopscore-lint scan README.md CHANGELOG.md --fail-on high
```

### Audit fairness

slopscore reports how often each rule fires on competent plain and non-native English, the writing
that pattern detectors are known to over-flag. No other slop linter publishes this:

```bash
slopscore-lint fairness        # per-rule false-positive rate on the plain/ESL benchmark slices
```

### Calibrate against your own writing

Instead of asking "does this look like AI?", ask "does this deviate from *my* usual style in
sloppy ways?". Build a baseline from a folder of your past writing, then compare new drafts to it:

```bash
slopscore-lint calibrate ./my-old-posts --name me
slopscore-lint scan new-post.md --baseline me     # reports per-dimension z-score deviations
```

### Higher-precision syntactic detection (optional)

The default install detects syntactic tells (trailing "-ing" analyses, and so on) with regex.
Install the `[nlp]` extra and the spaCy English model for a higher-precision, lower-false-positive
path:

```bash
pip install "slopscore-lint[nlp]"
python -m spacy download en_core_web_sm
```

slopscore auto-upgrades to the spaCy path when the model is present; nothing else changes.

### Use it as a linter in CI

```bash
slopscore-lint scan ./content --recursive --fail-on high          # exit 1 if any high finding
slopscore-lint scan ./content --recursive --format sarif -o out.sarif   # for GitHub code scanning
slopscore-lint scan post.md --format html -o report.html          # highlighted-span HTML (needs [report])
slopscore-lint scan . --diff origin/main --fail-on medium         # only files changed vs a ref
```

Exit codes: `0` clean (or below `--fail-on`), `1` findings at or above the threshold, `2` usage
error, `3` a needed extra is missing. A composite **GitHub Action** (`action.yml`) scans, uploads
SARIF to code scanning, and fails by threshold; a **pre-commit hook** (`.pre-commit-hooks.yaml`)
is published for `pre-commit`. SARIF and HTML line numbers for Markdown and code are relative to the
extracted prose (raw-source mapping is a later enhancement).

```python
from slopscore import SlopScorer

scorer = SlopScorer(profile="blog", strictness="conservative")
# the argument below is an example of the slop the tool flags:
report = scorer.scan_text("In today's fast-paced digital landscape, it is crucial to leverage synergy.")
print(report.score.slop_score, report.score.label)
print(report.evidence[:3])
```

## Status

v0.7: accuracy and robustness. Fixed a false "severe" on Markdown posts with code blocks (the code
fences inflated `prompt_residue` when ingested as text). The `[nlp]` extra now genuinely upgrades two
dimensions: spaCy named-entity density for genericity (benchmark AUROC 0.888 to 0.902) and
sentence-transformer embeddings for rephrased redundancy, both validated to keep the fairness gate at
0% false positives on plain and non-native English. Added rhetorical question-and-answer scaffold
detection and a `slopscore-lint explain` command. A sentence-length burstiness signal was tried and
reverted for regressing the non-native slice.

v0.6: differentiation and reach. Lints the **prose inside code** (Python docstrings/comments, JS/TS
JSDoc) so it catches slop that code linters skip; a `fairness` command that reports per-rule
false-positive rates on plain and non-native English (no other slop linter publishes this); and
`--by-paragraph` to surface a sloppy section inside an otherwise-clean document. Interpretable
feature work (spaCy NER, semantic redundancy, burstiness) is on the v0.7 roadmap. Settled by
evaluation: no model retrain and no gradient-boosting (XGBoost/LightGBM), since the held-out ceiling
is set by features, not the model class, and trees break the numpy-only path and the fairness gate.

v0.5: a real slop-labeled benchmark (`eval/datasets/benchmark.jsonl`) with `simple_english` and
`non_native` fairness slices, plus a held-out Wikipedia AI-Cleanup slice. Measured numbers in
`eval/RESULTS.md`: strong on overt slop (PR-AUC 0.91), honestly weak on subtle real-world slop
(held-out AUROC 0.69), which is why the accuracy claims stay modest.

v0.4: linter maturity. `slopscore.toml` / `[tool.slopscore]` config with per-rule toggles and
severity overrides, inline `<!-- slopscore-disable … -->` suppression, a findings baseline
(`--fail-on-new`), the implemented `unsupported_claims` dimension, opt-in `--suggest` rewrite
suggestions (with SARIF `fixes`), an optional **separate** authorship-adapter interface (no
detector bundled), PyPI packaging, and a docs site.

v0.3: an evaluation framework (`slopscore-lint eval`: TPR@FPR, PR-AUC, calibration, per-subgroup
FPR) and a transparent **learned scorer**, a sign-constrained, calibrated logistic regression over
the 13 dimensions, serialized as auditable JSON and run with pure numpy (`--scorer ml`). The rule
scorer stays the default: under a replace-if-wins gate the learned model must beat it on held-out
TPR@1%FPR *without regressing subgroup false positives*, and on the seed set it does not (it
over-flags plain English). See `MODEL_CARD.md` and `DATA_SOURCES.md`.

v0.2.1: productionization. console/JSON/Markdown/**SARIF**/**HTML** reports, recursive and
changed-files (`--diff`) batch scanning with CI exit codes, a GitHub Action, and a pre-commit hook.

v0.2: detection expansion grounded in Wikipedia's "Signs of AI writing" field guide. Dimensions:
lexical markers, formulaic structure, significance inflation, superficial "-ing" analyses, vague or
over-attribution, negative parallelism and rule-of-three, copula avoidance, genericity, redundancy,
cadence, formatting tells, prompt residue, and a negative human-writing signal. Scoring is
conservative by default: a corroboration gate damps weak-alone tells, and scores abstain on short
or non-English input. See `MODEL_CARD.md` for citations and limitations.

## License

MIT
