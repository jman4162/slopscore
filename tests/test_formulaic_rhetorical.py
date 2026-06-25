"""Rhetorical question-and-answer scaffolds fire, but not on plain factual prose."""

from __future__ import annotations

from slopscore.core import build_document
from slopscore.features.formulaic_patterns import FormulaicPatterns
from slopscore.ingest import from_string


def _rules(text: str) -> set[str]:
    doc = build_document(from_string(text))
    return {e.rule_id for e in FormulaicPatterns().extract(doc, "blog").spans}


def test_rhetorical_scaffolds_fire() -> None:
    ids = _rules(
        "Our tool helps teams. But what does this mean? Sound familiar? "
        "Here's the thing: it saves time. The answer is simple."
    )
    assert "FORMULAIC_RHETORICAL_WHAT_MEAN" in ids
    assert "FORMULAIC_RHETORICAL_SOUND_FAMILIAR" in ids
    assert "FORMULAIC_RHETORICAL_HERES" in ids
    assert "FORMULAIC_RHETORICAL_THE_ANSWER" in ids


def test_plain_factual_prose_is_quiet() -> None:
    # A genuine question in factual prose should not trip the rhetorical scaffolds.
    ids = _rules(
        "The bridge opened in 1937. Who designed it? Joseph Strauss led the project, "
        "and crews poured 389,000 cubic yards of concrete over four years."
    )
    assert not any(r.startswith("FORMULAIC_RHETORICAL") for r in ids)
