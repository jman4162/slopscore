"""Feature-level behavior: lexical, formulaic, prompt-residue."""

from __future__ import annotations

from slopscore.core import build_document
from slopscore.features.formulaic_patterns import FormulaicPatterns
from slopscore.features.lexical_markers import LexicalMarkers
from slopscore.features.prompt_residue import PromptResidue
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_lexical_markers_fire_on_slop(slop_text: str) -> None:
    result = LexicalMarkers().extract(_doc(slop_text), "blog")
    assert result.score > 0.5
    found = {e.span.lower() for e in result.spans}
    assert {"delve", "leverage", "robust"} & found


def test_lexical_markers_quiet_on_clean(clean_text: str) -> None:
    result = LexicalMarkers().extract(_doc(clean_text), "blog")
    assert result.score == 0.0
    assert result.spans == []


def test_lexical_profile_weight_lowers_technical_score(slop_text: str) -> None:
    doc = _doc(slop_text)
    blog = LexicalMarkers().extract(doc, "blog").score
    technical = LexicalMarkers().extract(doc, "technical").score
    assert technical <= blog


def test_formulaic_detects_scaffolding(slop_text: str) -> None:
    result = FormulaicPatterns().extract(_doc(slop_text), "blog")
    rule_ids = {e.rule_id for e in result.spans}
    assert "FORMULAIC_LETS_DELVE" in rule_ids
    assert result.score > 0.0


def test_prompt_residue_single_high_hit_saturates(residue_text: str) -> None:
    result = PromptResidue().extract(_doc(residue_text), "blog")
    assert result.score >= 0.9
    assert any(e.rule_id == "RESIDUE_AS_AN_AI" for e in result.spans)


def test_prompt_residue_clean_is_zero(clean_text: str) -> None:
    result = PromptResidue().extract(_doc(clean_text), "blog")
    assert result.score == 0.0


def test_evidence_offsets_round_trip(slop_text: str) -> None:
    doc = _doc(slop_text)
    result = LexicalMarkers().extract(doc, "blog")
    for e in result.spans:
        assert doc.original_text[e.start_char : e.end_char] == e.span
