"""Findings baseline: adopt slopscore on an existing repo and fail CI only on NEW findings.

`slopscore baseline <paths>` records the current findings as fingerprints; a later
`scan --baseline <file> --fail-on-new` treats those as known and gates only on new ones. A
fingerprint is ``sha256(file | rule_id | span_text)`` so it survives line-number drift and edits
elsewhere in the file.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from slopscore.models import SCHEMA_VERSION, Report


def fingerprint(source: str, rule_id: str, span: str) -> str:
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"\x00")
    h.update(rule_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(span.encode("utf-8"))
    return h.hexdigest()


class BaselineFile(BaseModel):
    version: str = SCHEMA_VERSION
    fingerprints: list[str] = Field(default_factory=list)

    def as_set(self) -> set[str]:
        return set(self.fingerprints)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


def report_fingerprints(report: Report) -> list[str]:
    return [
        fingerprint(report.input.source, e.rule_id, e.span) for e in report.evidence
    ]


def build_baseline(reports: list[Report]) -> BaselineFile:
    fps: list[str] = []
    for r in reports:
        fps.extend(report_fingerprints(r))
    return BaselineFile(fingerprints=sorted(set(fps)))


def new_findings(report: Report, known: set[str]) -> int:
    """Count findings whose fingerprint is not in the baseline."""
    return sum(
        1
        for e in report.evidence
        if fingerprint(report.input.source, e.rule_id, e.span) not in known
    )
