"""Metadiscourse dimension: writing that refers to the text rather than to its subject."""

from __future__ import annotations

import pytest

from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.phrase_packs import Metadiscourse
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def _core_ids(text: str) -> set[str]:
    return {e.rule_id for e in Metadiscourse.extract(_doc(text), "blog").spans}


def test_metadiscourse_fires() -> None:
    doc = _doc(
        "In this section, we will discuss the background. To be clear, the defensible version "
        "is narrower. As noted above, two things to notice. Put simply: the key takeaway is "
        "that precision matters."
    )
    result = Metadiscourse.extract(doc, "blog")
    assert result.score > 0.5
    assert "META_SECTION_PLAN" in {e.rule_id for e in result.spans}


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        # The originating catch: three sentences of prose-about-the-prose, none of which any
        # dimension scored through v0.13.
        ("The defensible version is narrower.", "META_PROSE_CORRECTION"),
        ("Precision matters here because the phrasing is loose.", "META_PROSE_ATTRIBUTE_SUBJECT"),
        ("That distinction is important.", "META_PROSE_ATTRIBUTE_SUBJECT"),
        ("In this section, we will discuss the background.", "META_SECTION_PLAN"),
        ("This section would speculate on potential developments.", "META_SECTION_PLAN"),
        ("As we saw above, the premium is compensation.", "META_ENDOPHORIC_BACKREF"),
        ("Having established that, we can turn to Germany.", "META_TRANSITION_ESTABLISHED"),
        ("The key takeaway is that time is not a hedge.", "META_TAKEAWAY"),
        ("Two things to notice.", "META_ENUMERATION_ANNOUNCE"),
        # The colon form: FORMULAIC_SIMPLY_PUT requires a trailing comma and misses it entirely.
        ("Put simply: the claim needs separating.", "META_RESTATEMENT_COLON"),
        ("In plain English: you lose money.", "META_PLAIN_ENGLISH"),
        ("To be clear, this is not a bear market.", "META_CLARIFY_FRAME"),
    ],
)
def test_previously_uncovered_constructions_fire(text: str, rule_id: str) -> None:
    assert rule_id in _core_ids(text)


@pytest.mark.parametrize(
    "text",
    [
        # Object-level uses of the same nouns: the subject is prose, the predicate is not.
        "The framing matters to the plaintiff more than to the court.",
        "The wording is important for the contract.",
        "He gave a clear and precise account of the 1948 currency reform.",
        "I want to be clear about the dates before we file.",
        "The purpose of the study was to measure inflation between 1971 and 1981.",
        "She noted above-average rainfall in March.",
        "Two things arrived in the mail today.",
        "The key was in the drawer.",
        "Overall performance improved 12% in the third quarter.",
        # MULTILINE means ^ matches every line start, so email sign-offs are the classic trap
        # (the same one CANDOR_ADVERB_PARENTHETICAL documents).
        "Thanks for the review.\nSincerely,\nJ. Hodge",
        "Let me know what you think.\nRegards,\nSam",
        # An ESL / simple-English restatement over a concrete fact: the clarity device this
        # dimension must not punish. The bare code glosses live in the --broad tier.
        "The bond lost 40% of its value. That is to say, 40 cents of every dollar was gone.",
    ],
)
def test_ordinary_prose_is_not_flagged(text: str) -> None:
    assert not any(r.startswith("META_") for r in _core_ids(text))


def test_metadiscourse_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert Metadiscourse.extract(doc, "blog").score == 0.0


def test_metadiscourse_offsets_round_trip() -> None:
    # broad=True so the lookahead- and lookbehind-bearing patterns are covered too.
    doc = _doc(
        "In this section, we will explain. To be clear, the accurate phrasing is this. "
        "As noted above, put simply: overall, that is to say, the point here is that "
        "the key takeaway is precision."
    )
    for e in Metadiscourse.extract(doc, "blog", broad=True).spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span


def test_no_double_charge_with_formulaic_or_candor() -> None:
    # Three constructions this dimension deliberately leaves to their existing owners:
    # FORMULAIC_SIMPLY_PUT (comma form), FORMULAIC_MAKE_NO_MISTAKE, CANDOR_HONEST_ABSTRACT_NOUN.
    for text in (
        "In other words, the risk does not go away.",
        "Let me be clear: the risk does not go away.",
        "The honest version is that we do not know.",
        # FORMULAIC_COMPREHENSIVE_GUIDE owns "in this <guide|article|post|blog>".
        "In this article, we will explore the evidence.",
    ):
        assert not any(r.startswith("META_") for r in _core_ids(text))


def test_code_glosses_are_broad_only() -> None:
    # "Overall," must be clause-initial, so it needs its own sentence here.
    text = "That is to say, the point here is that it was fine. Overall, the year was quiet."
    doc = _doc(text)
    assert Metadiscourse.extract(doc, "blog").score == 0.0
    broad_ids = {e.rule_id for e in Metadiscourse.extract(doc, "blog", broad=True).spans}
    assert {
        "META_BROAD_CODE_GLOSS",
        "META_BROAD_BARE_RESTATEMENT",
        "META_BROAD_OVERALL_CLOSER",
    } <= broad_ids


def test_broad_flag_enables_metadiscourse_broad() -> None:
    text = "That is to say, the point here is that the number moved."
    off = SlopScorer(settings=Settings()).scan_text(text)
    on = SlopScorer(settings=Settings(broad_rules=True)).scan_text(text)
    assert off.dimensions.metadiscourse == 0.0
    assert on.dimensions.metadiscourse > 0.0
    assert "META_BROAD_CODE_GLOSS" in {e.rule_id for e in on.evidence}


def test_disabled_dimension_suppresses_broad_rescore() -> None:
    settings = Settings(broad_rules=True, disabled_dimensions=frozenset({"metadiscourse"}))
    report = SlopScorer(settings=settings).scan_text(
        "In this section, we will explain. To be clear, that is to say, the point here is that."
    )
    assert report.dimensions.metadiscourse == 0.0
    assert not any(e.rule_id.startswith("META_") for e in report.evidence)
