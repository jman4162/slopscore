"""Phrase coverage and the human-signal cap (v0.13)."""

from __future__ import annotations

import pytest

from slopscore import scan_text


def _ids(text: str) -> set[str]:
    return {e.rule_id for e in scan_text(text).evidence}


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("FORMULAIC_WORTH_NOTING", "It's worth noting that the numbers moved."),
        ("FORMULAIC_THAT_SAID", "The plan is fine. That said, the budget is not."),
        ("FORMULAIC_SIMPLY_PUT", "The plan is fine. Simply put, we cannot pay for it."),
        ("FORMULAIC_MAKE_NO_MISTAKE", "Make no mistake, this changes everything."),
        ("FORMULAIC_A_WORLD_WHERE", "Imagine a world where every commute is optional."),
        ("FORMULAIC_EMBARK_JOURNEY", "We embark on a journey of continuous improvement."),
        ("FORMULAIC_DESPITE_CHALLENGES", "Despite these challenges, the outlook remains bright."),
        ("FORMULAIC_LETS_DELVE", "Let's unpack what that means."),
        ("FORMULAIC_LETS_DELVE", "Let's take a deep dive into the numbers."),
        ("FORMULAIC_IN_CONCLUSION", "To sum up, the plan works."),
        ("FORMULAIC_IN_CONCLUSION", "At the end of the day, the plan works."),
        ("FORMULAIC_RHETORICAL_HERES", "Here's the thing. Nobody read the spec."),
        ("PARALLEL_NOT_JUST", "This isn't just a tool, it's a movement."),
        ("PARALLEL_NOT_ABOUT_ITS_ABOUT", "It's not about speed. It's about clarity."),
        ("RESIDUE_SYCOPHANTIC_OPENER", "Great question! The answer depends on the load."),
        ("RESIDUE_OFFER_MORE", "Would you like me to expand on any of these points?"),
        ("RESIDUE_OFFER_MORE", "Hope that helps!"),
        ("RESIDUE_LIMITED_INFORMATION", "While specific details are limited, the firm grew."),
        (
            "RESIDUE_VENDOR_MARKUP",
            "The plant opened in 1962 :contentReference[oaicite:0]{index=0}.",
        ),
        ("RESIDUE_VENDOR_MARKUP", "See the source [cite: 3] for the figure."),
    ],
)
def test_new_rules_fire(rule: str, text: str) -> None:
    assert rule in _ids(text), _ids(text)


@pytest.mark.parametrize(
    "text",
    [
        "In summary judgment the court found for the plaintiff.",  # not the closer
        "Let's dive into the data file and count the rows.",  # a concrete object
        "The board said that the merger was off.",  # "that said" as a relative clause
        "Thanks for asking about the delivery date; it is Tuesday.",  # mid-sentence, no punctuation
    ],
)
def test_new_rules_stay_quiet_on_ordinary_uses(text: str) -> None:
    ids = _ids(text)
    assert not ids & {
        "FORMULAIC_IN_CONCLUSION",
        "FORMULAIC_LETS_DELVE",
        "FORMULAIC_THAT_SAID",
        "RESIDUE_SYCOPHANTIC_OPENER",
    }, ids


def test_concrete_filler_cannot_erase_intact_slop() -> None:
    slop = (
        "In today's fast-paced digital landscape, it is crucial to leverage robust tools. Let's "
        "delve into the details. At its core, innovation underscores transformative potential. "
        "It is not just a tool, it is a revolution. Experts argue that it stands as a testament "
        "to modern engineering and plays a pivotal role in shaping the future. "
    ) * 2
    filler = (
        " We shipped it in March 2022. I wrote the first spec. The team used 4 databases and "
        "found 11 bugs. It was the first release. One of the largest customers ran roughly 900 "
        "jobs a day. We sold 300 seats by June and lost 2 of them. The office moved in 2023."
    )
    base = scan_text(slop).score.slop_score
    padded = scan_text(slop + filler).score.slop_score
    assert base >= 75
    assert padded >= 50, (base, padded)
    breakdown = scan_text(slop + filler).breakdown
    assert breakdown is not None
    human = next(r for r in breakdown.contributions if r.dimension == "human_writing_signals")
    positive = sum(r.logit for r in breakdown.contributions if not r.statistical)
    assert human.logit >= -0.5 * positive - 1e-6
