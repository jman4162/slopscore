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
pip install slopscore          # lean, rule-based core
pip install "slopscore[web]"   # + website extraction (trafilatura)
pip install "slopscore[nlp]"   # + spaCy NER and sentence-transformer embeddings
pip install "slopscore[lang]"  # + non-English language detection
pip install "slopscore[all]"   # everything
```

## Usage

```bash
slopscore scan post.md
slopscore scan essay.txt --format json
slopscore scan content.json --json-path "$.article.body"
slopscore scan https://example.com/post        # requires slopscore[web]
```

```python
from slopscore import SlopScorer

scorer = SlopScorer(profile="blog", strictness="conservative")
report = scorer.scan_text("In today's fast-paced digital landscape, it is crucial to ...")
print(report.score.slop_score, report.score.label)
print(report.evidence[:3])
```

## Status

v0.1 — transparent rule-based linter. Live dimensions: lexical markers, formulaic structure,
prompt residue. Specificity, redundancy, and cadence have minimal implementations and grow in
v0.2. Profiles/calibration (v0.2), ML scoring (v0.3), and optional authorship-signal adapters
(v0.4) are on the roadmap. See `BACKGROUND_INFORMATION.local.md` for the full spec.

## License

MIT
