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


def test_single_insight_marker_in_specific_prose_stays_low() -> None:
    # One insight-signaling phrase ("load-bearing assumption") inside long, concrete, numeric
    # prose must not reach "severe" — these phrases are legitimate in good analytical writing.
    text = _SPECIFIC_PARAGRAPH + " The load-bearing assumption was that demand would hold."
    report = scan_text(text)
    assert report.score.label in (Label.low, Label.mild)


def test_single_weasel_certainty_in_specific_prose_stays_low() -> None:
    # One certainty opener ("Clearly, ...") inside long, concrete prose must not reach "severe".
    text = _SPECIFIC_PARAGRAPH + " Clearly, the plant mattered to the town."
    report = scan_text(text)
    assert report.score.label in (Label.low, Label.mild)


def test_single_candor_marker_in_specific_prose_stays_low() -> None:
    # One sincerity marker inside long, concrete prose must not reach "severe". "Honestly," is
    # ordinary spoken English and carries no weight on its own.
    text = _SPECIFIC_PARAGRAPH + " Honestly, the closure surprised the town."
    report = scan_text(text)
    assert report.score.label in (Label.low, Label.mild)


def test_candor_alone_is_damped() -> None:
    # Candor-dense but otherwise concrete and specific: performative_candor is the only elevated
    # dimension, so the corroboration gate must damp it rather than convict on candor alone.
    text = (
        "I have to be honest about the 1962 plant. Truth be told, it employed 1,200 workers "
        "and produced roughly 400 transmissions a day. Let me be candid: output rose 12 "
        "percent between 1971 and 1973. The honest answer is that it closed in 1989, and the "
        "city bought the 14-acre site in 1994 for 2.3 million dollars."
    )
    report = scan_text(text)
    assert report.dimensions.performative_candor > 0.5
    assert any("Damped (weak alone" in w for w in report.warnings)


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


def test_one_marker_in_a_short_document_does_not_convict() -> None:
    # per_hundred_words amplifies a 16-word document 6.25x, so one low-severity hit used to
    # saturate formulaic_structure at 1.0 and score the document 66.0. This row is a clean
    # simple_english benchmark row: a restatement gloss over a concrete fact, which is a
    # comprehension aid rather than slop.
    report = scan_text(
        "The bus costs two euros. In other words, you need two coins before you get on."
    )
    assert report.score.slop_score < 50
    assert report.dimensions.formulaic_structure < 1.0
    # The finding is still reported; only the composite score is no longer convicted on it.
    assert any(e.rule_id == "FORMULAIC_SIMPLY_PUT" for e in report.findings)


def test_the_density_floor_is_inert_on_real_length_documents() -> None:
    # The floor must smooth a tiny sample, not soften genuine slop. This is 136 words, well
    # above MIN_RATE_WORDS, and must be unaffected.
    from slopscore.features.base import MIN_RATE_WORDS, per_hundred_words

    assert per_hundred_words(3.0, MIN_RATE_WORDS * 5) == 3.0 * 100.0 / (MIN_RATE_WORDS * 5)
    assert per_hundred_words(3.0, 10) == 3.0 * 100.0 / MIN_RATE_WORDS
