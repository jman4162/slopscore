"""Conservatism guardrails: abstention, corroboration gate, negative human signal."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.models import Label

_SPECIFIC_PARAGRAPH = (
    "The factory opened in 1962 on a 14-acre site east of Cleveland. It employed 1,200 "
    "workers at its peak and produced roughly 400 transmissions a day. Managers tried a "
    "new shift schedule in 1971, and output rose 12 percent over the next two years. "
    "The plant closed in 1989 after the parent company moved production to Mexico. "
    "Local historians wrote two books about it, and the city bought the land in 1994."
)


def test_short_slop_text_abstains() -> None:
    report = scan_text("Let's delve into this transformative, robust, holistic tapestry.")
    assert report.score.abstained is True
    assert report.score.label in (Label.low, Label.mild)  # never severe when abstaining
    assert report.score.abstention_reason is not None


def test_specific_prose_scores_low_with_high_human_signal() -> None:
    report = scan_text(_SPECIFIC_PARAGRAPH)
    assert report.score.slop_score < 35
    assert report.dimensions.human_writing_signals > 0.4


def test_single_marker_in_specific_prose_stays_low() -> None:
    # One AI word dropped into otherwise concrete prose must not reach "severe".
    text = _SPECIFIC_PARAGRAPH + " The closure underscores the era's decline."
    report = scan_text(text)
    assert report.score.label in (Label.low, Label.mild)


def test_non_english_label_withheld() -> None:
    # A long Spanish paragraph should not be labelled severe (tuned for English).
    spanish = (
        "La fábrica abrió en 1962 en un sitio al este de la ciudad. Empleaba a mil "
        "doscientos trabajadores y producía cuatrocientas transmisiones al día. Los "
        "gerentes probaron un nuevo horario en 1971 y la producción aumentó. La planta "
        "cerró en 1989 cuando la empresa trasladó la producción a otro país lejano."
    ) * 2
    report = scan_text(spanish)
    if report.input.language != "en":  # depends on optional [lang] extra
        assert report.score.abstained is True
        assert report.score.label != Label.severe
