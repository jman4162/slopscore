"""Phrase-pack dimensions: significance inflation and weasel/over-attribution."""

from __future__ import annotations

from slopscore.core import build_document
from slopscore.features.phrase_packs import SignificanceInflation, WeaselAttribution
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_significance_inflation_fires() -> None:
    doc = _doc(
        "The festival stands as a testament to local culture and plays a pivotal role "
        "in the region, marking a significant moment in its history."
    )
    result = SignificanceInflation.extract(doc, "blog")
    assert result.score > 0.5
    rule_ids = {e.rule_id for e in result.spans}
    assert "SIGNIF_STANDS_AS_TESTAMENT" in rule_ids
    assert "SIGNIF_PIVOTAL_ROLE" in rule_ids


def test_weasel_attribution_fires() -> None:
    doc = _doc(
        "Experts argue the policy works. Studies show broad support. The company "
        "maintains an active social media presence and was featured in Wired and other outlets."
    )
    result = WeaselAttribution.extract(doc, "blog")
    rule_ids = {e.rule_id for e in result.spans}
    assert "WEASEL_EXPERTS_ARGUE" in rule_ids
    assert "OVERATTR_SOCIAL_PRESENCE" in rule_ids


def test_phrase_packs_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert SignificanceInflation.extract(doc, "blog").score == 0.0
    assert WeaselAttribution.extract(doc, "blog").score == 0.0


def test_phrase_pack_offsets_round_trip() -> None:
    doc = _doc("It stands as a testament to progress, experts argue.")
    for feature in (SignificanceInflation, WeaselAttribution):
        for e in feature.extract(doc, "blog").spans:
            assert doc.original_text[e.start_char : e.end_char] == e.span
