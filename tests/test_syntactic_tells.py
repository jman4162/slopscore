"""Syntactic tells: superficial '-ing' analyses, parallelism/tricolon, copula avoidance."""

from __future__ import annotations

import pytest

from slopscore.core import build_document
from slopscore.features._nlp import is_nlp_available
from slopscore.features.syntactic_tells import (
    CopulaAvoidance,
    Parallelism,
    SuperficialAnalysis,
)
from slopscore.ingest import from_string


def _doc(text: str):
    return build_document(from_string(text))


def test_superficial_analysis_fires_on_trailing_ing() -> None:
    doc = _doc(
        "The station opened in 1990, contributing to the socio-economic development of "
        "the region and reflecting its enduring significance."
    )
    result = SuperficialAnalysis().extract(doc, "blog")
    assert result.score > 0.0
    assert any(e.rule_id == "SUPERFICIAL_PARTICIPLE_CLAUSE" for e in result.spans)


def test_superficial_analysis_quiet_on_concrete_participle() -> None:
    # A participle clause with concrete content should not flag (vague-noun gate).
    doc = _doc("She opened the box, pulling out a wrench and a 12mm socket.")
    result = SuperficialAnalysis().extract(doc, "blog")
    assert result.score == 0.0


def test_parallelism_negative_and_tricolon() -> None:
    doc = _doc(
        "It is not just a tool, it is a revolution. The town offers a vibrant, dynamic, "
        "and transformative culture."
    )
    result = Parallelism().extract(doc, "blog")
    rule_ids = {e.rule_id for e in result.spans}
    assert "PARALLEL_RULE_OF_THREE" in rule_ids
    assert any(r.startswith("PARALLEL_") for r in rule_ids)


def test_tricolon_ignores_concrete_lists() -> None:
    doc = _doc("She bought apples, oranges, and pears at the market on Tuesday.")
    spans = Parallelism()._tricolon_spans(doc)
    assert spans == []


def test_copula_avoidance_fires() -> None:
    doc = _doc("The museum serves as a hub and boasts a large collection.")
    result = CopulaAvoidance().extract(doc, "blog")
    rule_ids = {e.rule_id for e in result.spans}
    assert "COPULA_SERVES_AS" in rule_ids
    assert "COPULA_BOASTS" in rule_ids


def test_all_syntactic_offsets_round_trip() -> None:
    doc = _doc(
        "It serves as a testament, reflecting its broader significance, and it is not "
        "just a building, it is a beacon."
    )
    for feature in (SuperficialAnalysis(), Parallelism(), CopulaAvoidance()):
        for e in feature.extract(doc, "blog").spans:
            assert doc.original_text[e.start_char : e.end_char] == e.span


@pytest.mark.skipif(not is_nlp_available(), reason="requires the [nlp] extra (spaCy)")
def test_superficial_nlp_path_runs() -> None:
    doc = _doc(
        "The bridge opened, highlighting its cultural significance and reflecting "
        "broader trends in engineering."
    )
    result = SuperficialAnalysis().extract(doc, "blog")
    assert result.score > 0.0
