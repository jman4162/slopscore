"""Metadiscourse dimension: writing that refers to the text rather than to its subject."""

from __future__ import annotations

import pytest

from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.metadiscourse import MetadiscoursePack as Metadiscourse
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


# --- the concentration term ---------------------------------------------------------------------
#
# The rate term alone cannot see this defect in long-form prose: the passage below saturates
# formulaic_structure at 1.0 at 123 words and scores 0.064 at 3,373, because per_hundred_words
# divides it away. These tests pin the length-invariant half.

_CATCH = (
    "A stock market going to zero is a true but loose claim. Precision matters here because "
    "the counter-argument will not survive sloppy phrasing. The defensible version is the one "
    "that separates the cases."
)
_CONCRETE = (
    "The Dimson Marsh Staunton dataset covers 35 markets from 1900 through 2024. Japan peaked "
    "at 38915 on the Nikkei in December 1989. Russia nationalized the Saint Petersburg exchange "
    "in 1917. The 1970s produced 7.4 percent annual inflation in the United States. "
)


def _buried(copies: int = 25):
    """The catch passage buried in `copies` blocks of concrete prose on either side."""
    return _doc(_CONCRETE * copies + _CATCH + " " + _CONCRETE * copies)


def test_run_of_meta_sentences_fires() -> None:
    result = Metadiscourse.extract(_doc(_CATCH), "blog")
    run = [e for e in result.spans if e.rule_id == "META_RUN_OF_META_SENTENCES"]
    assert len(run) == 1
    assert "3 consecutive sentences" in run[0].explanation
    # At 33 words the per-100-word rate term saturates on its own, so the dimension reads 1.0
    # here regardless of the run. The run's own contribution is isolated in the tests below,
    # where the document is long enough for the rate term to have decayed to noise.
    assert result.score == 1.0


def test_run_score_is_length_invariant() -> None:
    # The same three sentences buried in 100x the concrete prose must score the same. This is
    # the whole reason the term exists; a per-100-word rate would drop it to noise.
    small, large = _buried(25), _buried(50)
    assert small.word_count > 1500 and large.word_count > 3000
    small_score = Metadiscourse.extract(small, "blog").score
    large_score = Metadiscourse.extract(large, "blog").score
    # A run of three, scored the same at 1,700 words and at 3,400. The rate term alone would
    # have halved between them.
    assert small_score == pytest.approx(0.55)
    assert large_score == pytest.approx(0.55)


def test_isolated_meta_sentences_do_not_form_a_run() -> None:
    # One signpost per paragraph is ordinary writing, not the defect. Only consecutive
    # evidence-free meta sentences count.
    doc = _doc(
        "As noted above, the situation had not changed much at all by then. "
        + _CONCRETE
        + "To recap, the argument does not really depend on any of that. "
        + _CONCRETE
    )
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_meta_sentence_carrying_a_fact_is_exempt() -> None:
    # The fairness gate: a summary sentence that actually summarizes something is not the
    # defect, which is how ESL and simple-English writers use restatement scaffolding.
    doc = _doc(
        "In summary, Japan took 34 years to recover from its December 1989 peak. "
        "In other words, the Nikkei did not regain 38915 until 2024. "
        "As noted above, Russia and China went to zero in 1917 and 1949."
    )
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_score_spans_is_pure_over_surviving_spans() -> None:
    # The scorer drops suppressed spans and re-scores, so dropping the run span must drop the
    # concentration term with it.
    doc = _buried()
    result = Metadiscourse.extract(doc, "blog")
    assert Metadiscourse.score_spans(doc, "blog", result.spans) == result.score
    without_run = [e for e in result.spans if e.rule_id != "META_RUN_OF_META_SENTENCES"]
    assert Metadiscourse.score_spans(doc, "blog", without_run) < result.score


def test_run_detection_skips_headings_and_list_items() -> None:
    # A bulleted "Key takeaways:" label is structure_tells' business, not a run of prose.
    doc = _doc(
        "## In this section we will cover the argument\n\n"
        "- To be clear, the point here is not really about that at all\n"
        "- As noted above, the framing is what actually matters most here\n"
    )
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )
