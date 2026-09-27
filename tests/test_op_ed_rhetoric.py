"""v0.14.2 rules for argued op-ed rhetoric, from a human-reader catch (agentic bank run post).

The passage is specific and fact-dense, so it scores low by design: the rules surface the spans,
the corroboration gate keeps the label conservative. The regression test at the bottom locks
in both halves.
"""

from __future__ import annotations

import pytest

from slopscore import scan_text
from slopscore.config import Settings
from slopscore.core import SlopScorer

PASSAGE = (
    "In today's version of \"Doomerism Debunked\" we're looking at the idea of an agentic bank "
    "run and why it's overstated at best and wrong at worst.\n\n"
    "The argument goes like this. AI agents will sweep household cash out of 0.1% checking "
    "accounts and into 4% high yield savings accounts, banks will lose the cheap deposits they "
    "use to make loans, and the whole system gets into trouble.\n\n"
    "But think about where that money actually goes. When cash moves from a checking account at "
    "Bank A to a savings account at Bank B, Bank A's deposits fall and Bank B's deposits rise by "
    "the same amount. Total deposits in the banking system don't change. And most of the "
    "fintechs in the chart are either banks themselves or sweep your cash into partner banks. "
    "The money never leaves the system. It just changes addresses.\n\n"
    "It's also worth remembering that banks don't lend out deposits. Loans create deposits. "
    "Banks need deposits to settle payments and hold reserves, and if they lose cheap ones they "
    "can replace them with more expensive ones. That's a real cost, but it's a cost, not a "
    "collapse.\n\n"
    "Deposits really leave the banking system mainly through a few channels, such as physical "
    "cash withdrawals, payments to the Treasury (which comes back when spent), or money that "
    "ends up at the Fed's reverse repo facility. A bot moving your savings to a better rate "
    "isn't one of them.\n\n"
    "Now, the stronger version of this argument deserves a fair hearing. SVB was a run from one "
    "bank to other banks, and it still killed the bank. If AI agents can move uninsured deposits "
    "in hours instead of days, individual bank runs could happen faster than they used to. And "
    "sticky, low rate deposits have always been part of how banks manage interest rate risk. If "
    "that stickiness goes away, weaker banks have to manage their balance sheets more "
    "carefully.\n\n"
    "That's a legitimate risk for specific banks with bad balance sheets. It is not a "
    "system-wide run. The more likely outcome is that banks have to pay savers closer to market "
    "rates and their net interest margins get squeezed. That's bad for bank shareholders. It's "
    "pretty good for everyone holding cash.\n\n"
    "So yes, agentic banking will probably change the economics of deposits. But calling it a "
    "bank run confuses a repricing of bank funding with a panic driven collapse of the system. "
    "Those are very different animals.\n"
)


def _ids(text: str, *, broad: bool = False) -> set[str]:
    scorer = SlopScorer(settings=Settings(broad_rules=broad))
    return {e.rule_id for e in scorer.scan_text(text).evidence}


@pytest.mark.parametrize(
    "text",
    [
        "Now, the stronger version of this argument deserves a fair hearing.",
        "The strongest version of their case is simple.",
        "The best version of the opposing argument goes further.",
        "That is the strongest version of it.",
        "The objection deserves a fair hearing.",
    ],
)
def test_strongest_version_fires(text: str) -> None:
    assert "INSIGHT_STRONGEST_VERSION" in _ids(text)


@pytest.mark.parametrize(
    "text",
    [
        "The stronger version of the drug was pulled from pharmacies in 2019.",
        "The strongest version of the Mustang has 760 horsepower.",
        "Be the strongest version of yourself.",
        "The defendant deserves a fair hearing.",
    ],
)
def test_strongest_version_literal_is_core_quiet_broad_flagged(text: str) -> None:
    assert "INSIGHT_STRONGEST_VERSION" not in _ids(text)
    if "version of" in text:
        assert "INSIGHT_BROAD_STRONGEST_VERSION" in _ids(text, broad=True)


def test_broad_does_not_double_charge_the_argumentative_use() -> None:
    ids = _ids("The stronger version of this argument is better.", broad=True)
    assert "INSIGHT_STRONGEST_VERSION" in ids
    assert "INSIGHT_BROAD_STRONGEST_VERSION" not in ids


def test_one_hit_when_both_arms_share_a_sentence() -> None:
    report = scan_text("Now, the stronger version of this argument deserves a fair hearing.")
    hits = [e for e in report.evidence if e.rule_id == "INSIGHT_STRONGEST_VERSION"]
    assert len(hits) == 1


def test_contrastive_coda_fires() -> None:
    assert "PARALLEL_X_NOT_Y_CODA" in _ids("That's a real cost, but it's a cost, not a collapse.")


@pytest.mark.parametrize(
    "text",
    [
        # Sentence-initial slogans belong to PARALLEL_X_NOT_Y; the coda must not double-charge.
        "It's a cost, not a collapse.",
        # No article on both sides: the human MAGE rows this rule used to match.
        "Remember that this is based on averages, not individuals.",
        "The movie I saw was new and it was Jurassic World, not Jurassic Park.",
    ],
)
def test_contrastive_coda_quiet(text: str) -> None:
    assert "PARALLEL_X_NOT_Y_CODA" not in _ids(text)


def test_cross_sentence_antithesis_fires() -> None:
    text = "That's a legitimate risk for specific banks. It is not a system-wide run."
    assert "PARALLEL_THATS_X_ITS_NOT_Y" in _ids(text)


@pytest.mark.parametrize(
    "text",
    [
        "That's a Tuesday. It isn't raining.",
        "It's a fact that most people agree. It's not a debate.",
    ],
)
def test_cross_sentence_antithesis_quiet(text: str) -> None:
    assert "PARALLEL_THATS_X_ITS_NOT_Y" not in _ids(text)


def test_worth_remembering_and_argument_setup() -> None:
    assert "FORMULAIC_WORTH_NOTING" in _ids(
        "It's also worth remembering that loans create deposits."
    )
    assert "META_ARGUMENT_SETUP" in _ids("The argument goes like this. Rates rise and banks lose.")


def test_passage_regression_spans_found_label_conservative() -> None:
    report = scan_text(PASSAGE)
    ids = {e.rule_id for e in report.evidence}
    assert {
        "INSIGHT_STRONGEST_VERSION",
        "PARALLEL_X_NOT_Y_CODA",
        "PARALLEL_THATS_X_ITS_NOT_Y",
        "FORMULAIC_WORTH_NOTING",
        "META_ARGUMENT_SETUP",
    } <= ids
    # Evidence offsets index the original text.
    for e in report.evidence:
        if e.rule_id == "INSIGHT_STRONGEST_VERSION":
            assert report.original_text[e.start_char : e.end_char] == e.span
    # Specific, fact-dense prose: the spans surface, the label stays conservative.
    assert report.score.label in {"low", "mild"}
