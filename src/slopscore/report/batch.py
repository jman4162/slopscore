"""Batch scanning: aggregate many file reports into one summary for CI use."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from slopscore.models import SCHEMA_VERSION, Label, Report, Severity


class FileResult(BaseModel):
    path: str
    slop_score: float
    label: Label
    confidence: float
    abstained: bool
    word_count: int
    findings: int


class BatchSummary(BaseModel):
    total_files: int
    total_findings: int
    by_label: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    worst: list[FileResult] = Field(default_factory=list)


class BatchReport(BaseModel):
    version: str = SCHEMA_VERSION
    profile: str
    strictness: str
    files: list[FileResult] = Field(default_factory=list)
    summary: BatchSummary

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)


def build_batch_report(reports: list[Report], profile: str, strictness: str) -> BatchReport:
    files = [
        FileResult(
            path=r.input.source,
            slop_score=r.score.slop_score,
            label=r.score.label,
            confidence=r.score.confidence,
            abstained=r.score.abstained,
            word_count=r.input.word_count,
            findings=len(r.evidence),
        )
        for r in reports
    ]
    by_label = Counter(f.label.value for f in files)
    by_severity: Counter[str] = Counter()
    for r in reports:
        by_severity.update(e.severity.value for e in r.evidence)
    worst = sorted(files, key=lambda f: f.slop_score, reverse=True)[:5]
    summary = BatchSummary(
        total_files=len(files),
        total_findings=sum(f.findings for f in files),
        by_label=dict(by_label),
        by_severity=dict(by_severity),
        worst=worst,
    )
    return BatchReport(profile=profile, strictness=strictness, files=files, summary=summary)


# Severity ordering for --fail-on thresholds.
_SEVERITY_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}


def max_severity(reports: list[Report]) -> int:
    """Highest evidence severity rank across all reports (0 if none)."""
    rank = 0
    for r in reports:
        for e in r.evidence:
            rank = max(rank, _SEVERITY_RANK[e.severity.value])
    return rank


def fail_threshold_rank(fail_on: str) -> int:
    """Rank for a --fail-on value; 'none' -> 0 (never fail on findings)."""
    if fail_on == "none":
        return 99
    return _SEVERITY_RANK[Severity(fail_on).value]
