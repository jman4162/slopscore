"""JSON report (spec schema). The pydantic model IS the schema, so this is a thin wrapper."""

from __future__ import annotations

from slopscore.models import Report


def to_json(report: Report, *, indent: int = 2) -> str:
    return report.to_json(indent=indent)
