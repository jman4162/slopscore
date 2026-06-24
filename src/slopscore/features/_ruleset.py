"""Shared loader for YAML regex rulesets (formulaic patterns, prompt residue)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.models import Evidence, Severity


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    pattern: re.Pattern[str]
    explanation: str
    source: str = ""  # optional citation (e.g. "Kobak 2025"), for the model card


def _rules_from_yaml(raw: dict[str, Any]) -> list[Rule]:
    rules = []
    for entry in raw.get("rules", []) or []:
        rules.append(
            Rule(
                rule_id=entry["rule_id"],
                severity=Severity(entry.get("severity", "low")),
                pattern=re.compile(entry["pattern"], re.IGNORECASE | re.MULTILINE),
                explanation=entry["explanation"],
                source=entry.get("source", ""),
            )
        )
    return rules


def load_rules(*parts: str) -> list[Rule]:
    with data_path(*parts).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _rules_from_yaml(raw)


def load_rules_from_directory(*parts: str) -> list[Rule]:
    """Merge every ``*.yaml`` rule file under a packaged ``data/`` subdirectory.

    Lets a growing rule pack be split into small, themed files (the way Vale/proselint
    organize styles) without changing the loading feature.
    """
    directory = data_path(*parts)
    rules: list[Rule] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if entry.name.endswith(".yaml"):
            with entry.open(encoding="utf-8") as fh:
                rules.extend(_rules_from_yaml(yaml.safe_load(fh)))
    return rules


def find_matches(doc: Document, rules: list[Rule]) -> list[Evidence]:
    spans: list[Evidence] = []
    for rule in rules:
        for m in rule.pattern.finditer(doc.cleaned_text):
            spans.append(
                doc.evidence(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    clean_start=m.start(),
                    clean_end=m.end(),
                    explanation=rule.explanation,
                )
            )
    return spans


# Severity weights used when turning a set of hits into a [0, 1] score.
SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.low: 1.0,
    Severity.medium: 2.0,
    Severity.high: 4.0,
}
