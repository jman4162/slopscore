"""char_to_line_col: char spans -> 1-based SARIF (line, column) regions."""

from __future__ import annotations

import pytest

from slopscore.report.locations import char_to_line_col

_TEXT = "first line\nsecond line\nthird"


def test_first_line_span() -> None:
    # "first" is chars 0-5 on line 1.
    assert char_to_line_col(_TEXT, 0, 5) == (1, 1, 1, 6)


def test_span_on_later_line() -> None:
    start = _TEXT.index("second")
    end = start + len("second")
    assert char_to_line_col(_TEXT, start, end) == (2, 1, 2, 7)


def test_span_crossing_a_newline() -> None:
    start = _TEXT.index("line\nsecond")
    end = start + len("line\nsecond")
    start_line, _sc, end_line, _ec = char_to_line_col(_TEXT, start, end)
    assert (start_line, end_line) == (1, 2)


@pytest.mark.parametrize("start,end", [(0, 0), (len(_TEXT), len(_TEXT))])
def test_zero_width_spans_valid(start: int, end: int) -> None:
    start_line, start_col, end_line, end_col = char_to_line_col(_TEXT, start, end)
    assert start_line == end_line and start_col == end_col


def test_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        char_to_line_col(_TEXT, 0, len(_TEXT) + 1)
