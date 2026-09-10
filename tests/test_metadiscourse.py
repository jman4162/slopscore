"""Metadiscourse dimension: writing that refers to the text rather than to its subject."""

from __future__ import annotations

import pytest

from slopscore import scan_text
from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.metadiscourse import MetadiscoursePack as Metadiscourse
from slopscore.ingest import from_string
from slopscore.models import Dimension
from slopscore.scoring.weights import CORROBORATING_DIMENSIONS


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


# --- terminal recap -------------------------------------------------------------------------
#
# The spec's own report mock-up lists "Conclusion: formulaic summary without new information".
# The frame word alone must not convict: what distinguishes a recap is that it restates.

_BODY = (
    "Japan peaked at 38915 on the Nikkei in December 1989 and did not regain that level "
    "until 2024. Russia nationalized the Saint Petersburg exchange in 1917 and China closed "
    "Shanghai in 1949. The Dimson Marsh Staunton dataset covers 35 markets from 1900 through "
    "2024. Pastor and Stambaugh reported higher long-horizon variance in the Journal of "
    "Finance in 2012. The 1970s produced 7.4 percent annual inflation in the United States. "
) * 8


def test_terminal_recap_fires_when_the_closer_restates() -> None:
    doc = _doc(
        _BODY
        + "\n\nIn summary, Japan took 34 years to recover from its 1989 peak, Russia and China "
        "nationalized their exchanges in 1917 and 1949, and Pastor and Stambaugh reported "
        "higher long-horizon variance. The Dimson Marsh Staunton dataset covers 35 markets "
        "and the 1970s produced 7.4 percent inflation in the United States."
    )
    result = Metadiscourse.extract(doc, "blog")
    recap = [e for e in result.spans if e.rule_id == "META_TERMINAL_RECAP"]
    assert len(recap) == 1
    assert "already appear above" in recap[0].explanation
    assert result.score > 0.4


def test_terminal_recap_quiet_when_the_closer_adds_something() -> None:
    # Same frame word, new content. "In summary," is not itself the defect.
    doc = _doc(
        _BODY + "\n\nIn summary, my own allocation is 82 percent equities held through two funds, "
        "rebalanced each January, and I expect to hold that through retirement in 2047 "
        "regardless of what any of these datasets say next."
    )
    assert not any(
        e.rule_id == "META_TERMINAL_RECAP" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_terminal_recap_needs_a_body_to_restate() -> None:
    # A short note that opens with "In summary," has nothing to have restated.
    doc = _doc("The fund returned 8 percent.\n\nIn summary, the fund returned 8 percent in 2024.")
    assert not any(
        e.rule_id == "META_TERMINAL_RECAP" for e in Metadiscourse.extract(doc, "blog").spans
    )


_UNRELATED = (
    "The parser wraps the tokenizer and exposes a stable API. Rainfall in Manaus averaged 2300 "
    "millimetres in 1998. The kiln fired at 1280 degrees for nine hours. "
) * 8


def test_terminal_recap_survives_a_longer_and_more_varied_body() -> None:
    # An earlier version of this test repeated the SAME body, which cannot move a similarity
    # measure at all, and so passed vacuously while the underlying cosine fell 0.219 -> 0.071 on
    # a body extended with unrelated content. Containment is what actually holds this property.
    closer = (
        "\n\nIn summary, Japan took 34 years to recover from its 1989 peak and Russia and "
        "China nationalized their exchanges in 1917 and 1949. The Dimson Marsh Staunton "
        "dataset covers 35 markets from 1900 through 2024."
    )
    short = _doc(_BODY + closer)
    long = _doc(_BODY + _UNRELATED * 3 + closer)
    assert long.word_count > 2 * short.word_count
    for doc in (short, long):
        spans = Metadiscourse.extract(doc, "blog").spans
        assert any(e.rule_id == "META_TERMINAL_RECAP" for e in spans)


def test_quoted_markers_are_not_the_author_s_voice() -> None:
    # A style guide discussing the construction, and a character using it, are both quoting.
    # Without this the repo's own PROFILE_NOTES.md scored 0.22 for listing rule examples.
    for text in (
        'The academic profile softens signposting such as "As noted above" and "TL;DR".',
        '"To be clear," she said, "I never agreed to any of that."',
    ):
        assert not any(r.startswith("META_") for r in _core_ids(text))


def test_unquoted_markers_still_fire_alongside_a_quotation() -> None:
    # The originating catch opens on a quoted claim; the metadiscourse is the prose around it.
    text = (
        '"Some stock markets have gone to zero" is a true but loose claim. Precision matters '
        "here because the counter-argument will not survive sloppy phrasing. The defensible "
        "version is the one that separates the cases."
    )
    ids = _core_ids(text)
    assert {"META_PROSE_ATTRIBUTE_SUBJECT", "META_PROSE_CORRECTION"} <= ids


# --- guards for the code-review findings --------------------------------------------------------


def test_metadiscourse_does_not_unlock_the_weak_dimensions() -> None:
    # The concentration term is length-invariant and clears the gate on its own. Left in the
    # derived CORROBORATING_DIMENSIONS, three meta sentences took this document from 46.4 "mild"
    # to 97.6 "severe" by counting lexical_markers, parallelism and copula_avoidance at full
    # weight document-wide.
    base = (
        "The system is robust and the design is seamless. Teams leverage the layer to showcase "
        "results. The module serves as a bridge and functions as a relay. It is not a toy, it "
        "is a platform. The layer constitutes a boundary and represents a contract. "
    ) * 14
    run = (
        "As noted above, the framing here is what actually matters most of all. To be clear, "
        "the point is not really about any of that at all. In short: what this means is that "
        "the phrasing is doing the work."
    )
    without = scan_text(base)
    with_run = scan_text(base + run)
    assert with_run.dimensions.metadiscourse > 0.5
    # It still moves the score, by its own weight, but must not flip the label two steps.
    assert with_run.score.slop_score > without.score.slop_score
    assert with_run.score.slop_score - without.score.slop_score < 30
    assert Dimension.metadiscourse not in CORROBORATING_DIMENSIONS


def test_run_length_survives_an_abbreviation() -> None:
    # A naive (?<=[.!?])\s+ resplit of the span text counts "e.g." as a sentence end, so the
    # score disagreed with the count the evidence reports.
    plain = (
        "As noted above, the phrasing here is what actually matters most. To be clear, the "
        "point here is not really about that at all. In short: what this means is that the "
        "framing is doing the work."
    )
    with_abbrev = plain.replace("about that at all", "about that at all, e.g. the rest")
    scores = []
    for text in (plain, with_abbrev):
        result = Metadiscourse.extract(_doc(text), "blog")
        run = [e for e in result.spans if e.rule_id == "META_RUN_OF_META_SENTENCES"]
        assert run and run[0].explanation.startswith("3 consecutive")
        scores.append(result.score)
    assert scores[0] == scores[1]


def test_severity_override_reaches_the_concentration_term() -> None:
    # CLAUDE.md: severity overrides apply before by_dim. For a rule whose score is not derived
    # from SEVERITY_WEIGHT that has to be wired explicitly.
    text = (
        "Japan peaked at 38915 on the Nikkei in December 1989. Russia nationalized the exchange "
        "in 1917. "
        * 40
        + "As noted above, the framing here is what actually matters most of all. To be clear, "
        "the point is not really about any of that at all. In short: what this means is that "
        "the phrasing is doing the work."
    )
    default = SlopScorer(settings=Settings()).scan_text(text)
    lowered = SlopScorer(
        settings=Settings(rule_severity={"META_RUN_OF_META_SENTENCES": "low"})
    ).scan_text(text)
    assert default.dimensions.metadiscourse == pytest.approx(0.55)
    assert lowered.dimensions.metadiscourse < default.dimensions.metadiscourse


def test_recap_span_is_not_also_charged_to_the_rate_term() -> None:
    doc = _doc(
        _BODY
        + "\n\nIn summary, Japan took 34 years to recover from its 1989 peak, Russia and China "
        "nationalized their exchanges in 1917 and 1949, and the Dimson Marsh Staunton dataset "
        "covers 35 markets from 1900 through 2024."
    )
    spans = Metadiscourse.extract(doc, "blog").spans
    recap = [e for e in spans if e.rule_id == "META_TERMINAL_RECAP"]
    assert recap
    # Dropping the recap span must not leave its severity behind in the rate term.
    without = [e for e in spans if e.rule_id != "META_TERMINAL_RECAP"]
    assert Metadiscourse.score_spans(doc, "blog", without) < Metadiscourse.score_spans(
        doc, "blog", spans
    )


@pytest.mark.parametrize(
    "marker_sentence",
    [
        "In plain English, the whole thing simply does not work at all.",
        "There are three things to notice about the way this is written.",
        "The TL;DR is that the argument does not really hold together here.",
    ],
)
def test_markers_that_look_concrete_still_count_toward_a_run(marker_sentence: str) -> None:
    # Each of these contains its own apparent evidence ("English" as a proper noun, "three" as a
    # number, "TL"/"DR" as acronyms), so before the marker text was excised they could never
    # form a run and their lexicon entries were dead code.
    doc = _doc(marker_sentence + " " + marker_sentence)
    assert any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_a_short_sentence_does_not_sever_a_run() -> None:
    # A sentence too short to judge says nothing about the passage around it; treating it as
    # concrete meant a denser passage of prose-about-the-prose scored lower than a sparser one.
    doc = _doc(
        "In this section we will discuss the whole argument at length. To be clear, it fails. "
        "As noted above, the framing is what actually matters most here."
    )
    assert any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


@pytest.mark.parametrize(
    "closer",
    [
        "Overall performance across the markets improved after 1949 in every country measured.",
        "Takeaways for the dataset were presented at the 2019 conference in Lisbon that autumn.",
    ],
)
def test_bare_overall_is_not_an_announced_closer(closer: str) -> None:
    # META_BROAD_OVERALL_CLOSER requires "Overall," and is broad-only because bare "Overall" is
    # ordinary English. The default-scoring recap detector must not be a way around that.
    doc = _doc(_BODY + "\n\n" + closer)
    assert not any(
        e.rule_id == "META_TERMINAL_RECAP" for e in Metadiscourse.extract(doc, "blog").spans
    )
