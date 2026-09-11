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


def test_the_density_floor_is_opt_in() -> None:
    # Applied globally the floor raised scores on short text carrying human signal (a saturated
    # slop dimension cannot fall further while the negative human counterweight is shrunk) and
    # inverted --by-paragraph ranking, which tracks density. It is opt-in per call site;
    # metadiscourse is the only dimension that takes it.
    from slopscore.features.base import MIN_RATE_WORDS, per_hundred_words

    assert per_hundred_words(3.0, 10) == 30.0
    assert per_hundred_words(3.0, 10, MIN_RATE_WORDS) == 3.0
    assert per_hundred_words(3.0, 500, MIN_RATE_WORDS) == 0.6


def test_by_paragraph_ranking_tracks_density_not_length() -> None:
    # --by-paragraph exists to rank paragraphs; a short dense one must outrank a long mild one.
    short_dense = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders."
    )
    long_mild = (
        "It's worth noting that the committee met in Leeds on 14 March 2021 to review tenders. "
        "Costs rose 12 percent since the previous quarter, largely because of steel prices. "
        "Members asked the contractor for a revised schedule before the next session begins. "
        "The minutes record four abstentions and no dissent at all on the final vote taken. "
    )
    assert scan_text(short_dense).score.slop_score > scan_text(long_mild).score.slop_score
