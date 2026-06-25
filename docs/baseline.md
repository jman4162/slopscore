# Baseline

Adopt slopscore on an existing project without drowning in pre-existing findings: record a
baseline, then fail CI only on **new** findings.

```bash
# 1. Record current findings (commit the result).
slopscore baseline ./content --recursive -o .slopscore-baseline.json

# 2. In CI, gate only on findings not in the baseline.
slopscore scan ./content --recursive \
  --baseline-file .slopscore-baseline.json --fail-on-new
```

A finding is fingerprinted as `sha256(file | rule_id | matched text)`, so it survives line-number
drift and edits elsewhere in the file. Exit code is `1` only when a finding appears that is not in
the baseline; `0` otherwise. Refresh the baseline by re-running `slopscore baseline`.
