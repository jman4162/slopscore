# Prose-in-code, fairness, and triage

Three v0.6 features that set slopscore-lint apart from other slop linters.

## Lint the prose inside code

`scan` reads the natural-language prose out of source files and ignores the code itself. Python
docstrings and comments are extracted with `ast` and `tokenize`; JS/TS JSDoc and comments with a
best-effort regex. Code linters check the code and skip the prose; prose linters skip code files.
slopscore-lint covers the gap.

```bash
slopscore-lint scan src/app.py            # docstrings + comments in one file
slopscore-lint scan src/ --recursive      # across a package
slopscore-lint scan README.md --fail-on high
```

Offsets in the report index the extracted prose, so SARIF and HTML line numbers are relative to that
prose, not the raw source bytes (the same contract as Markdown ingestion).

## Audit fairness

Pattern detectors are known to over-flag competent plain and non-native English. slopscore-lint is
the only slop linter that measures and publishes this. The `fairness` command scans the clean rows
in the benchmark's `simple_english` and `non_native` slices and reports how often each rule fires:

```bash
slopscore-lint fairness                  # per-rule false-positive rate on plain/ESL text
slopscore-lint fairness --threshold 0.1  # flag rules over 10 percent
```

A rule that fires on competent plain or non-native writing is a fairness liability, not a catch. The
shipped rule scorer fires on neither slice (0 percent), which is why it stays the default over the
learned model. See [Limitations & authorship](limitations.md) and the
[Benchmark & results](benchmark.md).

## Triage a long document

A clean introduction can hide a sloppy middle behind a low average. `--by-paragraph` scores each
paragraph and prints them worst-first so you can find the section to fix:

```bash
slopscore-lint scan article.md --by-paragraph
```

Short paragraphs abstain, as usual, so treat this as triage, not a per-paragraph verdict.
