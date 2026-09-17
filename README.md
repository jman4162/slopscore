# slopscore

[![PyPI](https://img.shields.io/pypi/v/slopscore-lint.svg)](https://pypi.org/project/slopscore-lint/)
[![Python](https://img.shields.io/pypi/pyversions/slopscore-lint.svg)](https://pypi.org/project/slopscore-lint/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/jman4162/slopscore/actions/workflows/ci.yml/badge.svg)](https://github.com/jman4162/slopscore/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://jman4162.github.io/slopscore/)
[![Marketplace](https://img.shields.io/badge/GitHub_Marketplace-slopscore--lint-2ea44f.svg?logo=github&logoColor=white)](https://github.com/marketplace/actions/slopscore-lint)

A transparent **linter for AI-slop writing patterns** in essays, blog posts, Markdown, JSON, and
websites.

`slopscore` reads text and returns a 0 to 100 **SlopScore** measuring the density of formulaic,
generic, low-specificity, over-polished writing patterns associated with low-effort LLM output.
It reports per-dimension scores and **evidence spans** (the exact phrases that triggered each
finding), so you can see and fix what it flags.

**Try it in your browser:** [slopscore.mountsilabs.com](https://slopscore.mountsilabs.com). Paste prose and get the score with evidence spans, no install.

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
Rule-driven dimensions carry an evidence span for every hit. The four statistical dimensions
(genericity, cadence, redundancy, and the human-signal counterweight) are low-weighted, never
corroborate a weak tell, and point at the passage that drove them with a labeled summary span;
the JSON `breakdown` attributes every point of the score to a dimension.

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

## Quickstart

```bash
pip install slopscore-lint
slopscore-lint scan post.md
```

```text
SlopScore 100.0/100 (severe)   110 words   profile blog   strictness conservative

Evidence (26 findings; each line has a char offset, severity, and explanation):
   54  SIGNIF_STANDS_AS_TESTAMENT  high    "stands as a testament"
   91  PARALLEL_ITS_NOT_ITS        medium  "It is not just a tool, it is"
  138  LEXICAL_MARKETING_UPLIFT    medium  "empowers"
  152  WEASEL_EXPERTS_ARGUE        medium  "Experts argue"
```

Every finding traces to a rule and the span that triggered it. `scan` returns exit code
`1` when findings reach the `--fail-on` threshold, so it drops into CI unchanged:

```bash
slopscore-lint scan post.md --fail-on high   # exit 1 on the sample above; 0 when clean
```

Short text (under ~100 words) and non-English input abstain from a confident label by design.

## Usage

```bash
slopscore-lint scan post.md
slopscore-lint scan essay.txt --format json
slopscore-lint scan content.json --json-path "$.article.body"
slopscore-lint scan https://example.com/post        # requires slopscore-lint[web]
slopscore-lint scan src/app.py                       # lints docstring/comment prose, ignores code
slopscore-lint scan post.md --by-paragraph           # surfaces a sloppy section in a clean doc
slopscore-lint scan draft.md --suggest               # adds advisory rewrite suggestions
slopscore-lint scan essay.md --broad                 # opt-in tier: rationalist jargon + bare weasel words
slopscore-lint explain                               # what each of the 18 dimensions detects
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

## Use it in CI

Gate prose like any other linter. Exit codes: `0` clean (or below `--fail-on`), `1` findings at or
above the threshold, `2` usage error, `3` a needed extra is missing.

```bash
slopscore-lint scan ./content --recursive --fail-on high          # exit 1 if any high finding
slopscore-lint scan . --diff origin/main --fail-on medium         # only files changed vs a ref
slopscore-lint scan ./content --recursive --format sarif -o out.sarif   # for GitHub code scanning
slopscore-lint scan post.md --format html -o report.html          # highlighted-span HTML (needs [report])
```

**pre-commit** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/jman4162/slopscore
    rev: v0.14.1
    hooks:
      - id: slopscore-lint
        args: ["--fail-on", "high"]
```

**GitHub Action** (`.github/workflows/prose.yml`) scans on every pull request and uploads findings
to code scanning. `security-events: write` is required while `upload-sarif` is on (its default);
set `upload-sarif: false` to drop it.

```yaml
name: prose
on: [pull_request]
permissions:
  contents: read
  security-events: write
jobs:
  slopscore:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jman4162/slopscore@v0
        with:
          files: ./content
          profile: blog
          fail-on: high
```

## Adopt on an existing repo

Record the current findings as a baseline, commit it, then fail CI only on *new* findings so a
backlog does not block the first run:

```bash
slopscore-lint baseline ./content --recursive -o .slopscore-baseline.json
git add .slopscore-baseline.json && git commit -m "slopscore baseline"
slopscore-lint scan ./content --recursive --baseline-file .slopscore-baseline.json --fail-on-new
```

## Configure

Settings live in `slopscore.toml` or a `[tool.slopscore]` table in `pyproject.toml`. CLI flags win
over the file. Run `slopscore-lint config` to print the effective settings.

```toml
# slopscore.toml
profile = "technical"
strictness = "conservative"
disabled_rules = ["RESIDUE_CODE_FENCE"]
rule_severity = { COPULA_SERVES_AS = "low" }
suggest = false
```

`disabled_rules` and `rule_severity` take effect everywhere. For a one-off false positive in a
Markdown, plain-text, or reStructuredText file, an inline comment also works:

```text
<!-- slopscore-disable-next-line SIGNIF_STANDS_AS_TESTAMENT -->
The museum stands as a testament to the city's history.
```

`--suggest` adds advisory, non-destructive rewrite suggestions (it never edits files):

```bash
slopscore-lint scan draft.md --suggest --format json | jq '.evidence[] | select(.suggestion) | {span, fix: .suggestion.text}'
# {"span": "utilize", "fix": "use"}
# {"span": "in order to", "fix": "to"}
```

## Python API

```python
from slopscore import scan_text, scan_path

# the argument below is an example of the slop the tool flags:
report = scan_text("In today's fast-paced digital landscape, our platform empowers synergy.")
print(report.score.slop_score, report.score.label.value)   # 93.2 mild (short text abstains)
for e in report.evidence[:3]:
    print(e.rule_id, repr(e.span))

# batch a folder, skipping anything too short to judge:
from pathlib import Path
for f in Path("posts").glob("*.md"):
    r = scan_path(f)
    if not r.score.abstained and r.score.slop_score >= 50:
        print(f"{f.name}: {r.score.slop_score} {r.score.label.value}")
```

## Status

v0.14: `metadiscourse` for writing that refers to the text rather than to its subject: frame
markers ("in this section we will discuss"), endophoric markers ("as noted above"), code glosses
("put simply:"), and prose-grading ("the defensible version is"). It scores the longest run of
consecutive metadiscourse sentences that carry no name, number, date, or identifier, so a run of
three reads the same in a 120-word passage and a 3,000-word essay, where a per-100-word rate
would have divided it away. A marker over a concrete fact is exempt, which is both the precision
gate and the fairness gate. Also fixes `load-bearing` in predicative position ("this distinction
is load-bearing"), which had no rule.

v0.13: detection coverage. A `structure_tells` dimension scores the chatbot Markdown shape
(emoji headings, `**Label:** text` bullet runs, heading-level jumps, rules between every section,
heavy bold) from block metadata the Markdown ingester now records; pasted text that looks like
Markdown is ingested as Markdown, so emphasis markers no longer hide phrases. Quoted speech is
skipped by the candor, claims, and attribution packs. Twelve new phrase rules cover the connective
filler and chatbot residue the review found missing ("it's worth noting", "that said", "Great
question!", vendor citation markup). The human-signal counterweight is capped at half the
positive evidence, so appended dates and counts cannot erase intact slop.

v0.12: long-form evaluation and thresholds. A committed 180-document set of 300+ words (pre-LLM
web pages, 2023 Wikipedia, and full Wikipedia articles flagged as suspected AI-generated) and a
threshold report over 522 human-good documents: clean prose sits under 11 at P95 under every
profile, so `score_threshold = 25` gives a 1% false-positive rate ([docs](https://jman4162.github.io/slopscore/thresholds/)).
Recall on flagged Wikipedia articles at that cutoff is 1%, stated plainly.

v0.11: every point explained. Reports carry a per-dimension `breakdown`, the statistical
dimensions emit labeled summary spans, and CI can gate on the score (`--fail-on-score`,
`score_threshold`) instead of evidence severity alone. Config `fail_on`, `suggest`, `include`,
and `exclude` are honored.

v0.10: score correctness from an adversarial review. Silenced rules lose their points, the
corroboration gate is monotone, strictness is no longer inverted on clean text, genericity no
longer reads abstract human prose as slop, prompt residue decays in long documents, scikit-learn
left the scan path, and eight rule bugs were fixed.

v0.9: `performative_candor`, a third rule-driven axis after fake insight and fake evidence: points
framed as difficult confessions ("I have to be honest", "truth be told"), sincerity adjectives on
abstract nouns, and manufactured reluctance. Kept as its own dimension because its genre
multipliers invert relative to `insight_signaling`. v0.9.2 hardened the GitHub Action against
input injection, made `--fail-on-new` without a baseline a usage error, gave `--diff` a clean
exit on a bad ref, stopped scoring GFM tables as prose, and added a Python matrix, an extras job,
and a wheel-install smoke test to CI.

v0.8: `insight_signaling` for pseudo-profundity that announces insight rather than containing it
("load-bearing", "the crux of the issue", "pressure-test the claim"), with an opt-in `--broad`
tier for rationalist jargon; the weasel dimension gained impersonal-passive attribution and
unearned-certainty openers; `slopscore-lint explain` documents every rule.

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

v0.2: detection expansion grounded in Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) field guide. Dimensions:
lexical markers, formulaic structure, significance inflation, superficial "-ing" analyses, vague or
over-attribution, negative parallelism and rule-of-three, copula avoidance, genericity, redundancy,
cadence, formatting tells, prompt residue, and a negative human-writing signal. Scoring is
conservative by default: a corroboration gate damps weak-alone tells, and scores abstain on short
or non-English input. See `MODEL_CARD.md` for citations and limitations.

## License

MIT.

© 2026 Mount Si Labs LLC. All rights reserved.
