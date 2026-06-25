"""Opt-in rewrite suggestions (``--suggest``).

A non-destructive overlay: matches plain-language replacement patterns and emits low-severity
Evidence carrying a :class:`Suggestion`. These are advisory — appended only when requested, never
auto-applied, and excluded from the score and from ``--fail-on``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.models import Evidence, Severity, Suggestion


@dataclass(frozen=True)
class _Swap:
    rule_id: str
    pattern: re.Pattern[str]
    text: str
    confidence: float
    reasoning: str


@lru_cache(maxsize=1)
def _swaps() -> list[_Swap]:
    with data_path("patterns", "suggestions", "replacements.yaml").open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return [
        _Swap(
            rule_id=e["rule_id"],
            pattern=re.compile(e["pattern"], re.IGNORECASE),
            text=e["suggestion"],
            confidence=float(e["confidence"]),
            reasoning=e["reasoning"],
        )
        for e in raw.get("rules", [])
    ]


def find_suggestions(doc: Document) -> list[Evidence]:
    spans: list[Evidence] = []
    for swap in _swaps():
        for m in swap.pattern.finditer(doc.cleaned_text):
            ev = doc.evidence(
                rule_id=swap.rule_id,
                severity=Severity.low,
                clean_start=m.start(),
                clean_end=m.end(),
                explanation=swap.reasoning,
            )
            verb = "delete" if swap.text == "" else f"replace with '{swap.text}'"
            spans.append(
                ev.model_copy(
                    update={
                        "suggestion": Suggestion(
                            text=swap.text, confidence=swap.confidence, reasoning=verb
                        )
                    }
                )
            )
    return spans
