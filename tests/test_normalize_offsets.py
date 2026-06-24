"""OffsetMapper round-trip: cleaned spans must map back to the correct original bytes."""

from __future__ import annotations

import pytest

from slopscore.normalize.clean import canonicalize, clean


@pytest.mark.parametrize(
    "raw",
    [
        "plain text with no funny whitespace",
        "tabs\tand   multiple    spaces collapse",
        "windows\r\nline\r\nendings",
        "trailing spaces   \nand a second line",
        "  leading and trailing  ",
        "unicode — em dash and “curly quotes” stay put",
    ],
)
def test_clean_span_maps_back_to_original(raw: str) -> None:
    canonical = canonicalize(raw)
    cleaned, mapper = clean(canonical)
    # Every word in the cleaned text must map back to the same word in canonical text.
    for word in cleaned.split():
        start = cleaned.index(word)
        end = start + len(word)
        o_start, o_end = mapper.to_original(start, end)
        assert canonical[o_start:o_end] == word


def test_full_span_covers_text() -> None:
    canonical = canonicalize("hello   world")
    cleaned, mapper = clean(canonical)
    o_start, o_end = mapper.to_original(0, len(cleaned))
    assert canonical[o_start:o_end] == canonical


def test_empty_span_is_zero_width() -> None:
    _cleaned, mapper = clean(canonicalize("abc"))
    o_start, o_end = mapper.to_original(1, 1)
    assert o_start == o_end


def test_invalid_span_raises() -> None:
    _, mapper = clean(canonicalize("abc"))
    with pytest.raises(ValueError):
        mapper.to_original(5, 2)
