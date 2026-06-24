"""Negative human-writing signal and the weak formatting-tells signal."""

from __future__ import annotations

from slopscore.core import build_document
from slopscore.features.formatting import FormattingTells
from slopscore.features.human_signals import HumanWritingSignals
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_human_signals_high_on_specific_plain_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss was the first to use this design. He built it in about four years."
    )
    result = HumanWritingSignals().extract(doc, "blog")
    assert result.score > 0.4
    assert result.spans == []  # negative signal carries no evidence


def test_human_signals_low_on_abstract_slop() -> None:
    doc = _doc(
        "This transformative platform leverages a comprehensive ecosystem to foster "
        "synergy and unlock holistic value across the evolving landscape."
    )
    result = HumanWritingSignals().extract(doc, "blog")
    assert result.score < 0.3


def test_formatting_tells_fire_on_dash_heavy_text() -> None:
    doc = _doc(
        "It was great — really great — and more than that — it was — well — everything."
    )
    result = FormattingTells().extract(doc, "blog")
    assert result.score > 0.0


def test_formatting_tells_quiet_on_plain_text() -> None:
    doc = _doc("The cat sat on the mat. It was a sunny day, and the birds sang.")
    result = FormattingTells().extract(doc, "blog")
    assert result.score == 0.0
