"""The CI gate: why a scan should exit non-zero.

Two independent conditions, either of which fails the scan:

- **severity**: any rule hit at or above ``fail_on`` (``none`` disables it). With a findings
  baseline, this becomes "any NEW rule hit" instead. Statistical summaries and advisory
  suggestions are never rule hits.
- **score**: any document that did NOT abstain scoring at or above ``score_threshold``.
  Abstained documents (under 100 words, non-English) never fail on score; their number is not
  a confident label, so it must not be a gate either.

Before v0.11 the gate looked only at evidence severity, so the corroboration gate, abstention,
and the label had no effect on exit codes.
"""

from __future__ import annotations

from slopscore.models import Report
from slopscore.report.baseline import new_findings
from slopscore.report.batch import fail_threshold_rank, max_severity


def failure_reasons(
    reports: list[Report],
    *,
    fail_on: str,
    score_threshold: float | None,
    baseline: set[str] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if baseline is not None:
        total_new = sum(new_findings(r, baseline) for r in reports)
        if total_new:
            reasons.append(f"{total_new} new finding(s) not in the baseline.")
    elif fail_on != "none" and max_severity(reports) >= fail_threshold_rank(fail_on):
        hits = sum(
            1
            for r in reports
            for e in r.findings
            if fail_threshold_rank(e.severity.value) >= fail_threshold_rank(fail_on)
        )
        reasons.append(f"{hits} finding(s) at or above severity '{fail_on}'.")
    if score_threshold is not None:
        over = [
            r for r in reports if not r.score.abstained and r.score.slop_score >= score_threshold
        ]
        if over:
            listing = ", ".join(f"{r.input.source} ({r.score.slop_score})" for r in over[:5])
            more = f", +{len(over) - 5} more" if len(over) > 5 else ""
            reasons.append(
                f"{len(over)} document(s) at or above score {score_threshold:g}: {listing}{more}."
            )
    return reasons
