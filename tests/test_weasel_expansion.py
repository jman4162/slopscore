"""Expanded weasel_attribution: impersonal-passive attribution, unearned certainty, hedge+vague
adjective (core, on by default), plus the --broad tier of bare quantifiers/hedges/intensifiers."""

from __future__ import annotations

from slopscore.config import Settings
from slopscore.core import SlopScorer, build_document
from slopscore.features.phrase_packs import WeaselAttribution, broad_packs
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def _core_ids(text: str) -> set[str]:
    return {e.rule_id for e in WeaselAttribution.extract(_doc(text), "blog").spans}


def test_impersonal_attribution_fires() -> None:
    ids = _core_ids(
        "It is widely believed that the reforms worked. Sources say the numbers held, "
        "though mistakes were made along the way."
    )
    assert "WEASEL_IT_IS_BELIEVED" in ids
    assert "WEASEL_SOURCES_SAY" in ids
    assert "WEASEL_PASSIVE_DODGE" in ids


def test_certainty_openers_fire() -> None:
    ids = _core_ids(
        "Clearly, the plan is sound. Needless to say, it is fair to say the rest follows."
    )
    assert "WEASEL_CERTAINTY_OPENER" in ids
    assert "WEASEL_GOES_WITHOUT_SAYING" in ids
    assert "WEASEL_SAFE_TO_SAY" in ids


def test_certainty_adverb_midsentence_is_not_flagged() -> None:
    # "clearly" inside a sentence is ordinary prose, not a certainty opener.
    ids = _core_ids("She clearly explained each step and obviously enjoyed the work.")
    assert "WEASEL_CERTAINTY_OPENER" not in ids


def test_hedged_adjective_fires() -> None:
    assert "WEASEL_HEDGED_ADJECTIVE" in _core_ids("The rollout was somewhat successful overall.")
    # A bare hedge with a concrete measure is not the tell and must stay quiet.
    assert "WEASEL_HEDGED_ADJECTIVE" not in _core_ids("Output rose somewhat, about 12 percent.")


def test_core_quiet_on_specific_prose() -> None:
    doc = _doc(
        "The bridge opened in 1937. Workers poured 389,000 cubic yards of concrete. "
        "Strauss fought the Navy for two years over the design."
    )
    assert WeaselAttribution.extract(doc, "blog").score == 0.0


def test_weasel_offsets_round_trip() -> None:
    doc = _doc("It is widely believed that it was decided that the plan was somewhat effective.")
    for e in WeaselAttribution.extract(doc, "blog", broad=True).spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span


def test_bare_words_are_broad_only() -> None:
    text = "There are many reasons and it may be very good; various people could possibly agree."
    off = SlopScorer(settings=Settings()).scan_text(text)
    on = SlopScorer(settings=Settings(broad_rules=True)).scan_text(text)
    assert off.dimensions.weasel_attribution == 0.0
    assert on.dimensions.weasel_attribution > 0.0
    broad_ids = {e.rule_id for e in on.evidence if e.rule_id.startswith("WEASEL_BROAD_")}
    assert {
        "WEASEL_BROAD_QUANTIFIER",
        "WEASEL_BROAD_HEDGE",
        "WEASEL_BROAD_INTENSIFIER",
    } <= broad_ids


def test_broad_excludes_human_signal_hedges() -> None:
    # perhaps/maybe/arguably/likely are POSITIVE human signals; the broad tier must not flag them.
    on = SlopScorer(settings=Settings(broad_rules=True)).scan_text(
        "Perhaps the result is arguably good and maybe likely to hold."
    )
    assert not any(e.rule_id.startswith("WEASEL_BROAD_") for e in on.evidence)


def test_broad_generalization_covers_both_packs() -> None:
    # The generalized --broad must re-score every broad-capable pack, not just insight_signaling.
    dims = {p.dimension.value for p in broad_packs()}
    assert {"weasel_attribution", "insight_signaling"} <= dims
    on = SlopScorer(settings=Settings(broad_rules=True))
    # weasel broad AND insight broad both active in the same run.
    assert on.scan_text("It may be very good.").dimensions.weasel_attribution > 0.0
    assert (
        on.scan_text(
            "The steelman, from first principles, is directionally correct."
        ).dimensions.insight_signaling
        > 0.0
    )
