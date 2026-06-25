# slopscore

Transparent AI-slop writing-pattern analysis for essays, blog posts, Markdown, JSON, and
websites.

`slopscore` reads text and returns a 0–100 **SlopScore** measuring the density of formulaic,
generic, low-specificity, over-polished writing patterns associated with low-effort LLM output.
It reports per-dimension scores and **evidence spans** — the exact phrases that triggered each
finding — so you can see and fix what it flags.

## What it is, and what it is not

slopscore detects **writing patterns**, not authorship. It does not claim a text was written by
AI, and it should never be used to accuse a writer. AI-authorship detectors are unreliable on
short, edited, translated, and non-native-English text; slopscore takes the more honest and more
useful position:

> "This text has a high concentration of generic, formulaic, low-evidence writing patterns."

not

> "This was written by AI."

Think of it as a linter for slop — closer to Vale or ruff than to a black-box AI detector.
Every point in the score comes from a visible rule with an evidence span.

## Install

```bash
pip install slopscore            # lean, rule-based core
pip install "slopscore[web]"     # + website extraction (trafilatura)
pip install "slopscore[nlp]"     # + spaCy NER and sentence-transformer embeddings
pip install "slopscore[lang]"    # + non-English language detection
pip install "slopscore[report]"  # + HTML report rendering (Jinja2)
pip install "slopscore[all]"     # everything
```

## Usage

```bash
slopscore scan post.md
slopscore scan essay.txt --format json
slopscore scan content.json --json-path "$.article.body"
slopscore scan https://example.com/post        # requires slopscore[web]
```

### Calibrate against your own writing

Instead of asking "does this look like AI?", ask "does this deviate from *my* usual style in
sloppy ways?". Build a baseline from a folder of your past writing, then compare new drafts to it:

```bash
slopscore calibrate ./my-old-posts --name me
slopscore scan new-post.md --baseline me     # reports per-dimension z-score deviations
```

### Higher-precision syntactic detection (optional)

The default install detects syntactic tells (trailing "-ing" analyses, etc.) with regex. Install
the `[nlp]` extra and the spaCy English model for a higher-precision, lower-false-positive path:

```bash
pip install "slopscore[nlp]"
python -m spacy download en_core_web_sm
```

slopscore auto-upgrades to the spaCy path when the model is present; nothing else changes.

### Use it as a linter in CI

```bash
slopscore scan ./content --recursive --fail-on high          # exit 1 if any high finding
slopscore scan ./content --recursive --format sarif -o out.sarif   # for GitHub code scanning
slopscore scan post.md --format html -o report.html          # highlighted-span HTML (needs [report])
slopscore scan . --diff origin/main --fail-on medium         # only files changed vs a ref
```

Exit codes: `0` clean (or below `--fail-on`), `1` findings at/above the threshold, `2` usage
error, `3` a needed extra is missing. A composite **GitHub Action** (`action.yml`) scans, uploads
SARIF to code scanning, and fails by threshold; a **pre-commit hook** (`.pre-commit-hooks.yaml`)
is published for `pre-commit`. SARIF/HTML line numbers for Markdown are relative to the extracted
prose (raw-source mapping is a later enhancement).

```python
from slopscore import SlopScorer

scorer = SlopScorer(profile="blog", strictness="conservative")
report = scorer.scan_text("In today's fast-paced digital landscape, it is crucial to ...")
print(report.score.slop_score, report.score.label)
print(report.evidence[:3])
```

## Status

v0.2.1 — productionization: console/JSON/Markdown/**SARIF**/**HTML** reports, recursive and
changed-files (`--diff`) batch scanning with CI exit codes, a GitHub Action, and a pre-commit hook.

v0.2 — detection expansion grounded in Wikipedia's "Signs of AI writing" field guide. Dimensions:
lexical markers, formulaic structure, significance inflation, superficial "-ing" analyses, vague /
over-attribution, negative parallelism / rule-of-three, copula avoidance, genericity, redundancy,
cadence, formatting tells, prompt residue, and a negative human-writing signal. Scoring is
conservative by default: a corroboration gate damps weak-alone tells, and scores abstain on short
or non-English input. See `MODEL_CARD.md` for citations and limitations, and
`BACKGROUND_INFORMATION.local.md` for the full spec. ML scoring (v0.3) and optional
authorship-signal adapters (v0.4) remain on the roadmap.

## License

MIT
