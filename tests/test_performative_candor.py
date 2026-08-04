"""Performative candor / manufactured sincerity dimension and its opt-in broad tier."""

from __future__ import annotations

import pytest

from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.phrase_packs import PerformativeCandor
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def _core_ids(text: str) -> set[str]:
    return {e.rule_id for e in PerformativeCandor.extract(_doc(text), "blog").spans}


def test_confessional_frames_fire() -> None:
    doc = _doc(
        "I have to be honest: the schedule slipped. If I'm being honest, we knew in March. "
        "Let me be candid about the cost, and let's be real about the alternative."
    )
    result = PerformativeCandor.extract(doc, "blog")
    assert result.score > 0.5
    assert "CANDOR_CONFESSIONAL_FRAME" in {e.rule_id for e in result.spans}


def test_disclosure_markers_fire() -> None:
    ids = _core_ids(
        "Truth be told, nobody checked. Full disclosure: I own shares. Real talk: it is broken, "
        "and I won't sugarcoat that."
    )
    assert "CANDOR_DISCLOSURE_MARKER" in ids


def test_honest_abstract_noun_fires() -> None:
    # The reported catch: sincerity adjective bolted to an abstract noun, with "honest limits"
    # standing in for "limitations".
    ids = _core_ids("The honest framing is that the honest limits of the approach are real.")
    assert "CANDOR_HONEST_ABSTRACT_NOUN" in ids


def test_honest_common_noun_fires() -> None:
    assert "CANDOR_HONEST_COMMON_NOUN" in _core_ids("The honest answer is that we do not know.")


@pytest.mark.parametrize(
    "text",
    [
        "Honestly, this is filler.",  # sentence-initial
        "This is, frankly, absurd.",  # comma-flanked parenthetical
        "- Honestly, this is filler.",  # list item, the form LLM output actually produces
    ],
)
def test_adverb_opener_fires(text: str) -> None:
    assert "CANDOR_ADVERB_PARENTHETICAL" in _core_ids(text)


def test_sincerity_collocation_fires() -> None:
    assert "CANDOR_SINCERITY_COLLOCATION" in _core_ids("It was genuinely interesting work.")


def test_vulnerability_meta_fires() -> None:
    assert "CANDOR_NOT_LIGHTLY" in _core_ids("I don't say this lightly, but the plan is wrong.")
    assert "CANDOR_ADMISSION" in _core_ids("I have to admit, this is clever.")
    assert "CANDOR_PUSH_BACK" in _core_ids("I'm going to push back on that.")


@pytest.mark.parametrize(
    "text",
    [
        # The sincerity words in their ordinary senses. The head-noun and comma gates carry these.
        "He is an honest man who did honest work for thirty years.",
        "It was an honest mistake; the clerk fixed it the same day.",
        "She gave a frank account of the strike to the committee.",
        "The company disclosed the full disclosure schedule under Regulation FD.",
        "Real talk shows dominated daytime television in 1994.",
        "I have to admit the bike was faster than mine.",
        "He was genuinely surprised by the result.",
        "The team pushed back the release by two weeks.",
        "The report lists limitations of the method in section 4.",
        "She answered honestly and went back to work.",
        # Email sign-offs: patterns compile under MULTILINE, so ^ matches every line start.
        "Sincerely,\nJohn Smith",
        "Yours truly,\nMaria",
        # ESL calques. The required comma in CANDOR_ADVERB_PARENTHETICAL is what keeps these
        # quiet, and that is this rule set's most important fairness property.
        "Honestly speaking, my first winter in Helsinki was very hard.",
        "Frankly speaking, the training was too fast for me.",
    ],
)
def test_ordinary_prose_is_not_flagged(text: str) -> None:
    assert not any(r.startswith("CANDOR_") for r in _core_ids(text)), text


def test_no_double_fire_on_have_to_be_honest() -> None:
    # "I have to be honest" must score once as a confessional frame, not also as bare
    # "to be honest". Regression guard on the negative lookbehind in CANDOR_TO_BE_HONEST.
    spans = PerformativeCandor.extract(
        _doc("I have to be honest with you about the price."), "blog"
    ).spans
    assert len(spans) == 1
    assert spans[0].rule_id == "CANDOR_CONFESSIONAL_FRAME"


def test_bare_to_be_honest_still_fires_alone() -> None:
    assert "CANDOR_TO_BE_HONEST" in _core_ids("To be honest, I did not understand the form.")


def test_candor_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert PerformativeCandor.extract(doc, "blog").score == 0.0


def test_candor_offsets_round_trip() -> None:
    # Run with broad=True so the lookbehind- and lookahead-bearing patterns are covered too.
    doc = _doc(
        "Honestly, I have to be honest: the honest framing is that truth be told, it was "
        "genuinely hard. To be fair, I have to admit, that is genuinely surprising."
    )
    for e in PerformativeCandor.extract(doc, "blog", broad=True).spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span


def test_bare_adverbs_are_broad_only() -> None:
    text = "She answered honestly and was genuinely careful about the wiring."
    doc = _doc(text)
    assert PerformativeCandor.extract(doc, "blog").score == 0.0
    broad_ids = {e.rule_id for e in PerformativeCandor.extract(doc, "blog", broad=True).spans}
    assert {"CANDOR_BROAD_BARE_CANDOR", "CANDOR_BROAD_SINCERITY_ADVERB"} <= broad_ids


def test_broad_flag_enables_candor_broad() -> None:
    text = "To be fair, she answered honestly and was genuinely careful about the wiring."
    off = SlopScorer(settings=Settings()).scan_text(text)
    on = SlopScorer(settings=Settings(broad_rules=True)).scan_text(text)
    assert off.dimensions.performative_candor == 0.0
    assert on.dimensions.performative_candor > 0.0
    assert "CANDOR_BROAD_TO_BE_FAIR" in {e.rule_id for e in on.evidence}


def test_broad_does_not_duplicate_weasel_intensifiers() -> None:
    # "truly" is already WEASEL_BROAD_INTENSIFIER; the candor broad tier must not charge it again.
    report = SlopScorer(settings=Settings(broad_rules=True)).scan_text("That was truly remarkable.")
    assert not any(e.rule_id.startswith("CANDOR_BROAD_") for e in report.evidence)


def test_disabled_dimension_suppresses_broad_rescore() -> None:
    # A disabled performative_candor dimension must stay disabled even with --broad.
    settings = Settings(broad_rules=True, disabled_dimensions=frozenset({"performative_candor"}))
    report = SlopScorer(settings=settings).scan_text(
        "Honestly, to be fair, I have to be honest: truth be told it was genuinely hard."
    )
    assert report.dimensions.performative_candor == 0.0
    assert not any(e.rule_id.startswith("CANDOR_") for e in report.evidence)
