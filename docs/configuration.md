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

# Turn a whole dimension off (it then scores 0 and emits no findings):
disabled_dimensions = ["formatting_tells"]

# Turn individual rules off, or override their severity:
disabled_rules = ["FORMULAIC_IN_CONCLUSION"]
rule_severity = { "COPULA_SERVES_AS" = "low" }
```

CLI flags (`--profile`, `--strictness`, `--scorer`, `--suggest`) override the file. Use
`--config PATH` to point at an explicit file.
