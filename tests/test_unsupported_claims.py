"""unsupported_claims dimension: universal/inflated claims, distinct from weasel attribution."""

from __future__ import annotations

from slopscore.core import build_document
from slopscore.features.phrase_packs import UnsupportedClaims, WeaselAttribution
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_universal_and_sweeping_claims_fire() -> None:
    doc = _doc(
        "Everyone knows that this is essential. AI has revolutionized the industry. In an "
        "increasingly digital world, teams must adapt."
    )
    result = UnsupportedClaims.extract(doc, "blog")
    ids = {e.rule_id for e in result.spans}
    assert {"CLAIM_EVERYONE_KNOWS", "CLAIM_REVOLUTIONIZED", "CLAIM_INCREASINGLY_WORLD"} <= ids
    assert result.score > 0.5


def test_authority_without_citation_fires_but_cited_does_not() -> None:
    bare = UnsupportedClaims.extract(_doc("Studies show that this method works well."), "blog")
    assert any(e.rule_id == "CLAIM_AUTHORITY_NO_CITATION" for e in bare.spans)
    cited = UnsupportedClaims.extract(
        _doc("Studies show that this method works (Smith et al., 2024)."), "blog"
    )
    assert not any(e.rule_id == "CLAIM_AUTHORITY_NO_CITATION" for e in cited.spans)


def test_distinct_from_weasel() -> None:
    # "experts argue" is weasel (vague source); "everyone knows" is an unsupported claim.
    doc = _doc("Experts argue this is good. Everyone knows it is the future.")
    claims = {e.rule_id for e in UnsupportedClaims.extract(doc, "blog").spans}
    weasel = {e.rule_id for e in WeaselAttribution.extract(doc, "blog").spans}
    assert "CLAIM_EVERYONE_KNOWS" in claims
    assert any(r.startswith("WEASEL_") for r in weasel)
    assert not (claims & weasel)  # no overlap in rule_ids


def test_quiet_on_specific_prose() -> None:
    doc = _doc("The factory opened in 1962 and employed 1,200 workers near Cleveland.")
    assert UnsupportedClaims.extract(doc, "blog").score == 0.0


def test_offsets_round_trip() -> None:
    doc = _doc("Everyone knows this. Research shows that it helps.")
    for e in UnsupportedClaims.extract(doc, "blog").spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span
