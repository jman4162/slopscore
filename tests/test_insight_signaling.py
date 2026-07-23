"""Insight-signaling / pseudo-profundity dimension and its opt-in broad tier."""

from __future__ import annotations

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


def test_insight_signaling_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert InsightSignaling.extract(doc, "blog").score == 0.0


def test_insight_offsets_round_trip() -> None:
    doc = _doc(
        "The operative word is leverage, and that is doing the real work in this sentence. "
        "Here is the uncomfortable truth: the crux of the matter is elsewhere."
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
