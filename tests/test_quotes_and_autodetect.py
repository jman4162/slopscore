"""Quoted speech is not the author's voice; pasted Markdown is treated as Markdown (v0.13)."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.ingest import from_string
from slopscore.models import SourceType
from slopscore.normalize.quotes import inside_quotes, quoted_ranges


def _ids(text: str) -> set[str]:
    return {e.rule_id for e in scan_text(text).evidence}


def test_quoted_ranges_pair_straight_quotes_on_one_line() -> None:
    text = 'She said "honestly, I never liked him" and left. "Everyone knows that," he replied.'
    ranges = quoted_ranges(text)
    assert len(ranges) == 2
    assert text[ranges[0][0] : ranges[0][1]] == "honestly, I never liked him"
    assert inside_quotes(ranges, ranges[0][0] + 1, ranges[0][1] - 1)
    assert not inside_quotes(ranges, 0, 3)


def test_dialogue_does_not_charge_the_narrator() -> None:
    fiction = (
        '"Honestly, I don\'t know," she said. "To be honest, I never liked him." '
        '"Everyone knows that," he replied, and went back to the ledger he had kept since 1974. '
        "The clerk wrote the total in pencil and closed the book."
    )
    ids = _ids(fiction)
    assert not any(i.startswith(("CANDOR_", "CLAIM_")) for i in ids), ids
    narrator = "To be honest, everyone knows that the ledger was kept since 1974."
    ids = _ids(narrator)
    assert "CANDOR_TO_BE_HONEST" in ids and "CLAIM_EVERYONE_KNOWS" in ids


def test_curly_quoted_dialogue_is_also_skipped() -> None:
    fiction = "“Truth be told, I never liked him,” she said, and the clerk wrote it down."
    assert not any(i.startswith("CANDOR_") for i in _ids(fiction))


def test_pasted_markdown_is_ingested_as_markdown() -> None:
    md = "# Notes\n\n- first point\n- Let's **dive into** the details.\n"
    raw = from_string(md)
    assert raw.source_type is SourceType.markdown
    assert "FORMULAIC_LETS_DELVE" in _ids(md)


def test_plain_prose_stays_plain_text() -> None:
    text = "The bridge opened in 1937. It cost 35 million dollars and took four years."
    assert from_string(text).source_type is SourceType.text
