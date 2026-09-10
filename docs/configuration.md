# Configuration

slopscore reads configuration from a `slopscore.toml` file or a `[tool.slopscore]` section in
`pyproject.toml`. **Precedence** (highest first): CLI flags → `slopscore.toml` → `pyproject.toml
[tool.slopscore]` → built-in defaults. Show the effective config with `slopscore-lint config`.

```toml
# slopscore.toml  (or under [tool.slopscore] in pyproject.toml)
profile = "blog"            # blog | essay | academic | marketing | technical | social
strictness = "conservative" # conservative | balanced | sensitive
scorer = "rules"            # rules (default) | ml
min_reliable_words = 300
suggest = false             # include opt-in rewrite suggestions
broad = false               # include the opt-in broad rule tier (higher false-positive rate)

# CI gate. Either condition exits 1. Abstained documents (under 100 words, non-English) never
# fail on score, because their number is not a confident label.
fail_on = "none"            # none | low | medium | high: any rule hit at this severity fails
score_threshold = 50        # any non-abstained document at or above this score fails

# Batch walker filters (directory and multi-file scans). `exclude` REPLACES the defaults
# (node_modules, .venv, venv, .git, vendor, dist, build, __pycache__, .tox, .mypy_cache,
# .ruff_cache, site); patterns are root-relative globs or bare directory names.
include = ["docs/*", "*.md"]
exclude = ["node_modules", "build", "*.generated.md"]

# Turn a whole dimension off (it then scores 0 and emits no findings):
disabled_dimensions = ["formatting_tells"]

# Turn individual rules off, or override their severity:
disabled_rules = ["FORMULAIC_IN_CONCLUSION"]
rule_severity = { "COPULA_SERVES_AS" = "low" }
```

CLI flags (`--profile`, `--strictness`, `--scorer`, `--suggest`, `--broad`, `--fail-on`,
`--fail-on-score`, `--include`, `--exclude`) override the file. Use `--config PATH` to point at an
explicit file.

## Reading the score breakdown

Every JSON report carries a `breakdown`: one row per dimension with its value, weight, profile
multiplier, corroboration gate, and the logit it contributed, plus a `statistical` flag on the
four span-less dimensions (genericity, cadence, redundancy, human signals) and their summed
`statistical_logit`. Those four dimensions also emit low-severity `summary` evidence
(`GENERIC_SENTENCE`, `CADENCE_UNIFORM_RUN`, `REDUNDANT_ADJACENT_PAIR`) pointing at the passage
that drove them. Summaries explain the score; they are not rule hits, so they never trip
`--fail-on`, never enter SARIF, and never count as new findings against a baseline.

`--broad` enables an opt-in tier of higher-false-positive rules (rationalist/essayist jargon in
`insight_signaling`; bare quantifiers, hedges, and intensifiers in `weasel_attribution`; bare
sincerity adverbs such as "genuinely" and "honestly" in `performative_candor`; bare code glosses
such as "that is to say" and clause-initial "Overall," in `metadiscourse`). It is off
by default because those bare words also appear in ordinary and non-native English; treat it as a
self-editing highlighter, not an accusation.
