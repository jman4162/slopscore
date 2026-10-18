"""Insight-signaling / pseudo-profundity dimension and its opt-in broad tier."""

from __future__ import annotations

import pytest

from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.phrase_packs import InsightSignaling
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_insight_signaling_fires() -> None:
    doc = _doc(
        "The load-bearing assumption here is doing the real work. That is the crux of the "
        "issue; we should pressure-test the claim and separate signal from noise."
    )
    result = InsightSignaling.extract(doc, "blog")
    assert result.score > 0.5
    rule_ids = {e.rule_id for e in result.spans}
    assert "INSIGHT_LOAD_BEARING" in rule_ids
    assert "INSIGHT_REAL_WORK" in rule_ids
    assert "INSIGHT_CRUX" in rule_ids
    assert "INSIGHT_PRESSURE_TEST" in rule_ids


def test_load_bearing_literal_is_not_flagged() -> None:
    # The engineering sense of "load-bearing" must stay quiet.
    doc = _doc("They removed a load-bearing wall during the 1962 remodel of the plant.")
    rule_ids = {e.rule_id for e in InsightSignaling.extract(doc, "blog").spans}
    assert "INSIGHT_LOAD_BEARING" not in rule_ids


@pytest.mark.parametrize(
    "text",
    [
        # Predicative: the commonest form of the metaphor, and the one with no rule through
        # v0.13 (INSIGHT_LOAD_BEARING matched only "load-bearing <noun>").
        "This distinction is load-bearing.",
        "That assumption is load bearing.",
        "That single word is really load-bearing.",
        "That caveat is load-bearing.",
        "Those two premises are load-bearing.",
        # The "doing the work" arm.
        "The comma is doing the load-bearing work here.",
    ],
)
def test_predicative_load_bearing_fires(text: str) -> None:
    rule_ids = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
    assert "INSIGHT_LOAD_BEARING" in rule_ids


@pytest.mark.parametrize(
    "text",
    [
        "The load-bearing wall is on the north side.",
        # Nouns with a literal construction sense are excluded from the predicative arm: in
        # carpentry the framing IS the load-bearing structure.
        "The framing is load-bearing in this wall assembly.",
        "We checked whether that detail is load-bearing before demolition.",
        "The point is load bearing on the south elevation.",
        # All three arms share one prose-noun list now; an ungated "doing load-bearing work"
        # arm and construction terms in the attributive list fired on literal site prose.
        "We replaced the load-bearing framing on the second floor.",
        "The contractor marked every load-bearing point on the plan.",
        "The crew is doing load-bearing work on the second floor.",
        "Contractors inspect a load-bearing beam before signing off.",
        "The column is load bearing.",
        # "part" is in the attributive noun list but deliberately not the predicative one:
        # this is ordinary engineering speech.
        "That part is load-bearing and must not be removed.",
    ],
)
def test_load_bearing_engineering_sense_stays_quiet(text: str) -> None:
    rule_ids = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
    assert "INSIGHT_LOAD_BEARING" not in rule_ids


def test_load_bearing_work_does_not_double_fire() -> None:
    # "doing the load-bearing work" must not also trip INSIGHT_REAL_WORK, which requires
    # real/heavy/actual. One construction, one span.
    spans = InsightSignaling.extract(
        _doc("The hedge is doing the load-bearing work."), "blog"
    ).spans
    assert len(spans) == 1
    assert spans[0].rule_id == "INSIGHT_LOAD_BEARING"


def test_structural_metaphor_fires() -> None:
    # The exact sentence a human reader caught (Summitward finance-books guide) + the noun-of-noun
    # form. See INSIGHT_STRUCTURAL_COPULA / INSIGHT_STRUCTURAL_METAPHOR.
    copula = {
        e.rule_id
        for e in InsightSignaling.extract(
            _doc("The spine is the same evidence behind Summitward."), "blog"
        ).spans
    }
    assert "INSIGHT_STRUCTURAL_COPULA" in copula
    metaphor = {
        e.rule_id
        for e in InsightSignaling.extract(
            _doc("The backbone of the argument carries the piece."), "blog"
        ).spans
    }
    assert "INSIGHT_STRUCTURAL_METAPHOR" in metaphor


def test_structural_metaphor_fix_does_not_fire() -> None:
    # Regression: the applied fix ("built on the same evidence") must stay clean.
    rule_ids = {
        e.rule_id
        for e in InsightSignaling.extract(
            _doc("The list is built on the same evidence behind Summitward."), "blog"
        ).spans
    }
    assert not any(r.startswith("INSIGHT_STRUCTURAL") for r in rule_ids)


def test_structural_metaphor_literals_are_not_flagged() -> None:
    # Literal senses of the metaphor nouns (medical, networking, construction, software, book) must
    # never fire. This is the real guard for this rule class: there are no literal negatives in the
    # eval JSONL, so these unit tests are the gate.
    literals = [
        "A herniated disc in the lumbar spine caused the pain.",
        "The backbone network handles routing between data centers.",
        "Scaffolding around the building came down in May.",
        "React scaffolding generates boilerplate components.",
        "The spine of the book is cracked after years of use.",
        "The spine is a column of 33 vertebrae.",
        "The backbone is a fiber-optic link to the coast.",
    ]
    for text in literals:
        rule_ids = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
        assert not any(r.startswith("INSIGHT_STRUCTURAL") for r in rule_ids), text


def test_bare_throughline_is_broad_only() -> None:
    text = "The through-line here is grief."
    off = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
    on = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog", broad=True).spans}
    assert "INSIGHT_BROAD_THROUGHLINE" not in off
    assert "INSIGHT_BROAD_THROUGHLINE" in on


def test_not_nothing_fires_and_lands_cleanly_is_broad() -> None:
    ids = {e.rule_id for e in InsightSignaling.extract(_doc("It's not nothing."), "blog").spans}
    assert "INSIGHT_NOT_NOTHING" in ids
    text = "The argument lands cleanly."
    off = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
    on = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog", broad=True).spans}
    assert "INSIGHT_BROAD_LANDS_CLEANLY" not in off
    assert "INSIGHT_BROAD_LANDS_CLEANLY" in on


@pytest.mark.parametrize(
    "text",
    [
        # The reader-flagged essay sentences (2026-10).
        "Markets sit in the middle layer. They earn their place by serving the ends.",
        "An intervention earns its place by beating a feasible alternative.",
        "## Make active bets earn their place",
        "Every feature must earn its place.",
        "When a picture earns its place, draw it.",
        "BOXX earns a place in a cash-heavy portfolio when rates are high.",
        "The tool has earned a place in my workflow.",
    ],
)
def test_earns_its_place_fires(text: str) -> None:
    spans = [
        e
        for e in InsightSignaling.extract(_doc(text), "blog").spans
        if e.rule_id == "INSIGHT_EARNS_ITS_PLACE"
    ]
    assert len(spans) == 1


EARN_PLACE_LITERALS = [
    "He earned his place in the starting eleven.",
    "Young players have to earn their place in the squad.",
    "The club earned its place in the final by beating Leeds.",
    "The novel earned its place in history.",
    "The dog earns its keep on the farm.",
    "She earned a place at Oxford.",
    "Coaches make them earn their place.",
]


@pytest.mark.parametrize("text", EARN_PLACE_LITERALS)
def test_earns_its_place_literal_sense_stays_quiet(text: str) -> None:
    rule_ids = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog").spans}
    assert "INSIGHT_EARNS_ITS_PLACE" not in rule_ids


@pytest.mark.parametrize("text", [t for t in EARN_PLACE_LITERALS if "his place" not in t])
def test_bare_earn_place_is_broad_only(text: str) -> None:
    on = {e.rule_id for e in InsightSignaling.extract(_doc(text), "blog", broad=True).spans}
    assert "INSIGHT_BROAD_EARN_PLACE" in on


def test_earns_its_place_is_charged_once_under_broad() -> None:
    doc = _doc(
        "An intervention earns its place by beating a feasible alternative. Make active bets "
        "earn their place. The fund has earned a place in my portfolio."
    )
    spans = [e for e in InsightSignaling.extract(doc, "blog", broad=True).spans if "earn" in e.span]
    assert [e.rule_id for e in spans] == ["INSIGHT_EARNS_ITS_PLACE"] * 3


def test_insight_signaling_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert InsightSignaling.extract(doc, "blog").score == 0.0


def test_insight_offsets_round_trip() -> None:
    doc = _doc(
        "The operative word is leverage, and that is doing the real work in this sentence. "
        "Here is the uncomfortable truth: the crux of the matter is elsewhere. Every chart "
        "must earn its place, and the dog earns its keep."
    )
    for e in InsightSignaling.extract(doc, "blog", broad=True).spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span


def test_broad_tier_off_by_default() -> None:
    doc = _doc("The steelman of the argument, from first principles, is directionally correct.")
    # Core-only extraction ignores the broad-tier jargon.
    assert InsightSignaling.extract(doc, "blog").score == 0.0
    rule_ids = {e.rule_id for e in InsightSignaling.extract(doc, "blog").spans}
    assert not any(r.startswith("INSIGHT_BROAD_") for r in rule_ids)


def test_broad_flag_enables_broad_rules() -> None:
    text = "The steelman of the argument, from first principles, is directionally correct."
    off = SlopScorer(settings=Settings()).scan_text(text)
    on = SlopScorer(settings=Settings(broad_rules=True)).scan_text(text)
    assert off.dimensions.insight_signaling == 0.0
    assert on.dimensions.insight_signaling > 0.0
    broad_ids = {e.rule_id for e in on.evidence if e.rule_id.startswith("INSIGHT_BROAD_")}
    assert {"INSIGHT_BROAD_STEELMAN", "INSIGHT_BROAD_FIRST_PRINCIPLES"} <= broad_ids


def test_disabled_dimension_suppresses_broad_rescore() -> None:
    # A disabled insight_signaling dimension must stay disabled even with --broad.
    text = "The steelman is directionally correct from first principles."
    settings = Settings(broad_rules=True, disabled_dimensions=frozenset({"insight_signaling"}))
    report = SlopScorer(settings=settings).scan_text(text)
    assert report.dimensions.insight_signaling == 0.0
    assert not any(e.rule_id.startswith("INSIGHT_") for e in report.evidence)
