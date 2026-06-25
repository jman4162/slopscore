"""SARIF 2.1.0 output for GitHub code scanning and other SARIF consumers.

Hand-built (no dependency): findings already carry char spans, rule_ids, severities, and
explanations. Severity maps to SARIF level (high->error, medium->warning, low->note). Regions
are computed from char offsets via :func:`char_to_line_col`. The ``rules[]`` registry is derived
from the distinct rule_ids present so consumers get rule metadata.
"""

from __future__ import annotations

from typing import Any

from slopscore import __version__
from slopscore.models import Evidence, Report, Severity
from slopscore.report.locations import char_to_line_col

SARIF_VERSION = "2.1.0"
_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_INFO_URI = "https://github.com/jman4162/slopscore"

_LEVEL: dict[Severity, str] = {
    Severity.high: "error",
    Severity.medium: "warning",
    Severity.low: "note",
}


def _rules_registry(evidence: list[Evidence]) -> list[dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for e in evidence:
        if e.rule_id not in rules:
            rules[e.rule_id] = {
                "id": e.rule_id,
                "shortDescription": {"text": e.explanation},
                "defaultConfiguration": {"level": _LEVEL[e.severity]},
            }
    return list(rules.values())


def _result(e: Evidence, uri: str, text: str) -> dict[str, Any]:
    sl, sc, el, ec = char_to_line_col(text, e.start_char, e.end_char)
    return {
        "ruleId": e.rule_id,
        "level": _LEVEL[e.severity],
        "message": {"text": f"{e.explanation} (matched: {e.span!r})"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {
                        "startLine": sl,
                        "startColumn": sc,
                        "endLine": el,
                        "endColumn": ec,
                    },
                }
            }
        ],
    }


def _run(report: Report) -> dict[str, Any]:
    uri = report.input.source
    text = report.original_text
    results = [_result(e, uri, text) for e in report.evidence]
    return {
        "tool": {
            "driver": {
                "name": "slopscore",
                "version": __version__,
                "informationUri": _INFO_URI,
                "rules": _rules_registry(report.evidence),
            }
        },
        "results": results,
    }


def to_sarif(reports: Report | list[Report]) -> dict[str, Any]:
    """Build a SARIF 2.1.0 log from one report or many (batch -> one run per file)."""
    items = [reports] if isinstance(reports, Report) else list(reports)
    return {
        "version": SARIF_VERSION,
        "$schema": _SCHEMA,
        "runs": [_run(r) for r in items],
    }
