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
    assert "run of 3 consecutive sentences" in run[0].explanation
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
        assert run and run[0].explanation.startswith("Starts a run of 3")
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


def test_headings_and_list_items_break_a_run() -> None:
    # Four sections each opening with a signpost are four signposts, not a four-sentence run.
    # Treating non-prose as transparent produced one high-severity finding on ordinary IMRaD
    # structure, in the genre the 0.5 profile multiplier exists to protect.
    md = "".join(
        f"## Section {i}\n\nIn this section we will describe the approach we have taken.\n\n"
        for i in (1, 2, 3, 4)
    )
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES"
        for e in Metadiscourse.extract(_doc(md), "blog").spans
    )


def test_a_run_never_spans_intervening_content() -> None:
    # The span used to cover the bullets between two signposts, so its text visibly contained
    # numbers while its own explanation said none were present.
    doc = _doc(
        "## Approach\n\nIn this section we will describe the approach we have taken.\n\n"
        "- Nikkei 38915 in 1989\n- Russia 1917\n- China 1949\n\n"
        "As noted above, the framing here is what actually matters most of all.\n"
    )
    for e in Metadiscourse.extract(doc, "blog").spans:
        if e.rule_id == "META_RUN_OF_META_SENTENCES":
            assert "38915" not in e.span and "Russia" not in e.span


def test_stacked_markers_do_not_break_a_run() -> None:
    # Only the first matching marker used to be excised, so the leftover markers' text ("English"
    # as a proper noun) read as evidence and the densest meta sentence broke the run.
    dense = "As noted above, in plain English, three things stand out about the framing here."
    plain = "To be clear, the point here is not really about any of that at all."
    doc = _doc(dense + " " + plain)
    assert any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_run_span_is_anchored_not_sprawling() -> None:
    # report/html.py picks the longest span at each offset and skips the ones inside it, so a
    # multi-sentence finding swallowed every phrase-level highlight in the passage. A short
    # anchor also keeps report/baseline.py fingerprints stable across unrelated edits.
    text = (
        "As noted above, the framing here is what actually matters most. To be clear, the point "
        "here is not really about that at all. In short: what this means is that the phrasing "
        "is doing the work."
    )
    spans = Metadiscourse.extract(_doc(text), "blog").spans
    run = next(e for e in spans if e.rule_id == "META_RUN_OF_META_SENTENCES")
    assert run.span.count(".") == 1
    assert "run of 3 consecutive sentences" in run.explanation
    # The phrase-level findings inside the run survive alongside it.
    assert {"META_ENDOPHORIC_BACKREF", "META_CLARIFY_FRAME"} <= {e.rule_id for e in spans}


def test_severity_override_scales_the_run_both_ways() -> None:
    text = (
        "Japan peaked at 38915 on the Nikkei in December 1989. Russia nationalized the exchange "
        "in 1917. "
        * 40
        + "As noted above, the framing here is what actually matters most of all. To be clear, "
        "the point is not really about any of that at all. In short: what this means is that "
        "the phrasing is doing the work."
    )
    base = SlopScorer(settings=Settings()).scan_text(text).dimensions.metadiscourse
    lower = (
        SlopScorer(settings=Settings(rule_severity={"META_RUN_OF_META_SENTENCES": "low"}))
        .scan_text(text)
        .dimensions.metadiscourse
    )
    higher = (
        SlopScorer(settings=Settings(rule_severity={"META_RUN_OF_META_SENTENCES": "high"}))
        .scan_text(text)
        .dimensions.metadiscourse
    )
    assert lower < base < higher


def test_a_name_after_a_comma_terminated_marker_still_counts_as_evidence() -> None:
    # _PROPER matches on (?<=[a-z,;:]\s) -- exactly one space. Replacing "In short," with a bare
    # space (or with ", " and no whitespace collapse) hid the name that followed, so the sentence
    # read evidence-free and a run fired whose explanation said "none carrying a name" while its
    # own span said "Tokyo".
    doc = _doc(
        "In short, Tokyo remains the largest market. To be clear, Sony still dominates the "
        "sector. In other words, Honda has recovered from the slump."
    )
    result = Metadiscourse.extract(doc, "blog")
    assert not any(e.rule_id == "META_RUN_OF_META_SENTENCES" for e in result.spans)
    assert result.score == 0.0


def test_the_run_term_honors_skip_quoted() -> None:
    # The pack sets skip_quoted=True; the run term bypassed it, so a critique quoting three
    # assistant sentences was charged for writing them. The marker's own offsets are tested,
    # not the sentence's: pysbd keeps 'He said "In this section we will..."' as one sentence,
    # which contains the quotation rather than sitting inside it.
    doc = _doc(
        'He kept saying things like "In this section we will explore the housing question in '
        'detail." Then "As noted above, the framing matters here quite a lot." Then "To be '
        'clear, that distinction is important and worth stating." I stopped reading.'
    )
    result = Metadiscourse.extract(doc, "blog")
    assert not any(e.rule_id == "META_RUN_OF_META_SENTENCES" for e in result.spans)
    assert result.score == 0.0


def test_skipped_sentences_cannot_bridge_a_run_without_limit() -> None:
    # "skip" is tolerated inside a run so a short factless sentence does not sever it, but past
    # the budget the run is not "consecutive" in any sense its explanation could claim.
    doc = _doc(
        "In this section we will explore the topic in some detail. Rates fell. Prices rose. "
        "Output grew. As noted above, the framing matters here quite a lot."
    )
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_paragraph_breaks_end_a_run_on_plain_text() -> None:
    # Document.in_block_kind returns False whenever doc.blocks is empty, which is every
    # non-Markdown source: plain text, stdin, extracted code comments, web articles. The
    # heading/list guard was therefore a no-op on all of them, and three signposts in three
    # separate paragraphs read as one "run of 3 consecutive sentences".
    doc = _doc(
        "In this section we will describe the approach we have taken.\n\n"
        "As noted above, the framing here is what actually matters most of all.\n\n"
        "To be clear, the point is not really about any of that at all.\n"
    )
    assert doc.blocks == []
    assert len(doc.paragraphs) == 3
    assert not any(
        e.rule_id == "META_RUN_OF_META_SENTENCES" for e in Metadiscourse.extract(doc, "blog").spans
    )


def test_a_run_of_borrowed_markers_alone_does_not_score() -> None:
    # The marker lexicon is a superset of this dimension's rules, so a run can be built entirely
    # from phrases whose scoring rule lives in formulaic_structure. Charging for those billed one
    # set of phrases to two weighted dimensions at once.
    doc = _doc(
        "In summary, the whole argument does not really hold together at all. It is worth noting "
        "that the point here is not about any of that. In other words, the thing being described "
        "is not what was claimed."
    )
    result = Metadiscourse.extract(doc, "blog")
    assert not any(
        e.rule_id.startswith("META_") and e.rule_id != "META_RUN_OF_META_SENTENCES"
        for e in result.spans
    )
    assert result.score == 0.0


def test_a_quoted_marker_is_judged_as_if_absent() -> None:
    # The contract is that a quoted marker is not the author's voice, so the sentence should
    # classify exactly as the same sentence without it: short and factless skips, anything
    # longer breaks. It used to hard-break either way, so a short quotation dropped into a
    # genuine run severed it and denser prose-about-the-prose scored lower.
    from slopscore.core import build_document
    from slopscore.features.metadiscourse import _classify
    from slopscore.ingest import from_string

    for quoted, plain in (
        ('He said "to be clear."', "He said nothing."),
        (
            'He said "to be clear," and then he left the room.',
            "He said nothing and then he left the room.",
        ),
    ):
        qd, pd = build_document(from_string(quoted)), build_document(from_string(plain))
        assert _classify(qd, qd.sentences[0]) == _classify(pd, pd.sentences[0])


@pytest.mark.parametrize(
    "text",
    [
        "Precision matters in practice.",
        "That distinction is important in this debate.",
        "The phrasing matters at scale.",
    ],
)
def test_prose_attribute_subject_survives_in_at_with(text: str) -> None:
    # The lookahead blocked in/at/with, which follow the metadiscourse use at least as often as
    # the object-level one it targets.
    assert "META_PROSE_ATTRIBUTE_SUBJECT" in _core_ids(text)


# --- review round 6 --------------------------------------------------------------------------

_RUN_OF_THREE = (
    "To be clear, the framing here is what actually matters most of all. In short, the point "
    "is not really about any of that at all either. Simply put, none of this is about the "
    "subject at hand whatsoever."
)


def _meta(report):  # type: ignore[no-untyped-def]
    return [(e.rule_id, e.severity.value) for e in report.findings if e.rule_id.startswith("META_")]


def test_disabling_the_licensing_rule_removes_the_run() -> None:
    # The scorer filters by rule id AFTER extraction, so the run span used to survive the removal
    # of the one META_ rule that licensed it: a medium finding, metadiscourse 0.0, and --fail-on
    # medium exiting non-zero for a rule the user had turned off.
    on = SlopScorer(settings=Settings()).scan_text(_RUN_OF_THREE)
    assert ("META_RUN_OF_META_SENTENCES", "medium") in _meta(on)
    assert on.dimensions.metadiscourse == 0.55

    off = SlopScorer(settings=Settings(disabled_rules=frozenset({"META_CLARIFY_FRAME"}))).scan_text(
        _RUN_OF_THREE
    )
    assert _meta(off) == []
    assert off.dimensions.metadiscourse == 0.0


def test_suppressing_the_licensing_rule_removes_the_run() -> None:
    text = "<!-- slopscore-disable-file META_CLARIFY_FRAME -->\n" + _RUN_OF_THREE
    report = scan_text(text)
    assert _meta(report) == []
    assert report.dimensions.metadiscourse == 0.0


def test_a_wrapped_run_scores_the_same_as_flat() -> None:
    # Fragments are re-joined before classification. Before, a wrapped meta sentence became a
    # first fragment (skipped) plus a marker-less tail (a break), so wrapping switched the run
    # term off: 0.55 flat became 0.094 wrapped on a 1,066-word plain-text file.
    import textwrap

    fact = "The bridge in Leeds opened in 1932 after three years of work by two firms. " * 40
    flat = fact + "\n\n" + _RUN_OF_THREE
    wrapped = (
        "\n".join(textwrap.wrap(fact, 60)) + "\n\n" + "\n".join(textwrap.wrap(_RUN_OF_THREE, 60))
    )
    a, b = scan_text(flat), scan_text(wrapped)
    assert a.dimensions.metadiscourse == b.dimensions.metadiscourse == 0.55
    assert _meta(a) == _meta(b)


def test_a_marker_a_wrap_put_at_line_start_is_still_mid_sentence() -> None:
    # "and,\nin short, nothing changed" is one sentence with a parenthetical, not a meta sentence.
    # Matched fragment by fragment, the lexicon's \A saw "in short," at the head of a line.
    text = (
        "The team reviewed the two lists and the schedule and,\n"
        "in short, nothing about the plan had changed at all by then.\n"
        "To be clear, the deadline had not moved at all for anyone."
    )
    wrapped, flat = scan_text(text), scan_text(" ".join(text.split()))
    assert _meta(wrapped) == _meta(flat) == [("META_CLARIFY_FRAME", "low")]


def test_a_fact_bearing_line_without_terminal_punctuation_breaks_a_run() -> None:
    # The evidence test runs before any length or termination test: a caption, a list line, or
    # a URL line with no period is still a fact, and a fact ends a run.
    text = (
        "To be clear, the framing here is what actually matters most of all.\n"
        "- Revenue: 4.2 million dollars in 2021 (Leeds filing)\n"
        "In short, the point is not really about any of that at all either."
    )
    report = scan_text(text)
    assert ("META_RUN_OF_META_SENTENCES", "medium") not in _meta(report)


_FACT = "The bridge in Leeds opened in 1932 after three years of work by two firms."


@pytest.mark.parametrize(
    "text",
    [
        "Key points:\nTo be clear, the point is not really about any of that at all.",
        _FACT + " \nTo be clear, the point is not really about any of that at all.",
        "\nTo be clear, the point is not really about any of that at all. " + _FACT,
        _FACT + "\n \nTo be clear, the point is not about any of that at all.",
        'He said "no." To be clear, the point is not about any of that at all.',
    ],
    ids=["colon-line", "dot-space-newline", "leading-blank", "blank-with-space", "after-quote"],
)
def test_clause_anchor_accepts_every_sentence_boundary(text: str) -> None:
    assert ("META_CLARIFY_FRAME", "low") in _meta(scan_text(text))


def test_clause_anchor_refuses_a_hard_wrap() -> None:
    assert _meta(scan_text("and\nto be clear, the point is not about any of that at all.")) == []


def test_a_suppression_comment_does_not_exempt_the_paragraph_below_it(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # The Markdown ingester leaves "-->\nTo be clear," in front of a paragraph carrying a
    # suppression comment. Two defects hid the marker: the anchor did not accept "-->" as a
    # boundary, and, once fragments were re-joined, the rule id inside the comment counted as an
    # identifier that made the sentence "concrete".
    p = tmp_path / "doc.md"
    p.write_text(
        _FACT + "\n\n<!-- slopscore-disable-next-line LEXICAL_MARKERS -->\n"
        "To be clear, the point is not really about any of that at all.\n",
        encoding="utf-8",
    )
    assert ("META_CLARIFY_FRAME", "low") in _meta(SlopScorer().scan_file(p))


def test_marketing_profile_softens_metadiscourse() -> None:
    from slopscore.scoring.profiles import profile_multipliers

    assert profile_multipliers("marketing")[Dimension.metadiscourse] == 0.8
