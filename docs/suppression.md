# Inline suppression

Silence a false positive in place with an HTML comment (works in plain text and Markdown). Names
are comma-separated **rule_ids** and/or **dimension** names; omit them to suppress everything.

```markdown
<!-- slopscore-disable-next-line unsupported_claims -->
Everyone knows this is the future.

This line is fine. <!-- slopscore-disable-line COPULA_SERVES_AS -->

<!-- slopscore-disable significance_inflation -->
A block where significance-inflation findings are ignored …
<!-- slopscore-enable significance_inflation -->

<!-- slopscore-disable-file -->
Suppress every finding in this file (e.g. generated content).
```

- `disable-next-line` / `disable-line` / `disable … enable` (block) / `disable-file`.
- Scoping by **dimension** suppresses all of that dimension's rules; by **rule_id** suppresses one.
- An unknown name produces a warning so typos don't silently do nothing.

For project-wide silencing, prefer `disabled_rules` / `disabled_dimensions` in
[configuration](configuration.md).
