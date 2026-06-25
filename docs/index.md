# slopscore

A transparent **linter for AI-slop writing patterns** in essays, blog posts, Markdown, JSON,
and websites. It returns a 0 to 100 SlopScore with per-dimension breakdowns and **evidence spans**
(the exact phrases that triggered each finding), so you can see and fix what it flags.

!!! warning "What slopscore is NOT"
    It does **not** detect whether text was written by AI, and must never be used to accuse a
    writer. It flags writing *patterns in text* (not authorship, not authors): patterns common in
    low-effort or AI-like prose **and** in plenty of human writing. Use it as a prose linter, not an
    AI detector. See [Limitations & authorship](limitations.md).

## Install

```bash
pip install slopscore-lint            # lean, rule-based core
pip install "slopscore-lint[report]"  # + HTML reports
pip install "slopscore-lint[nlp]"     # + spaCy precision
pip install "slopscore-lint[all]"     # everything
```

## Scan

```bash
slopscore-lint scan post.md
slopscore-lint scan ./content --recursive --fail-on high      # CI gate
slopscore-lint scan post.md --format sarif -o out.sarif       # GitHub code scanning
slopscore-lint scan post.md --suggest                         # opt-in rewrite suggestions
```

## Make it yours

- [Configuration](configuration.md): `slopscore.toml` / `[tool.slopscore]`, per-rule toggles.
- [Suppression](suppression.md): inline `<!-- slopscore-disable … -->` comments.
- [Baseline](baseline.md): adopt on an existing repo; fail CI only on new findings.
